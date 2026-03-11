"""
Edge TTS Service for N.A.T. AI Assistant
Generates high-quality voice audio using Microsoft's Edge TTS
Supports both full audio generation and streaming audio chunks
"""

import base64
import edge_tts
import tempfile
import os
import asyncio


class TTSService:
    def __init__(self):
        self.voice = "en-US-AriaNeural"
        self.rate = "+0%"
        self.volume = "+0%"

    async def stream_audio(self, text: str):
        """Generator that yields audio chunks as they are generated"""
        try:
            communicate = edge_tts.Communicate(text, self.voice, rate=self.rate, volume=self.volume)
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    yield base64.b64encode(chunk["data"]).decode()
        except Exception as e:
            print(f"[Edge TTS Stream] Error: {e}")

    async def get_audio_base64(self, text: str) -> str:
        """Generate full audio and return as single base64 string"""
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as f:
                temp_file = f.name
            
            communicate = edge_tts.Communicate(text, self.voice, rate=self.rate, volume=self.volume)
            await communicate.save(temp_file)
            
            with open(temp_file, 'rb') as f:
                audio_data = f.read()
            
            os.unlink(temp_file)
            
            return base64.b64encode(audio_data).decode()
            
        except Exception as e:
            print(f"[Edge TTS] Error: {e}")
            return ""

    def set_voice(self, voice: str):
        self.voice = voice

    def set_rate(self, rate: str):
        self.rate = rate

    def set_volume(self, volume: str):
        self.volume = volume


tts_service = TTSService()
