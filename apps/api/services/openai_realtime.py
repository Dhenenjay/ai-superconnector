"""
OpenAI Realtime API Integration for Voice Conversations
Uses WebSocket for low-latency, natural voice interactions
"""
import asyncio
import base64
import json
import logging
import websockets
import websockets.exceptions
from typing import Optional, Dict, Any
from core.config import settings

logger = logging.getLogger(__name__)


class OpenAIRealtimeClient:
    """
    Client for OpenAI's Realtime API with GPT-4o
    Enables natural, low-latency voice conversations
    Latest model as of December 2024
    """
    
    def __init__(self):
        self.api_key = settings.openai_api_key
        # Using the latest GPT-4o Realtime API endpoint
        self.ws_url = "wss://api.openai.com/v1/realtime"
        # Latest GPT-4o realtime model - best available for voice
        self.model = "gpt-4o-realtime-preview-2024-12-17"
        self.websocket = None
        self.session_id: Optional[str] = None
        self.is_connected = False
        # Track how much audio (in ms) has been appended since the last commit
        self._ms_since_last_commit: float = 0.0
        # Track whether a model response is currently streaming
        self._response_in_progress: bool = False
        # If a response.create is requested during an in-progress response, queue one
        self._pending_response_request: bool = False
        
    async def connect(self) -> bool:
        """
        Establish WebSocket connection to OpenAI Realtime API
        """
        try:
            # Prepare headers for authentication
            headers_dict = {
                "Authorization": f"Bearer {self.api_key}",
                "OpenAI-Beta": "realtime=v1"
            }
            # Some websockets versions want list of tuples
            headers_list = [(k, v) for k, v in headers_dict.items()]
            
            # Connect with the model specified in URL
            url = f"{self.ws_url}?model={self.model}"
            
            logger.info(f"Connecting to OpenAI Realtime API at {url}")
            
            # Try multiple header styles for compatibility across websockets versions
            ws = None
            last_err = None
            for attempt in (
                {"param": "extra_headers", "value": headers_list},
                {"param": "extra_headers", "value": headers_dict},
                {"param": "additional_headers", "value": headers_list},
                {"param": "additional_headers", "value": headers_dict},
            ):
                try:
                    kwargs = {
                        "ping_interval": 20,
                        "ping_timeout": 10
                    }
                    kwargs[attempt["param"]] = attempt["value"]
                    ws = await websockets.connect(url, **kwargs)
                    break
                except TypeError as e:
                    last_err = e
                    continue
                except Exception as e:
                    last_err = e
                    continue
            if ws is None:
                raise last_err or RuntimeError("Failed to open WebSocket with any header style")
            self.websocket = ws
            
            logger.info("WebSocket connection established, waiting for session...")
            
            # Wait for session creation
            response = await self.websocket.recv()
            data = json.loads(response)
            
            logger.info(f"Received response: {data.get('type')}")
            
            if data.get("type") == "session.created":
                self.session_id = data.get("session", {}).get("id")
                logger.info(f"OpenAI Realtime session created: {self.session_id}")
                
                # Don't configure session here - let the bridge do it with user context
                self.is_connected = True
                return True
            else:
                logger.error(f"Unexpected response type: {data.get('type')}")
                logger.error(f"Full response: {json.dumps(data, indent=2)}")
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to connect to OpenAI Realtime API: {str(e)}", exc_info=True)
            return False
    
    async def configure_session(self, user_name: Optional[str] = None, user_email: Optional[str] = None):
        """
        Configure the session for optimal voice conversation
        """
        try:
            # Build personalized instructions with user context
            if user_name and user_name != "there":
                instructions = f"""You are Eli, a warm, charismatic AI superconnector having a phone conversation with {user_name}.
                You already know their name is {user_name} and their email is {user_email}.
                Don't ask for their name or email again - you already have this information.
                You help professionals build meaningful connections and expand their network.
                Be conversational, engaging, and genuinely interested in helping them.
                Keep responses concise and natural for phone conversation.
                Show enthusiasm about their networking goals.
                Use their name naturally in conversation."""
            else:
                instructions = """You are Eli, a warm, charismatic AI superconnector having a phone conversation. 
                You help professionals build meaningful connections and expand their network.
                Be conversational, engaging, and genuinely interested in helping them.
                Keep responses concise and natural for phone conversation.
                Show enthusiasm about their networking goals."""
            
            config = {
                "type": "session.update",
                "session": {
                    "modalities": ["text", "audio"],
                    "instructions": instructions,
                    "voice": "echo",  # Natural male voice option for Eli
                    "input_audio_format": "pcm16",
                    "output_audio_format": "pcm16",
                    "input_audio_transcription": {
                        "model": "whisper-1"
                    },
                    "turn_detection": {
                        "type": "server_vad",  # Server-side voice activity detection
                        "threshold": 0.5,
                        "prefix_padding_ms": 300,
                        "silence_duration_ms": 800  # Increased to give users more time to speak
                    },
                    "tools": [],
                    "tool_choice": "none",
                    "temperature": 0.8,
                    "max_response_output_tokens": 4096
                }
            }
            
            await self.websocket.send(json.dumps(config))
            logger.info(f"Session configured for voice conversation with user: {user_name}")
            
        except Exception as e:
            logger.error(f"Failed to configure session: {str(e)}")
    
    async def send_audio(self, audio_data: bytes):
        """
        Send audio data to OpenAI for processing
        """
        try:
            if not self.websocket:
                logger.warning("[OPENAI TRACE] No websocket, cannot send audio")
                return None
            
            # Encode audio as base64
            audio_base64 = base64.b64encode(audio_data).decode('utf-8')
            
            message = {
                "type": "input_audio_buffer.append",
                "audio": audio_base64
            }
            
            await self.websocket.send(json.dumps(message))
            # Update ms counter: PCM16 24kHz -> samples = len/2, ms = samples/24000*1000
            try:
                samples = max(0, len(audio_data) // 2)
                ms_added = (samples / 24000.0) * 1000.0
                self._ms_since_last_commit += ms_added
                logger.debug(f"[OPENAI TRACE] Appended {len(audio_data)} bytes ({ms_added:.1f}ms), total buffered: {self._ms_since_last_commit:.1f}ms")
            except Exception:
                pass
            return True
            
        except Exception as e:
            logger.error(f"Failed to send audio: {str(e)}")
            return None
    
    async def commit_audio(self):
        """
        Commit the audio buffer for processing. Only commit if at least 100ms of audio
        has been appended since the last commit to avoid empty-buffer errors.
        Returns True if a commit was sent, False if skipped.
        """
        try:
            if not self.websocket:
                logger.warning("[OPENAI TRACE] No websocket, cannot commit audio")
                return None
            
            if self._ms_since_last_commit < 100.0:
                logger.warning(f"[OPENAI TRACE] Skipping commit: only {self._ms_since_last_commit:.1f}ms buffered (<100ms minimum)")
                return False
            
            # Save the amount we're committing
            ms_to_commit = self._ms_since_last_commit
            
            message = {
                "type": "input_audio_buffer.commit"
            }
            
            await self.websocket.send(json.dumps(message))
            logger.info(f"[OPENAI TRACE] Committed audio buffer with {ms_to_commit:.1f}ms of audio")
            # Only reset after successful send
            self._ms_since_last_commit = 0.0
            return True
            
        except Exception as e:
            logger.error(f"Failed to commit audio: {str(e)}")
            return None
    
    async def create_response(self):
        """
        Request a response from the model. If a response is already in progress,
        queue a single pending request to be sent once the current response completes.
        Returns True if sent immediately, False if queued/skipped.
        """
        try:
            if not self.websocket:
                return None
            
            if self._response_in_progress:
                # Debounce: queue a single pending request
                self._pending_response_request = True
                logger.debug("response.create requested while response in progress; queued for later")
                return False
            
            message = {
                "type": "response.create",
                "response": {
                    "modalities": ["audio", "text"],
                    "instructions": "Respond naturally and conversationally."
                }
            }
            
            await self.websocket.send(json.dumps(message))
            self._response_in_progress = True
            logger.debug("response.create sent; marked response as in progress")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create response: {str(e)}")
            return None
    
    async def receive_events(self):
        """
        Receive and process events from OpenAI
        """
        try:
            while self.websocket and self.is_connected:
                message = await self.websocket.recv()
                data = json.loads(message)
                
                event_type = data.get("type")
                logger.debug(f"OpenAI event: {event_type}")
                
                if event_type == "response.audio.delta":
                    # Audio chunk received - the audio is base64 encoded in the delta field
                    delta = data.get("delta", "")
                    if delta:
                        try:
                            audio_data = base64.b64decode(delta)
                            # Mark that we are in a response if we weren't already
                            if not self._response_in_progress:
                                self._response_in_progress = True
                            yield {"type": "audio", "data": audio_data}
                            logger.debug(f"Audio chunk received: {len(audio_data)} bytes")
                        except Exception as e:
                            logger.error(f"Failed to decode audio: {e}")
                
                elif event_type == "response.audio_transcript.delta":
                    # Transcript chunk received
                    text = data.get("delta", "")
                    if text:
                        yield {"type": "transcript", "text": text}
                
                elif event_type == "response.done":
                    # Response complete
                    yield {"type": "done"}
                    # Clear in-progress and send any queued response
                    self._response_in_progress = False
                    if self._pending_response_request:
                        self._pending_response_request = False
                        try:
                            await self.create_response()
                        except Exception as e:
                            logger.error(f"Failed to send queued response.create: {e}")
                    
                elif event_type == "input_audio_buffer.speech_started":
                    # User started speaking
                    yield {"type": "speech_started"}
                
                elif event_type == "input_audio_buffer.speech_stopped":
                    # User stopped speaking
                    yield {"type": "speech_stopped"}
                
                elif event_type == "error":
                    # Error occurred
                    error = data.get("error", {})
                    logger.error(f"OpenAI Realtime error: {error}")
                    yield {"type": "error", "error": error}
                    
        except websockets.exceptions.ConnectionClosed:
            logger.info("OpenAI Realtime connection closed")
        except Exception as e:
            logger.error(f"Error receiving events: {str(e)}")
    
    async def send_text(self, text: str):
        """
        Send text input to the model
        """
        try:
            if not self.websocket:
                return None
            
            message = {
                "type": "conversation.item.create",
                "item": {
                    "type": "message",
                    "role": "user",
                    "content": [
                        {
                            "type": "text",  # Correct field name
                            "text": text
                        }
                    ]
                }
            }
            
            await self.websocket.send(json.dumps(message))
            
            # Request a response
            await self.create_response()
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to send text: {str(e)}")
            return None
    
    async def disconnect(self):
        """
        Close the WebSocket connection
        """
        try:
            self.is_connected = False
            if self.websocket:
                await self.websocket.close()
                self.websocket = None
                self.session_id = None
                logger.info("Disconnected from OpenAI Realtime API")
        except Exception as e:
            logger.error(f"Error disconnecting: {str(e)}")


# Global instance
openai_realtime = OpenAIRealtimeClient()
