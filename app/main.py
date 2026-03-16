"""
N.A.T. AI Assistant v4 — FastAPI Backend
Upgraded with: desktop control, browser detection, activity popup, file writing
"""
import asyncio, json, os, requests, queue as _queue
from datetime import datetime
from pydantic import BaseModel
from fastapi import FastAPI, HTTPException, Request, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager

FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")

from config import config
from app.models import ChatRequest, ChatResponse, SystemStatus, VectorStoreStatus, DetailedSystemStatus
from app.services.chat_service import chat_service
from app.services.vector_store import vector_store_service
from app.services.groq_service import groq_service
from app.services.realtime_service import realtime_service
from app.services.intelligence_service import intelligence_service
from app.services.memory_service import memory_service
from app.services.action_engine import action_engine, register_activity_callback
from app.services.terminal_browser_service import terminal_service, browser_service
from app.services.filler_service import get_filler_for_message, get_typing_filler, is_question, is_statement_or_command
from app.services.tts_service import tts_service
from app.services.browser_detect import browser_store
from app.services.desktop_service import keyboard_ctrl, mouse_ctrl, screen_ctrl, desktop_status
from app.utils.time_info import get_current_datetime

startup_time = datetime.now()

# ── Activity queue (SSE → frontend popup) ────────────────────────────────
_activity_q: _queue.Queue = _queue.Queue(maxsize=500)

def _activity_push(msg: str):
    try: _activity_q.put_nowait({"step": msg, "ts": datetime.now().isoformat()})
    except _queue.Full: pass

register_activity_callback(_activity_push)


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("\n" + "="*55)
    print("  N.A.T. AI Assistant v4 — Natasha")
    print("  Desktop Control + Browser Detection + Activity Feed")
    print("="*55)
    print(f"  Model:       {config.GROQ_MODEL}")
    print(f"  Groq API:    {'✓' if groq_service.is_available() else '✗ not configured'}")
    print(f"  Web Search:  {'✓' if getattr(config,'TAVILY_API_KEY',None) else '✗ not configured'}")
    print(f"  Desktop:     {'✓ pyautogui' if keyboard_ctrl.is_available() else '✗ pip install pyautogui'}")
    print(f"  Learning:    {config.LEARNING_DATA_PATH}")
    print("="*55 + "\n")
    yield
    print("\n[Natasha] Shutting down...")


app = FastAPI(title="N.A.T. v4", version="4.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


# ════════════════════════════════════════════════════════════════════════════
#  STREAM GENERATOR
# ════════════════════════════════════════════════════════════════════════════

async def _stream_generator(session_id: str, message: str, chat_type: str,
                             use_tts: bool, browser_key: str = "unknown"):
    session = chat_service.get_or_create_session(session_id, chat_type)
    yield f"data: {json.dumps({'session_id': session.session_id, 'chunk': '', 'done': False})}\n\n"

    # Tell action engine which browser to use this request
    action_engine.set_browser(browser_key)

    # Try action engine first
    action_result, action_type, suggested_mode = await asyncio.to_thread(
        action_engine.evaluate_and_execute_with_type, message)
    
    # Auto-route to realtime if LLM suggests it
    if suggested_mode == "realtime" and chat_type != "realtime":
        chat_type = "realtime"
    
    if action_result:
        # Send filler immediately for action (smart - detects question vs statement)
        filler = get_filler_for_message(message, action_type)
        chat_service.add_message(session.session_id, "user", message)
        chat_service.add_message(session.session_id, "assistant", filler)
        await asyncio.to_thread(chat_service.save_session, session.session_id)
        
        # Send filler as first chunk with TTS
        if use_tts:
            try:
                audio_b64 = await tts_service.get_audio_base64(filler[:300])
                if audio_b64:
                    yield f"data: {json.dumps({'tts_audio': audio_b64})}\n\n"
            except Exception: pass
        
        yield f"data: {json.dumps({'chunk': filler, 'done': False})}\n\n"
        
        # Small delay for effect, then send actual result
        await asyncio.sleep(0.5)
        
        chat_service.add_message(session.session_id, "assistant", action_result)
        await asyncio.to_thread(chat_service.save_session, session.session_id)
        
        # TTS for action result
        if use_tts and action_result:
            try:
                audio_b64 = await tts_service.get_audio_base64(action_result[:300])
                if audio_b64:
                    yield f"data: {json.dumps({'tts_audio': audio_b64})}\n\n"
            except Exception: pass
        yield f"data: {json.dumps({'chunk': action_result, 'done': True})}\n\n"
        return

    # Check if we need to switch to realtime mode based on LLM suggestion
    if suggested_mode == "realtime":
        chat_type = "realtime"

    # Normal chat flow
    chat_service.add_message(session.session_id, "user", message)
    history = chat_service.get_conversation_history(session.session_id)
    full_response = ""

    try:
        # Send immediate filler for chat/realtime (smart - question or statement)
        filler = get_filler_for_message(message, "realtime" if chat_type == "realtime" else "chat")
        
        if use_tts:
            try:
                audio_b64 = await tts_service.get_audio_base64(filler[:300])
                if audio_b64:
                    yield f"data: {json.dumps({'tts_audio': audio_b64})}\n\n"
            except Exception: pass
        
        yield f"data: {json.dumps({'chunk': filler, 'done': False})}\n\n"
        
        if chat_type == "realtime":
            response_stream = realtime_service.stream_chat(message, history)
        else:
            context = await asyncio.to_thread(vector_store_service.get_relevant_context, message)
            response_stream = groq_service.stream_chat_with_context(message, context, history)

        tts_buffer = ""
        async for chunk in response_stream:
            if chunk:
                full_response += chunk
                tts_buffer += chunk
                yield f"data: {json.dumps({'chunk': chunk, 'done': False})}\n\n"
                if use_tts:
                    if any(tts_buffer.endswith(p) for p in [". ","? ","! ",".\n","?\n","!\n","\n\n"]):
                        clean = tts_buffer.strip()
                        if clean:
                            try:
                                audio_b64 = await tts_service.get_audio_base64(clean)
                                if audio_b64:
                                    yield f"data: {json.dumps({'tts_audio': audio_b64})}\n\n"
                            except Exception as e:
                                print(f"[TTS] {e}")
                        tts_buffer = ""

        if use_tts and tts_buffer.strip():
            try:
                audio_b64 = await tts_service.get_audio_base64(tts_buffer.strip())
                if audio_b64:
                    yield f"data: {json.dumps({'tts_audio': audio_b64})}\n\n"
            except Exception: pass

        try:
            extracted = await asyncio.to_thread(memory_service.extract_and_save_memory, message, full_response)
            if extracted: print(f"[Memory] {extracted}")
        except Exception: pass

        chat_service.add_message(session.session_id, "assistant", full_response)
        await asyncio.to_thread(chat_service.save_session, session.session_id)

    except Exception as e:
        print(f"[Stream Error] {e}")
        yield f"data: {json.dumps({'error': str(e)})}\n\n"

    yield f"data: {json.dumps({'done': True})}\n\n"


# ════════════════════════════════════════════════════════════════════════════
#  CORE ENDPOINTS
# ════════════════════════════════════════════════════════════════════════════

@app.get("/")
async def root():
    fp = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "index.html")
    if os.path.exists(fp): return FileResponse(fp)
    return {"name": "N.A.T. v4", "status": "running"}

@app.get("/health")
async def health():
    return {"status": "healthy", "timestamp": get_current_datetime(),
            "uptime_seconds": (datetime.now() - startup_time).total_seconds()}

@app.get("/greet")
async def greet():
    """Time-aware greeting with TTS audio for first-load."""
    hour = datetime.now().hour
    if   0  <= hour < 5:  greeting = "Working late, Boss. Natasha online."
    elif 5  <= hour < 12: greeting = "Good morning, Boss. How can I help?"
    elif 12 <= hour < 17: greeting = "Good afternoon, Boss. Ready when you are."
    elif 17 <= hour < 21: greeting = "Good evening, Boss. What's on your mind?"
    else:                 greeting = "Late night session, Boss. Natasha's here."
    audio_b64 = ""
    try: audio_b64 = await tts_service.get_audio_base64(greeting)
    except Exception: pass
    return {"greeting": greeting, "audio": audio_b64}


# ── Chat endpoints ────────────────────────────────────────────────────────

@app.post("/chat/stream")
async def chat_stream(request: Request):
    data = await request.json()
    message = data.get("message", "")
    session_id = data.get("session_id")
    use_tts = data.get("tts", False)
    ua = request.headers.get("user-agent", "")
    client_ip = request.client.host if request.client else "unknown"
    browser_key = browser_store.register(client_ip, ua)
    return StreamingResponse(
        _stream_generator(session_id, message, "general", use_tts, browser_key),
        media_type="text/event-stream"
    )

@app.post("/chat/realtime/stream")
async def chat_realtime_stream(request: Request):
    data = await request.json()
    message = data.get("message", "")
    session_id = data.get("session_id")
    use_tts = data.get("tts", False)
    ua = request.headers.get("user-agent", "")
    client_ip = request.client.host if request.client else "unknown"
    browser_key = browser_store.register(client_ip, ua)
    return StreamingResponse(
        _stream_generator(session_id, message, "realtime", use_tts, browser_key),
        media_type="text/event-stream"
    )

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    try:
        session = chat_service.get_or_create_session(request.session_id, request.chat_type)
        chat_service.add_message(session.session_id, "user", request.message)
        history = chat_service.get_conversation_history(session.session_id)
        response_text, sources = "", None
        if request.chat_type == "realtime":
            result = realtime_service.chat(request.message, history)
            response_text = result["response"]; sources = result.get("sources")
        elif request.chat_type == "intelligence":
            result = intelligence_service.analyze(request.message, history)
            response_text = result["response"]; sources = result.get("sources")
        else:
            context = vector_store_service.get_relevant_context(request.message)
            response_text = groq_service.chat_with_context(request.message, context, history)
        chat_service.add_message(session.session_id, "assistant", response_text)
        chat_service.save_session(session.session_id)
        return ChatResponse(response=response_text, session_id=session.session_id,
                            chat_type=request.chat_type, sources=sources)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Voice transcription ───────────────────────────────────────────────────

@app.post("/transcribe")
async def transcribe_audio(audio: UploadFile = File(...)):
    """Transcribe audio via Groq Whisper-large-v3."""
    try:
        audio_bytes = await audio.read()
        keys = getattr(config, 'GROQ_API_KEYS', [])
        api_key = keys[0] if keys else getattr(config, 'GROQ_API_KEY', '')
        if not api_key: return {"text": "", "error": "No Groq API key"}
        headers = {"Authorization": f"Bearer {api_key}"}
        files = {"file": (audio.filename, audio_bytes, audio.content_type)}
        data = {"model": "whisper-large-v3", "response_format": "json"}
        resp = requests.post("https://api.groq.com/openai/v1/audio/transcriptions",
                             headers=headers, files=files, data=data)
        if resp.status_code == 200:
            return {"text": resp.json().get("text", "").strip()}
        return {"text": "", "error": f"Groq: {resp.text}"}
    except Exception as e:
        return {"text": "", "error": str(e)}

@app.post("/chat/transcribe")
async def transcribe_chat_audio(file: UploadFile = File(...)):
    try:
        audio_bytes = await file.read()
        text = await asyncio.to_thread(groq_service.transcribe_audio, audio_bytes, file.filename)
        return {"text": text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── TTS endpoint ──────────────────────────────────────────────────────────

class TTSRequest(BaseModel):
    text: str

@app.post("/tts")
async def generate_tts(request: TTSRequest):
    try:
        audio_b64 = await tts_service.get_audio_base64(request.text)
        if audio_b64: return {"success": True, "audio": audio_b64}
        return {"success": False, "error": "Failed"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Activity SSE stream ───────────────────────────────────────────────────

@app.get("/activity/stream")
async def activity_stream():
    """SSE stream for the live activity popup in the frontend."""
    async def gen():
        yield f"data: {json.dumps({'step': '🟢 Natasha activity feed connected'})}\n\n"
        while True:
            try:
                item = _activity_q.get(timeout=0.2)
                yield f"data: {json.dumps(item)}\n\n"
            except:
                yield f"data: {json.dumps({'heartbeat': True})}\n\n"
                await asyncio.sleep(4.8)
    return StreamingResponse(gen(), media_type="text/event-stream")

@app.get("/activity/browser")
async def browser_info():
    return {"browser": browser_store.current}


# ════════════════════════════════════════════════════════════════════════════
#  KEYBOARD ENDPOINTS
# ════════════════════════════════════════════════════════════════════════════

class TypeTextReq(BaseModel):
    text: str
    delay: float = 2.0
    interval: float = 0.03

class HotkeyReq(BaseModel):
    keys: list

class PressKeyReq(BaseModel):
    key: str

@app.post("/keyboard/type")
async def kb_type(request: TypeTextReq):
    result = await asyncio.to_thread(keyboard_ctrl.type_text, request.text, request.delay)
    return result

@app.post("/keyboard/hotkey")
async def kb_hotkey(request: HotkeyReq):
    result = await asyncio.to_thread(keyboard_ctrl.hotkey, *request.keys)
    return result

@app.post("/keyboard/press")
async def kb_press(request: PressKeyReq):
    result = await asyncio.to_thread(keyboard_ctrl.press_key, request.key)
    return result

@app.get("/keyboard/status")
async def kb_status():
    return keyboard_ctrl.get_status()


# ════════════════════════════════════════════════════════════════════════════
#  MOUSE ENDPOINTS
# ════════════════════════════════════════════════════════════════════════════

class MouseMoveReq(BaseModel):
    x: int
    y: int
    duration: float = 0.3

class MouseClickReq(BaseModel):
    x: int = None
    y: int = None
    button: str = "left"
    double: bool = False

class MouseScrollReq(BaseModel):
    amount: int = 3
    x: int = None
    y: int = None

@app.post("/mouse/move")
async def mouse_move(request: MouseMoveReq):
    return await asyncio.to_thread(mouse_ctrl.move, request.x, request.y, request.duration)

@app.post("/mouse/click")
async def mouse_click(request: MouseClickReq):
    if request.double:
        return await asyncio.to_thread(mouse_ctrl.double_click, request.x, request.y)
    return await asyncio.to_thread(mouse_ctrl.click, request.x, request.y, request.button)

@app.post("/mouse/scroll")
async def mouse_scroll(request: MouseScrollReq):
    return await asyncio.to_thread(mouse_ctrl.scroll, request.x, request.y, request.amount)

@app.get("/mouse/position")
async def mouse_position():
    return mouse_ctrl.get_position()

@app.get("/mouse/screen-size")
async def screen_size():
    return mouse_ctrl.get_screen_size()


# ════════════════════════════════════════════════════════════════════════════
#  SCREENSHOT ENDPOINT
# ════════════════════════════════════════════════════════════════════════════

@app.get("/screenshot")
async def take_screenshot():
    result = await asyncio.to_thread(screen_ctrl.screenshot, None, True)
    return result

@app.get("/desktop/status")
async def get_desktop_status():
    return await asyncio.to_thread(desktop_status)


# ════════════════════════════════════════════════════════════════════════════
#  TERMINAL & BROWSER ENDPOINTS (unchanged from v2)
# ════════════════════════════════════════════════════════════════════════════

class TerminalCommandRequest(BaseModel):
    command: str; cwd: str = None

class CreateFolderRequest(BaseModel):
    path: str

class CreateFileRequest(BaseModel):
    path: str; content: str = ""

class OpenPathRequest(BaseModel):
    path: str

class ListDirRequest(BaseModel):
    path: str = "."

class OpenAppRequest(BaseModel):
    app: str

@app.post("/terminal/run")
async def terminal_run(request: TerminalCommandRequest):
    return await asyncio.to_thread(terminal_service.run, request.command, request.cwd)

@app.post("/terminal/create-folder")
async def terminal_create_folder(request: CreateFolderRequest):
    return await asyncio.to_thread(terminal_service.create_folder, request.path)

@app.post("/terminal/create-file")
async def terminal_create_file(request: CreateFileRequest):
    return await asyncio.to_thread(terminal_service.create_file, request.path, request.content)

@app.post("/terminal/open-path")
async def terminal_open_path(request: OpenPathRequest):
    return await asyncio.to_thread(terminal_service.open_path, request.path)

@app.post("/terminal/open-app")
async def terminal_open_app(request: OpenAppRequest):
    return await asyncio.to_thread(terminal_service.open_app, request.app)

@app.post("/terminal/list-directory")
async def terminal_list_directory(request: ListDirRequest):
    return await asyncio.to_thread(terminal_service.list_directory, request.path)

@app.get("/terminal/status")
async def terminal_status():
    import platform
    return {"os": platform.system(), "terminal_available": True,
            "desktop_control": keyboard_ctrl.is_available()}

class OpenUrlRequest(BaseModel):
    url: str

class SearchRequest(BaseModel):
    query: str; engine: str = "google"

@app.post("/browser/open")
async def browser_open(request: OpenUrlRequest):
    from app.services.browser_detect import open_url_in_browser
    return open_url_in_browser(request.url, browser_store.current)

@app.post("/browser/search")
async def browser_search(request: SearchRequest):
    return browser_service.open_search(request.query, request.engine)


# ════════════════════════════════════════════════════════════════════════════
#  SYSTEM, SESSIONS, MEMORY, VECTOR STORE
# ════════════════════════════════════════════════════════════════════════════

@app.get("/system/status", response_model=SystemStatus)
async def system_status():
    vs = vector_store_service.get_status()
    return SystemStatus(
        vector_store=VectorStoreStatus(loaded=vs["loaded"], document_count=vs["document_count"], sources=[]),
        groq_available=groq_service.is_available(),
        search_available=realtime_service.is_available(),
        model_name=config.GROQ_MODEL,
        active_sessions=len(chat_service.sessions)
    )

@app.get("/system/detailed", response_model=DetailedSystemStatus)
async def detailed_status():
    vs = vector_store_service.get_status()
    api_sources = []
    if getattr(config,'GROQ_API_KEYS',None): api_sources.append("groq")
    if getattr(config,'TAVILY_API_KEY',None): api_sources.append("tavily")
    return DetailedSystemStatus(
        name="N.A.T.", full_name="Natasha", version="4.0.0", status="running",
        uptime_start=startup_time.strftime("%Y-%m-%d %H:%M:%S"),
        current_time=get_current_datetime(), model=config.GROQ_MODEL,
        groq_api="Available" if groq_service.is_available() else "Not configured",
        tavily_search="Available" if getattr(config,'TAVILY_API_KEY',None) else "Not configured",
        alpha_vantage="Available" if getattr(config,'ALPHA_VANTAGE_KEY',None) else "Not configured",
        fmp_data="Available" if getattr(config,'FMP_KEY',None) else "Not configured",
        news_api="Available" if getattr(config,'NEWS_API_KEY',None) else "Not configured",
        google_search="Available" if (getattr(config,'GOOGLE_API_KEY',None) and getattr(config,'GOOGLE_CSE_ID',None)) else "Not configured",
        vector_store={"loaded":vs["loaded"],"document_count":vs["document_count"],"model":vs.get("model","N/A"),"path":str(vs.get("path",""))},
        cache_status={"entries":len(intelligence_service.cache),"ttl_seconds":intelligence_service.cache_ttl},
        active_sessions=len(chat_service.sessions),
        endpoints={"/chat/stream":"/chat/stream","/greet":"/greet","/keyboard/type":"/keyboard/type",
                   "/mouse/move":"/mouse/move","/screenshot":"/screenshot","/activity/stream":"/activity/stream"},
        api_sources_configured=api_sources
    )

@app.get("/vectorstore/status")
async def vectorstore_status():
    return vector_store_service.get_status()

@app.post("/vectorstore/rebuild")
async def rebuild_vectorstore():
    return vector_store_service.add_learning_files()

@app.get("/sessions")
async def list_sessions():
    return chat_service.list_sessions()

@app.get("/sessions/{session_id}")
async def get_session(session_id: str):
    session = chat_service.get_session(session_id)
    if not session: raise HTTPException(status_code=404, detail="Session not found")
    return {"session_id": session.session_id, "chat_type": session.chat_type,
            "message_count": len(session.messages),
            "messages": [{"role": m.role, "content": m.content, "timestamp": m.timestamp.isoformat()} for m in session.messages]}

@app.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    if not chat_service.delete_session(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    return {"status": "deleted", "session_id": session_id}

@app.get("/memory")
async def get_memories():
    return {"memories": memory_service.get_all_memories(), "count": len(memory_service.memories)}

class MemoryReq(BaseModel):
    content: str; category: str = "general"; importance: int = 5

@app.post("/memory")
async def add_memory(request: MemoryReq):
    mem = memory_service.add_memory(request.content, request.category, request.importance)
    return {"success": True, "memory": mem}

@app.delete("/memory/{memory_id}")
async def delete_memory(memory_id: int):
    memory_service.delete_memory(memory_id)
    return {"success": True, "deleted_id": memory_id}

@app.get("/learning/files")
async def list_learning_files():
    files = []
    for fp in config.LEARNING_DATA_PATH.glob("*.txt"):
        files.append({"name": fp.name, "size": fp.stat().st_size})
    return files

# Intelligence
class IntelligenceReq(BaseModel):
    query: str; force_refresh: bool = False

@app.post("/intelligence")
async def intelligence(request: IntelligenceReq):
    try:
        if request.force_refresh:
            key = request.query.lower().strip()
            if key in intelligence_service.cache: del intelligence_service.cache[key]
        result = intelligence_service.analyze(request.query)
        return {"success": True, "query": request.query,
                "entity_name": result.get("entity_name", request.query),
                "entity_type": result.get("entity_type", "unknown"),
                "response": result.get("response", ""),
                "cached": result.get("cached", False),
                "timestamp": get_current_datetime()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
