"""
Working Context Service — N.A.T. AI Assistant
============================================
Persists working state between commands - like human memory.
Solves path continuity issues: "open that folder" → knows which folder.
"""
import json
import os
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime

from config import config


class WorkingContext:
    """
    Maintains working state across commands for context-aware execution.
    This is the core solution for path/continuity issues.
    """
    
    def __init__(self):
        self.context_file = config.BASE_DIR / "database" / "working_context.json"
        self._context: Dict[str, Any] = {
            "current_directory": "",
            "last_created_path": "",
            "last_opened_path": "",
            "last_closed_path": "",
            "last_app_opened": "",
            "last_app_closed": "",
            "last_file_path": "",
            "last_browser_url": "",
            "last_search_query": "",
            "last_operation": "",
            "recent_paths": [],
            "pending_operations": [],
            "screen_size": {"width": 1920, "height": 1080},
            "last_mouse_position": {"x": 0, "y": 0},
            "active_window_title": "",
            "user_home": str(Path.home()),
        }
        self._load_context()
    
    def _load_context(self):
        """Load context from file if exists."""
        if self.context_file.exists():
            try:
                with open(self.context_file, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    self._context.update(loaded)
                print(f"[Context] Loaded working context")
            except Exception as e:
                print(f"[Context] Error loading: {e}")
    
    def _save_context(self):
        """Persist context to file."""
        try:
            os.makedirs(self.context_file.parent, exist_ok=True)
            self._context["updated_at"] = datetime.now().isoformat()
            with open(self.context_file, "w", encoding="utf-8") as f:
                json.dump(self._context, f, indent=2)
        except Exception as e:
            print(f"[Context] Error saving: {e}")
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get a context value."""
        return self._context.get(key, default)
    
    def set(self, key: str, value: Any):
        """Set a context value and persist."""
        self._context[key] = value
        self._save_context()
    
    def add_recent_path(self, path: str):
        """Add path to recent paths list."""
        if path and path not in self._context["recent_paths"]:
            self._context["recent_paths"].insert(0, path)
            # Keep only last 20 paths
            self._context["recent_paths"] = self._context["recent_paths"][:20]
            self._save_context()
    
    def resolve_path(self, path_hint: str) -> str:
        """
        Smart path resolution - handles relative references.
        
        Examples:
        - "that folder" → last_created_path or current_directory
        - "it" → last operation target
        - "there" → current_directory
        - "the file" → last_file_path
        - "Desktop" → C:/Users/.../Desktop
        """
        path_hint = path_hint.lower().strip()
        
        # Handle pronouns and references
        if path_hint in ["that", "that folder", "it", "the folder", "there"]:
            if self._context["last_created_path"]:
                return self._context["last_created_path"]
            elif self._context["last_opened_path"]:
                return self._context["last_opened_path"]
            elif self._context["current_directory"]:
                return self._context["current_directory"]
        
        if path_hint in ["this", "this folder", "current", "here"]:
            return self._context["current_directory"] or os.getcwd()
        
        if path_hint in ["the file", "that file"]:
            return self._context["last_file_path"] or ""
        
        # Handle special folders
        home = Path.home()
        special_folders = {
            "desktop": home / "Desktop",
            "downloads": home / "Downloads",
            "documents": home / "Documents",
            "pictures": home / "Pictures",
            "music": home / "Music",
            "videos": home / "Videos",
            "home": home,
            "my pc": home,
            "this pc": home,
        }
        
        if path_hint in special_folders:
            return str(special_folders[path_hint])
        
        # Check if it's an absolute path
        if os.path.isabs(path_hint):
            return os.path.expandvars(os.path.expanduser(path_hint))
        
        # Resolve relative to current directory or home
        base = self._context["current_directory"] or str(home)
        resolved = os.path.join(base, path_hint)
        return os.path.expandvars(os.path.expanduser(resolved))
    
    def update_from_operation(self, operation: str, path: str = "", app: str = "", url: str = ""):
        """Update context after an operation."""
        self._context["last_operation"] = operation
        
        if path:
            self._context["last_opened_path"] = path
            if operation in ["create_folder", "create_file"]:
                self._context["last_created_path"] = path
            if operation == "delete_folder":
                self._context["last_closed_path"] = path
            if operation == "read_file":
                self._context["last_file_path"] = path
            self.add_recent_path(path)
        
        if app:
            if operation == "open_app":
                self._context["last_app_opened"] = app
            elif operation == "close_app":
                self._context["last_app_closed"] = app
        
        if url:
            self._context["last_browser_url"] = url
        
        self._save_context()
    
    def get_current_directory(self) -> str:
        """Get current working directory."""
        return self._context.get("current_directory") or str(Path.home())
    
    def set_current_directory(self, path: str):
        """Set current working directory."""
        if os.path.isdir(path):
            self._context["current_directory"] = os.path.abspath(path)
            self._save_context()
    
    def queue_operation(self, operation: Dict):
        """Add operation to pending queue for sequential execution."""
        self._context["pending_operations"].append(operation)
        self._save_context()
    
    def get_next_operation(self) -> Optional[Dict]:
        """Get next pending operation."""
        ops = self._context.get("pending_operations", [])
        if ops:
            return ops[0]
        return None
    
    def complete_operation(self):
        """Mark current operation as complete."""
        ops = self._context.get("pending_operations", [])
        if ops:
            ops.pop(0)
            self._context["pending_operations"] = ops
            self._save_context()
    
    def clear_pending_operations(self):
        """Clear all pending operations."""
        self._context["pending_operations"] = []
        self._save_context()
    
    def get_summary(self) -> str:
        """Get human-readable context summary."""
        parts = []
        if self._context.get("current_directory"):
            parts.append(f"Current: {self._context['current_directory']}")
        if self._context.get("last_created_path"):
            parts.append(f"Last created: {self._context['last_created_path']}")
        if self._context.get("last_app_opened"):
            parts.append(f"Last app: {self._context['last_app_opened']}")
        return " | ".join(parts) if parts else "No active context"
    
    def to_prompt_context(self) -> str:
        """Format context for LLM prompt."""
        ctx = []
        if self._context.get("current_directory"):
            ctx.append(f"CURRENT FOLDER: {self._context['current_directory']}")
        if self._context.get("last_created_path"):
            ctx.append(f"LAST CREATED: {self._context['last_created_path']}")
        if self._context.get("last_opened_path"):
            ctx.append(f"LAST OPENED: {self._context['last_opened_path']}")
        if self._context.get("last_app_opened"):
            ctx.append(f"LAST APP: {self._context['last_app_opened']}")
        if self._context.get("last_browser_url"):
            ctx.append(f"BROWSER URL: {self._context['last_browser_url']}")
        
        recent = self._context.get("recent_paths", [])[:5]
        if recent:
            ctx.append(f"RECENT PATHS: {', '.join(recent)}")
        
        return "\n".join(ctx) if ctx else ""


# Global singleton
working_context = WorkingContext()
