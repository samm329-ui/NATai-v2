"""
System Control Service — N.A.T. AI Assistant
============================================
Controls Windows system settings: brightness, volume, Wi-Fi, airplane mode.
Optimized for NO ADMIN privileges required.
Includes auto-download of NirCmd if not present.
"""
import os
import platform
import subprocess
import time
import shutil
from typing import Optional, Dict, Any

OS = platform.system()


class SystemController:
    """
    Controls Windows system settings without admin privileges.
    Works on Windows 10/11.
    """
    
    def __init__(self):
        self._nircmd_path = None
        self._ensure_nircmd()
    
    def _ensure_nircmd(self):
        """Ensure NirCmd is available, auto-download if needed."""
        from app.services.auto_install_service import auto_installer
        
        # Check if already available
        if auto_installer.is_nircmd_available():
            self._nircmd_path = auto_installer.get_nircmd_path()
            print(f"[SystemControl] NirCmd available: {self._nircmd_path}")
            return
        
        # Try to download
        print("[SystemControl] NirCmd not found. Downloading automatically...")
        result = auto_installer.download_nircmd()
        
        if result.get("success"):
            self._nircmd_path = result.get("path")
            print(f"[SystemControl] NirCmd downloaded: {self._nircmd_path}")
        else:
            print(f"[SystemControl] Could not download NirCmd: {result.get('message')}")
    
    def _check_nircmd(self) -> bool:
        """Check if NirCmd is available."""
        return self._nircmd_path is not None and os.path.exists(self._nircmd_path)
    
    def is_available(self) -> bool:
        """Check if system control is available."""
        return OS == "Windows"
    
    # ==================== VOLUME CONTROL ====================
    
    def get_volume(self) -> Dict[str, Any]:
        """Get current volume level (0-100)."""
        try:
            result = subprocess.run(
                ['powershell', '-Command', 
                 'Get-AudioDevice -PlaybackVolume | Select-Object -ExpandProperty Volume'],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0 and result.stdout.strip():
                vol = int(float(result.stdout.strip()) * 100)
                return {"success": True, "volume": vol}
        except:
            pass
        
        # Try alternative
        try:
            result = subprocess.run(
                ['powershell', '-Command', 
                 '(Get-AudioDevice | Where-Object {$_.Role -eq "Render"}).Volume'],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0 and result.stdout.strip():
                vol = int(float(result.stdout.strip()) * 100)
                return {"success": True, "volume": vol}
        except:
            pass
            
        return {"success": False, "message": "Volume control unavailable"}
    
    def set_volume(self, level: int) -> Dict[str, Any]:
        """
        Set volume level (0-100). No admin required.
        Uses NirCmd (auto-downloaded) first, then PowerShell.
        """
        level = max(0, min(100, level))
        
        # Ensure we have NirCmd path
        if not self._nircmd_path or not os.path.exists(self._nircmd_path):
            from app.services.auto_install_service import auto_installer
            auto_installer.ensure_nircmd()
            self._nircmd_path = auto_installer.get_nircmd_path()
        
        # Method 1: Use NirCmd if available
        if self._nircmd_path and os.path.exists(self._nircmd_path):
            try:
                subprocess.run([self._nircmd_path, "setsysvolume", str(level * 65535 // 100)], 
                             capture_output=True, timeout=3)
                return {"success": True, "volume": level, "method": "nircmd"}
            except:
                pass
        
        # Method 2: PowerShell AudioDevice module
        try:
            subprocess.run(
                ['powershell', '-Command', 
                 f'Set-AudioDevice -PlaybackVolume {level}'],
                capture_output=True, timeout=5
            )
            return {"success": True, "volume": level, "method": "powershell"}
        except:
            pass
        
        return {"success": False, "message": "Volume control unavailable"}
    
    def mute_volume(self, mute: bool = True) -> Dict[str, Any]:
        """Mute or unmute system volume."""
        # Try NirCmd first
        if self._nircmd_path:
            nircmd = r"C:\Program Files\nircmd.exe"
            if not os.path.exists(nircmd):
                nircmd = r"C:\Program Files (x86)\nircmd.exe"
            try:
                cmd = "mutesysvolume" if mute else "mutesysvolume 0"
                subprocess.run([nircmd, cmd], capture_output=True, timeout=3)
                return {"success": True, "muted": mute, "method": "nircmd"}
            except:
                pass
        
        # PowerShell method
        try:
            state = "1" if mute else "0"
            subprocess.run(
                ['powershell', '-Command', 
                 f'Set-AudioDevice -PlaybackMute {state}'],
                capture_output=True, timeout=5
            )
            return {"success": True, "muted": mute, "method": "powershell"}
        except:
            pass
        
        return {"success": False, "message": "Mute control unavailable"}
    
    def increase_volume(self, amount: int = 10) -> Dict[str, Any]:
        """Increase volume by amount."""
        current = self.get_volume()
        if current.get("success"):
            new_level = min(100, current["volume"] + amount)
            return self.set_volume(new_level)
        return self.set_volume(50)
    
    def decrease_volume(self, amount: int = 10) -> Dict[str, Any]:
        """Decrease volume by amount."""
        current = self.get_volume()
        if current.get("success"):
            new_level = max(0, current["volume"] - amount)
            return self.set_volume(new_level)
        return self.set_volume(50)
    
    # ==================== BRIGHTNESS CONTROL ====================
    
    def get_brightness(self) -> Dict[str, Any]:
        """Get current brightness level (0-100)."""
        # Try NirCmd
        if self._nircmd_path:
            try:
                nircmd = r"C:\Program Files\nircmd.exe"
                if not os.path.exists(nircmd):
                    nircmd = r"C:\Program Files (x86)\nircmd.exe"
                result = subprocess.run([nircmd, "getbrightness"], 
                                     capture_output=True, text=True, timeout=3)
                if result.returncode == 0:
                    # Output is 0-100
                    return {"success": True, "brightness": int(result.stdout.strip())}
            except:
                pass
        
        # WMI method (might need admin)
        try:
            result = subprocess.run(
                ['powershell', '-Command', 
                 '(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightness).CurrentBrightness'],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0 and result.stdout.strip():
                return {"success": True, "brightness": int(result.stdout.strip())}
        except:
            pass
        
        return {"success": False, "message": "Brightness control unavailable"}
    
    def set_brightness(self, level: int) -> Dict[str, Any]:
        """
        Set brightness level (0-100). 
        Uses NirCmd for non-admin control.
        """
        level = max(0, min(100, level))
        
        # Ensure we have NirCmd path
        if not self._nircmd_path or not os.path.exists(self._nircmd_path):
            from app.services.auto_install_service import auto_installer
            auto_installer.ensure_nircmd()
            self._nircmd_path = auto_installer.get_nircmd_path()
        
        # NirCmd method (best - no admin needed)
        if self._nircmd_path and os.path.exists(self._nircmd_path):
            try:
                subprocess.run([self._nircmd_path, "setbrightness", str(level)], 
                             capture_output=True, timeout=3)
                return {"success": True, "brightness": level, "method": "nircmd"}
            except Exception as e:
                pass  # Try other methods
        
        # Alternative: Use Windows Display API via PowerShell
        try:
            # This might require admin, but let's try
            subprocess.run(
                ['powershell', '-Command', 
                 f'(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods).SetBrightness({level},0)'],
                capture_output=True, timeout=5
            )
            return {"success": True, "brightness": level, "method": "wmi"}
        except:
            pass
        
        return {"success": False, 
                "message": "Brightness control unavailable. Install NirCmd from nirsoft.net for non-admin control."}
    
    def increase_brightness(self, amount: int = 10) -> Dict[str, Any]:
        """Increase brightness by amount."""
        current = self.get_brightness()
        if current.get("success"):
            new_level = min(100, current["brightness"] + amount)
            return self.set_brightness(new_level)
        return self.set_brightness(50)
    
    def decrease_brightness(self, amount: int = 10) -> Dict[str, Any]:
        """Decrease brightness by amount."""
        current = self.get_brightness()
        if current.get("success"):
            new_level = max(0, current["brightness"] - amount)
            return self.set_brightness(new_level)
        return self.set_brightness(50)
    
    # ==================== WIFI CONTROL ====================
    
    def get_wifi_status(self) -> Dict[str, Any]:
        """Get Wi-Fi status."""
        try:
            result = subprocess.run(
                ['netsh', 'wlan', 'show', 'interfaces'],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                output = result.stdout.lower()
                connected = "state" in output and "connected" in output
                return {"success": True, "wifi_on": connected}
        except Exception as e:
            return {"success": False, "message": str(e)}
        return {"success": False, "message": "Wi-Fi status unavailable"}
    
    def toggle_wifi(self, enable: bool) -> Dict[str, Any]:
        """Toggle Wi-Fi. Note: Usually requires admin."""
        # This typically needs admin, but we can try
        return {
            "success": False,
            "message": "Wi-Fi toggle requires admin privileges. Use Windows Settings or physical switch."
        }
    
    def get_wifi_networks(self) -> Dict[str, Any]:
        """Get list of available Wi-Fi networks."""
        try:
            result = subprocess.run(
                ['netsh', 'wlan', 'show', 'networks', 'mode=bssid'],
                capture_output=True, text=True, timeout=15
            )
            if result.returncode == 0:
                networks = []
                current_ssid = None
                for line in result.stdout.split('\n'):
                    line = line.strip()
                    if line.startswith("SSID"):
                        current_ssid = line.split(":", 1)[1].strip()
                    elif line.startswith("Authentication") and current_ssid:
                        auth = line.split(":", 1)[1].strip()
                        networks.append({"ssid": current_ssid, "auth": auth})
                        current_ssid = None
                return {"success": True, "networks": networks[:10]}
        except Exception as e:
            return {"success": False, "message": str(e)}
        return {"success": False, "message": "Failed to get networks"}
    
    # ==================== SETTINGS ====================
    
    def open_settings(self, page: str = "") -> Dict[str, Any]:
        """
        Open Windows Settings to a specific page.
        
        Common pages:
        - "" (default) - Main Settings
        - "display" - Display settings
        - "sound" - Sound settings
        - "network" - Network & Internet
        - "bluetooth" - Bluetooth
        - "apps" - Apps
        - "privacy" - Privacy
        - "update" - Windows Update
        """
        settings_uris = {
            "": "ms-settings:",
            "display": "ms-settings:display",
            "sound": "ms-settings:sound",
            "network": "ms-settings:network",
            "wifi": "ms-settings:network-wifi",
            "bluetooth": "ms-settings:bluetooth",
            "apps": "ms-settings:appsfeatures",
            "privacy": "ms-settings:privacy",
            "update": "ms-settings:windowsupdate",
            "battery": "ms-settings:batterysaver",
            "display": "ms-settings:display",
            "notifications": "ms-settings:notifications",
        }
        
        uri = settings_uris.get(page.lower(), f"ms-settings:{page}")
        
        try:
            # Use start command for Windows settings URIs
            subprocess.Popen(f'start "" "{uri}"', shell=True)
            return {"success": True, "opened": page or "Settings"}
        except Exception as e:
            return {"success": False, "message": str(e)}
    
    # ==================== SYSTEM ACTIONS ====================
    
    def open_control_panel(self) -> Dict[str, Any]:
        """Open Control Panel."""
        try:
            subprocess.Popen('start "" control', shell=True)
            return {"success": True}
        except Exception as e:
            return {"success": False, "message": str(e)}
    
    def open_task_manager(self) -> Dict[str, Any]:
        """Open Task Manager."""
        try:
            subprocess.Popen("taskmgr", shell=True)
            return {"success": True}
        except Exception as e:
            return {"success": False, "message": str(e)}
    
    def open_device_manager(self) -> Dict[str, Any]:
        """Open Device Manager."""
        try:
            subprocess.Popen("devmgmt.msc", shell=True)
            return {"success": True}
        except Exception as e:
            return {"success": False, "message": str(e)}
    
    def lock_computer(self) -> Dict[str, Any]:
        """Lock the computer."""
        try:
            subprocess.Popen("rundll32.exe user32.dll,LockWorkStation", shell=True)
            return {"success": True}
        except Exception as e:
            return {"success": False, "message": str(e)}
    
    def sleep_computer(self) -> Dict[str, Any]:
        """Put computer to sleep."""
        try:
            subprocess.Popen("rundll32.exe powrprof.dll,SetSuspendState 0,1,0", shell=True)
            return {"success": True}
        except Exception as e:
            return {"success": False, "message": str(e)}
    
    def shutdown_computer(self, restart: bool = False) -> Dict[str, Any]:
        """Shutdown or restart computer."""
        try:
            cmd = "shutdown /r /t 0" if restart else "shutdown /s /t 0"
            subprocess.Popen(cmd, shell=True)
            return {"success": True, "action": "restart" if restart else "shutdown"}
        except Exception as e:
            return {"success": False, "message": str(e)}
    
    # ==================== APP CONTROL ====================
    
    def close_app(self, app_name: str) -> Dict[str, Any]:
        """Close an application by name."""
        process_map = {
            "brave": "brave.exe",
            "chrome": "chrome.exe", 
            "google chrome": "chrome.exe",
            "firefox": "firefox.exe",
            "microsoft edge": "msedge.exe",
            "edge": "msedge.exe",
            "notepad": "notepad.exe",
            "word": "winword.exe",
            "excel": "excel.exe",
            "powerpoint": "powerpnt.exe",
            "spotify": "spotify.exe",
            "discord": "discord.exe",
            "teams": "Teams.exe",
            "code": "Code.exe",
            "vscode": "Code.exe",
            "terminal": "WindowsTerminal.exe",
            "cmd": "cmd.exe",
            "powershell": "powershell.exe",
        }
        
        exe_name = process_map.get(app_name.lower(), app_name)
        
        try:
            subprocess.run(
                ['taskkill', '/IM', exe_name, '/F'],
                capture_output=True, timeout=5
            )
            return {"success": True, "app": app_name}
        except Exception as e:
            return {"success": False, "message": str(e)}
    
    def open_app(self, app_name: str) -> Dict[str, Any]:
        """Open an application."""
        app_map = {
            "brave": "brave",
            "chrome": "chrome",
            "firefox": "firefox",
            "edge": "msedge",
            "notepad": "notepad",
            "calculator": "calc",
            "cmd": "cmd",
            "terminal": "wt",
            "powershell": "powershell",
            "settings": "ms-settings:",
            "explorer": "explorer",
        }
        
        exe = app_map.get(app_name.lower(), app_name)
        
        # Special handling for settings
        if app_name.lower() == "settings":
            return self.open_settings()
        
        try:
            subprocess.Popen(exe, shell=True)
            return {"success": True, "app": app_name}
        except Exception as e:
            return {"success": False, "message": str(e)}
    
    # ==================== KEYBOARD SHORTCUTS ====================
    
    def send_hotkey(self, *keys) -> Dict[str, Any]:
        """Send a hotkey combination."""
        try:
            import pyautogui
            pyautogui.hotkey(*[k.lower() for k in keys])
            return {"success": True, "keys": list(keys)}
        except Exception as e:
            return {"success": False, "message": str(e)}
    
    def press_key(self, key: str) -> Dict[str, Any]:
        """Press a single key."""
        try:
            import pyautogui
            pyautogui.press(key.lower())
            return {"success": True, "key": key}
        except Exception as e:
            return {"success": False, "message": str(e)}
    
    # ==================== SYSTEM INFO ====================
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get current system status."""
        vol = self.get_volume()
        bright = self.get_brightness()
        wifi = self.get_wifi_status()
        
        return {
            "platform": OS,
            "volume": vol.get("volume", "N/A"),
            "brightness": bright.get("brightness", "N/A"),
            "wifi_on": wifi.get("wifi_on", "N/A"),
            "nircmd_available": self._nircmd_path is not None and os.path.exists(self._nircmd_path),
        }


# Global singleton
system_controller = SystemController()
