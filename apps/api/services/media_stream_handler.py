"""
Twilio Media Streams WebSocket Handler for Real-time Voice Interaction
"""
import json
import base64
import asyncio
import logging
from typing import Optional, Dict, Any
from fastapi import WebSocket, WebSocketDisconnect
import openai
from openai import AsyncOpenAI
import websockets
import struct

logger = logging.getLogger(__name__)


class MediaStreamHandler:
    """Handles real-time audio streaming with Twilio Media Streams"""
    
    def __init__(self):
        self.active_calls: Dict[str, 'CallSession'] = {}
        self.openai_client: Optional[AsyncOpenAI] = None
        
    def initialize(self, openai_api_key: Optional[str] = None):
        """Initialize the handler with API keys"""
        if openai_api_key:
            self.openai_client = AsyncOpenAI(api_key=openai_api_key)
            
    async def handle_media_stream(self, websocket: WebSocket, call_sid: str):
        """Handle incoming media stream from Twilio"""
        session = CallSession(websocket, call_sid, self.openai_client)
        self.active_calls[call_sid] = session
        
        try:
            await session.start()
        finally:
            # Cleanup
            if call_sid in self.active_calls:
                del self.active_calls[call_sid]


class CallSession:
    """Manages a single call session with real-time audio processing"""
    
    def __init__(self, websocket: WebSocket, call_sid: str, openai_client: Optional[AsyncOpenAI]):
        self.websocket = websocket
        self.call_sid = call_sid
        self.openai_client = openai_client
        self.stream_sid: Optional[str] = None
        self.audio_buffer = bytearray()
        self.is_speaking = False
        self.conversation_context = []
        self.user_name: Optional[str] = None
        self.user_email: Optional[str] = None
        
        # OpenAI Realtime API connection (if available)
        self.openai_ws: Optional[websockets.WebSocketClientProtocol] = None
        
    async def start(self):
        """Start the call session"""
        try:
            # Accept WebSocket connection
            await self.websocket.accept()
            logger.info(f"Media stream connected for call {self.call_sid}")
            
            # If OpenAI Realtime API is available, connect to it
            if self.openai_client:
                await self.connect_openai_realtime()
            
            # Start handling messages
            await self.handle_messages()
            
        except WebSocketDisconnect:
            logger.info(f"Media stream disconnected for call {self.call_sid}")
        except Exception as e:
            logger.error(f"Error in call session {self.call_sid}: {str(e)}")
        finally:
            await self.cleanup()
            
    async def connect_openai_realtime(self):
        """Connect to OpenAI Realtime API for voice interaction"""
        try:
            # OpenAI Realtime API WebSocket endpoint
            ws_url = "wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-10-01"
            
            headers = {
                "Authorization": f"Bearer {self.openai_client.api_key}",
                "OpenAI-Beta": "realtime=v1"
            }
            
            self.openai_ws = await websockets.connect(ws_url, extra_headers=headers)
            
            # Configure the session
            await self.openai_ws.send(json.dumps({
                "type": "session.update",
                "session": {
                    "modalities": ["text", "audio"],
                    "instructions": """You are Eli, a warm, charismatic AI superconnector having a phone conversation.
                    Be natural, conversational, and helpful. Focus on understanding the user's networking goals.
                    Keep responses concise and engaging. Sound genuinely interested in helping them build connections.
                    Don't ask too many questions at once - have a natural conversation flow.""",
                    "voice": "alloy",
                    "input_audio_format": "pcm16",
                    "output_audio_format": "pcm16",
                    "input_audio_transcription": {
                        "model": "whisper-1"
                    },
                    "turn_detection": {
                        "type": "server_vad",
                        "threshold": 0.5,
                        "prefix_padding_ms": 300,
                        "silence_duration_ms": 500
                    }
                }
            }))
            
            # Start listening to OpenAI responses
            asyncio.create_task(self.handle_openai_responses())
            
            logger.info(f"Connected to OpenAI Realtime API for call {self.call_sid}")
            
        except Exception as e:
            logger.error(f"Failed to connect to OpenAI Realtime API: {str(e)}")
            self.openai_ws = None
            
    async def handle_messages(self):
        """Handle incoming messages from Twilio"""
        while True:
            try:
                message = await self.websocket.receive_text()
                data = json.loads(message)
                
                event_type = data.get("event")
                
                if event_type == "start":
                    await self.handle_start(data)
                elif event_type == "media":
                    await self.handle_media(data)
                elif event_type == "stop":
                    logger.info(f"Stream stopped for call {self.call_sid}")
                    break
                    
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"Error handling message: {str(e)}")
                break
                
    async def handle_start(self, data: Dict[str, Any]):
        """Handle stream start event"""
        start_data = data.get("start", {})
        self.stream_sid = start_data.get("streamSid")
        
        # Get custom parameters if passed
        custom_params = start_data.get("customParameters", {})
        self.user_name = custom_params.get("userName", "")
        self.user_email = custom_params.get("userEmail", "")
        
        logger.info(f"Stream started: {self.stream_sid} for user: {self.user_name}")
        
        # Send initial greeting
        await self.send_greeting()
        
    async def send_greeting(self):
        """Send initial greeting to the user"""
        if self.user_name and self.user_name != "there":
            greeting = f"Hi {self.user_name}! This is Eli. Great to connect with you by voice! I understand you're interested in expanding your professional network. Tell me, what kind of connections would be most valuable for you right now?"
        else:
            greeting = "Hi there! This is Eli calling. Thanks for switching to voice! I'd love to hear about your networking goals. What kind of professional connections are you looking to make?"
        
        # If using OpenAI Realtime, send through that
        if self.openai_ws:
            await self.openai_ws.send(json.dumps({
                "type": "response.create",
                "response": {
                    "modalities": ["audio", "text"],
                    "instructions": greeting
                }
            }))
        else:
            # Fallback to TTS
            await self.generate_and_send_tts(greeting)
            
    async def handle_media(self, data: Dict[str, Any]):
        """Handle incoming audio media"""
        media_data = data.get("media", {})
        audio_payload = media_data.get("payload")
        
        if audio_payload and self.openai_ws:
            # Decode the audio (it comes as base64)
            audio_bytes = base64.b64decode(audio_payload)
            
            # Convert from mulaw to PCM16 for OpenAI
            pcm_audio = self.mulaw_to_pcm16(audio_bytes)
            
            # Send to OpenAI Realtime API
            await self.openai_ws.send(json.dumps({
                "type": "input_audio_buffer.append",
                "audio": base64.b64encode(pcm_audio).decode()
            }))
            
    async def handle_openai_responses(self):
        """Handle responses from OpenAI Realtime API"""
        if not self.openai_ws:
            return
            
        try:
            async for message in self.openai_ws:
                data = json.loads(message)
                event_type = data.get("type")
                
                if event_type == "response.audio.delta":
                    # Received audio from OpenAI
                    audio_delta = data.get("delta")
                    if audio_delta:
                        await self.send_audio_to_twilio(audio_delta)
                        
                elif event_type == "response.audio.done":
                    # Audio response completed
                    logger.info("OpenAI audio response completed")
                    
                elif event_type == "response.text.done":
                    # Text response (for logging)
                    text = data.get("text", "")
                    logger.info(f"Eli said: {text}")
                    
                elif event_type == "input_audio_buffer.speech_started":
                    # User started speaking
                    logger.info("User started speaking")
                    self.is_speaking = True
                    
                elif event_type == "input_audio_buffer.speech_stopped":
                    # User stopped speaking
                    logger.info("User stopped speaking")
                    self.is_speaking = False
                    
                elif event_type == "conversation.item.created":
                    # New conversation item
                    item = data.get("item", {})
                    if item.get("role") == "user":
                        transcript = item.get("content", [{}])[0].get("transcript", "")
                        logger.info(f"User said: {transcript}")
                        
        except Exception as e:
            logger.error(f"Error handling OpenAI responses: {str(e)}")
            
    async def send_audio_to_twilio(self, audio_base64: str):
        """Send audio back to Twilio"""
        try:
            # Decode the audio
            pcm_audio = base64.b64decode(audio_base64)
            
            # Convert PCM16 to mulaw for Twilio
            mulaw_audio = self.pcm16_to_mulaw(pcm_audio)
            
            # Encode to base64
            audio_payload = base64.b64encode(mulaw_audio).decode()
            
            # Send to Twilio
            message = {
                "event": "media",
                "streamSid": self.stream_sid,
                "media": {
                    "payload": audio_payload
                }
            }
            
            await self.websocket.send_text(json.dumps(message))
            
        except Exception as e:
            logger.error(f"Error sending audio to Twilio: {str(e)}")
            
    async def generate_and_send_tts(self, text: str):
        """Generate TTS and send to Twilio (fallback if no Realtime API)"""
        try:
            if not self.openai_client:
                return
                
            # Generate speech using OpenAI TTS
            response = await self.openai_client.audio.speech.create(
                model="tts-1",
                voice="alloy",
                input=text,
                response_format="pcm"  # Get PCM format
            )
            
            # Get the audio data
            audio_data = response.content
            
            # Convert to mulaw and send
            mulaw_audio = self.pcm16_to_mulaw(audio_data)
            audio_payload = base64.b64encode(mulaw_audio).decode()
            
            message = {
                "event": "media",
                "streamSid": self.stream_sid,
                "media": {
                    "payload": audio_payload
                }
            }
            
            await self.websocket.send_text(json.dumps(message))
            
        except Exception as e:
            logger.error(f"Error generating TTS: {str(e)}")
            
    def mulaw_to_pcm16(self, mulaw_bytes: bytes) -> bytes:
        """Convert mulaw audio to PCM16"""
        import audioop
        # Convert 8-bit mulaw to 16-bit PCM
        return audioop.ulaw2lin(mulaw_bytes, 2)
        
    def pcm16_to_mulaw(self, pcm_bytes: bytes) -> bytes:
        """Convert PCM16 audio to mulaw"""
        import audioop
        # Convert 16-bit PCM to 8-bit mulaw
        return audioop.lin2ulaw(pcm_bytes, 2)
        
    async def cleanup(self):
        """Clean up resources"""
        try:
            if self.openai_ws:
                await self.openai_ws.close()
                
            if self.websocket:
                await self.websocket.close()
                
        except Exception as e:
            logger.error(f"Error during cleanup: {str(e)}")


# Global instance
media_stream_handler = MediaStreamHandler()
