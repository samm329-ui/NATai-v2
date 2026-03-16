"""
Terminal & Browser Service for N.A.T. AI Assistant
Gives Natasha full control over:
  - Terminal commands (run shell commands, create/open files/folders)
  - Browser automation (open URLs, navigate, interact with pages)
  - File system operations (create, list, delete, move files)
  - App launching (open installed applications)

All actions are logged and streamed back to the frontend in real time.
"""

import os
import sys
import subprocess
import platform
import shutil
from pathlib import Path
from typing import Optional
import asyncio


# ─────────────────────────────────────────────
#  Platform helpers
# ─────────────────────────────────────────────

OS = platform.system()  # "Windows", "Darwin", "Linux"

def _open_path(path: str) -> str:
    """Open a file, folder, or app using the OS default handler."""
    path = os.path.expandvars(os.path.expanduser(path))
    if OS == "Windows":
        os.startfile(path)
    elif OS == "Darwin":
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])
    return path


# ─────────────────────────────────────────────
#  Terminal Service
# ─────────────────────────────────────────────

class TerminalService:
    """
    Executes shell commands safely on the host machine.
    Returns structured output: stdout, stderr, return_code, summary.
    """

    BLOCKED = [
        "rm -rf /", "rmdir /s /q C:\\", "format c:", ":(){:|:&};:",
        "dd if=/dev/zero", "mkfs", "shutdown", "reboot", "halt",
        "sudo rm -rf", "del /f /s /q C:\\"
    ]

    def run(self, command: str, cwd: Optional[str] = None) -> dict:
        """Run a terminal command."""
        cmd_lower = command.lower().strip()
        for blocked in self.BLOCKED:
            if blocked.lower() in cmd_lower:
                return {
                    "success": False,
                    "output": "",
                    "error": f"⛔ Blocked command for safety: '{blocked}' pattern detected.",
                    "command": command,
                    "cwd": cwd or os.getcwd()
                }

        working_dir = os.path.expandvars(os.path.expanduser(cwd)) if cwd else None

        try:
            print(f"[Terminal] Running: {command}")
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30,
                cwd=working_dir
            )
            output = result.stdout.strip()
            error  = result.stderr.strip()
            success = result.returncode == 0

            print(f"[Terminal] Exit code: {result.returncode}")
            if output: print(f"[Terminal] Output: {output[:200]}")
            if error:  print(f"[Terminal] Stderr: {error[:200]}")

            return {
                "success": success,
                "output": output or "(no output)",
                "error": error,
                "command": command,
                "return_code": result.returncode,
                "cwd": working_dir or os.getcwd()
            }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "output": "",
                "error": "Command timed out after 30 seconds.",
                "command": command,
                "return_code": -1,
                "cwd": working_dir or os.getcwd()
            }
        except Exception as e:
            return {
                "success": False,
                "output": "",
                "error": str(e),
                "command": command,
                "return_code": -1,
                "cwd": working_dir or os.getcwd()
            }

    def _normalize_path(self, path: str) -> str:
        """
        Auto-corrects paths to OneDrive equivalents if Windows PC Folder Backup is on.
        For example: 'C:/Users/name/Desktop' -> 'C:/Users/name/OneDrive/Desktop'
        """
        expanded = os.path.expandvars(os.path.expanduser(path))
        path_obj = Path(expanded).resolve()

        # Typical Windows profile structure: C:\Users\Username
        # Usually checking if it's currently looking at Desktop/Documents/Pictures
        user_home = Path.home()
        onedrive_path = user_home / "OneDrive"
        
        if onedrive_path.exists() and onedrive_path.is_dir():
            target_folders = ["Desktop", "Documents", "Pictures"]
            
            for folder in target_folders:
                standard_folder = user_home / folder
                onedrive_folder = onedrive_path / folder
                
                # If the requested path is exactly or inside ONE of these folders...
                try:
                    # Check if standard folder is a parent of path_obj
                    if standard_folder in path_obj.parents or path_obj == standard_folder:
                        # But make sure the OneDrive equivalent actually exists before rerouting
                        if onedrive_folder.exists():
                            # Rebuild the path substituting the base folder
                            rel_path = path_obj.relative_to(standard_folder)
                            new_path = onedrive_folder / rel_path
                            print(f"[Terminal] Auto-routed OneDrive path: {new_path}")
                            return str(new_path)
                except ValueError:
                    # relative_to throws ValueError if it's not a subpath, which is fine, just continue
                    pass

        return str(path_obj)

    def create_folder(self, path: str) -> dict:
        """Create a folder (and all parents) at the given path."""
        expanded = self._normalize_path(path)
        try:
            Path(expanded).mkdir(parents=True, exist_ok=True)
            print(f"[Terminal] Created folder: {expanded}")
            return {"success": True, "path": expanded, "message": f"Folder created: {expanded}"}
        except Exception as e:
            return {"success": False, "path": expanded, "message": str(e)}

    def create_file(self, path: str, content: str = "") -> dict:
        """Create a file with optional content."""
        expanded = self._normalize_path(path)
        try:
            p = Path(expanded)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
            print(f"[Terminal] Created file: {expanded}")
            return {"success": True, "path": expanded, "message": f"File created: {expanded}"}
        except Exception as e:
            return {"success": False, "path": expanded, "message": str(e)}

    def list_directory(self, path: str = ".") -> dict:
        """List contents of a directory."""
        expanded = self._normalize_path(path)
        try:
            p = Path(expanded)
            if not p.exists():
                return {"success": False, "path": expanded, "items": [], "message": "Path does not exist"}
            items = []
            for item in sorted(p.iterdir()):
                items.append({
                    "name": item.name,
                    "type": "folder" if item.is_dir() else "file",
                    "size": item.stat().st_size if item.is_file() else None
                })
            return {"success": True, "path": str(p.resolve()), "items": items, "count": len(items)}
        except Exception as e:
            return {"success": False, "path": expanded, "items": [], "message": str(e)}

    def open_path(self, path: str) -> dict:
        """Open a file or folder in the default OS application."""
        expanded = os.path.expandvars(os.path.expanduser(path))
        try:
            opened = _open_path(expanded)
            return {"success": True, "path": opened, "message": f"Opened: {opened}"}
        except Exception as e:
            return {"success": False, "path": expanded, "message": str(e)}

    def open_app(self, app_name: str) -> dict:
        """Try to launch a known application by name."""
        try:
            print(f"[Terminal] Launching app: {app_name}")
            if OS == "Windows":
                result = subprocess.Popen(f'start "" "{app_name}"', shell=True)
            elif OS == "Darwin":
                result = subprocess.Popen(["open", "-a", app_name])
            else:
                exe = shutil.which(app_name.lower().replace(" ", "-"))
                if exe:
                    result = subprocess.Popen([exe])
                else:
                    return {"success": False, "message": f"App '{app_name}' not found on PATH."}
            return {"success": True, "message": f"Launched: {app_name}"}
        except Exception as e:
            return {"success": False, "message": str(e)}


# ─────────────────────────────────────────────
#  Browser Service
# ─────────────────────────────────────────────

class BrowserService:
    """Controls a web browser via Playwright or fallback to webbrowser."""

    def __init__(self):
        self._playwright = None
        self._browser = None
        self._page = None
        self._playwright_available = False
        self._check_playwright()

    def _check_playwright(self):
        try:
            import playwright
            self._playwright_available = True
            print("[Browser] Playwright is available")
        except ImportError:
            self._playwright_available = False
            print("[Browser] Playwright not installed — using webbrowser fallback.")

    def open_url_simple(self, url: str) -> dict:
        """Open URL in the user's default browser."""
        import webbrowser
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        try:
            webbrowser.open(url)
            return {"success": True, "url": url, "message": f"Opened in browser: {url}"}
        except Exception as e:
            return {"success": False, "url": url, "message": str(e)}

    def open_search(self, query: str, engine: str = "google") -> dict:
        """Open a search query in the browser."""
        import urllib.parse
        engines = {
            "google":  "https://www.google.com/search?q=",
            "youtube": "https://www.youtube.com/results?search_query=",
            "github":  "https://github.com/search?q=",
            "bing":    "https://www.bing.com/search?q=",
        }
        base = engines.get(engine.lower(), engines["google"])
        url = base + urllib.parse.quote_plus(query)
        return self.open_url_simple(url)

    async def async_open_url(self, url: str, headless: bool = False) -> dict:
        """Open a URL using Playwright."""
        if not self._playwright_available:
            return self.open_url_simple(url)

        if not url.startswith(("http://", "https://")):
            url = "https://" + url

        try:
            from playwright.async_api import async_playwright
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=headless)
                page = await browser.new_page()
                await page.goto(url, timeout=15000)
                title = await page.title()
                final_url = page.url
                await browser.close()

            return {
                "success": True,
                "url": final_url,
                "title": title,
                "message": f"Opened '{title}' at {final_url}"
            }
        except Exception as e:
            print(f"[Browser] Playwright error: {e}, falling back to webbrowser")
            return self.open_url_simple(url)

    async def async_get_page_text(self, url: str) -> dict:
        """Fetch the visible text content of a webpage using Playwright."""
        if not self._playwright_available:
            return {"success": False, "message": "Playwright not installed. Run: pip install playwright && playwright install chromium"}

        if not url.startswith(("http://", "https://")):
            url = "https://" + url

        try:
            from playwright.async_api import async_playwright
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                await page.goto(url, timeout=15000)
                text = await page.inner_text("body")
                title = await page.title()
                await browser.close()

            return {
                "success": True,
                "url": url,
                "title": title,
                "text": text[:3000],
                "message": f"Fetched content from '{title}'"
            }
        except Exception as e:
            return {"success": False, "url": url, "message": str(e)}

    async def async_screenshot(self, url: str, save_path: str = "screenshot.png") -> dict:
        """Take a screenshot of a webpage."""
        if not self._playwright_available:
            return {"success": False, "message": "Playwright not installed."}

        if not url.startswith(("http://", "https://")):
            url = "https://" + url

        try:
            from playwright.async_api import async_playwright
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                await page.goto(url, timeout=15000)
                await page.screenshot(path=save_path, full_page=True)
                await browser.close()

            return {"success": True, "url": url, "screenshot_path": save_path, "message": f"Screenshot saved to {save_path}"}
        except Exception as e:
            return {"success": False, "url": url, "message": str(e)}


terminal_service = TerminalService()
browser_service  = BrowserService()
