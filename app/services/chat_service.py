"""
Chat Service for N.A.T. AI Assistant
Handles chat session persistence, history management, and business logging.
"""
import os
import json
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path

from config import config
from app.models import Message, ChatSession

class ChatService:
    def __init__(self):
        self.sessions: Dict[str, ChatSession] = {}
        # Ensure the chats directory exists on startup
        os.makedirs(config.CHATS_PATH, exist_ok=True)
        
    def create_session(self, chat_type: str = "general", session_id: Optional[str] = None) -> ChatSession:
        """Creates a new session, optionally with a specific ID."""
        if not session_id:
            session_id = str(uuid.uuid4())
            
        session = ChatSession(
            session_id=session_id,
            chat_type=chat_type,
            messages=[],
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        self.sessions[session_id] = session
        print(f"[ChatService] Created new session: {session_id} ({chat_type})")
        return session
    
    def _load_session_from_disk(self, session_id: str) -> Optional[ChatSession]:
        """Attempts to load a saved session from the JSON file."""
        file_path = config.CHATS_PATH / f"{session_id}.json"
        if file_path.exists():
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                
                messages = []
                for msg in data.get("messages", []):
                    # Handle parsing timestamps safely
                    ts = datetime.fromisoformat(msg["timestamp"]) if "timestamp" in msg else datetime.now()
                    messages.append(Message(
                        role=msg["role"],
                        content=msg["content"],
                        timestamp=ts
                    ))
                    
                created_ts = datetime.fromisoformat(data["created_at"]) if "created_at" in data else datetime.now()
                updated_ts = datetime.fromisoformat(data["updated_at"]) if "updated_at" in data else datetime.now()
                
                session = ChatSession(
                    session_id=data["session_id"],
                    chat_type=data.get("chat_type", "general"),
                    messages=messages,
                    created_at=created_ts,
                    updated_at=updated_ts
                )
                self.sessions[session_id] = session
                print(f"[ChatService] Loaded session from disk: {session_id}")
                return session
            except Exception as e:
                print(f"[ChatService] Error loading session {session_id} from disk: {e}")
        return None

    def get_session(self, session_id: str) -> Optional[ChatSession]:
        """Gets a session from memory, or loads it from disk if not in memory."""
        if session_id in self.sessions:
            return self.sessions[session_id]
        return self._load_session_from_disk(session_id)
    
    def get_or_create_session(self, session_id: Optional[str], chat_type: str = "general") -> ChatSession:
        """Gets an existing session or creates a new one."""
        if session_id:
            session = self.get_session(session_id)
            if session:
                return session
            # If a specific ID was requested but doesn't exist anywhere, create it with that ID
            return self.create_session(chat_type, session_id)
        
        # No ID provided, make a brand new one
        return self.create_session(chat_type)
    
    def add_message(self, session_id: str, role: str, content: str) -> Message:
        """Adds a message to the session."""
        session = self.get_session(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")
            
        message = Message(role=role, content=content)
        session.messages.append(message)
        session.updated_at = datetime.now()
        return message
    
    def get_conversation_history(self, session_id: str, limit: int = 15) -> List[Dict[str, str]]:
        """Gets formatted history. Limits to last 15 messages to prevent token overflow."""
        session = self.get_session(session_id)
        if not session:
            return []
            
        recent_messages = session.messages[-limit:] if len(session.messages) > limit else session.messages
        return [{"role": msg.role, "content": msg.content} for msg in recent_messages]
    
    def save_session(self, session_id: str) -> bool:
        """Saves the session to a JSON file on disk."""
        session = self.get_session(session_id)
        if not session:
            return False
            
        try:
            os.makedirs(config.CHATS_PATH, exist_ok=True)
            file_path = config.CHATS_PATH / f"{session_id}.json"
            
            data = {
                "session_id": session.session_id,
                "chat_type": session.chat_type,
                "messages": [
                    {
                        "role": msg.role, 
                        "content": msg.content, 
                        "timestamp": msg.timestamp.isoformat()
                    } for msg in session.messages
                ],
                "created_at": session.created_at.isoformat(),
                "updated_at": session.updated_at.isoformat()
            }
            
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
                
            return True
        except Exception as e:
            print(f"[ChatService] Error saving session: {e}")
            return False
    
    def list_sessions(self) -> List[Dict]:
        """Lists all saved sessions."""
        sessions = []
        if not config.CHATS_PATH.exists():
            return sessions
            
        for file_path in config.CHATS_PATH.glob("*.json"):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    sessions.append({
                        "session_id": data.get("session_id", file_path.stem),
                        "chat_type": data.get("chat_type", "general"),
                        "message_count": len(data.get("messages", [])),
                        "created_at": data.get("created_at", ""),
                        "updated_at": data.get("updated_at", "")
                    })
            except Exception as e:
                print(f"[ChatService] Error reading {file_path}: {e}")
                
        # Sort so newest is first
        return sorted(sessions, key=lambda x: x.get("updated_at", ""), reverse=True)
    
    def delete_session(self, session_id: str) -> bool:
        """Deletes a session from memory and disk."""
        if session_id in self.sessions:
            del self.sessions[session_id]
            
        file_path = config.CHATS_PATH / f"{session_id}.json"
        if file_path.exists():
            file_path.unlink()
            return True
            
        return False

chat_service = ChatService()