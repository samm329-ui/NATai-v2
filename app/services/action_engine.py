"""
Smart Action Engine v5 — N.A.T. AI Assistant
═════════════════════════════════════════════
New in v5:
  - smart_search       → focus browser address bar, type search, hit Enter
  - open_browser       → open URL in new browser tab (Playwright)
  - browser_click      → click element on page
  - browser_type       → type into input field
  - browser_scroll     → scroll browser page
  - browser_screenshot→ take screenshot of page
  - github_search     → search GitHub
  - scroll_n          → scroll page N times then stop
  - scroll_start      → begin continuous scrolling
  - scroll_stop       → stop scrolling (voice: "stop")
  - type_text         → type into active window
  - press_key         → single key press
  - hotkey            → keyboard shortcut
  - mouse_move        → move cursor
  - mouse_click       → click at coordinates
  - mouse_scroll      → scroll once
  - screenshot        → take desktop screenshot
"""

import json, re, os, platform
from pathlib import Path
from typing import Optional

OS = platform.system()

_activity_callbacks = []
def register_activity_callback(fn):
    _activity_callbacks.append(fn)

def _log(msg):
    print(f"[Activity] {msg}")
    for fn in _activity_callbacks:
        try: fn(msg)
        except: pass

WIN_SPECIAL = {
    "my pc":        "explorer ::{20D04FE0-3AEA-1069-A2D8-08002B30309D}",
    "this pc":      "explorer ::{20D04FE0-3AEA-1069-A2D8-08002B30309D}",
    "computer":     "explorer ::{20D04FE0-3AEA-1069-A2D8-08002B30309D}",
    "desktop":      "explorer %USERPROFILE%\\Desktop",
    "downloads":    "explorer %USERPROFILE%\\Downloads",
    "documents":    "explorer %USERPROFILE%\\Documents",
    "pictures":     "explorer %USERPROFILE%\\Pictures",
    "music":        "explorer %USERPROFILE%\\Music",
    "videos":       "explorer %USERPROFILE%\\Videos",
    "appdata":      "explorer %APPDATA%",
    "temp":         "explorer %TEMP%",
    "recycle bin":  "explorer ::{645FF040-5081-101B-9F08-00AA002F954E}",
    "control panel":"control",
    "task manager": "taskmgr",
    "device manager":"devmgmt.msc",
    "c drive":      "explorer C:\\",
    "d drive":      "explorer D:\\",
    "e drive":      "explorer E:\\",
    "f drive":      "explorer F:\\",
}

WIN_APPS = {
    "notepad":"notepad","calculator":"calc","paint":"mspaint","wordpad":"wordpad",
    "cmd":"cmd","command prompt":"cmd","powershell":"powershell","terminal":"wt",
    "windows terminal":"wt","vs code":"code","vscode":"code","visual studio code":"code",
    "chrome":"chrome","google chrome":"chrome","firefox":"firefox","edge":"msedge",
    "microsoft edge":"msedge","brave":"brave","excel":"excel","word":"winword",
    "powerpoint":"powerpnt","outlook":"outlook","teams":"teams","discord":"discord",
    "spotify":"spotify","vlc":"vlc","file explorer":"explorer","explorer":"explorer",
    "task manager":"taskmgr","settings":"ms-settings:","snipping tool":"snippingtool",
    "steam":"steam","obs":"obs64",
}

_SYSTEM_PROMPT = '''You are a strict JSON command router for an AI assistant called Natasha on Windows.
Return ONLY raw JSON — no markdown, no explanation.

ACTIONS:

1. open_web → {"action":"open_web","url":"https://youtube.com"}

2. smart_search → USE THIS for any "search X on Y" command. Types directly into browser address bar.
   {"action":"smart_search","query":"python tutorials","engine":"google"}
   engine: google|youtube|github|bing|reddit

3. web_search → fallback URL-open search (if browser not open)
   {"action":"web_search","query":"python tutorials","engine":"google"}

4. open_browser → OPEN URL IN NEW BROWSER TAB (uses Playwright)
   {"action":"open_browser","url":"https://github.com"}
   Use for: "open github", "open a new tab", "open website", "go to youtube"

5. browser_click → CLICK ELEMENT ON PAGE
   {"action":"browser_click","selector":"button.submit"}
   Use for: "click the button", "click on login"

6. browser_type → TYPE INTO INPUT FIELD
   {"action":"browser_type","selector":"input[name=q]","text":"search query"}
   Use for: "type in search", "fill the form"

7. browser_scroll → SCROLL BROWSER PAGE
   {"action":"browser_scroll","direction":"down","amount":500}
   direction: up|down, amount: pixels

8. browser_screenshot → TAKE SCREENSHOT OF CURRENT PAGE
   {"action":"browser_screenshot"}
   Use for: "screenshot", "take a picture of the page"

9. github_search → SEARCH GITHUB
   {"action":"github_search","query":"ruview"}
   Use for: "search github for X", "find ruview on github"

10. run_terminal → {"action":"run_terminal","command":"pip list","cwd":null}

11. create_folder → {"action":"create_folder","path":"C:/Users/jishu/NewFolder"}

12. create_file → {"action":"create_file","path":"C:/Users/jishu/file.txt","content":"content here","generate_content":false}
   Set generate_content=true when user says "write X and save as file"

13. open_special → {"action":"open_special","name":"downloads"}
   names: my pc, desktop, downloads, documents, c drive, d drive, control panel, task manager

14. open_folder → {"action":"open_folder","path":"C:/Users/jishu/Documents"}

15. open_file → {"action":"open_file","path":"C:/Users/jishu/report.pdf"}

16. open_app → {"action":"open_app","app":"notepad"}

17. list_directory → {"action":"list_directory","path":"C:/Users/jishu"}

18. type_text → {"action":"type_text","text":"hello world","delay":1.5}

19. press_key → {"action":"press_key","key":"enter"}

20. hotkey → {"action":"hotkey","keys":["ctrl","c"]}

21. mouse_move → {"action":"mouse_move","x":960,"y":540}

22. mouse_click → {"action":"mouse_click","x":100,"y":200,"button":"left","double":false}

23. mouse_scroll → {"action":"mouse_scroll","amount":3}  (negative=down)

24. scroll_n → SCROLL PAGE N TIMES THEN STOP
    {"action":"scroll_n","count":5,"direction":"down"}
    Use for: "scroll down 5 times", "scroll up 3 times"

25. scroll_start → START CONTINUOUS SCROLLING
    {"action":"scroll_start","direction":"down","speed":"slow"}
    speed: slow|medium|fast
    Use for: "scroll slowly", "keep scrolling", "scroll the page"

26. scroll_stop → STOP SCROLLING
    {"action":"scroll_stop"}
    Use for: "stop", "stop scrolling"

27. screenshot → {"action":"screenshot"}

28. chat → {"action":"chat"}

RULES:
- "search X on youtube" → smart_search engine=youtube (NOT open_web)
- "search X on google" → smart_search engine=google
- "find X on reddit" → smart_search engine=reddit
- "scroll down 5 times" → scroll_n count=5 direction=down
- "scroll slowly" → scroll_start speed=slow
- "stop" or "stop scrolling" → scroll_stop
- "detect people" → wifi_sense_start
- "is someone there?" → wifi_sense_status
- "type this for me" → type_text
- "open youtube" → open_web url=https://youtube.com
Return ONLY the JSON.'''


class SmartActionEngine:
    def __init__(self):
        self.local_projects = {
            "Doctor Drift":  r"C:\Users\jishu\DoctorDrift",
            "Protein Zone":  r"C:\Users\jishu\ProteinZone",
        }
        self._browser = "unknown"

    def set_browser(self, browser: str):
        self._browser = browser

    def _classify(self, message: str) -> Optional[dict]:
        from app.services.groq_service import groq_service
        try:
            print(f"\n[ActionEngine] → {message!r}")
            resp = groq_service.chat(
                messages=[{"role": "user", "content": message}],
                system_prompt=_SYSTEM_PROMPT
            )
            print(f"[ActionEngine] LLM: {resp}")
            m = re.search(r'\{.*\}', resp, re.DOTALL)
            if m:
                data = json.loads(m.group(0))
                print(f"[ActionEngine] Action: {data.get('action')}")
                return data
        except Exception as e:
            print(f"[ActionEngine] Error: {e}")
        return None

    def _resolve(self, path: str) -> str:
        pl = path.lower().strip()
        for name, p in self.local_projects.items():
            if name.lower() in pl:
                return os.path.expandvars(p)
        return os.path.expandvars(os.path.expanduser(path))

    def _open_url(self, url: str) -> dict:
        try:
            from app.services.browser_detect import open_url_in_browser
            return open_url_in_browser(url, self._browser)
        except ImportError:
            from app.services.terminal_browser_service import browser_service
            return browser_service.open_url_simple(url)

    def _open_special(self, name: str) -> dict:
        import subprocess
        nl = name.lower().strip()
        for n, p in self.local_projects.items():
            if n.lower() in nl:
                try: os.startfile(os.path.expandvars(p)); return {"success": True}
                except Exception as e: return {"success": False, "message": str(e)}
        cmd = WIN_SPECIAL.get(nl)
        if cmd:
            try: subprocess.Popen(os.path.expandvars(cmd), shell=True); return {"success": True}
            except Exception as e: return {"success": False, "message": str(e)}
        if re.match(r'^[a-z]:$', nl):
            try: subprocess.Popen(f"explorer {nl.upper()}\\", shell=True); return {"success": True}
            except Exception as e: return {"success": False, "message": str(e)}
        return {"success": False, "message": f"Unknown: {name}"}

    def _launch_app(self, app: str) -> dict:
        import subprocess
        exe = WIN_APPS.get(app.lower().strip(), app)
        try:
            if exe.endswith(":"): subprocess.Popen(f'start "" "{exe}"', shell=True)
            else: subprocess.Popen(exe, shell=True)
            return {"success": True}
        except Exception as e: return {"success": False, "message": str(e)}

    def _generate_content(self, topic: str, ext: str) -> str:
        from app.services.groq_service import groq_service
        hints = {
            "py":"Write complete Python code.","js":"Write JavaScript code.",
            "html":"Write a complete HTML file.","md":"Write Markdown documentation.",
            "txt":"Write clear plain text.","csv":"Write CSV with header row.",
            "json":"Write valid JSON.",
        }
        hint = hints.get(ext, "Write useful content.")
        try:
            content = groq_service.chat(
                messages=[{"role": "user", "content": f"{hint}\n\nRequest: {topic}\n\nReturn ONLY the file content."}],
                system_prompt="You are a file content generator. Return ONLY the raw file content, no explanation, no markdown fences."
            )
            return re.sub(r'^```\w*\n?|\n?```$', '', content.strip())
        except Exception as e:
            return f"# Error: {e}"

    def _build_search_url(self, query: str, engine: str) -> str:
        import urllib.parse
        bases = {
            "google":  "https://www.google.com/search?q=",
            "youtube": "https://www.youtube.com/results?search_query=",
            "github":  "https://github.com/search?q=",
            "bing":    "https://www.bing.com/search?q=",
            "reddit":  "https://www.reddit.com/search/?q=",
        }
        return bases.get(engine.lower(), bases["google"]) + urllib.parse.quote_plus(query)

    def _quick_trigger(self, message: str) -> Optional[dict]:
        """Quick keyword-based triggers for common actions"""
        msg = message.lower()
        
        # GitHub triggers
        if "open github" in msg or "go to github" in msg:
            if "search" in msg:
                # Extract query from message
                query = msg.replace("open github", "").replace("go to github", "").replace("search", "").replace("for", "").strip()
                if query:
                    return {"action": "github_search", "query": query}
            return {"action": "open_browser", "url": "https://github.com"}
        
        # YouTube
        if "open youtube" in msg or "go to youtube" in msg:
            if "search" in msg:
                query = msg.replace("open youtube", "").replace("go to youtube", "").replace("search", "").replace("for", "").strip()
                if query:
                    return {"action": "smart_search", "query": query, "engine": "youtube"}
            return {"action": "open_browser", "url": "https://youtube.com"}
        
        # Google search
        if msg.startswith("search ") or "search for " in msg:
            query = msg.replace("search ", "").replace("search for ", "").strip()
            if query:
                return {"action": "smart_search", "query": query, "engine": "google"}
        
        # Open website
        if msg.startswith("open ") and ("." in msg or "website" in msg):
            words = msg.split()
            for i, word in enumerate(words):
                if word in ["open", "website", "a", "the"]:
                    words[i] = ""
            url = " ".join(words).strip()
            if url and "." in url:
                if not url.startswith("http"):
                    url = "https://" + url
                return {"action": "open_browser", "url": url}
        
        return None

    def evaluate_and_execute(self, message: str, data: Optional[dict] = None) -> Optional[str]:
        # First try quick keyword triggers
        if not data:
            data = self._quick_trigger(message)
        
        # Then try LLM classification
        if not data:
            data = self._classify(message)
        
        if not data: return None
        action = data.get("action", "chat")
        if action == "chat": return None

        from app.services.terminal_browser_service import terminal_service
        from app.services.desktop_service import keyboard_ctrl, mouse_ctrl, screen_ctrl

        # ── smart_search: types into address bar ──────────────────────────
        if action == "smart_search":
            query = data.get("query", message)
            engine = data.get("engine", "google").lower()
            url = self._build_search_url(query, engine)
            _log(f'🔍 Smart search: "{query}" on {engine.capitalize()}...')
            if not keyboard_ctrl.is_available():
                # Fallback to URL open
                r = self._open_url(url)
                return f'Searching **"{query}"** on {engine.capitalize()}...' if r["success"] else f"Search failed."
            r = keyboard_ctrl.focus_addressbar_and_search(url)
            if r["success"]:
                return f'🔍 Searching **"{query}"** on {engine.capitalize()}...'
            # Fallback
            r = self._open_url(url)
            return f'Searching **"{query}"** on {engine.capitalize()}...' if r["success"] else f"Search failed: {r.get('message','')}"

        # ── open_web ──────────────────────────────────────────────────────
        elif action == "open_web":
            url = data.get("url") or data.get("target", "")
            if not url: return "No URL."
            _log(f"🌐 Opening {url}...")
            r = self._open_url(url)
            return f"Opening **{url}**..." if r["success"] else f"Failed: {r.get('message','')}"

        # ── open_browser: Playwright browser automation ─────────────────
        elif action == "open_browser":
            url = data.get("url", "")
            if not url: return "No URL provided."
            _log(f"🌐 Opening in browser: {url}")
            from app.services.browser_automation_service import browser_service as playwright_browser
            import asyncio
            try:
                r = asyncio.get_event_loop().run_until_complete(playwright_browser.open_url(url))
            except RuntimeError:
                asyncio.run(playwright_browser.init())
                r = asyncio.run(playwright_browser.open_url(url))
            return f"🌐 Opened **{url}** in new browser tab." if r.get("success") else f"Failed: {r.get('message','')}"

        # ── browser_click ─────────────────────────────────────────────────
        elif action == "browser_click":
            selector = data.get("selector", "")
            _log(f"🖱️ Clicking: {selector}")
            from app.services.browser_automation_service import browser_service as playwright_browser
            import asyncio
            try:
                r = asyncio.get_event_loop().run_until_complete(playwright_browser.click(selector))
            except RuntimeError:
                asyncio.run(playwright_browser.init())
                r = asyncio.run(playwright_browser.click(selector))
            return f"Clicked **{selector}**." if r.get("success") else f"Failed: {r.get('message','')}"

        # ── browser_type ──────────────────────────────────────────────────
        elif action == "browser_type":
            selector = data.get("selector", "")
            text = data.get("text", "")
            _log(f"⌨️ Typing in {selector}: {text}")
            from app.services.browser_automation_service import browser_service as playwright_browser
            import asyncio
            try:
                r = asyncio.get_event_loop().run_until_complete(playwright_browser.fill(selector, text))
            except RuntimeError:
                asyncio.run(playwright_browser.init())
                r = asyncio.run(playwright_browser.fill(selector, text))
            return f"Typed in **{selector}**." if r.get("success") else f"Failed: {r.get('message','')}"

        # ── browser_scroll ─────────────────────────────────────────────────
        elif action == "browser_scroll":
            direction = data.get("direction", "down")
            amount = data.get("amount", 500)
            y = amount if direction == "down" else -amount
            _log(f"📜 Scrolling {direction}: {amount}px")
            from app.services.browser_automation_service import browser_service as playwright_browser
            import asyncio
            try:
                r = asyncio.get_event_loop().run_until_complete(playwright_browser.scroll(0, y))
            except RuntimeError:
                asyncio.run(playwright_browser.init())
                r = asyncio.run(playwright_browser.scroll(0, y))
            return f"Scrolled **{direction}**." if r.get("success") else f"Failed: {r.get('message','')}"

        # ── browser_screenshot ────────────────────────────────────────────
        elif action == "browser_screenshot":
            _log(f"📸 Taking browser screenshot...")
            from app.services.browser_automation_service import browser_service as playwright_browser
            import asyncio
            try:
                r = asyncio.get_event_loop().run_until_complete(playwright_browser.screenshot("browser_screenshot.png"))
            except RuntimeError:
                asyncio.run(playwright_browser.init())
                r = asyncio.run(playwright_browser.screenshot("browser_screenshot.png"))
            return "📸 Browser screenshot saved!" if r.get("success") else f"Failed: {r.get('message','')}"

        # ── github_search ─────────────────────────────────────────────────
        elif action == "github_search":
            query = data.get("query", "")
            _log(f"🔍 Searching GitHub: {query}")
            from app.services.browser_automation_service import browser_service as playwright_browser
            import asyncio
            try:
                r = asyncio.get_event_loop().run_until_complete(playwright_browser.search_github(query))
            except RuntimeError:
                asyncio.run(playwright_browser.init())
                r = asyncio.run(playwright_browser.search_github(query))
            if r.get("success"):
                results = r.get("results", [])
                if results:
                    msg = f"🔍 GitHub results for **\"{query}\"**:\n\n"
                    for i, res in enumerate(results[:5], 1):
                        msg += f"{i}. {res.get('title', 'No title')}\n"
                    return msg
                return f"No results found for **{query}**."
            return f"GitHub search failed: {r.get('message','')}"

        # ── web_search (fallback URL open) ────────────────────────────────
        elif action == "web_search":
            query = data.get("query", message)
            engine = data.get("engine", "google")
            url = self._build_search_url(query, engine)
            _log(f'🔍 Searching: "{query}"...')
            r = self._open_url(url)
            return f'Searching **"{query}"** on {engine.capitalize()}...' if r["success"] else f"Failed."

        # ── run_terminal ──────────────────────────────────────────────────
        elif action == "run_terminal":
            cmd = data.get("command",""); cwd = data.get("cwd") or None
            if not cmd: return "No command."
            _log(f"⚙️ Running: {cmd}")
            r = terminal_service.run(cmd, cwd=cwd)
            if r["success"]:
                out = r.get("output","")
                resp = f"✅ `{cmd}`\n\n"
                if out and out != "(no output)":
                    out = out[:1500] + ("\n...(truncated)" if len(out) > 1500 else "")
                    resp += f"```\n{out}\n```"
                else: resp += "*(Completed with no output)*"
                return resp
            return f"❌ `{cmd}` failed:\n```\n{r.get('error','')[:800]}\n```"

        # ── create_folder ─────────────────────────────────────────────────
        elif action == "create_folder":
            path = self._resolve(data.get("path",""))
            _log(f"📁 Creating: {path}")
            r = terminal_service.create_folder(path)
            return f"📁 Created: `{r.get('path',path)}`" if r["success"] else f"Failed: {r.get('message','')}"

        # ── create_file ───────────────────────────────────────────────────
        elif action == "create_file":
            path = self._resolve(data.get("path","untitled.txt"))
            content = data.get("content","")
            if data.get("generate_content") or not content.strip():
                ext = Path(path).suffix.lstrip(".")
                _log(f"🤖 Generating content for {Path(path).name}...")
                content = self._generate_content(data.get("topic", message), ext)
            _log(f"📄 Writing: {path}")
            r = terminal_service.create_file(path, content)
            if r["success"]:
                preview = content[:100].replace('\n',' ') + ("..." if len(content)>100 else "")
                return f"📄 Written: `{r.get('path',path)}`\n\nPreview: *{preview}*"
            return f"Failed: {r.get('message','')}"

        # ── open_special ──────────────────────────────────────────────────
        elif action == "open_special":
            name = data.get("name") or data.get("target","")
            _log(f"🖥️ Opening: {name}")
            r = self._open_special(name)
            return f"Opening **{name}**..." if r["success"] else f"Couldn't open: {r.get('message','')}"

        # ── open_folder / open_file ───────────────────────────────────────
        elif action in ("open_folder","open_file"):
            path = self._resolve(data.get("path",""))
            icon = "📂" if action=="open_folder" else "📄"
            _log(f"{icon} Opening: {path}")
            r = terminal_service.open_path(path)
            return f"{icon} Opening `{path}`..." if r["success"] else f"Failed: {r.get('message','')}"

        # ── open_app ──────────────────────────────────────────────────────
        elif action == "open_app":
            app = data.get("app","")
            _log(f"🚀 Launching: {app}")
            r = self._launch_app(app)
            return f"🚀 Launching **{app}**..." if r["success"] else f"Couldn't launch: {r.get('message','')}"

        # ── list_directory ────────────────────────────────────────────────
        elif action == "list_directory":
            path = self._resolve(data.get("path","."))
            _log(f"📂 Listing: {path}")
            r = terminal_service.list_directory(path)
            if not r["success"]: return f"Cannot list: {r.get('message','')}"
            items = r.get("items",[])
            out = f"📂 **{r.get('path',path)}** — {r.get('count',len(items))} items\n\n"
            folders = [i for i in items if i.get("type")=="folder"]
            files   = [i for i in items if i.get("type")=="file"]
            if folders: out += "**Folders:** " + "  ".join(f['name']+"/" for f in folders[:20]) + "\n"
            if files: out += "**Files:** " + "  ".join(f['name'] for f in files[:20])
            if r.get("count", 0) > 40: out += f"\n...and {r['count'] - 40} more"
            return out

        # ── type_text ─────────────────────────────────────────────────────
        elif action == "type_text":
            text = data.get("text",""); delay = float(data.get("delay",1.5))
            if not text: return "No text."
            if not keyboard_ctrl.is_available(): return "⚠️ pyautogui not installed."
            _log(f"⌨️ Typing {len(text)} chars...")
            r = keyboard_ctrl.type_text(text, delay_before=delay)
            return f"⌨️ Typed **{r.get('chars',len(text))} chars**." if r["success"] else f"Failed: {r.get('message','')}"

        # ── press_key ─────────────────────────────────────────────────────
        elif action == "press_key":
            key = data.get("key","")
            if not key: return "No key."
            if not keyboard_ctrl.is_available(): return "⚠️ pyautogui not installed."
            _log(f"⌨️ Pressing: {key}")
            r = keyboard_ctrl.press_key(key)
            return f"⌨️ Pressed **{key}**." if r["success"] else f"Failed: {r.get('message','')}"

        # ── hotkey ────────────────────────────────────────────────────────
        elif action == "hotkey":
            keys = data.get("keys",[])
            if not keys: return "No keys."
            if not keyboard_ctrl.is_available(): return "⚠️ pyautogui not installed."
            _log(f"⌨️ Hotkey: {'+'.join(str(k) for k in keys)}")
            r = keyboard_ctrl.hotkey(*keys)
            return f"⌨️ **{'+'.join(str(k) for k in keys)}** pressed." if r["success"] else f"Failed."

        # ── mouse_move ────────────────────────────────────────────────────
        elif action == "mouse_move":
            x, y = int(data.get("x",0)), int(data.get("y",0))
            if not mouse_ctrl.is_available(): return "⚠️ pyautogui not installed."
            _log(f"🖱️ Moving to ({x}, {y})...")
            r = mouse_ctrl.move(x, y)
            return f"🖱️ Mouse at **({x},{y})**." if r["success"] else f"Failed."

        # ── mouse_click ───────────────────────────────────────────────────
        elif action == "mouse_click":
            x, y = data.get("x"), data.get("y")
            button = data.get("button","left"); double = data.get("double",False)
            if not mouse_ctrl.is_available(): return "⚠️ pyautogui not installed."
            _log(f"🖱️ {'Double-c' if double else 'C'}licking at ({x},{y})...")
            r = mouse_ctrl.double_click(x,y) if double else mouse_ctrl.click(x,y,button)
            label = "Double-click" if double else f"{button.capitalize()}-click"
            return f"🖱️ {label} at **({x},{y})**." if r["success"] else f"Failed."

        # ── mouse_scroll ──────────────────────────────────────────────────
        elif action == "mouse_scroll":
            amount = int(data.get("amount",3))
            if not mouse_ctrl.is_available(): return "⚠️ pyautogui not installed."
            _log(f"🖱️ Scrolling {amount}...")
            r = mouse_ctrl.scroll(amount=amount)
            return f"🖱️ Scrolled **{'up' if amount>0 else 'down'}**." if r["success"] else f"Failed."

        # ── scroll_n: scroll page N times ─────────────────────────────────
        elif action == "scroll_n":
            count = int(data.get("count", 3))
            direction = data.get("direction", "down")
            if not mouse_ctrl.is_available(): return "⚠️ pyautogui not installed."
            _log(f"🖱️ Scrolling {direction} {count} times...")
            r = mouse_ctrl.scroll_n_times(count, direction)
            return f"🖱️ Scrolled **{direction}** {count} times." if r["success"] else f"Failed: {r.get('message','')}"

        # ── scroll_start: continuous scroll ───────────────────────────────
        elif action == "scroll_start":
            direction = data.get("direction", "down")
            speed = data.get("speed", "slow")
            if not mouse_ctrl.is_available(): return "⚠️ pyautogui not installed."
            _log(f"🖱️ Starting continuous {speed} scroll {direction}...")
            r = mouse_ctrl.start_continuous_scroll(direction, speed)
            return f"🖱️ Scrolling **{direction}** slowly. Say **'stop'** when done." if r["success"] else f"Failed: {r.get('message','')}"

        # ── scroll_stop ───────────────────────────────────────────────────
        elif action == "scroll_stop":
            if not mouse_ctrl.is_available(): return "⚠️ pyautogui not installed."
            _log("🖱️ Stopping scroll...")
            r = mouse_ctrl.stop_scroll()
            return "🖱️ Scrolling **stopped**." if r["success"] else "Nothing was scrolling."

        # ── screenshot ────────────────────────────────────────────────────
        elif action == "screenshot":
            if not screen_ctrl.is_available(): return "⚠️ pyautogui not installed."
            _log("📸 Taking screenshot...")
            r = screen_ctrl.screenshot(as_base64=False)
            return "📸 Screenshot taken." if r["success"] else f"Failed."

        return None

    def evaluate_and_execute_with_type(self, message: str) -> tuple:
        """Returns (result, action_type) tuple — used by filler service."""
        data = self._classify(message)
        if not data:
            return (None, "chat")
        action = data.get("action", "chat")
        if action == "chat":
            return (None, "chat")
        result = self.evaluate_and_execute(message, data=data)
        return (result, action)


action_engine = SmartActionEngine()
