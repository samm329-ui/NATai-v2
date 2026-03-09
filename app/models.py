"""
Pydantic Models for N.A.T. AI Assistant
Defines the strict data structures for API requests and responses.
"""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime

class ChatType:
    GENERAL = "general"
    REALTIME = "realtime"
    INTELLIGENCE = "intelligence"

class Message(BaseModel):
    role: str
    content: str
    timestamp: datetime = Field(default_factory=datetime.now)

class ChatSession(BaseModel):
    session_id: str
    chat_type: str
    messages: List[Message] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    chat_type: str = "general"
    use_search: bool = False
    tts: bool = False  # Added for Video 2: Tells the server to generate TTS audio

class ChatResponse(BaseModel):
    response: str
    session_id: str
    chat_type: str
    sources: Optional[List[Dict[str, str]]] = None
    timestamp: datetime = Field(default_factory=datetime.now)

class VectorStoreStatus(BaseModel):
    loaded: bool
    document_count: int
    sources: List[str] = Field(default_factory=list)

class SystemStatus(BaseModel):
    vector_store: VectorStoreStatus
    groq_available: bool
    search_available: bool
    model_name: str = "llama-3.3-70b-versatile"
    active_sessions: int = 0

class IntelligenceRequest(BaseModel):
    query: str
    force_refresh: bool = False

class ClassificationResult(BaseModel):
    entity_type: str
    name: str
    industry: str
    sector: str
    country: str
    is_listed: bool
    stock_symbol: Optional[str] = None
    exchange: Optional[str] = None
    description: str

class IntelligenceResponse(BaseModel):
    success: bool
    query: str
    entity_name: str
    entity_type: str
    classification: Dict[str, Any]
    structured_data: Dict[str, Any]
    response: str
    sources_searched: int
    cached: bool
    timestamp: str
    api_sources_used: List[str] = Field(default_factory=list)

class DetailedSystemStatus(BaseModel):
    name: str = "N.A.T."
    full_name: str = "Natasha"
    version: str = "2.0.0"
    status: str
    uptime_start: str
    current_time: str
    model: str
    groq_api: str
    tavily_search: str
    alpha_vantage: str
    fmp_data: str
    news_api: str
    google_search: str
    vector_store: Dict[str, Any]
    cache_status: Dict[str, Any]
    active_sessions: int
    endpoints: Dict[str, str]
    api_sources_configured: List[str]

class LearningDataItem(BaseModel):
    filename: str
    content: str
    char_count: int