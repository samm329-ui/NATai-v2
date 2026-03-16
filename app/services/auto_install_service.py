"""
Auto-Install Service — N.A.T. AI Assistant
==========================================
Automatically downloads required tools (NirCmd) and supports Android control via ADB.
"""
import os
import sys
import platform
import subprocess
import urllib.request
import zipfile
import shutil
from typing import Optional, Dict, Any

OS = platform.system()


class AutoInstaller:
    """
    Automatically downloads and installs required tools.
    """
    
    def __init__(self):
        self.nircmd_path = None
        self._find_nircmd()
    
    def _find_nircmd(self):
        """Check if NirCmd is already installed."""
        possible_paths = [
            os.path.expandvars(r"%LOCALAPPDATA%\NATai\Tools\nircmd.exe"),
            r"C:\Program Files\nircmd.exe",
            r"C:\Program Files (x86)\nircmd.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\nircmd.exe"),
            os.path.expandvars(r"%USERPROFILE%\Downloads\nircmd.exe"),
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                self.nircmd_path = path
                print(f"[AutoInstall] Found NirCmd at: {path}")
                return
        
        # Check in PATH
        try:
            result = subprocess.run(["where", "nircmd"], capture_output=True, text=True)
            if result.returncode == 0:
                self.nircmd_path = result.stdout.strip().split('\n')[0]
                print(f"[AutoInstall] Found NirCmd in PATH: {self.nircmd_path}")
                return
        except:
            pass
        
        self.nircmd_path = None
    
    def is_nircmd_available(self) -> bool:
        """Check if NirCmd is available."""
        return self.nircmd_path is not None
    
    def _add_to_path(self, directory: str):
        """Add directory to user PATH."""
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Environment", 0, winreg.KEY_WRITE)
            current_path, _ = winreg.QueryValueEx(key, "Path")
            if directory.lower() not in current_path.lower():
                new_path = current_path + ";" + directory
                winreg.SetValueEx(key, "Path", 0, winreg.REG_EXPAND_SZ, new_path)
                print(f"[AutoInstall] Added {directory} to PATH")
            winreg.CloseKey(key)
        except Exception as e:
            print(f"[AutoInstall] Could not add to PATH: {e}")
    
    def download_nircmd(self) -> Dict[str, Any]:
        """
        Automatically download and install NirCmd.
        NirCmd is a free utility from nirsoft.net for system control without admin.
        """
        print("[AutoInstall] Downloading NirCmd...")
        
        # NirSoft download URL
        nircmd_url = "https://www.nirsoft.net/utils/nircmd.zip"
        
        # Download location
        download_dir = os.path.expandvars(r"%LOCALAPPDATA%\Temp")
        os.makedirs(download_dir, exist_ok=True)
        
        zip_path = os.path.join(download_dir, "nircmd.zip")
        extract_dir = download_dir
        
        try:
            # Download the zip file
            print("[AutoInstall] Downloading from nirsoft.net...")
            urllib.request.urlretrieve(nircmd_url, zip_path)
            print("[AutoInstall] Download complete!")
            
            # Extract
            print("[AutoInstall] Extracting...")
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(extract_dir)
            
            # Find the extracted nircmd.exe
            nircmd_src = os.path.join(extract_dir, "nircmd.exe")
            
            if not os.path.exists(nircmd_src):
                # Try alternative filename
                for f in os.listdir(extract_dir):
                    if f.lower() == "nircmd.exe":
                        nircmd_src = os.path.join(extract_dir, f)
                        break
            
            if os.path.exists(nircmd_src):
                # Install to user-writable location first (AppData)
                install_dir = os.path.expandvars(r"%LOCALAPPDATA%\NATai\Tools")
                os.makedirs(install_dir, exist_ok=True)
                
                self.nircmd_path = os.path.join(install_dir, "nircmd.exe")
                shutil.copy2(nircmd_src, self.nircmd_path)
                
                # Also add to PATH for easy access
                self._add_to_path(install_dir)
                
                # Clean up zip
                try:
                    os.remove(zip_path)
                except:
                    pass
                
                print(f"[AutoInstall] NirCmd installed to: {self.nircmd_path}")
                return {"success": True, "path": self.nircmd_path}
            else:
                return {"success": False, "message": "Could not find nircmd.exe after extraction"}
                
        except Exception as e:
            return {"success": False, "message": f"Download failed: {str(e)}"}
    
    def ensure_nircmd(self) -> str:
        """Ensure NirCmd is available, download if not."""
        if self.nircmd_path and os.path.exists(self.nircmd_path):
            return self.nircmd_path
        
        result = self.download_nircmd()
        if result.get("success"):
            return result.get("path", "")
        
        return ""
    
    def get_nircmd_path(self) -> Optional[str]:
        """Get the NirCmd path."""
        return self.nircmd_path


# ==================== ANDROID CONTROL ====================

class AndroidController:
    """
    Controls Android devices via ADB (Android Debug Bridge).
    Works on Windows, Mac, Linux.
    Requires: ADB installed on PC and USB debugging enabled on Android.
    """
    
    def __init__(self):
        self._adb_available = None
        self._check_adb()
    
    def _check_adb(self):
        """Check if ADB is available."""
        try:
            result = subprocess.run(["adb", "version"], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                self._adb_available = True
                print(f"[Android] ADB available: {result.stdout.split()[4]}")
            else:
                self._adb_available = False
        except FileNotFoundError:
            self._adb_available = False
        except Exception as e:
            self._adb_available = False
            print(f"[Android] ADB check failed: {e}")
    
    def is_available(self) -> bool:
        """Check if Android control is available."""
        return self._adb_available is True
    
    def get_devices(self) -> Dict[str, Any]:
        """Get list of connected Android devices."""
        if not self._adb_available:
            # Try to find ADB
            return {"success": False, "message": "ADB not found. Install Android SDK Platform Tools."}
        
        try:
            result = subprocess.run(["adb", "devices"], capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')[1:]
                devices = []
                for line in lines:
                    if line.strip():
                        parts = line.split()
                        if len(parts) >= 2:
                            devices.append({"id": parts[0], "status": parts[1]})
                return {"success": True, "devices": devices}
        except Exception as e:
            return {"success": False, "message": str(e)}
        
        return {"success": False, "message": "No devices found"}
    
    def shell(self, command: str, device_id: str = "") -> Dict[str, Any]:
        """Execute shell command on Android device."""
        if not self._adb_available:
            return {"success": False, "message": "ADB not available"}
        
        cmd = ["adb"]
        if device_id:
            cmd.extend(["-s", device_id])
        cmd.extend(["shell", command])
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            return {
                "success": result.returncode == 0,
                "output": result.stdout,
                "error": result.stderr
            }
        except Exception as e:
            return {"success": False, "message": str(e)}
    
    def get_screen_size(self, device_id: str = "") -> Dict[str, Any]:
        """Get Android screen size."""
        result = self.shell("wm size", device_id)
        if result.get("success"):
            output = result.get("output", "")
            # Parse "Physical size: 1080x1920"
            if "x" in output:
                size = output.split(":")[-1].strip()
                w, h = size.split("x")
                return {"success": True, "width": int(w), "height": int(h)}
        return {"success": False, "message": "Could not get screen size"}
    
    def tap(self, x: int, y: int, device_id: str = "") -> Dict[str, Any]:
        """Tap at coordinates."""
        return self.shell(f"input tap {x} {y}", device_id)
    
    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration: int = 300, device_id: str = "") -> Dict[str, Any]:
        """Swipe from (x1,y1) to (x2,y2)."""
        return self.shell(f"input swipe {x1} {y1} {x2} {y2} {duration}", device_id)
    
    def type_text(self, text: str, device_id: str = "") -> Dict[str, Any]:
        """Type text on Android."""
        # Escape special characters
        text = text.replace(" ", "%s")
        return self.shell(f"input text {text}", device_id)
    
    def press_key(self, key: str, device_id: str = "") -> Dict[str, Any]:
        """Press a key (home, back, volume_up, etc.)."""
        key_map = {
            "home": "KEYCODE_HOME",
            "back": "KEYCODE_BACK",
            "power": "KEYCODE_POWER",
            "volume_up": "KEYCODE_VOLUME_UP",
            "volume_down": "KEYCODE_VOLUME_DOWN",
            "mute": "KEYCODE_VOLUME_MUTE",
            "up": "KEYCODE_DPAD_UP",
            "down": "KEYCODE_DPAD_DOWN",
            "left": "KEYCODE_DPAD_LEFT",
            "right": "KEYCODE_DPAD_RIGHT",
            "enter": "KEYCODE_ENTER",
            "delete": "KEYCODE_DEL",
        }
        
        keycode = key_map.get(key.lower(), f"KEYCODE_{key.upper()}")
        return self.shell(f"input keyevent {keycode}", device_id)
    
    def open_app(self, package_name: str, device_id: str = "") -> Dict[str, Any]:
        """Open an app by package name."""
        return self.shell(f"monkey -p {package_name} -c android.intent.category.LAUNCHER 1", device_id)
    
    def get_volume(self, device_id: str = "") -> Dict[str, Any]:
        """Get current volume level."""
        result = self.shell("media volume --get", device_id)
        # Parse output
        return {"success": True, "volume": 50, "message": "Volume check not fully supported via ADB"}
    
    def set_volume(self, level: int, device_id: str = "") -> Dict[str, Any]:
        """Set volume (0-100)."""
        # ADB can only set stream volumes
        return self.shell(f"media volume --set {level}", device_id)
    
    def take_screenshot(self, save_path: str = "", device_id: str = "") -> Dict[str, Any]:
        """Take screenshot on Android."""
        device_path = "/sdcard/screenshot.png"
        result = self.shell(f"screencap -p {device_path}", device_id)
        
        if result.get("success") and save_path:
            # Pull the screenshot to PC
            pull_cmd = ["adb"]
            if device_id:
                pull_cmd.extend(["-s", device_id])
            pull_cmd.extend(["pull", device_path, save_path])
            
            try:
                subprocess.run(pull_cmd, capture_output=True, timeout=10)
                return {"success": True, "path": save_path}
            except Exception as e:
                return {"success": False, "message": str(e)}
        
        return result
    
    def install_adb_instructions(self) -> str:
        """Return instructions for installing ADB."""
        return """
To control your Android phone from NATasha:

1. Enable Developer Options on your Android:
   - Go to Settings > About Phone
   - Tap "Build Number" 7 times
   
2. Enable USB Debugging:
   - Settings > Developer Options > USB Debugging
   - Enable it
   
3. Install ADB on your PC:
   - Download Android SDK Platform Tools
   - Or: `winget install Google.PlatformTools`
   
4. Connect your phone via USB
   - Authorize the PC on your phone
   
5. NATasha will detect your phone automatically!
"""


# Global singletons
auto_installer = AutoInstaller()
android_controller = AndroidController()
