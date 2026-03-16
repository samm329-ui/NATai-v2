"""
Smart Action Engine v5 — N.A.T. AI Assistant
==============================================
Enhanced with context awareness, sequential tasks, system controls,
and Perplexity-style browser automation.
"""
import json
import re
import os
import platform
import shutil
import subprocess
import time
from pathlib import Path
from typing import Optional, Dict, Any, List

from app.services.context_service import working_context

OS = platform.system()

_activity_callbacks = []

def register_activity_callback(fn):
    _activity_callbacks.append(fn)

def _log(msg):
    print(f"[Activity] {msg}")
    for fn in _activity_callbacks:
        try: fn(msg)
        except: pass


# ==================== SPECIAL FOLDERS & APPS ====================

WIN_SPECIAL = {
    "my pc": "explorer ::{20D04FE0-3AEA-1069-A2D8-08002B30309D}",
    "this pc": "explorer ::{20D04FE0-3AEA-1069-A2D8-08002B30309D}",
    "computer": "explorer ::{20D04FE0-3AEA-1069-A2D8-08002B30309D}",
    "desktop": "explorer %USERPROFILE%\\Desktop",
    "downloads": "explorer %USERPROFILE%\\Downloads",
    "documents": "explorer %USERPROFILE%\\Documents",
    "pictures": "explorer %USERPROFILE%\\Pictures",
    "music": "explorer %USERPROFILE%\\Music",
    "videos": "explorer %USERPROFILE%\\Videos",
    "appdata": "explorer %APPDATA%",
    "temp": "explorer %TEMP%",
    "recycle bin": "explorer ::{645FF040-5081-101B-9F08-00AA002F954E}",
    "control panel": "control",
    "task manager": "taskmgr",
    "device manager": "devmgmt.msc",
    "c drive": "explorer C:\\",
    "d drive": "explorer D:\\",
    "e drive": "explorer E:\\",
    "f drive": "explorer F:\\",
}

WIN_APPS = {
    # System
    "notepad": "notepad", "calculator": "calc", "paint": "mspaint", "wordpad": "wordpad",
    "cmd": "cmd", "command prompt": "cmd", "powershell": "powershell", "terminal": "wt",
    "windows terminal": "wt", "settings": "ms-settings:",
    "task manager": "taskmgr", "snipping tool": "snippingtool",
    "on screen keyboard": "osk", "onscreenkeyboard": "osk", "osk": "osk",
    
    # Browsers
    "chrome": "chrome", "google chrome": "chrome", "firefox": "firefox", "edge": "msedge",
    "microsoft edge": "msedge", "brave": "brave", "opera": "opera",
    
    # Microsoft Office
    "excel": "excel", "word": "winword", "powerpoint": "powerpnt", "outlook": "outlook",
    "onenote": "onenote", "teams": "teams",
    
    # Adobe
    "premiere": "Adobe Premiere Pro", "premiere pro": "Adobe Premiere Pro",
    "photoshop": "Adobe Photoshop", "after effects": "Adobe After Effects",
    "illustrator": "Adobe Illustrator", "adobe": "Adobe",
    
    # Development
    "vs code": "code", "vscode": "code", "visual studio": "devenv",
    "sublime": "sublime_text", "notepad++": "notepad++",
    
    # Communication
    "discord": "discord", "slack": "slack", "zoom": "zoom", "teams": "teams",
    
    # Media
    "spotify": "spotify", "vlc": "vlc", "youtube": "youtube",
    "netflix": "netflix", "spotify": "spotify",
    
    # Gaming & Other
    "steam": "steam", "obs": "obs64", "twitch": "twitch",
    "file explorer": "explorer", "explorer": "explorer",
}

# ==================== ENHANCED SYSTEM PROMPT ====================

_SYSTEM_PROMPT = '''You are Natasha, an AI assistant that performs tasks on Windows like a human.

IMPORTANT ROUTING RULE:
- For news, current events, live sports scores, stock prices, weather → return {"action": "chat", "mode": "realtime"}
- For general knowledge, coding help, explanations → return {"action": "chat", "mode": "general"}

OPEN WEBSITE (any website URL):
- "open wikipedia.org" → {"action": "open_web", "url": "https://wikipedia.org"}
- "open amazon.com" → {"action": "open_web", "url": "https://amazon.com"}
- "open netflix.com" → {"action": "open_web", "url": "https://netflix.com"}
- "open youtube.com" → {"action": "open_web", "url": "https://youtube.com"}

SEARCH (when user wants to search):
- "search X" or "search for X" → {"action": "web_search", "query": "X"}

OPEN APP (when user wants to open a software/app):
- "open notepad" → {"action": "open_app", "app": "notepad"}
- "open chrome" → {"action": "open_app", "app": "chrome"}
3. "open app name" = open_app app="app name"
4. "open website.com" = web_search engine="google" (or appropriate engine)

4. ACTIONS: create_folder, delete_folder, create_file, delete_file, read_file
   - open_folder, open_file, open_app, close_app, open_settings
   - type_text, press_key, hotkey, mouse_move, mouse_click
   - web_search, browser_open, browser_click
   - system_volume, system_brightness
   - list_directory, screenshot, chat

Return JSON. For realtime queries: {"action": "chat", "mode": "realtime"}
For general chat: {"action": "chat", "mode": "general"}
For actions: {"action": "action_name", ...}'''


# ==================== SMART ACTION ENGINE ====================

class SmartActionEngine:
    def __init__(self):
        self.local_projects = {
            "Doctor Drift": r"C:\Users\jishu\DoctorDrift",
            "Protein Zone": r"C:\Users\jishu\ProteinZone",
        }
        self._browser = "unknown"
    
    def set_browser(self, browser: str):
        self._browser = browser
    
    def _classify(self, message: str) -> Optional[List[dict]]:
        """Classify user message into action(s)."""
        from app.services.groq_service import groq_service
        
        # Get context for the prompt
        ctx_info = working_context.to_prompt_context()
        full_prompt = _SYSTEM_PROMPT
        if ctx_info:
            full_prompt += f"\n\nCURRENT CONTEXT:\n{ctx_info}"
        
        try:
            print(f"\n[ActionEngine] → {message!r}")
            
            resp = groq_service.chat(
                messages=[{"role": "user", "content": message}],
                system_prompt=full_prompt
            )
            
            print(f"[ActionEngine] LLM: {resp}")
            
            # Try to parse as JSON array first, then single object
            m = re.search(r'\[.*\]', resp, re.DOTALL)
            if m:
                data = json.loads(m.group(0))
                print(f"[ActionEngine] Actions: {[a.get('action') for a in data]}")
                return data
            
            m = re.search(r'\{.*\}', resp, re.DOTALL)
            if m:
                data = json.loads(m.group(0))
                print(f"[ActionEngine] Action: {data.get('action')}")
                return [data]
                
        except Exception as e:
            print(f"[ActionEngine] Error: {e}")
        
        return None
    
    def _resolve_path(self, path_hint: str) -> str:
        """Smart path resolution using context."""
        # Try context resolution first
        if path_hint in ["that", "that folder", "it", "the folder", "there", "this"]:
            resolved = working_context.resolve_path(path_hint)
            if resolved:
                return resolved
        
        # Check special folders
        home = Path.home()
        special = {
            "desktop": str(home / "Desktop"),
            "downloads": str(home / "Downloads"),
            "documents": str(home / "Documents"),
            "pictures": str(home / "Pictures"),
            "music": str(home / "Music"),
            "videos": str(home / "Videos"),
        }
        
        path_lower = path_hint.lower().strip()
        if path_lower in special:
            return special[path_lower]
        
        # Check local projects
        for name, p in self.local_projects.items():
            if name.lower() in path_lower:
                return os.path.expandvars(p)
        
        # Absolute or relative
        if os.path.isabs(path_hint):
            return os.path.expandvars(os.path.expanduser(path_hint))
        
        # Relative to current directory
        base = working_context.get_current_directory() or str(home)
        return os.path.join(base, os.path.expandvars(os.path.expanduser(path_hint)))
    
    def _generate_content(self, topic: str, ext: str) -> str:
        from app.services.groq_service import groq_service
        hints = {
            "py": "Write complete Python code.",
            "js": "Write JavaScript code.",
            "html": "Write a complete HTML file.",
            "md": "Write Markdown documentation.",
            "txt": "Write clear plain text.",
            "csv": "Write CSV with header row.",
            "json": "Write valid JSON.",
        }
        hint = hints.get(ext, "Write useful content.")
        try:
            content = groq_service.chat(
                messages=[{"role": "user", "content": f"{hint}\n\nRequest: {topic}\n\nReturn ONLY the raw file content."}],
                system_prompt="You are a file content generator. Return ONLY the raw file content, no explanation, no markdown fences."
            )
            return re.sub(r'^```\w*\n?|\n?```$', '', content.strip())
        except Exception as e:
            return f"# Error: {e}"
    
    # ==================== EXECUTE SINGLE ACTION ====================
    
    def execute_single(self, action_data: dict, context: dict = None) -> str:
        """Execute a single action and return the result message."""
        action = action_data.get("action", "chat")
        
        if action == "chat":
            return None
        
        from app.services.terminal_browser_service import terminal_service
        from app.services.desktop_service import keyboard_ctrl, mouse_ctrl, screen_ctrl
        from app.services.system_control import system_controller
        from app.services.browser_automation import browser_automation
        import urllib.parse
        
        # === FILE OPERATIONS ===
        
        if action == "create_folder":
            path = self._resolve_path(action_data.get("path", ""))
            _log(f"📁 Creating: {path}")
            r = terminal_service.create_folder(path)
            if r["success"]:
                working_context.update_from_operation("create_folder", path=path)
            return f"📁 Created folder: `{r.get('path', path)}`" if r["success"] else f"Failed: {r.get('message', '')}"
        
        elif action == "delete_folder":
            path = self._resolve_path(action_data.get("path", ""))
            _log(f"🗑️ Deleting folder: {path}")
            try:
                if os.path.isdir(path):
                    shutil.rmtree(path)
                    working_context.update_from_operation("delete_folder", path=path)
                    return f"🗑️ Deleted folder: `{path}`"
            except Exception as e:
                return f"Failed to delete: {e}"
            return f"Folder not found: {path}"
        
        elif action == "create_file":
            path = self._resolve_path(action_data.get("path", "untitled.txt"))
            content = action_data.get("content", "")
            if action_data.get("generate_content") or not content.strip():
                ext = Path(path).suffix.lstrip(".")
                _log(f"🤖 Generating content for {Path(path).name}...")
                content = self._generate_content(action_data.get("topic", ""), ext)
            _log(f"📄 Writing: {path}")
            r = terminal_service.create_file(path, content)
            if r["success"]:
                working_context.update_from_operation("create_file", path=path)
                preview = content[:100].replace('\n', ' ') + ("..." if len(content) > 100 else "")
                return f"📄 Created file: `{r.get('path', path)}`\n\nPreview: *{preview}*"
            return f"Failed: {r.get('message', '')}"
        
        elif action == "delete_file":
            path = self._resolve_path(action_data.get("path", ""))
            _log(f"🗑️ Deleting file: {path}")
            try:
                if os.path.isfile(path):
                    os.remove(path)
                    working_context.update_from_operation("delete_file", path=path)
                    return f"🗑️ Deleted file: `{path}`"
            except Exception as e:
                return f"Failed to delete: {e}"
            return f"File not found: {path}"
        
        elif action == "read_file":
            path = self._resolve_path(action_data.get("path", ""))
            _log(f"📖 Reading: {path}")
            try:
                if os.path.isfile(path):
                    with open(path, "r", encoding="utf-8") as f:
                        content = f.read()
                    working_context.update_from_operation("read_file", path=path)
                    preview = content[:500] + ("..." if len(content) > 500 else "")
                    return f"📖 File: `{path}`\n\n```\n{preview}\n```"
            except Exception as e:
                return f"Failed to read: {e}"
            return f"File not found: {path}"
        
        elif action == "append_file":
            path = self._resolve_path(action_data.get("path", ""))
            content = action_data.get("content", "")
            _log(f"📝 Appending to: {path}")
            try:
                with open(path, "a", encoding="utf-8") as f:
                    f.write(content)
                return f"📝 Appended to: `{path}`"
            except Exception as e:
                return f"Failed to append: {e}"
        
        # === FOLDER/APP OPERATIONS ===
        
        elif action == "open_special":
            name = action_data.get("name") or action_data.get("target", "")
            _log(f"🖥️ Opening: {name}")
            cmd = WIN_SPECIAL.get(name.lower())
            if cmd:
                try:
                    # Use start command for better compatibility
                    subprocess.Popen(f'start "" "{os.path.expandvars(cmd)}"', shell=True)
                    return f"🖥️ Opened: **{name}**"
                except Exception as e:
                    return f"Failed: {e}"
            return f"Unknown special: {name}"
        
        elif action in ("open_folder", "open_file"):
            path = self._resolve_path(action_data.get("path", ""))
            _log(f"{'📂' if action == 'open_folder' else '📄'} Opening: {path}")
            r = terminal_service.open_path(path)
            if r["success"]:
                working_context.update_from_operation(action, path=path)
            icon = "📂" if action == "open_folder" else "📄"
            return f"{icon} Opened: `{path}`" if r["success"] else f"Failed: {r.get('message', '')}"
        
        elif action == "open_app":
            # Try both "app" and "app_name" fields
            app = action_data.get("app", action_data.get("app_name", ""))
            _log(f"🚀 Launching: {app}")
            
            # Check known apps first
            exe = WIN_APPS.get(app.lower())
            if not exe:
                exe = app
            
            # Try to launch known app
            try:
                subprocess.Popen(exe, shell=True)
                working_context.update_from_operation("open_app", app=app)
                return f"🚀 Launched: **{app}**"
            except:
                pass
            
            # Try Windows Start Menu search for unknown apps
            try:
                # Use explorer to open app via Start Menu
                result = subprocess.run(
                    f'start "" "{app}"',
                    shell=True,
                    capture_output=True,
                    text=True
                )
                if result.returncode == 0:
                    working_context.update_from_operation("open_app", app=app)
                    return f"🚀 Launched: **{app}**"
            except:
                pass
            
            return f"❌ Could not find or launch: **{app}**. Is it installed?"
        
        elif action == "close_app":
            app = action_data.get("app", "")
            _log(f"❌ Closing: {app}")
            r = system_controller.close_app(app)
            if r["success"]:
                working_context.update_from_operation("close_app", app=app)
                return f"❌ Closed: **{app}**"
            return f"Failed to close: {r.get('message', 'Unknown error')}"
        
        # === WEB BROWSER ===
        
        elif action == "open_web":
            url = action_data.get("url") or action_data.get("target", "")
            
            if not url:
                return "No URL provided."
            
            # Add https if missing
            if not url.startswith(("http://", "https://")):
                url = "https://" + url
            
            _log(f"🌐 Opening {url}...")
            
            # Get nice website name using learner
            from app.services.website_learner import website_learner
            nice_name = website_learner.get_or_extract_name(url)
            
            # Use browser_automation
            from app.services.browser_automation import browser_automation
            browser = self._browser or "brave"
            r = browser_automation.open_browser(url, browser)
            
            if r["success"]:
                working_context.update_from_operation("open_web", url=url)
                return f"🌐 Opened **{nice_name}**"
            return f"Failed to open {nice_name}: {r.get('message', '')}"
        
        elif action == "web_search":
            query = action_data.get("query", action_data.get("text", ""))
            
            # Get engine - default to google if not specified
            engine = action_data.get("engine", action_data.get("website", "google")).lower()
            
            # Auto-detect engine based on query content
            query_lower = query.lower()
            auto_detect = False
            
            # If no specific engine mentioned, auto-detect from query
            if not engine or engine == "google" or engine == "search":
                # Check if query suggests YouTube (music, videos, songs)
                music_keywords = ["song", "music", "video", "playlist", "album", "歌手", "歌曲", "音乐", "mv"]
                if any(kw in query_lower for kw in music_keywords):
                    engine = "youtube"
                    auto_detect = True
                elif "github" in query_lower or "code" in query_lower:
                    engine = "github"
                    auto_detect = True
                else:
                    engine = "google"  # Default
            
            # Handle website names
            website_to_engine = {
                "youtube": "youtube",
                "github": "github",
                "google": "google",
                "bing": "bing",
                "twitter": "google",
                "reddit": "google",
                "search": "google",
            }
            
            if engine in website_to_engine:
                engine = website_to_engine[engine]
            
            _log(f"🔍 Searching \"{query}\" on {engine}...")
            
            # Use browser_automation for proper search workflow
            from app.services.browser_automation import browser_automation
            browser = self._browser or "brave"
            r = browser_automation.open_search(query, engine, browser)
            
            if r["success"]:
                if query and query.strip():
                    return f"🔍 Searched **{query}** on {engine.capitalize()}"
                else:
                    return f"🌐 Opened **{engine.capitalize()}**"
            return f"Failed: {r.get('message', '')}"
        
        elif action == "learn_website":
            # Learn a website name (e.g., "learn that chatgpt is ChatGPT")
            url = action_data.get("url", "")
            name = action_data.get("name", "")
            
            if url and name:
                from app.services.website_learner import website_learner
                website_learner.learn_name(url, name)
                return f"📚 Learned: **{name}** for {url}"
            return "Please provide URL and name to learn"
        
        elif action == "browser_click":
            element = action_data.get("element", action_data.get("target", ""))
            _log(f"🖱️ Clicking: {element}")
            r = browser_automation.click_element(element)
            return f"🖱️ Clicked: {element}" if r["success"] else f"Failed: {r.get('message', '')}"
        
        elif action == "browser_type":
            text = action_data.get("text", "")
            _log(f"⌨️ Typing in browser: {text}")
            r = browser_automation.type_text(text)
            return f"⌨️ Typed: {text}" if r["success"] else f"Failed: {r.get('message', '')}"
        
        # === KEYBOARD & MOUSE ===
        
        elif action == "type_text":
            text = action_data.get("text", "")
            delay = float(action_data.get("delay", 1.5))
            if not text:
                return "No text to type."
            if not keyboard_ctrl.is_available():
                return "⚠️ pyautogui not installed."
            _log(f"⌨️ Typing {len(text)} chars...")
            r = keyboard_ctrl.type_text(text, delay_before=delay)
            return f"⌨️ Typed **{len(text)} chars**." if r["success"] else f"Failed: {r.get('message', '')}"
        
        elif action == "press_key":
            key = action_data.get("key", "")
            if not key:
                return "No key specified."
            if not keyboard_ctrl.is_available():
                return "⚠️ pyautogui not installed."
            _log(f"⌨️ Pressing: {key}")
            r = keyboard_ctrl.press_key(key)
            return f"⌨️ Pressed **{key}**." if r["success"] else f"Failed: {r.get('message', '')}"
        
        elif action == "hotkey":
            keys = action_data.get("keys", [])
            if not keys:
                return "No keys specified."
            if not keyboard_ctrl.is_available():
                return "⚠️ pyautogui not installed."
            _log(f"⌨️ Hotkey: {'+'.join(keys)}")
            r = keyboard_ctrl.hotkey(*keys)
            return f"⌨️ **{'+'.join(keys)}** pressed." if r["success"] else f"Failed: {r.get('message', '')}"
        
        elif action == "mouse_move":
            x = int(action_data.get("x", 0))
            y = int(action_data.get("y", 0))
            if not mouse_ctrl.is_available():
                return "⚠️ pyautogui not installed."
            _log(f"🖱️ Moving to ({x}, {y})...")
            r = mouse_ctrl.move(x, y)
            return f"🖱️ Mouse at **({x}, {y})**." if r["success"] else f"Failed: {r.get('message', '')}"
        
        elif action == "mouse_click":
            x = action_data.get("x")
            y = action_data.get("y")
            button = action_data.get("button", "left")
            double = action_data.get("double", False)
            if not mouse_ctrl.is_available():
                return "⚠️ pyautogui not installed."
            _log(f"🖱️ Clicking at ({x}, {y})...")
            r = mouse_ctrl.double_click(x, y) if double else mouse_ctrl.click(x, y, button)
            label = "Double-click" if double else f"{button.capitalize()}-click"
            return f"🖱️ {label} at **({x}, {y})**." if r["success"] else f"Failed: {r.get('message', '')}"
        
        elif action == "mouse_scroll":
            amount = int(action_data.get("amount", 3))
            if not mouse_ctrl.is_available():
                return "⚠️ pyautogui not installed."
            _log(f"🖱️ Scrolling {amount}...")
            r = mouse_ctrl.scroll(amount=amount)
            return f"🖱️ Scrolled **{'up' if amount > 0 else 'down'}**." if r["success"] else f"Failed: {r.get('message', '')}"
        
        # === TERMINAL ===
        
        elif action == "run_terminal":
            cmd = action_data.get("command", "")
            cwd = action_data.get("cwd")
            if not cmd:
                return "No command."
            _log(f"⚙️ Running: {cmd}")
            r = terminal_service.run(cmd, cwd=cwd)
            if r["success"]:
                out = r.get("output", "")
                resp = f"✅ `{cmd}`\n\n"
                if out and out != "(no output)":
                    out = out[:1500] + ("\n...(truncated)" if len(out) > 1500 else "")
                    resp += f"```\n{out}\n```"
                else:
                    resp += "*(Completed with no output)*"
                return resp
            return f"❌ `{cmd}` failed:\n```\n{r.get('error', '')[:800]}\n```"
        
        elif action == "list_directory":
            path = self._resolve_path(action_data.get("path", "."))
            _log(f"📂 Listing: {path}")
            r = terminal_service.list_directory(path)
            if not r["success"]:
                return f"Cannot list: {r.get('message', '')}"
            items = r.get("items", [])
            out = f"📂 **{r.get('path', path)}** — {r.get('count', len(items))} items\n\n"
            folders = [i for i in items if i.get("type") == "folder"]
            files = [i for i in items if i.get("type") == "file"]
            if folders:
                out += "**Folders:** " + "  ".join(f['name'] + "/" for f in folders[:20]) + "\n"
            if files:
                out += "**Files:** " + "  ".join(f['name'] for f in files[:20])
            if r.get("count", 0) > 40:
                out += f"\n...and {r['count'] - 40} more"
            return out
        
        # === SYSTEM CONTROLS ===
        
        elif action == "system_volume":
            # Check for increase/decrease keywords
            direction = action_data.get("direction", "")
            level = action_data.get("level", 50)
            
            # Parse level if it's a string like "50%"
            if isinstance(level, str):
                level = int(level.replace("%", "").strip())
            
            if "up" in direction or "increase" in direction or "higher" in direction:
                r = system_controller.increase_volume(level)
            elif "down" in direction or "decrease" in direction or "lower" in direction:
                r = system_controller.decrease_volume(level)
            elif action_data.get("mute"):
                r = system_controller.mute_volume(True)
            else:
                r = system_controller.set_volume(level)
            
            if r["success"]:
                return f"🔊 Volume set to **{r.get('volume', level)}%**"
            return f"⚠️ {r.get('message', 'Volume control unavailable. Install NirCmd for full control.')}"
        
        elif action == "system_brightness":
            direction = action_data.get("direction", "")
            level = action_data.get("level", action_data.get("percentage", 50))
            
            # Handle negative percentage (like -50 for dimming)
            if isinstance(level, str):
                level = level.replace("%", "").replace("percent", "").strip()
                if level.startswith("-"):
                    direction = "down"
                    level = level[1:]
                level = int(level)
            
            # Check for negative values
            if level < 0:
                direction = "down"
                level = abs(level)
            
            if "up" in direction or "increase" in direction or "higher" in direction or "brighten" in direction:
                r = system_controller.increase_brightness(level)
            elif "down" in direction or "decrease" in direction or "dim" in direction or "lower" in direction or "dark" in direction:
                r = system_controller.decrease_brightness(level)
            else:
                r = system_controller.set_brightness(level)
            
            if r["success"]:
                return f"☀️ Brightness set to **{r.get('brightness', level)}%**"
            return f"⚠️ {r.get('message', 'Brightness control unavailable. Install NirCmd for full control.')}"
        
        elif action == "open_settings":
            page = action_data.get("page", "")
            _log(f"⚙️ Opening settings: {page}")
            r = system_controller.open_settings(page)
            if r["success"]:
                return f"⚙️ Opened **{r.get('opened', 'Settings')}**"
            return f"Failed: {r.get('message', '')}"
        
        elif action == "toggle_wifi":
            enable = action_data.get("enable", True)
            _log(f"📡 Wi-Fi: {'on' if enable else 'off'}")
            r = system_controller.toggle_wifi(enable)
            return f"📡 Wi-Fi toggled" if r["success"] else r.get("message", "Failed")
        
        # === OTHER ===
        
        elif action == "screenshot":
            if not screen_ctrl.is_available():
                return "⚠️ pyautogui not installed."
            _log("📸 Taking screenshot...")
            r = screen_ctrl.screenshot(as_base64=False)
            return "📸 Screenshot taken." if r["success"] else f"Failed: {r.get('message', '')}"
        
        elif action == "wait":
            seconds = float(action_data.get("seconds", 1))
            _log(f"⏳ Waiting {seconds}s...")
            time.sleep(seconds)
            return f"⏳ Waited {seconds} seconds."
        
        return None
    
    # ==================== CHAIN EXECUTION ====================
    
    def evaluate_and_execute(self, message: str) -> Optional[str]:
        """Original single-action execution (for compatibility)."""
        actions = self._classify(message)
        if not actions:
            return None
        
        if len(actions) == 1:
            # Single action
            result = self.execute_single(actions[0])
            return result
        else:
            # Multiple actions - execute sequentially
            return self.execute_chain(actions, message)
    
    def execute_chain(self, actions: List[dict], original_message: str = "") -> str:
        """Execute multiple actions sequentially."""
        results = []
        
        for i, action_data in enumerate(actions):
            action_name = action_data.get("action", "unknown")
            _log(f"🔗 Step {i+1}/{len(actions)}: {action_name}")
            
            try:
                result = self.execute_single(action_data)
                if result:
                    results.append(result)
                
                # Small delay between actions
                time.sleep(0.5)
                
            except Exception as e:
                results.append(f"❌ Step {i+1} failed: {e}")
                break
        
        if not results:
            return "No actions executed."
        
        # Combine results
        if len(results) == 1:
            return results[0]
        
        combined = "📋 **Completed " + str(len(results)) + " actions:**\n\n"
        combined += "\n\n".join(f"{i+1}. {r}" for i, r in enumerate(results))
        return combined
    
    def evaluate_and_execute_with_type(self, message: str) -> tuple:
        """Returns (result, action_type, mode) tuple. Mode is 'general', 'realtime', or None."""
        actions = self._classify(message)
        
        if not actions:
            return (None, "chat", None)
        
        if len(actions) == 1:
            action = actions[0].get("action", "chat")
            
            # Check if LLM suggests realtime mode
            mode = actions[0].get("mode")
            if mode == "realtime":
                return (None, "chat", "realtime")
            elif mode == "general":
                return (None, "chat", "general")
            
            if action == "chat":
                # Do a quick check if this needs realtime
                return (None, "chat", None)
            
            result = self.execute_single(actions[0])
            return (result, action, None)
        else:
            # Multiple actions
            result = self.execute_chain(actions, message)
            return (result, "chain", None)


# Global singleton
action_engine = SmartActionEngine()
