"""
Browser Detection Service — N.A.T. AI Assistant
════════════════════════════════════════════════
Detects which browser opened the Natasha tab from the User-Agent header.
When Natasha opens URLs or does searches, she uses THAT specific browser —
no more "choose your browser" dialog popping up.

Supported: Chrome, Firefox, Edge, Brave, Opera, Vivaldi, Safari
Falls back to webbrowser.open() if browser not detected or not found.
"""

import os
import re
import shutil
import subprocess
import platform
import webbrowser
from typing import Optional

OS = platform.system()

# ── Executable paths per browser per OS ───────────────────────────────────

_WIN_PATHS = {
    "chrome": [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
    ],
    "firefox": [
        r"C:\Program Files\Mozilla Firefox\firefox.exe",
        r"C:\Program Files (x86)\Mozilla Firefox\firefox.exe",
    ],
    "edge": [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\Application\msedge.exe"),
    ],
    "brave": [
        os.path.expandvars(r"%LOCALAPPDATA%\BraveSoftware\Brave-Browser\Application\brave.exe"),
        r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
    ],
    "opera": [
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Opera\opera.exe"),
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Opera GX\launcher.exe"),
    ],
    "vivaldi": [
        os.path.expandvars(r"%LOCALAPPDATA%\Vivaldi\Application\vivaldi.exe"),
    ],
}

_MAC_APPS = {
    "chrome":  "Google Chrome",
    "firefox": "Firefox",
    "edge":    "Microsoft Edge",
    "brave":   "Brave Browser",
    "opera":   "Opera",
    "safari":  "Safari",
    "vivaldi": "Vivaldi",
}

_LINUX_BINS = {
    "chrome":  ["google-chrome-stable", "google-chrome", "chromium-browser", "chromium"],
    "firefox": ["firefox"],
    "edge":    ["microsoft-edge-stable", "microsoft-edge"],
    "brave":   ["brave-browser", "brave"],
    "opera":   ["opera"],
}

_WIN_PATH_BINS = {"chrome": "chrome", "firefox": "firefox", "edge": "msedge",
                  "brave": "brave", "opera": "opera", "vivaldi": "vivaldi"}


def detect_browser(user_agent: str) -> str:
    """Parse User-Agent string → browser key ('chrome', 'firefox', 'edge', etc.)"""
    if not user_agent:
        return "unknown"
    ua = user_agent.lower()
    # Order matters — Edge contains "Chrome", check specific ones first
    if "edg/" in ua or "edghtml" in ua:
        return "edge"
    if "opr/" in ua or "opera" in ua:
        return "opera"
    if "vivaldi" in ua:
        return "vivaldi"
    if "brave" in ua:
        return "brave"
    if "firefox" in ua:
        return "firefox"
    if "chrome" in ua or "crios" in ua:
        return "chrome"
    if "safari" in ua:
        return "safari"
    return "unknown"


def _find_exe_windows(browser: str) -> Optional[str]:
    paths = _WIN_PATHS.get(browser, [])
    for p in paths:
        expanded = os.path.expandvars(p)
        if os.path.exists(expanded):
            return expanded
    # Try PATH
    bin_name = _WIN_PATH_BINS.get(browser)
    if bin_name:
        found = shutil.which(bin_name)
        if found:
            return found
    return None


def open_url_in_browser(url: str, browser: str = "unknown") -> dict:
    """
    Open url in the specified browser.
    If browser unknown or not found, falls back to system default.
    """
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    print(f"[BrowserDetect] Opening {url!r} in {browser!r}")

    try:
        if OS == "Windows":
            exe = _find_exe_windows(browser) if browser != "unknown" else None
            if exe:
                subprocess.Popen([exe, url])
                return {"success": True, "url": url, "browser": browser, "method": "direct_exe"}
            # Fall back: shell 'start' respects default browser
            subprocess.Popen(f'start "" "{url}"', shell=True)
            return {"success": True, "url": url, "browser": "default", "method": "shell_start"}

        elif OS == "Darwin":
            app = _MAC_APPS.get(browser)
            if app:
                subprocess.Popen(["open", "-a", app, url])
                return {"success": True, "url": url, "browser": browser, "method": "open_a"}
            subprocess.Popen(["open", url])
            return {"success": True, "url": url, "browser": "default", "method": "open"}

        else:  # Linux
            bins = _LINUX_BINS.get(browser, [])
            for b in bins:
                exe = shutil.which(b)
                if exe:
                    subprocess.Popen([exe, url])
                    return {"success": True, "url": url, "browser": browser, "method": "linux_bin"}
            subprocess.Popen(["xdg-open", url])
            return {"success": True, "url": url, "browser": "default", "method": "xdg_open"}

    except Exception as e:
        try:
            webbrowser.open(url)
            return {"success": True, "url": url, "browser": "system_fallback", "method": "webbrowser"}
        except Exception as e2:
            return {"success": False, "url": url, "message": str(e2)}


# ── Session store: remembers browser per client IP ────────────────────────

class _BrowserStore:
    def __init__(self):
        self._map: dict[str, str] = {}
        self.current = "unknown"

    def register(self, ip: str, user_agent: str) -> str:
        browser = detect_browser(user_agent)
        self._map[ip] = browser
        self.current = browser
        print(f"[BrowserDetect] {ip} → {browser}")
        return browser

    def get(self, ip: str) -> str:
        return self._map.get(ip, self.current)


browser_store = _BrowserStore()
