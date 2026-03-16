"""
Browser Automation Service — N.A.T. AI Assistant
===============================================
Perplexity-style browser control: open browser, take screenshot, 
analyze with vision, click/type elements, repeat until task complete.
"""
import os
import time
import subprocess
import urllib.parse
from typing import Optional, Dict, Any, Tuple, List

from app.services.context_service import working_context


class BrowserAutomation:
    """
    Perplexity-style browser automation.
    
    Workflow:
    1. Open browser to URL
    2. Wait for page load
    3. Find search bar and click it
    4. Type search query
    5. Press Enter to search
    """
    
    def __init__(self):
        self._browser_process = None
        self._last_screenshot = None
        self._screen_size = {"width": 1920, "height": 1080}
    
    def is_available(self) -> bool:
        """Check if browser automation is available."""
        try:
            import pyautogui
            return True
        except ImportError:
            return False
    
    # ==================== BROWSER CONTROL ====================
    
    def open_browser(self, url: str, browser: str = "brave") -> Dict[str, Any]:
        """
        Open a browser to a specific URL.
        """
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        
        browser_cmds = {
            "brave": "brave",
            "chrome": "chrome",
            "edge": "msedge",
            "firefox": "firefox",
        }
        
        cmd = browser_cmds.get(browser.lower(), browser.lower())
        if not cmd:
            cmd = browser
        
        try:
            # Try different command formats
            commands = [
                f'start "" "{cmd}" "{url}"',
                f'"{cmd}" --new-window "{url}"',
                f'start {cmd} "{url}"',
            ]
            
            for cmd_str in commands:
                try:
                    subprocess.run(cmd_str, shell=True, timeout=2, capture_output=True)
                    time.sleep(2)
                    working_context.update_from_operation("open_browser", url=url)
                    return {
                        "success": True,
                        "url": url,
                        "browser": browser,
                        "message": f"Opened {browser}"
                    }
                except:
                    continue
            
            # If all commands failed, try webbrowser module as last resort
            import webbrowser
            webbrowser.open(url)
            return {"success": True, "url": url, "browser": browser}
            
        except Exception as e:
            # Try webbrowser as fallback
            try:
                import webbrowser
                webbrowser.open(url)
                return {"success": True, "url": url, "browser": browser}
            except:
                return {"success": False, "message": f"Could not open browser: {str(e)}"}
    
    def open_search(self, query: str = "", engine: str = "google", browser: str = "brave") -> Dict[str, Any]:
        """
        Open a search query in the browser.
        """
        search_urls = {
            "google": "https://www.google.com",
            "youtube": "https://www.youtube.com",
            "github": "https://github.com",
            "bing": "https://www.bing.com",
            "duckduckgo": "https://duckduckgo.com",
        }
        
        base_url = search_urls.get(engine.lower(), search_urls["google"])
        
        # If query is provided, add it to URL
        if query and query.strip():
            if engine.lower() == "youtube":
                base_url = f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}"
            elif engine.lower() == "github":
                base_url = f"https://github.com/search?q={query.replace(' ', '+')}"
            else:
                base_url = f"{base_url}/search?q={query.replace(' ', '+')}"
        
        # Open browser to the URL
        result = self.open_browser(base_url, browser)
        if not result["success"]:
            return result
        
        return {
            "success": True,
            "query": query,
            "engine": engine,
            "message": f"Opened {engine.capitalize()}" + (f" and searched for '{query}'" if query else "")
        }
    
    def close_browser(self, browser: str = "brave") -> Dict[str, Any]:
        """Close the browser."""
        browser_procs = {
            "brave": "brave.exe",
            "chrome": "chrome.exe",
            "edge": "msedge.exe",
            "firefox": "firefox.exe",
        }
        
        exe = browser_procs.get(browser.lower(), browser + ".exe")
        
        try:
            subprocess.run(
                ['taskkill', '/IM', exe, '/F'],
                capture_output=True,
                timeout=5
            )
            return {"success": True, "browser": browser}
        except Exception as e:
            return {"success": False, "message": str(e)}
    
    # ==================== SCREENSHOT ====================
    
    def take_screenshot(self, region: Optional[Tuple[int, int, int, int]] = None) -> Dict[str, Any]:
        """Take a screenshot."""
        try:
            import pyautogui
            import io
            import base64
            
            if region:
                img = pyautogui.screenshot(region=region)
            else:
                img = pyautogui.screenshot()
            
            self._screen_size = {"width": img.width, "height": img.height}
            
            buf = io.BytesIO()
            img.save(buf, format='PNG')
            b64 = base64.b64encode(buf.getvalue()).decode()
            
            self._last_screenshot = b64
            
            return {
                "success": True,
                "image_b64": b64,
                "width": img.width,
                "height": img.height,
            }
        except Exception as e:
            return {"success": False, "message": str(e)}
    
    # ==================== MOUSE CONTROL ====================
    
    def move_mouse(self, x: int, y: int, duration: float = 0.3) -> Dict[str, Any]:
        """Move mouse to coordinates."""
        try:
            import pyautogui
            pyautogui.moveTo(x, y, duration=duration)
            return {"success": True, "x": x, "y": y}
        except Exception as e:
            return {"success": False, "message": str(e)}
    
    def click_at(self, x: int, y: int, button: str = "left", double: bool = False) -> Dict[str, Any]:
        """Click at specific coordinates."""
        try:
            import pyautogui
            
            if double:
                pyautogui.doubleClick(x, y)
            else:
                pyautogui.click(x, y, button=button)
            
            return {
                "success": True,
                "x": x,
                "y": y,
                "button": button,
                "double": double
            }
        except Exception as e:
            return {"success": False, "message": str(e)}
    
    def click_element(self, element_description: str) -> Dict[str, Any]:
        """Find and click an element by description."""
        return {
            "success": False,
            "message": f"Could not find: {element_description}. Use click_at with coordinates."
        }
    
    def scroll(self, amount: int = 3) -> Dict[str, Any]:
        """Scroll the page."""
        try:
            import pyautogui
            pyautogui.scroll(amount)
            return {"success": True, "amount": amount}
        except Exception as e:
            return {"success": False, "message": str(e)}
    
    # ==================== KEYBOARD CONTROL ====================
    
    def type_text(self, text: str, delay: float = 0.3) -> Dict[str, Any]:
        """Type text at current cursor position."""
        try:
            import pyautogui
            time.sleep(delay)
            pyautogui.typewrite(text, interval=0.05)
            return {"success": True, "chars": len(text)}
        except Exception as e:
            return {"success": False, "message": str(e)}
    
    def press_key(self, key: str) -> Dict[str, Any]:
        """Press a key."""
        try:
            import pyautogui
            pyautogui.press(key.lower())
            return {"success": True, "key": key}
        except Exception as e:
            return {"success": False, "message": str(e)}
    
    def hotkey(self, *keys) -> Dict[str, Any]:
        """Press a key combination."""
        try:
            import pyautogui
            pyautogui.hotkey(*[k.lower() for k in keys])
            return {"success": True, "keys": list(keys)}
        except Exception as e:
            return {"success": False, "message": str(e)}
    
    # ==================== UTILITY ====================
    
    def wait(self, seconds: float) -> Dict[str, Any]:
        """Wait for specified seconds."""
        time.sleep(seconds)
        return {"success": True, "waited": seconds}


# Global singleton
browser_automation = BrowserAutomation()
