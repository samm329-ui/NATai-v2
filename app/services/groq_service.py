import time
import requests
from typing import List, Dict, Optional, Iterator
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, BaseMessage
from config import config
from app.services.memory_service import memory_service

class GroqService:
    def __init__(self):
        self.current_key_index = 0
        self.llm = None
        self.model_name = getattr(config, 'GROQ_MODEL', 'llama-3.3-70b-versatile')
        
    def _get_next_api_key(self):
        """Fetches the next API key from the list for rotation."""
        keys = getattr(config, 'GROQ_API_KEYS', [])
        if not keys:
            # Fallback in case a single key is used in config instead of a list
            single_key = getattr(config, 'GROQ_API_KEY', None)
            if single_key:
                return single_key
            raise Exception("No Groq API keys configured")
            
        key = keys[self.current_key_index]
        self.current_key_index = (self.current_key_index + 1) % len(keys)
        return key
    
    def _create_llm(self):
        """Initializes the LangChain ChatGroq object."""
        api_key = self._get_next_api_key()
        self.llm = ChatGroq(
            groq_api_key=api_key, 
            model_name=self.model_name, 
            temperature=0.7, 
            max_tokens=2048, 
            timeout=60
        )

    def _format_messages(self, messages: List[Dict[str, str]], system_prompt: Optional[str] = None) -> List[BaseMessage]:
        """Converts raw dictionary messages into LangChain message objects."""
        lc_messages = []
        if system_prompt:
            lc_messages.append(SystemMessage(content=system_prompt))
            
        for msg in messages:
            if msg["role"] == "user":
                lc_messages.append(HumanMessage(content=msg["content"]))
            elif msg["role"] == "assistant":
                lc_messages.append(AIMessage(content=msg["content"]))
        return lc_messages

    def chat(self, messages: List[Dict[str, str]], system_prompt: Optional[str] = None) -> str:
        """Standard non-streaming chat with multi-key fallback."""
        keys = getattr(config, 'GROQ_API_KEYS', [])
        max_retries = len(keys) if keys else 0
        retries = 0
        
        lc_messages = self._format_messages(messages, system_prompt)
        
        if max_retries == 0:
            raise Exception("No Groq API keys configured. Please set GROQ_API_KEY in your .env file.")
        
        while retries < max_retries:
            try:
                if not self.llm:
                    self._create_llm()
                response = self.llm.invoke(lc_messages)
                return response.content
            except Exception as e:
                error_str = str(e).lower()
                if "rate_limit" in error_str or "429" in error_str:
                    print(f"[Groq] Rate limit reached, rotating to next key... ({retries + 1}/{max_retries})")
                elif "api" in error_str or "auth" in error_str or "401" in error_str:
                    print(f"[Groq] API error: {e}, trying next key...")
                else:
                    print(f"[Groq] Unexpected error: {e}")
                    
                self.llm = None
                retries += 1
                time.sleep(1)
                
        raise Exception("All Groq API keys failed")
    
    async def stream_chat(self, messages: List[Dict[str, str]], system_prompt: Optional[str] = None) -> Iterator[str]:
        """Streaming chat yielding tokens one by one with multi-key fallback."""
        keys = getattr(config, 'GROQ_API_KEYS', [])
        max_retries = len(keys) if keys else 1
        retries = 0
        
        lc_messages = self._format_messages(messages, system_prompt)
        
        while retries < max_retries:
            try:
                if not self.llm:
                    self._create_llm()
                
                # Yield chunks immediately as they arrive from Groq asynchronously
                async for chunk in self.llm.astream(lc_messages):
                    yield chunk.content
                return  # Exit the loop cleanly if stream completes without error
                
            except Exception as e:
                error_str = str(e).lower()
                if "rate_limit" in error_str or "429" in error_str:
                    print(f"[Groq Stream] Rate limit reached, rotating to next key... ({retries + 1}/{max_retries})")
                else:
                    print(f"[Groq Stream] Error: {e}, trying next key...")
                    
                self.llm = None
                retries += 1
                time.sleep(1)
                
        yield "I apologize, but I am currently experiencing connection issues. All of my API keys failed."

    def _build_system_prompt(self, context: str) -> str:
        """Builds the custom system prompt for Natasha."""
        assistant_name = getattr(config, 'ASSISTANT_NAME', 'Natasha')
        persistent_memory = memory_service.get_system_prompt_context()
        
        prompt = f"""You are {assistant_name}, an advanced AI assistant. Your full name is Natasha.

IMPORTANT CONTEXT FROM YOUR MEMORY:
{context}

"""
        
        if persistent_memory:
            prompt += f"""{persistent_memory}

"""
        
        prompt += """Guidelines:
- Use the persistent memories above to personalize your responses to the user
- Always remember the user's name, preferences, and important details they told you
- Be helpful, concise, and friendly
- If you don't know something, say so honestly
- Always be respectful and professional"""
        
        return prompt

    def chat_with_context(self, user_message: str, context: str, conversation_history: List[Dict[str, str]] = None) -> str:
        """Non-streaming context chat."""
        system_prompt = self._build_system_prompt(context)
        messages = conversation_history.copy() if conversation_history else []
        messages.append({"role": "user", "content": user_message})
        return self.chat(messages, system_prompt)

    async def stream_chat_with_context(self, user_message: str, context: str, conversation_history: List[Dict[str, str]] = None) -> Iterator[str]:
        """Streaming context chat."""
        system_prompt = self._build_system_prompt(context)
        messages = conversation_history.copy() if conversation_history else []
        messages.append({"role": "user", "content": user_message})
        async for chunk in self.stream_chat(messages, system_prompt):
            yield chunk

    def is_available(self) -> bool:
        """Checks if Groq API keys are configured."""
        keys = getattr(config, 'GROQ_API_KEYS', [])
        single = getattr(config, 'GROQ_API_KEY', None)
        return len(keys) > 0 or bool(single)

    def transcribe_audio(self, audio_bytes: bytes, filename: str = "audio.webm") -> str:
        """Transcribes audio using Groq's Whisper model (whisper-large-v3-turbo)."""
        api_key = self._get_next_api_key()
        url = "https://api.groq.com/openai/v1/audio/transcriptions"
        
        headers = {
            "Authorization": f"Bearer {api_key}"
        }
        
        files = {
            "model": (None, "whisper-large-v3-turbo"),
            "file": (filename, audio_bytes, "audio/webm")
        }
        
        response = requests.post(url, headers=headers, files=files)
        
        if response.status_code == 200:
            return response.json().get("text", "").strip()
        else:
            raise Exception(f"Groq Whisper API Error: {response.text}")

groq_service = GroqService()