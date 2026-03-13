"""
Smart Action Engine v4 — N.A.T. AI Assistant
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
Return ONLY raw JSON, no markdown, no explanation.

Actions:
1. open_web → {"action":"open_web","url":"https://youtube.com"}
2. web_search → {"action":"web_search","query":"search terms","engine":"google"}
   engine: google|youtube|github|bing
3. run_terminal → {"action":"run_terminal","command":"pip list","cwd":null}
4. create_folder → {"action":"create_folder","path":"C:/Users/jishu/NewFolder"}
5. create_file → {"action":"create_file","path":"C:/Users/jishu/file.txt","content":"file content","generate_content":false}
   Set generate_content=true if user says "write X and save as file" without explicit content.
6. open_special → {"action":"open_special","name":"downloads"}
   names: my pc, this pc, desktop, downloads, documents, pictures, c drive, d drive, control panel, recycle bin, task manager, settings
7. open_folder → {"action":"open_folder","path":"C:/Users/jishu/Documents"}
8. open_file → {"action":"open_file","path":"C:/Users/jishu/report.pdf"}
9. open_app → {"action":"open_app","app":"notepad"}
   apps: notepad, calculator, paint, cmd, powershell, vs code, chrome, firefox, edge, brave, excel, word, discord, spotify, vlc, steam, settings...
10. list_directory → {"action":"list_directory","path":"C:/Users/jishu"}
11. type_text → {"action":"type_text","text":"hello world","delay":1.5}
    Use when: "type this", "write this in current window", "type for me"
12. press_key → {"action":"press_key","key":"enter"}
    keys: enter, tab, backspace, escape, space, delete, up, down, left, right
13. hotkey → {"action":"hotkey","keys":["ctrl","c"]}
14. mouse_move → {"action":"mouse_move","x":960,"y":540}
15. mouse_click → {"action":"mouse_click","x":100,"y":200,"button":"left","double":false}
16. mouse_scroll → {"action":"mouse_scroll","amount":3}  (positive=up, negative=down)
17. screenshot → {"action":"screenshot"}
18. chat → {"action":"chat"}  (everything else)

RULES:
- "open youtube" → open_web url=https://youtube.com
- "search X on youtube" → web_search engine=youtube
- "open my downloads" → open_special name=downloads
- "open chrome" → open_app app=chrome
- "type hello" → type_text text=hello
- "press enter" → press_key key=enter
- "ctrl+v" → hotkey keys=["ctrl","v"]
- "move mouse to 500 300" → mouse_move x=500 y=300
- "click here" or "click at 200 400" → mouse_click
- "scroll down" → mouse_scroll amount=-5
- "take screenshot" → screenshot
- "write poem about X save as poem.txt" → create_file generate_content=true
Return ONLY the JSON object.'''


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
        from app.services.browser_detect import open_url_in_browser
        return open_url_in_browser(url, self._browser)

    def _open_special(self, name: str) -> dict:
        import subprocess
        nl = name.lower().strip()
        for n, p in self.local_projects.items():
            if n.lower() in nl:
                try: os.startfile(os.path.expandvars(p)); return {"success": True}
                except Exception as e: return {"success": False, "message": str(e)}
        cmd = WIN_SPECIAL.get(nl)
        if cmd:
            try: import subprocess; subprocess.Popen(os.path.expandvars(cmd), shell=True); return {"success": True}
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

    def evaluate_and_execute(self, message: str) -> Optional[str]:
        data = self._classify(message)
        if not data:
            return None
        action = data.get("action", "chat")
        if action == "chat":
            return None

        from app.services.terminal_browser_service import terminal_service
        from app.services.desktop_service import keyboard_ctrl, mouse_ctrl, screen_ctrl
        import urllib.parse

        if action == "open_web":
            url = data.get("url") or data.get("target", "")
            if not url: return "No URL provided."
            _log(f"🌐 Opening {url}...")
            r = self._open_url(url)
            return f"Opening **{url}**..." if r["success"] else f"Failed: {r.get('message','')}"

        elif action == "web_search":
            query = data.get("query", message)
            engine = data.get("engine", "google").lower()
            _log(f"🔍 Searching \"{query}\" on {engine.capitalize()}...")
            bases = {"google":"https://www.google.com/search?q=","youtube":"https://www.youtube.com/results?search_query=","github":"https://github.com/search?q=","bing":"https://www.bing.com/search?q="}
            url = bases.get(engine, bases["google"]) + urllib.parse.quote_plus(query)
            r = self._open_url(url)
            return f"Searching **\"{query}\"** on {engine.capitalize()}..." if r["success"] else f"Failed: {r.get('message','')}"

        elif action == "run_terminal":
            cmd = data.get("command", "")
            cwd = data.get("cwd") or None
            if not cmd: return "No command."
            _log(f"⚙️ Running: {cmd}")
            r = terminal_service.run(cmd, cwd=cwd)
            if r["success"]:
                out = r.get("output", "")
                resp = f"✅ `{cmd}`\n\n"
                if out and out != "(no output)":
                    out = out[:1500] + ("\n...(truncated)" if len(out) > 1500 else "")
                    resp += f"```\n{out}\n```"
                else: resp += "*(Completed with no output)*"
                return resp
            return f"❌ `{cmd}` failed:\n```\n{r.get('error','')[:800]}\n```"

        elif action == "create_folder":
            path = self._resolve(data.get("path", ""))
            _log(f"📁 Creating: {path}")
            r = terminal_service.create_folder(path)
            return f"📁 Created: `{r.get('path', path)}`" if r["success"] else f"Failed: {r.get('message','')}"

        elif action == "create_file":
            path = self._resolve(data.get("path", "untitled.txt"))
            content = data.get("content", "")
            if data.get("generate_content") or not content.strip():
                ext = Path(path).suffix.lstrip(".")
                _log(f"🤖 Generating content for {Path(path).name}...")
                content = self._generate_content(data.get("topic", message), ext)
            _log(f"📄 Writing: {path}")
            r = terminal_service.create_file(path, content)
            if r["success"]:
                preview = content[:100].replace('\n', ' ') + ("..." if len(content) > 100 else "")
                return f"📄 Written: `{r.get('path', path)}`\n\nPreview: *{preview}*"
            return f"Failed: {r.get('message','')}"

        elif action == "open_special":
            name = data.get("name") or data.get("target", "")
            _log(f"🖥️ Opening: {name}")
            r = self._open_special(name)
            return f"Opening **{name}**..." if r["success"] else f"Couldn't open '{name}': {r.get('message','')}"

        elif action in ("open_folder", "open_file"):
            path = self._resolve(data.get("path", ""))
            _log(f"{'📂' if action=='open_folder' else '📄'} Opening: {path}")
            r = terminal_service.open_path(path)
            icon = "📂" if action == "open_folder" else "📄"
            return f"{icon} Opening `{path}`..." if r["success"] else f"Failed: {r.get('message','')}"

        elif action == "open_app":
            app = data.get("app", "")
            _log(f"🚀 Launching: {app}")
            r = self._launch_app(app)
            return f"🚀 Launching **{app}**..." if r["success"] else f"Couldn't launch '{app}': {r.get('message','')}"

        elif action == "list_directory":
            path = self._resolve(data.get("path", "."))
            _log(f"📂 Listing: {path}")
            r = terminal_service.list_directory(path)
            if not r["success"]: return f"Cannot list: {r.get('message','')}"
            items = r.get("items", [])
            out = f"📂 **{r.get('path', path)}** — {r.get('count', len(items))} items\n\n"
            folders = [i for i in items if i.get("type") == "folder"]
            files   = [i for i in items if i.get("type") == "file"]
            if folders: out += "**Folders:** " + "  ".join(f['name'] + "/" for f in folders[:20]) + "\n"
            if files: out += "**Files:** " + "  ".join(f['name'] for f in files[:20])
            if r.get("count", 0) > 40: out += f"\n...and {r['count'] - 40} more"
            return out

        elif action == "type_text":
            text = data.get("text", "")
            delay = float(data.get("delay", 1.5))
            if not text: return "No text to type."
            if not keyboard_ctrl.is_available():
                return "⚠️ **pyautogui not installed.**\nRun: `pip install pyautogui pyperclip pygetwindow`"
            _log(f"⌨️ Typing {len(text)} chars (delay: {delay}s)...")
            r = keyboard_ctrl.type_text(text, delay_before=delay)
            return f"⌨️ Typed **{r.get('chars', len(text))} chars**." if r["success"] else f"Failed: {r.get('message','')}"

        elif action == "press_key":
            key = data.get("key", "")
            if not key: return "No key."
            if not keyboard_ctrl.is_available(): return "⚠️ pyautogui not installed."
            _log(f"⌨️ Pressing: {key}")
            r = keyboard_ctrl.press_key(key)
            return f"⌨️ Pressed **{key}**." if r["success"] else f"Failed: {r.get('message','')}"

        elif action == "hotkey":
            keys = data.get("keys", [])
            if not keys: return "No keys."
            if not keyboard_ctrl.is_available(): return "⚠️ pyautogui not installed."
            _log(f"⌨️ Hotkey: {'+'.join(str(k) for k in keys)}")
            r = keyboard_ctrl.hotkey(*keys)
            return f"⌨️ **{'+'.join(str(k) for k in keys)}** pressed." if r["success"] else f"Failed: {r.get('message','')}"

        elif action == "mouse_move":
            x, y = int(data.get("x", 0)), int(data.get("y", 0))
            if not mouse_ctrl.is_available(): return "⚠️ pyautogui not installed."
            _log(f"🖱️ Moving to ({x}, {y})...")
            r = mouse_ctrl.move(x, y)
            return f"🖱️ Mouse at **({x}, {y})**." if r["success"] else f"Failed: {r.get('message','')}"

        elif action == "mouse_click":
            x, y = data.get("x"), data.get("y")
            button = data.get("button", "left")
            double = data.get("double", False)
            if not mouse_ctrl.is_available(): return "⚠️ pyautogui not installed."
            _log(f"🖱️ {'Double-c' if double else 'C'}licking at ({x},{y})...")
            r = mouse_ctrl.double_click(x, y) if double else mouse_ctrl.click(x, y, button)
            label = "Double-click" if double else f"{button.capitalize()}-click"
            return f"🖱️ {label} at **({x},{y})**." if r["success"] else f"Failed: {r.get('message','')}"

        elif action == "mouse_scroll":
            amount = int(data.get("amount", 3))
            if not mouse_ctrl.is_available(): return "⚠️ pyautogui not installed."
            _log(f"🖱️ Scrolling {amount}...")
            r = mouse_ctrl.scroll(amount=amount)
            return f"🖱️ Scrolled **{'up' if amount > 0 else 'down'}**." if r["success"] else f"Failed: {r.get('message','')}"

        elif action == "screenshot":
            if not screen_ctrl.is_available(): return "⚠️ pyautogui not installed."
            _log("📸 Taking screenshot...")
            r = screen_ctrl.screenshot(as_base64=False)
            return "📸 Screenshot taken." if r["success"] else f"Failed: {r.get('message','')}"

        return None

    def evaluate_and_execute_with_type(self, message: str) -> tuple:
        """Returns (result, action_type) tuple"""
        data = self._classify(message)
        if not data:
            return (None, "chat")
        action = data.get("action", "chat")
        if action == "chat":
            return (None, "chat")
        
        # Execute the action
        result = self.evaluate_and_execute(message)
        return (result, action)


action_engine = SmartActionEngine()
