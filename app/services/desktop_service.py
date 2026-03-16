"""
Desktop Control Service — N.A.T. AI Assistant
══════════════════════════════════════════════
Full keyboard + mouse control of the user's PC using PyAutoGUI.
Natasha can physically type, click, move the mouse, scroll, take screenshots,
and fire hotkey combos — like a real person at the keyboard.

Features:
  Keyboard:
    - type_text(text)           → type into active window
    - press_key(key)            → press single key (enter, tab, esc…)
    - hotkey(*keys)             → key combo (ctrl+c, alt+f4…)
    - clipboard_type(text)      → paste via clipboard (fast for long text)

  Mouse:
    - move(x, y)                → move mouse to position
    - click(x, y, button)       → left/right/middle click
    - double_click(x, y)        → double click
    - drag(x1, y1, x2, y2)      → drag from A to B
    - scroll(x, y, amount)      → scroll wheel
    - get_position()            → current cursor position
    - get_screen_size()         → screen resolution

  Screen:
    - screenshot(path)          → take screenshot, return path/base64
    - find_on_screen(image)     → find image on screen (template matching)

  System:
    - is_available()            → True if pyautogui installed
    - get_status()              → full status dict
"""

import os
import time
import platform
import base64
import io
import subprocess
import shutil
from typing import Optional, Tuple

OS = platform.system()

# ── Safe import ────────────────────────────────────────────────────────────

def _pg():
    """Get pyautogui, raise RuntimeError with install hint if missing."""
    try:
        import pyautogui
        pyautogui.FAILSAFE = True   # Move mouse to top-left corner to abort
        pyautogui.PAUSE = 0.05      # Small delay between actions (natural feel)
        return pyautogui
    except ImportError:
        raise RuntimeError(
            "pyautogui not installed.\n"
            "Run:  pip install pyautogui pyperclip pygetwindow\n"
            "Linux also needs:  pip install python3-xlib"
        )


# ══════════════════════════════════════════════════════════════════════════════
#  KEYBOARD SERVICE
# ══════════════════════════════════════════════════════════════════════════════

class KeyboardController:
    """Types text and sends keystrokes to whatever window is focused."""

    CHAR_INTERVAL = 0.02   # delay between chars (feels natural, not robotic)
    SAFE_DELAY    = 0.4    # wait before typing (user can focus target window)

    def is_available(self) -> bool:
        try:
            import pyautogui
            return True
        except ImportError:
            return False

    def type_text(self, text: str, delay_before: float = 1.5) -> dict:
        """
        Type text at the current cursor position.
        delay_before: seconds to wait (so user can click the target window).
        For text >100 chars, uses clipboard paste for speed and reliability.
        """
        if not text:
            return {"success": False, "message": "No text provided"}
        try:
            pg = _pg()
            time.sleep(delay_before)
            if len(text) > 100:
                return self._clipboard_paste(text)
            pg.typewrite(text, interval=self.CHAR_INTERVAL)
            print(f"[Keyboard] Typed {len(text)} chars")
            return {"success": True, "chars": len(text), "method": "typewrite"}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def _clipboard_paste(self, text: str) -> dict:
        """Copy to clipboard and Ctrl+V — fast for long text."""
        try:
            # Try pyperclip first
            import pyperclip
            pyperclip.copy(text)
        except ImportError:
            # Fallback per-platform
            try:
                if OS == "Windows":
                    subprocess.run("clip", input=text.encode("utf-16"), shell=True, check=True)
                elif OS == "Darwin":
                    subprocess.run(["pbcopy"], input=text.encode(), check=True)
                else:
                    subprocess.run(["xclip", "-selection", "clipboard"], input=text.encode(), check=True)
            except Exception as e:
                return {"success": False, "message": f"Clipboard copy failed: {e}"}

        try:
            pg = _pg()
            time.sleep(0.3)
            if OS == "Darwin":
                pg.hotkey("command", "v")
            else:
                pg.hotkey("ctrl", "v")
            print(f"[Keyboard] Pasted {len(text)} chars via clipboard")
            return {"success": True, "chars": len(text), "method": "clipboard_paste"}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def press_key(self, key: str) -> dict:
        """Press a single named key: enter, tab, backspace, escape, space, up, down, etc."""
        try:
            pg = _pg()
            pg.press(key.lower())
            return {"success": True, "key": key}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def hotkey(self, *keys) -> dict:
        """Press a key combination. E.g. hotkey('ctrl', 'c') for copy."""
        try:
            pg = _pg()
            pg.hotkey(*[k.lower() for k in keys])
            return {"success": True, "keys": list(keys)}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def get_status(self) -> dict:
        ok = self.is_available()
        clip_ok = False
        try:
            import pyperclip
            clip_ok = True
        except ImportError:
            pass
        return {
            "keyboard_available": ok,
            "clipboard_available": clip_ok,
            "platform": OS,
            "install_cmd": "pip install pyautogui pyperclip pygetwindow" if not ok else "installed"
        }


# ══════════════════════════════════════════════════════════════════════════════
#  MOUSE SERVICE
# ══════════════════════════════════════════════════════════════════════════════

class MouseController:
    """Controls the mouse cursor — move, click, scroll, drag."""

    MOVE_DURATION = 0.3   # seconds for smooth mouse movement

    def is_available(self) -> bool:
        try:
            import pyautogui
            return True
        except ImportError:
            return False

    def get_screen_size(self) -> dict:
        try:
            pg = _pg()
            w, h = pg.size()
            return {"success": True, "width": w, "height": h}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def get_position(self) -> dict:
        try:
            pg = _pg()
            x, y = pg.position()
            return {"success": True, "x": x, "y": y}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def move(self, x: int, y: int, duration: float = 0.3) -> dict:
        """Move mouse to (x, y) smoothly."""
        try:
            pg = _pg()
            pg.moveTo(x, y, duration=duration)
            return {"success": True, "x": x, "y": y}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def click(self, x: Optional[int] = None, y: Optional[int] = None,
              button: str = "left") -> dict:
        """Click at (x, y). If x/y omitted, click at current cursor position."""
        try:
            pg = _pg()
            if x is not None and y is not None:
                pg.click(x, y, button=button)
            else:
                pg.click(button=button)
            return {"success": True, "x": x, "y": y, "button": button}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def double_click(self, x: Optional[int] = None, y: Optional[int] = None) -> dict:
        """Double-click at (x, y) or current position."""
        try:
            pg = _pg()
            if x is not None and y is not None:
                pg.doubleClick(x, y)
            else:
                pg.doubleClick()
            return {"success": True, "x": x, "y": y}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def right_click(self, x: Optional[int] = None, y: Optional[int] = None) -> dict:
        """Right-click at (x, y) or current position."""
        return self.click(x, y, button="right")

    def drag(self, x1: int, y1: int, x2: int, y2: int, duration: float = 0.5) -> dict:
        """Click and drag from (x1,y1) to (x2,y2)."""
        try:
            pg = _pg()
            pg.moveTo(x1, y1, duration=0.2)
            pg.dragTo(x2, y2, duration=duration, button="left")
            return {"success": True, "from": [x1, y1], "to": [x2, y2]}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def scroll(self, x: Optional[int] = None, y: Optional[int] = None,
               amount: int = 3) -> dict:
        """
        Scroll the mouse wheel. Positive amount = scroll up, negative = scroll down.
        If x/y provided, move there first.
        """
        try:
            pg = _pg()
            if x is not None and y is not None:
                pg.moveTo(x, y, duration=0.2)
            pg.scroll(amount)
            return {"success": True, "amount": amount}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def move_relative(self, dx: int, dy: int) -> dict:
        """Move mouse relative to current position."""
        try:
            pg = _pg()
            pg.moveRel(dx, dy)
            return {"success": True, "dx": dx, "dy": dy}
        except Exception as e:
            return {"success": False, "message": str(e)}


# ══════════════════════════════════════════════════════════════════════════════
#  SCREEN SERVICE
# ══════════════════════════════════════════════════════════════════════════════

class ScreenController:
    """Screenshot and screen reading."""

    def is_available(self) -> bool:
        try:
            import pyautogui
            return True
        except ImportError:
            return False

    def screenshot(self, save_path: Optional[str] = None, as_base64: bool = True) -> dict:
        """
        Take a screenshot.
        Returns base64 image string (for frontend display) and optionally saves to disk.
        """
        try:
            pg = _pg()
            img = pg.screenshot()

            result = {"success": True}

            if save_path:
                img.save(save_path)
                result["saved_to"] = save_path

            if as_base64:
                buf = io.BytesIO()
                img.save(buf, format="PNG")
                result["image_b64"] = base64.b64encode(buf.getvalue()).decode()
                result["width"] = img.width
                result["height"] = img.height

            print(f"[Screen] Screenshot taken ({img.width}×{img.height})")
            return result

        except Exception as e:
            return {"success": False, "message": str(e)}

    def screenshot_region(self, x: int, y: int, w: int, h: int) -> dict:
        """Screenshot a specific region of the screen."""
        try:
            pg = _pg()
            img = pg.screenshot(region=(x, y, w, h))
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            b64 = base64.b64encode(buf.getvalue()).decode()
            return {"success": True, "image_b64": b64, "region": [x, y, w, h]}
        except Exception as e:
            return {"success": False, "message": str(e)}


# ══════════════════════════════════════════════════════════════════════════════
#  GLOBAL SINGLETONS
# ══════════════════════════════════════════════════════════════════════════════

keyboard_ctrl = KeyboardController()
mouse_ctrl    = MouseController()
screen_ctrl   = ScreenController()


def desktop_status() -> dict:
    """Single status check for all desktop control features."""
    available = keyboard_ctrl.is_available()
    size = mouse_ctrl.get_screen_size() if available else {}
    return {
        "available": available,
        "keyboard": keyboard_ctrl.get_status(),
        "screen": size,
        "platform": OS,
        "install_cmd": "pip install pyautogui pyperclip pygetwindow" if not available else "installed"
    }
