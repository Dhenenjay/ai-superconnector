"""
OpenAI Voice Service for Natural Text-to-Speech
"""
import os
import logging
from typing import Optional
import openai
from pathlib import Path
import tempfile
import hashlib
from datetime import datetime
import asyncio

logger = logging.getLogger(__name__)

class OpenAIVoiceService:
    def __init__(self):
        from core.config import settings
        self.api_key = settings.openai_api_key
        self.client = openai.OpenAI(api_key=self.api_key) if self.api_key else None
        
        # Create cache directory for audio files
        self.cache_dir = Path("C:/Users/Dhenenjay/ai-superconnector/.data/audio_cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Available OpenAI voices
        self.voices = {
            "alloy": "neutral, balanced",
            "echo": "male, conversational", 
            "fable": "british, narrative",
            "onyx": "male, deep",
            "nova": "female, friendly",
            "shimmer": "female, warm"
        }
        
        # Default voice for Eli
        self.default_voice = "echo"  # Male, conversational voice
        
    def generate_audio_url(self, text: str, voice: str = None, speed: float = 1.0) -> Optional[str]:
        """
        Generate audio from text using OpenAI TTS and return a public URL
        """
        try:
            if not self.client:
                logger.error("OpenAI client not initialized")
                return None
                
            voice = voice or self.default_voice
            
            # Generate cache key based on text and voice
            cache_key = hashlib.md5(f"{text}_{voice}_{speed}".encode()).hexdigest()
            cache_file = self.cache_dir / f"{cache_key}.mp3"
            
            # Check if already cached
            if cache_file.exists():
                logger.info(f"Using cached audio for: {text[:50]}...")
                # You would need to serve this file via your API
                # For now, return the local path
                return f"https://d81b58157b66.ngrok-free.app/audio/{cache_key}.mp3"
            
            # Generate new audio
            logger.info(f"Generating audio for: {text[:50]}...")
            response = self.client.audio.speech.create(
                model="tts-1",  # or "tts-1-hd" for higher quality
                voice=voice,
                input=text,
                speed=speed
            )
            
            # Save to cache
            response.stream_to_file(str(cache_file))
            logger.info(f"Audio saved to cache: {cache_file}")
            
            # Return URL (you'll need to serve these files via FastAPI)
            return f"https://d81b58157b66.ngrok-free.app/audio/{cache_key}.mp3"
            
        except Exception as e:
            logger.error(f"Error generating audio: {str(e)}")
            return None
    
    async def generate_conversation_audio(self, text: str, voice: str = None) -> Optional[str]:
        """
        Generate conversational audio asynchronously
        """
        try:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, self.generate_audio_url, text, voice)
        except Exception as e:
            logger.error(f"Error in async audio generation: {str(e)}")
            return None
    
    def get_voice_for_personality(self, personality: str = "professional") -> str:
        """
        Get appropriate voice based on personality type
        """
        voice_map = {
            "professional": "echo",
            "friendly": "nova",
            "authoritative": "onyx",
            "warm": "shimmer",
            "neutral": "alloy"
        }
        return voice_map.get(personality, self.default_voice)

# Global instance
openai_voice = OpenAIVoiceService()
