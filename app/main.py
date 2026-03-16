"""
N.A.T. AI Assistant v5 — FastAPI Backend
Upgraded with: desktop control, browser detection, activity popup, file writing,
smart search, scroll control, WiFi sensing, mini widget
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
from app.services.terminal_browser_service import terminal_service, browser_service as terminal_browser_service
from app.services.filler_service import get_filler_for_message, get_typing_filler, is_question, is_statement_or_command
from app.services.tts_service import tts_service
from app.services.browser_detect import browser_store
from app.services.desktop_service import keyboard_ctrl, mouse_ctrl, screen_ctrl, desktop_status
from app.services.browser_automation_service import browser_service as playwright_browser
from app.services.wifi_sensing_service import wifi_sensing_service
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
    print("\n" + "="*70)
    print("  N.A.T. AI Assistant v5 — Natasha + WiFi Sensing")
    print("  Smart Search + Browser Automation + WiFi DensePose Integration")
    print("="*70)
    print(f"  Model:        {config.GROQ_MODEL}")
    print(f"  Groq API:     {'✓' if groq_service.is_available() else '✗ not configured'}")
    print(f"  Web Search:   {'✓' if getattr(config,'TAVILY_API_KEY',None) else '✗ not configured'}")
    print(f"  Desktop:      {'✓ pyautogui' if keyboard_ctrl.is_available() else '✗ pip install pyautogui'}")
    print(f"  WiFi Sensing: {'✓ available' if TORCH_AVAILABLE else '✗ demo mode'}")
    print(f"  Learning:     {config.LEARNING_DATA_PATH}")
    print("="*70 + "\n")
    yield
    print("\n[Natasha] Shutdown complete")

# Import torch check for WiFi sensing
try:
    import torch
    TORCH_AVAILABLE = True
except:
    TORCH_AVAILABLE = False


app = FastAPI(title="N.A.T. v5", version="5.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

# Mount RuView UI
RUVIEW_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "ruview_ui")
if os.path.exists(RUVIEW_DIR):
    app.mount("/ruview", StaticFiles(directory=RUVIEW_DIR, html=True), name="ruview")
    print(f"[INFO] RuView UI mounted at /ruview from {RUVIEW_DIR}")
else:
    print(f"[WARNING] RuView UI directory not found at {RUVIEW_DIR}")



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
    action_result, action_type = await asyncio.to_thread(
        action_engine.evaluate_and_execute_with_type, message)
    
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
    return {"name": "N.A.T. v5", "status": "running"}

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

@app.get("/widget")
async def widget():
    """Serve the floating mini-window widget."""
    fp = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "widget.html")
    if os.path.exists(fp): return FileResponse(fp)
    return {"error": "widget.html not found"}


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

@app.post("/keyboard/search")
async def kb_search(request: Request):
    data = await request.json()
    url = data.get("url",""); query = data.get("query",""); engine = data.get("engine","google")
    if not url and query:
        import urllib.parse
        bases = {"google":"https://www.google.com/search?q=","youtube":"https://www.youtube.com/results?search_query=","github":"https://github.com/search?q=","bing":"https://www.bing.com/search?q=","reddit":"https://www.reddit.com/search/?q="}
        url = bases.get(engine,bases["google"]) + urllib.parse.quote_plus(query)
    return await asyncio.to_thread(keyboard_ctrl.focus_addressbar_and_search, url)

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

class ScrollNReq(BaseModel):
    count: int = 3
    direction: str = "down"
    interval: float = 0.8

class ScrollStartReq(BaseModel):
    direction: str = "down"
    speed: str = "slow"

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

@app.post("/mouse/scroll-n")
async def mouse_scroll_n(request: ScrollNReq):
    return await asyncio.to_thread(mouse_ctrl.scroll_n_times, request.count, request.direction, request.interval)

@app.post("/mouse/scroll-start")
async def mouse_scroll_start(request: ScrollStartReq):
    return await asyncio.to_thread(mouse_ctrl.start_continuous_scroll, request.direction, request.speed)

@app.post("/mouse/scroll-stop")
async def mouse_scroll_stop():
    return mouse_ctrl.stop_scroll()

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
    return terminal_browser_service.open_search(request.query, request.engine)


# ════════════════════════════════════════════════════════════════════════════
#  PLAYWRIGHT BROWSER AUTOMATION ENDPOINTS
# ════════════════════════════════════════════════════════════════════════════

class BrowserActionRequest(BaseModel):
    action: str
    selector: str = ""
    text: str = ""
    url: str = ""
    key: str = ""
    x: int = 0
    y: int = 500
    path: str = ""
    script: str = ""
    index: int = 0

@app.post("/playwright/init")
async def playwright_init(headless: bool = False):
    return await playwright_browser.init(headless=headless)

@app.post("/playwright/open")
async def playwright_open(url: str):
    return await playwright_browser.open_url(url)

@app.post("/playwright/github-search")
async def playwright_github_search(query: str):
    return await playwright_browser.search_github(query)

@app.post("/playwright/action")
async def playwright_action(request: BrowserActionRequest):
    action = request.action
    if action == "click":
        return await playwright_browser.click(request.selector)
    elif action == "fill":
        return await playwright_browser.fill(request.selector, request.text)
    elif action == "type":
        return await playwright_browser.type_text(request.selector, request.text)
    elif action == "press":
        return await playwright_browser.press_key(request.key)
    elif action == "scroll":
        return await playwright_browser.scroll(request.x, request.y)
    elif action == "screenshot":
        return await playwright_browser.screenshot(request.path)
    elif action == "new_tab":
        return await playwright_browser.new_tab(request.url)
    elif action == "close_tab":
        return await playwright_browser.close_tab(request.index)
    elif action == "switch_tab":
        return await playwright_browser.switch_tab(request.index)
    elif action == "script":
        return await playwright_browser.execute_script(request.script)
    else:
        return {"success": False, "message": f"Unknown action: {action}"}

@app.get("/playwright/get-text")
async def playwright_get_text(selector: str):
    return await playwright_browser.get_text(selector)

@app.get("/playwright/get-html")
async def playwright_get_html(selector: str = ""):
    return await playwright_browser.get_html(selector)

@app.get("/playwright/screenshot")
async def playwright_screenshot(path: str = "playwright_screenshot.png"):
    return await playwright_browser.screenshot(path)

@app.post("/playwright/close")
async def playwright_close():
    return await playwright_browser.close()

@app.get("/playwright/status")
async def playwright_status():
    return {"initialized": playwright_browser.is_initialized, "available": playwright_browser.is_available()}


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
        name="N.A.T.", full_name="Natasha", version="5.0.0", status="running",
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

# ════════════════════════════════════════════════════════════════════════════
#  WiFi SENSING - RuView Integration
# ════════════════════════════════════════════════════════════════════════════

@app.get("/wifi/status")
async def wifi_sensing_status():
    """Get WiFi sensing system status"""
    return wifi_sensing_service.get_current_status()

@app.post("/wifi/start")
async def start_wifi_sensing():
    """Start WiFi sensing"""
    try:
        await wifi_sensing_service.start_sensing()
        return {"success": True, "message": "WiFi sensing started", "status": wifi_sensing_service.get_current_status()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/wifi/stop")
async def stop_wifi_sensing():
    """Stop WiFi sensing"""
    try:
        await wifi_sensing_service.stop_sensing()
        return {"success": True, "message": "WiFi sensing stopped"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/wifi/detections")
async def get_wifi_detections():
    """Get current WiFi pose detections"""
    return {
        "detections": wifi_sensing_service.get_current_detections(),
        "timestamp": datetime.now().isoformat()
    }

@app.websocket("/wifi/ws")
async def wifi_sensing_websocket(websocket):
    """WebSocket endpoint for real-time WiFi sensing data"""
    await websocket.accept()
    await wifi_sensing_service.add_connection(websocket)
    
    try:
        # Send initial status
        await websocket.send_json({
            "type": "connected",
            "status": wifi_sensing_service.get_current_status()
        })
        
        # Keep connection alive and handle incoming messages
        while True:
            try:
                data = await websocket.receive_text()
                message = json.loads(data)
                
                # Handle control messages
                if message.get("command") == "start":
                    await wifi_sensing_service.start_sensing()
                    await websocket.send_json({"type": "status", "message": "Sensing started"})
                elif message.get("command") == "stop":
                    await wifi_sensing_service.stop_sensing()
                    await websocket.send_json({"type": "status", "message": "Sensing stopped"})
                elif message.get("command") == "status":
                    await websocket.send_json({
                        "type": "status",
                        "status": wifi_sensing_service.get_current_status()
                    })
                    
            except Exception as e:
                print(f"WebSocket message error: {e}")
                break
                
    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        await wifi_sensing_service.remove_connection(websocket)
