"""
Bridge between Twilio Media Streams and OpenAI Realtime API
Handles bidirectional audio streaming for natural conversations
"""
import asyncio
import base64
import json
import logging
from typing import Optional, Dict, Any
from fastapi import WebSocket
from apps.api.services.openai_realtime import OpenAIRealtimeClient
import struct

logger = logging.getLogger(__name__)


class RealtimeBridge:
    """
    Bridges Twilio Media Streams with OpenAI Realtime API
    """
    
    def __init__(self, websocket: WebSocket, call_sid: str):
        self.websocket = websocket
        self.call_sid = call_sid
        self.stream_sid: Optional[str] = None
        self.is_active = True
        self.audio_buffer = bytearray()
        self.user_name: Optional[str] = None
        self.user_email: Optional[str] = None
        # pacing for committing audio to OpenAI
        self._chunks_since_commit = 0
        # set when Twilio sends 'start' event with streamSid
        self.started_event = asyncio.Event()
        # Track which audio flows are enabled
        self.has_inbound_track = False
        self.has_outbound_track = False
        # Create a new OpenAI client instance for this connection
        self.openai_realtime = OpenAIRealtimeClient()
        
    async def handle_connection(self):
        """
        Main handler for the WebSocket connection
        """
        try:
            logger.info(f"Starting realtime bridge for call {self.call_sid}")
            
            # Start handling Twilio messages immediately to obtain streamSid
            twilio_task = asyncio.create_task(self.handle_twilio_messages())
            
            # Wait briefly for Twilio 'start' event
            try:
                await asyncio.wait_for(self.started_event.wait(), timeout=5.0)
                logger.info(f"Twilio stream initialized with streamSid={self.stream_sid}")
            except asyncio.TimeoutError:
                logger.warning("Timed out waiting for Twilio 'start' event; continuing anyway")
            
            # Try connecting to OpenAI Realtime API, but do not abort if it fails
            logger.info("Attempting to connect to OpenAI Realtime API...")
            connected = await self.openai_realtime.connect()
            if connected:
                logger.info("Successfully connected to OpenAI Realtime API")
                openai_task = asyncio.create_task(self.handle_openai_events())
                # Start heartbeat to keep WebSocket alive for Connect verb
                heartbeat_task = asyncio.create_task(self.send_heartbeat())
                tasks = [twilio_task, openai_task, heartbeat_task]
            else:
                logger.error("Failed to connect to OpenAI Realtime API; proceeding with Media Stream only")
                # Still send heartbeat even without OpenAI
                heartbeat_task = asyncio.create_task(self.send_heartbeat())
                tasks = [twilio_task, heartbeat_task]
            
            logger.info("Started message handling tasks")
            
            # Wait for tasks to complete
            await asyncio.gather(*tasks, return_exceptions=True)
            
        except asyncio.CancelledError:
            logger.info("Connection cancelled")
        except Exception as e:
            logger.error(f"Error in realtime bridge: {str(e)}", exc_info=True)
        finally:
            self.is_active = False
            logger.info("Cleaning up connection...")
            try:
                await self.openai_realtime.disconnect()
            except:
                pass
            try:
                await self.websocket.close()
            except:
                pass
    
    async def handle_twilio_messages(self):
        """
        Handle incoming messages from Twilio
        """
        try:
            logger.info("Starting Twilio message handler")
            while self.is_active:
                try:
                    message = await self.websocket.receive_text()
                    data = json.loads(message)
                    
                    event_type = data.get("event")
                    logger.debug(f"Received Twilio event: {event_type}")
                    
                    if event_type == "connected":
                        # WebSocket connection established - this is the FIRST message
                        protocol = data.get("protocol", "")
                        version = data.get("version", "")
                        logger.info(f"WebSocket connected - Protocol: {protocol}, Version: {version}")
                        # No action needed, just acknowledge we received it
                        
                    elif event_type == "start":
                        # Stream started - this is the SECOND message with metadata
                        start_data = data.get("start", {})
                        # Twilio provides streamSid inside the 'start' object
                        self.stream_sid = start_data.get("streamSid")
                        
                        # Get tracks information to know what audio flows to expect
                        tracks = start_data.get("tracks", [])
                        logger.info(f"Stream tracks configuration: {tracks}")
                        
                        # Check which tracks are enabled
                        self.has_inbound_track = "inbound" in tracks
                        self.has_outbound_track = "outbound" in tracks
                        
                        if not self.has_outbound_track:
                            logger.warning("CRITICAL: 'outbound' track not enabled! Cannot send audio to caller.")
                            logger.warning("Check Twilio Stream configuration - need track='both' for bidirectional audio")
                        
                        if not self.has_inbound_track:
                            logger.warning("'inbound' track not enabled! Cannot receive audio from caller.")
                        
                        # Get custom parameters from Twilio
                        custom_params = start_data.get("customParameters", {})
                        
                        # Extract user information
                        self.call_sid = custom_params.get("callSid", self.call_sid)
                        self.user_name = custom_params.get("userName", "")
                        self.user_email = custom_params.get("userEmail", "")
                        
                        logger.info(f"Media stream started: {self.stream_sid}")
                        if not self.stream_sid:
                            logger.warning("No streamSid found in start event; outbound audio will fail until set")
                        logger.info(f"User: {self.user_name} ({self.user_email})")
                        
                        # Signal that stream has started
                        try:
                            self.started_event.set()
                        except Exception:
                            pass
                        
                        # Clear Twilio's audio buffer first (for bidirectional streams)
                        await self.clear_twilio_buffer()
                        
                        # Immediately play a short test tone to verify outbound audio path
                        await self.send_test_tone_ms(300)
                        
                        # DISABLED: Initial greeting might be interfering with audio
                        # try:
                        #     await self.send_initial_greeting()
                        # except Exception:
                        #     pass
                        
                    elif event_type == "media":
                        # Audio data received from Twilio
                        media = data.get("media", {})
                        audio_payload = media.get("payload", "")
                        
                        if audio_payload:
                            # Decode the base64 audio (μ-law 8kHz from Twilio)
                            audio_bytes = base64.b64decode(audio_payload)
                            logger.debug(f"[AUDIO TRACE] Received from Twilio: {len(audio_bytes)} bytes μ-law, base64 length: {len(audio_payload)}")
                            
                            # Buffer incoming audio to reduce noise
                            self.audio_buffer.extend(audio_bytes)
                            logger.debug(f"[AUDIO TRACE] Buffer size after append: {len(self.audio_buffer)} bytes")
                            
                            # Process buffer when we have enough data (160 bytes = 20ms at 8kHz)
                            frames_processed = 0
                            while len(self.audio_buffer) >= 160:
                                # Slice out exactly one frame (160 bytes μ-law)
                                frame_ulaw = bytes(self.audio_buffer[:160])
                                self.audio_buffer = self.audio_buffer[160:]
                                frames_processed += 1

                                # Check if frame has actual audio data (not silence)
                                is_silent = all(b == 0xFF or b == 0x7F for b in frame_ulaw[:10])  # Check first 10 bytes
                                logger.debug(f"[AUDIO TRACE] Processing frame {frames_processed}: {len(frame_ulaw)} bytes, silent={is_silent}")

                                # DISABLED: Echo back causes audio feedback loop
                                # The echo back feature is now disabled to prevent hearing your own voice
                                # If you need to test the outbound audio path, use the test tone instead
                                '''
                                try:
                                    from core.config import settings
                                    if settings.media_echo_back:
                                        logger.info(f"MEDIA_ECHO_BACK is enabled, echoing {len(frame_ulaw)} bytes back to Twilio")
                                        await self.send_audio_to_twilio(frame_ulaw)
                                        logger.debug("Echo sent successfully")
                                    else:
                                        logger.debug("MEDIA_ECHO_BACK is disabled")
                                except Exception as e:
                                    logger.error(f"Error in echo back: {str(e)}")
                                '''

                                # Convert μ-law to PCM16 for OpenAI
                                pcm_audio = self.mulaw_to_pcm16(frame_ulaw)
                                logger.debug(f"[AUDIO TRACE] Converted to PCM16: {len(pcm_audio)} bytes")
                                
                                # Send to OpenAI
                                ok = await self.openai_realtime.send_audio(pcm_audio)
                                logger.debug(f"[AUDIO TRACE] Sent to OpenAI: success={ok}")
                                if ok:  # Only count successful sends
                                    self._chunks_since_commit += 1
                                    logger.debug(f"[AUDIO TRACE] Chunks since commit: {self._chunks_since_commit}/10")
                                else:
                                    logger.warning(f"[AUDIO TRACE] Failed to send audio to OpenAI, not counting chunk")
                                
                                # Commit less frequently to ensure we have enough audio
                                # 160 bytes μ-law per chunk = 20ms; 10 chunks = 200ms (well above 100ms minimum)
                                # This prevents the "input_audio_buffer_commit_empty" errors
                                if self._chunks_since_commit >= 10:  # Changed from 5 to 10 chunks
                                    logger.info(f"[AUDIO TRACE] Committing after {self._chunks_since_commit} chunks")
                                    try:
                                        did_commit = await self.openai_realtime.commit_audio()
                                        logger.info(f"[AUDIO TRACE] Commit result: {did_commit}")
                                        if did_commit:
                                            # Only reset counter if commit was successful
                                            self._chunks_since_commit = 0
                                            response_sent = await self.openai_realtime.create_response()
                                            logger.info(f"[AUDIO TRACE] Response creation: {response_sent}")
                                        else:
                                            logger.warning(f"[AUDIO TRACE] Commit skipped or failed, keeping chunks for next attempt")
                                    except Exception as e:
                                        # Log the actual error instead of silently ignoring
                                        logger.error(f"[AUDIO TRACE] Error during audio commit/response: {str(e)}", exc_info=True)
                                        # Don't reset counter on error, try again later
                            
                    elif event_type == "mark":
                        # Mark event received - this is sent for bidirectional streams
                        mark_data = data.get("mark", {})
                        mark_name = mark_data.get("name", "")
                        logger.info(f"Received mark event: {mark_name}")
                        # Mark events indicate Twilio has processed our audio
                        # This is normal for bidirectional streams
                        
                    elif event_type == "stop":
                        # Stream stopped
                        logger.info(f"Media stream stopped: {self.stream_sid}")
                        self.is_active = False
                        break
                        
                except asyncio.CancelledError:
                    logger.info("Twilio handler cancelled")
                    break
                except Exception as e:
                    logger.error(f"Error processing Twilio message: {str(e)}")
                    continue
                    
        except Exception as e:
            logger.error(f"Error handling Twilio messages: {str(e)}", exc_info=True)
            self.is_active = False
    
    async def send_heartbeat(self):
        """
        Send periodic heartbeat to keep WebSocket connection alive
        This is important when using Connect verb to prevent timeout
        """
        try:
            logger.info("Starting heartbeat task")
            while self.is_active:
                # Wait 30 seconds between heartbeats
                await asyncio.sleep(30)
                
                if not self.is_active:
                    break
                
                # Send a heartbeat message (Twilio ignores unknown events)
                heartbeat = {
                    "event": "heartbeat",
                    "timestamp": asyncio.get_event_loop().time()
                }
                
                try:
                    await self.websocket.send_text(json.dumps(heartbeat))
                    logger.debug("Sent heartbeat to keep connection alive")
                except Exception as e:
                    logger.error(f"Failed to send heartbeat: {str(e)}")
                    # Connection might be lost, stop the bridge
                    self.is_active = False
                    break
                    
        except asyncio.CancelledError:
            logger.info("Heartbeat task cancelled")
        except Exception as e:
            logger.error(f"Error in heartbeat task: {str(e)}")
    
    async def handle_openai_events(self):
        """
        Handle events from OpenAI Realtime API
        """
        try:
            logger.info("Starting OpenAI event handler")
            async for event in self.openai_realtime.receive_events():
                if not self.is_active:
                    break
                
                event_type = event.get("type")
                logger.debug(f"Received OpenAI event: {event_type}")
                
                if event_type == "audio":
                    # Audio response from OpenAI - the raw PCM16 data comes in the 'data' field
                    audio_data = event.get("data")
                    if audio_data:
                        logger.info(f"Processing audio from OpenAI: {len(audio_data)} bytes PCM16")
                        # Convert PCM16 to μ-law for Twilio
                        mulaw_audio = self.pcm16_to_mulaw(audio_data)
                        logger.info(f"Converted to μ-law: {len(mulaw_audio)} bytes")
                        
                        # Send all audio immediately without chunking delays
                        # Twilio needs the audio sent quickly to avoid dropouts
                        await self.send_audio_to_twilio(mulaw_audio)
                        
                elif event_type == "transcript":
                    # Transcript of AI response
                    text = event.get("text", "")
                    logger.info(f"AI: {text}")
                    
                elif event_type == "speech_started":
                    logger.info("User started speaking")
                    # Optionally interrupt AI response
                    
                elif event_type == "speech_stopped":
                    logger.info("User stopped speaking")
                    # Only commit and create response if we have audio
                    # OpenAI handles this automatically with VAD
                    
                elif event_type == "error":
                    error = event.get("error", {})
                    logger.error(f"OpenAI error: {error}")
                    
                elif event_type == "done":
                    logger.info("OpenAI response complete")
                    
        except asyncio.CancelledError:
            logger.info("OpenAI handler cancelled")
        except Exception as e:
            logger.error(f"Error handling OpenAI events: {str(e)}", exc_info=True)
            self.is_active = False
    
    async def send_initial_greeting(self):
        """
        Send initial greeting to start the conversation
        """
        try:
            logger.info(f"Sending initial greeting for user: {self.user_name}")
            
            # Send an immediate greeting through OpenAI
            if self.user_name and self.user_name != "there":
                greeting = f"Hi {self.user_name}! I heard you're interested in expanding your professional network. What specific connections are you looking to make?"
            else:
                greeting = "Hi! I understand you're looking to expand your professional network. What kind of connections would be most valuable for you?"
            
            # Send text and immediately create response for audio
            await self.openai_realtime.send_text(greeting)
            logger.info("Sent greeting text to OpenAI")
            
            # Explicitly trigger response creation
            await self.openai_realtime.create_response()
            logger.info("Triggered OpenAI response generation")
            
        except Exception as e:
            logger.error(f"Error sending initial greeting: {str(e)}")
    
    async def send_audio_to_twilio(self, audio_data: bytes):
        """
        Send audio data to Twilio in proper chunks
        """
        try:
            if not self.stream_sid:
                logger.warning("No stream SID available, cannot send audio")
                return
            
            # DISABLED: Mark events might be causing issues
            # mark_message = {
            #     "event": "mark",
            #     "streamSid": self.stream_sid,
            #     "mark": {
            #         "name": "audio_chunk"
            #     }
            # }
            # await self.websocket.send_text(json.dumps(mark_message))
            
            # Twilio expects audio in 160-byte chunks (20ms of 8kHz μ-law audio)
            chunk_size = 160
            
            for i in range(0, len(audio_data), chunk_size):
                chunk = audio_data[i:i+chunk_size]
                
                # Pad the last chunk if necessary
                if len(chunk) < chunk_size:
                    chunk = chunk + b'\xff' * (chunk_size - len(chunk))
                
                # Log first chunk for debugging
                if i == 0 and len(chunk) > 0:
                    logger.info(f"Audio sample (first 10 bytes): {list(chunk[:10])}")
                
                # Encode audio as base64
                audio_base64 = base64.b64encode(chunk).decode('utf-8')
                
                # Create media message for bidirectional stream
                # According to Twilio docs, we need to send media messages back
                # with event type "media" and the audio payload
                message = {
                    "event": "media",
                    "streamSid": self.stream_sid,
                    "media": {
                        "payload": audio_base64
                    }
                }
                
                # Log first message
                if i == 0:
                    logger.info(f"Sending audio to Twilio: {len(chunk)} bytes μ-law, base64 length: {len(audio_base64)}")
                    message_json = json.dumps(message)
                    logger.debug(f"Sending WebSocket message (first 200 chars): {message_json[:200]}")
                else:
                    message_json = json.dumps(message)
                
                # Send to Twilio
                await self.websocket.send_text(message_json)
                # Small delay to prevent overwhelming Twilio
                await asyncio.sleep(0.001)  # 1ms delay between chunks
            
            logger.debug(f"Audio sent successfully to stream {self.stream_sid}: {len(audio_data)} bytes total")
            
        except Exception as e:
            logger.error(f"Error sending audio to Twilio: {str(e)}, stream_sid: {self.stream_sid}")
    
    async def clear_twilio_buffer(self):
        """
        Send a clear message to Twilio to clear the audio buffer
        This is useful for bidirectional streams to ensure clean audio playback
        """
        try:
            if not self.stream_sid:
                logger.warning("No stream SID available, cannot clear buffer")
                return
            
            clear_message = {
                "event": "clear",
                "streamSid": self.stream_sid
            }
            
            await self.websocket.send_text(json.dumps(clear_message))
            logger.info("Sent clear buffer message to Twilio")
            
        except Exception as e:
            logger.error(f"Error clearing Twilio buffer: {str(e)}")
    
    async def send_fallback_greeting(self):
        """
        Send a fallback greeting when OpenAI is not available
        """
        try:
            logger.info("Sending fallback greeting...")
            # As a minimal signal, play a brief tone so caller hears something
            await self.send_test_tone_ms(300)
            logger.warning("OpenAI Realtime API unavailable - using minimal tone fallback")
        except Exception as e:
            logger.error(f"Error sending fallback greeting: {str(e)}")
    
    def mulaw_to_pcm16(self, mulaw_data: bytes) -> bytes:
        """
        Convert μ-law 8kHz audio to PCM16 24kHz format for OpenAI
        We need to upsample by repeating each sample 3 times
        """
        import audioop
        
        try:
            # Convert μ-law to PCM16 using audioop
            pcm_data = audioop.ulaw2lin(mulaw_data, 2)
            
            # Upsample from 8kHz to 24kHz by repeating each sample 3 times
            upsampled = bytearray()
            for i in range(0, len(pcm_data), 2):  # Process each 16-bit sample
                sample = pcm_data[i:i+2]
                # Repeat sample 3 times for 3x upsampling
                for _ in range(3):
                    upsampled.extend(sample)
            
            logger.debug(f"Converted {len(mulaw_data)} bytes μ-law (8kHz) to {len(upsampled)} bytes PCM16 (24kHz)")
            return bytes(upsampled)
            
        except Exception as e:
            logger.error(f"Error in μ-law to PCM16 conversion: {str(e)}")
            # Fallback to manual conversion
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
            
            pcm_data = bytearray()
            for byte in mulaw_data:
                pcm_value = MULAW_TABLE[byte]
                # Upsample from 8kHz to 24kHz by repeating each sample 3 times
                for _ in range(3):
                    pcm_data.extend(struct.pack('<h', pcm_value))
            
            return bytes(pcm_data)
    
    def pcm16_to_mulaw(self, pcm_data: bytes) -> bytes:
        """
        Convert PCM16 audio to μ-law format
        OpenAI sends 24kHz PCM16, Twilio expects 8kHz μ-law
        We need to downsample by taking every 3rd sample
        """
        import audioop
        
        try:
            # First, convert from 24kHz to 8kHz by taking every 3rd sample
            # PCM16 is 2 bytes per sample
            downsampled = bytearray()
            for i in range(0, len(pcm_data) - 2, 6):  # Every 3rd sample (6 bytes = 3 samples * 2 bytes)
                downsampled.extend(pcm_data[i:i+2])  # Take one 16-bit sample
            
            # Convert PCM16 to μ-law using audioop
            # audioop.lin2ulaw expects 2-byte samples
            mulaw_data = audioop.lin2ulaw(bytes(downsampled), 2)
            
            logger.debug(f"Converted {len(pcm_data)} bytes PCM16 (24kHz) to {len(mulaw_data)} bytes μ-law (8kHz)")
            return mulaw_data
            
        except Exception as e:
            logger.error(f"Error in PCM16 to μ-law conversion: {str(e)}")
            # Fallback to manual conversion
            def linear_to_mulaw(sample):
                sample = max(-32768, min(32767, sample))
                sign = 0x80 if sample < 0 else 0
                if sample < 0:
                    sample = -sample
                sample = min(0x7FFF, sample + 0x84)
                
                if sample < 0x100:
                    exp = 0
                elif sample < 0x200:
                    exp = 1
                elif sample < 0x400:
                    exp = 2
                elif sample < 0x800:
                    exp = 3
                elif sample < 0x1000:
                    exp = 4
                elif sample < 0x2000:
                    exp = 5
                elif sample < 0x4000:
                    exp = 6
                else:
                    exp = 7
                    
                mantissa = (sample >> (exp + 3)) & 0x0F
                mulaw = ~(sign | (exp << 4) | mantissa) & 0xFF
                return mulaw
            
            mulaw_data = bytearray()
            for i in range(0, len(pcm_data) - 2, 6):  # Downsample from 24kHz to 8kHz
                if i + 1 < len(pcm_data):
                    sample = struct.unpack('<h', pcm_data[i:i+2])[0]
                    mulaw_data.append(linear_to_mulaw(sample))
            
            return bytes(mulaw_data)

    async def send_test_tone_ms(self, duration_ms: int = 300, freq: int = 440):
        """
        Generate a short PCM16 tone, convert to μ-law and send to Twilio to validate audio path.
        """
        try:
            sample_rate = 24000  # PCM16 rate expected by OpenAI conversion path
            import math
            num_samples = int(sample_rate * (duration_ms / 1000.0))
            pcm = bytearray()
            amplitude = 16000
            for i in range(num_samples):
                t = i / sample_rate
                sample = int(amplitude * math.sin(2 * math.pi * freq * t))
                pcm.extend(struct.pack('<h', sample))
            # Convert to μ-law 8kHz and send
            mulaw = self.pcm16_to_mulaw(bytes(pcm))
            await self.send_audio_to_twilio(mulaw)
            logger.info(f"Sent {duration_ms}ms test tone to Twilio")
        except Exception as e:
            logger.error(f"Error generating/sending test tone: {str(e)}")


async def handle_media_stream(websocket: WebSocket, call_sid: str):
    """
    Entry point for handling a media stream connection
    """
    try:
        await websocket.accept()
        bridge = RealtimeBridge(websocket, call_sid)
        await bridge.handle_connection()
    except Exception as e:
        logger.error(f"Error in media stream handler: {str(e)}")
        await websocket.close()
