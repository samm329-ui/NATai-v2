"""
Configuration Settings for N.A.T. AI Assistant
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from the .env file
load_dotenv()

class Config:
    def __init__(self):
        # 1. Base Paths & Folders
        self.BASE_DIR = Path(__file__).resolve().parent
        self.DATABASE_DIR = self.BASE_DIR / "database"
        self.LEARNING_DATA_PATH = self.DATABASE_DIR / "learning_data"
        self.CHATS_PATH = self.DATABASE_DIR / "chats_data"
        self.VECTOR_STORE_PATH = self.DATABASE_DIR / "vector_store"
        self.MEMORY_PATH = self.DATABASE_DIR / "persistent_memory.json"

        # 2. Assistant Branding
        self.ASSISTANT_NAME = os.getenv("ASSISTANT_NAME", "Natasha")
        self.USER_TITLE = os.getenv("JARVIS_USER_TITLE", "Boss") 
        
        # 3. LLM Configuration
        self.GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
        
        # 4. Multi-Key Setup for Groq
        self.GROQ_API_KEYS = []
        primary_key = os.getenv("GROQ_API_KEY")
        if primary_key:
            self.GROQ_API_KEYS.append(primary_key)
            
        for i in range(2, 20):
            extra_key = os.getenv(f"GROQ_API_KEY_{i}")
            if extra_key:
                self.GROQ_API_KEYS.append(extra_key)

        # 5. External APIs
        self.TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
        self.ALPHA_VANTAGE_KEY = os.getenv("ALPHA_VANTAGE_KEY")
        self.FMP_KEY = os.getenv("FMP_KEY")
        self.NEWS_API_KEY = os.getenv("NEWS_API_KEY")
        self.GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
        self.GOOGLE_CSE_ID = os.getenv("GOOGLE_CSE_ID")
        self.SERPAPI_KEY = os.getenv("SERPAPI_KEY")

        # 6. Text-to-Speech (TTS) Configuration
        self.TTS_VOICE = os.getenv("TTS_VOICE", "en-US-AriaNeural") 
        self.TTS_RATE = os.getenv("TTS_RATE", "+15%")

# Create the global config object that main.py is looking for
config = Config()