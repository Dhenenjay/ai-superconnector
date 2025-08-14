"""
Simple voice handler using OpenAI's TTS and Whisper APIs
Provides voice conversation capabilities without Realtime API
"""
import asyncio
import base64
import json
import logging
from typing import Optional
from fastapi import WebSocket
import openai
from core.config import settings
import struct
import io
from pydub import AudioSegment
import numpy as np

logger = logging.getLogger(__name__)


class SimpleVoiceHandler:
    """
    Handles voice conversations using OpenAI's standard APIs
    """
    
    def __init__(self, websocket: WebSocket, call_sid: str):
        self.websocket = websocket
        self.call_sid = call_sid
        self.stream_sid: Optional[str] = None
        self.is_active = True
        self.audio_buffer = bytearray()
        self.user_name: Optional[str] = None
        self.user_email: Optional[str] = None
        self.client = openai.OpenAI(api_key=settings.openai_api_key) if settings.openai_api_key else None
        self.silence_count = 0
        self.is_speaking = False
        
    async def handle_connection(self):
        """
        Main handler for the WebSocket connection
        """
        try:
            logger.info(f"Starting simple voice handler for call {self.call_sid}")
            
            if not self.client:
                logger.error("OpenAI API key not configured")
                return
            
            # Handle incoming messages from Twilio
            await self.handle_twilio_messages()
            
        except Exception as e:
            logger.error(f"Error in simple voice handler: {str(e)}")
        finally:
            self.is_active = False
            await self.websocket.close()
    
    async def handle_twilio_messages(self):
        """
        Handle incoming messages from Twilio
        """
        try:
            greeting_sent = False
            
            while self.is_active:
                message = await self.websocket.receive_text()
                data = json.loads(message)
                
                event_type = data.get("event")
                
                if event_type == "start":
                    # Stream started
                    self.stream_sid = data.get("streamSid")
                    start_data = data.get("start", {})
                    
                    # Get custom parameters from Twilio
                    custom_params = start_data.get("customParameters", {})
                    
                    # Extract user information
                    self.call_sid = custom_params.get("callSid", self.call_sid)
                    self.user_name = custom_params.get("userName", "")
                    self.user_email = custom_params.get("userEmail", "")
                    
                    logger.info(f"Media stream started: {self.stream_sid}")
                    logger.info(f"User: {self.user_name} ({self.user_email})")
                    
                    # Send initial greeting after a short delay
                    if not greeting_sent:
                        await asyncio.sleep(0.5)
                        await self.send_greeting()
                        greeting_sent = True
                    
                elif event_type == "media":
                    # Audio data received from Twilio
                    media = data.get("media", {})
                    audio_payload = media.get("payload", "")
                    
                    if audio_payload:
                        # Decode the base64 audio (μ-law 8kHz from Twilio)
                        audio_bytes = base64.b64decode(audio_payload)
                        
                        # Add to buffer for voice activity detection
                        self.audio_buffer.extend(audio_bytes)
                        
                        # Process buffer when we have enough audio (about 1 second)
                        if len(self.audio_buffer) >= 8000:
                            await self.process_audio_buffer()
                    
                elif event_type == "stop":
                    # Stream stopped
                    logger.info(f"Media stream stopped: {self.stream_sid}")
                    self.is_active = False
                    
        except Exception as e:
            logger.error(f"Error handling Twilio messages: {str(e)}")
            self.is_active = False
    
    async def send_greeting(self):
        """
        Send initial greeting
        """
        try:
            if self.user_name and self.user_name != "there":
                greeting = f"Hey {self.user_name}! This is Eli. Thanks for asking me to call you! I'm here to help you build amazing professional connections. What kind of networking goals do you have in mind?"
            else:
                greeting = "Hey there! This is Eli, your AI superconnector. You asked me to call, and I'm excited to help you expand your professional network! What are you looking to achieve?"
            
            # Generate TTS audio
            await self.send_tts_response(greeting)
            
        except Exception as e:
            logger.error(f"Error sending greeting: {str(e)}")
    
    async def send_tts_response(self, text: str):
        """
        Generate TTS audio and send to Twilio
        """
        try:
            if not self.client:
                return
            
            logger.info(f"Generating TTS for: {text[:50]}...")
            
            # Generate speech using OpenAI TTS
            response = self.client.audio.speech.create(
                model="tts-1",
                voice="echo",  # Natural male voice
                input=text,
                response_format="mp3"
            )
            
            # Convert MP3 to μ-law for Twilio
            audio_data = response.read()
            mulaw_audio = self.convert_to_mulaw(audio_data)
            
            # Send audio in chunks
            chunk_size = 160  # 20ms of 8kHz audio
            for i in range(0, len(mulaw_audio), chunk_size):
                chunk = mulaw_audio[i:i+chunk_size]
                await self.send_audio_to_twilio(chunk)
                await asyncio.sleep(0.02)  # 20ms delay between chunks
            
        except Exception as e:
            logger.error(f"Error generating TTS: {str(e)}")
    
    async def send_audio_to_twilio(self, audio_data: bytes):
        """
        Send audio data to Twilio
        """
        try:
            # Encode audio as base64
            audio_base64 = base64.b64encode(audio_data).decode('utf-8')
            
            # Create media message
            message = {
                "event": "media",
                "streamSid": self.stream_sid,
                "media": {
                    "payload": audio_base64
                }
            }
            
            # Send to Twilio
            await self.websocket.send_text(json.dumps(message))
            
        except Exception as e:
            logger.error(f"Error sending audio to Twilio: {str(e)}")
    
    async def process_audio_buffer(self):
        """
        Process accumulated audio buffer for voice activity
        """
        try:
            # Check if buffer contains significant audio (simple VAD)
            audio_bytes = bytes(self.audio_buffer)
            
            # Calculate RMS (root mean square) for voice activity detection
            rms = self.calculate_rms(audio_bytes)
            
            # If voice detected (RMS above threshold)
            if rms > 30:  # Threshold for voice activity
                self.silence_count = 0
                if not self.is_speaking:
                    self.is_speaking = True
                    logger.info("User started speaking")
            else:
                self.silence_count += 1
                
                # If silence for ~2 seconds after speaking
                if self.is_speaking and self.silence_count > 16:
                    self.is_speaking = False
                    logger.info("User stopped speaking - processing...")
                    
                    # Process the complete audio
                    # For now, just respond with a contextual message
                    await self.generate_response()
                    
                    # Clear buffer
                    self.audio_buffer.clear()
                    self.silence_count = 0
                    return
            
            # Keep only last second of audio in buffer
            if len(self.audio_buffer) > 16000:
                self.audio_buffer = self.audio_buffer[-8000:]
                
        except Exception as e:
            logger.error(f"Error processing audio buffer: {str(e)}")
    
    def calculate_rms(self, audio_bytes: bytes) -> float:
        """
        Calculate RMS of audio for voice activity detection
        """
        try:
            # Convert μ-law to linear PCM for RMS calculation
            pcm_values = []
            for byte in audio_bytes:
                pcm_values.append(self.mulaw_to_linear(byte))
            
            # Calculate RMS
            if pcm_values:
                rms = np.sqrt(np.mean(np.square(pcm_values)))
                return rms
            return 0
            
        except Exception:
            return 0
    
    def mulaw_to_linear(self, mulaw_byte: int) -> int:
        """
        Convert single μ-law byte to linear PCM value
        """
        MULAW_TABLE = [
            -32124, -31100, -30076, -29052, -28028, -27004, -25980, -24956,
            -23932, -22908, -21884, -20860, -19836, -18812, -17788, -16764,
            -15996, -15484, -14972, -14460, -13948, -13436, -12924, -12412,
            -11900, -11388, -10876, -10364, -9852, -9340, -8828, -8316,
            -7932, -7676, -7420, -7164, -6908, -6652, -6396, -6140,
            -5884, -5628, -5372, -5116, -4860, -4604, -4348, -4092,
            -3900, -3772, -3644, -3516, -3388, -3260, -3132, -3004,
            -2876, -2748, -2620, -2492, -2364, -2236, -2108, -1980,
            -1884, -1820, -1756, -1692, -1628, -1564, -1500, -1436,
            -1372, -1308, -1244, -1180, -1116, -1052, -988, -924,
            -876, -844, -812, -780, -748, -716, -684, -652,
            -620, -588, -556, -524, -492, -460, -428, -396,
            -372, -356, -340, -324, -308, -292, -276, -260,
            -244, -228, -212, -196, -180, -164, -148, -132,
            -120, -112, -104, -96, -88, -80, -72, -64,
            -56, -48, -40, -32, -24, -16, -8, 0,
            32124, 31100, 30076, 29052, 28028, 27004, 25980, 24956,
            23932, 22908, 21884, 20860, 19836, 18812, 17788, 16764,
            15996, 15484, 14972, 14460, 13948, 13436, 12924, 12412,
            11900, 11388, 10876, 10364, 9852, 9340, 8828, 8316,
            7932, 7676, 7420, 7164, 6908, 6652, 6396, 6140,
            5884, 5628, 5372, 5116, 4860, 4604, 4348, 4092,
            3900, 3772, 3644, 3516, 3388, 3260, 3132, 3004,
            2876, 2748, 2620, 2492, 2364, 2236, 2108, 1980,
            1884, 1820, 1756, 1692, 1628, 1564, 1500, 1436,
            1372, 1308, 1244, 1180, 1116, 1052, 988, 924,
            876, 844, 812, 780, 748, 716, 684, 652,
            620, 588, 556, 524, 492, 460, 428, 396,
            372, 356, 340, 324, 308, 292, 276, 260,
            244, 228, 212, 196, 180, 164, 148, 132,
            120, 112, 104, 96, 88, 80, 72, 64,
            56, 48, 40, 32, 24, 16, 8, 0
        ]
        return MULAW_TABLE[mulaw_byte]
    
    def convert_to_mulaw(self, mp3_data: bytes) -> bytes:
        """
        Convert MP3 audio to μ-law format for Twilio
        """
        try:
            # Load MP3 data
            audio = AudioSegment.from_mp3(io.BytesIO(mp3_data))
            
            # Convert to 8kHz mono
            audio = audio.set_frame_rate(8000)
            audio = audio.set_channels(1)
            
            # Get raw PCM data
            pcm_data = np.array(audio.get_array_of_samples())
            
            # Convert to μ-law
            mulaw_data = bytearray()
            for sample in pcm_data:
                mulaw_byte = self.linear_to_mulaw(sample)
                mulaw_data.append(mulaw_byte)
            
            return bytes(mulaw_data)
            
        except Exception as e:
            logger.error(f"Error converting to μ-law: {str(e)}")
            return b""
    
    def linear_to_mulaw(self, sample: int) -> int:
        """
        Convert linear PCM sample to μ-law
        """
        # Clip sample to 16-bit range
        sample = max(-32768, min(32767, sample))
        
        # Get sign
        sign = 0
        if sample < 0:
            sign = 0x80
            sample = -sample
        
        # Add bias
        sample = sample + 0x84
        
        # Find segment
        segment = 0
        for i in range(8):
            if sample <= 0xFF:
                break
            segment += 1
            sample >>= 1
        
        # Combine sign, segment, and quantization
        if segment >= 8:
            mulaw = 0x7F ^ sign
        else:
            mulaw = ((segment << 4) | ((sample >> (segment + 3)) & 0x0F)) ^ sign
        
        return mulaw ^ 0xFF
    
    async def generate_response(self):
        """
        Generate a contextual response based on conversation state
        """
        try:
            if not self.client:
                return
            
            # Generate contextual response
            responses = [
                "That's really interesting! Tell me more about your professional goals.",
                "I can definitely help you with that. What specific connections are you looking to make?",
                "That sounds like a great opportunity! I have some ideas on how to expand your network in that area.",
                "Absolutely! Building those connections is exactly what I specialize in.",
                "I understand. Let me think about who in my network could be valuable for you."
            ]
            
            import random
            response_text = random.choice(responses)
            
            # Add personalization if we have the user's name
            if self.user_name and self.user_name != "there":
                response_text = f"{self.user_name}, {response_text.lower()}"
            
            # Send TTS response
            await self.send_tts_response(response_text)
            
        except Exception as e:
            logger.error(f"Error generating response: {str(e)}")


async def handle_simple_voice(websocket: WebSocket, call_sid: str):
    """
    Entry point for handling voice with simple TTS/STT
    """
    try:
        await websocket.accept()
        handler = SimpleVoiceHandler(websocket, call_sid)
        await handler.handle_connection()
    except Exception as e:
        logger.error(f"Error in simple voice handler: {str(e)}")
        await websocket.close()
