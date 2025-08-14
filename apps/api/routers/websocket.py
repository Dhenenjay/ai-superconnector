"""
WebSocket endpoints for real-time communication
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
import logging
from apps.api.services.media_stream_handler import media_stream_handler
from core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()


@router.websocket("/ws/media-stream")
async def media_stream_endpoint(
    websocket: WebSocket,
    call_sid: str = Query(..., description="Twilio Call SID")
):
    """
    WebSocket endpoint for Twilio Media Streams
    Handles real-time audio streaming for voice calls
    """
    try:
        # Initialize the media stream handler with OpenAI key if available
        media_stream_handler.initialize(settings.openai_api_key)
        
        # Handle the media stream
        await media_stream_handler.handle_media_stream(websocket, call_sid)
        
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for call {call_sid}")
    except Exception as e:
        logger.error(f"Error in media stream endpoint: {str(e)}")
    finally:
        # Ensure websocket is closed
        try:
            await websocket.close()
        except:
            pass


@router.websocket("/ws/realtime-bridge")
async def realtime_bridge_endpoint(
    websocket: WebSocket
):
    """
    WebSocket endpoint for OpenAI Realtime API bridge
    Handles real-time bidirectional audio for natural voice conversations
    """
    logger.info(f"WebSocket connection attempt from {websocket.client}")
    try:
        # Accept the WebSocket connection first
        await websocket.accept()
        logger.info(f"Realtime bridge WebSocket accepted from {websocket.client}")
        
        # Get call_sid from the first message if needed
        call_sid = "unknown"
        
        # Import here to avoid circular imports
        from apps.api.services.realtime_bridge import RealtimeBridge
        
        # Create and handle the realtime bridge
        bridge = RealtimeBridge(websocket, call_sid)
        await bridge.handle_connection()
        
    except WebSocketDisconnect:
        logger.info(f"Realtime bridge disconnected")
    except Exception as e:
        logger.error(f"Error in realtime bridge endpoint: {str(e)}", exc_info=True)
    finally:
        # Ensure websocket is closed
        try:
            await websocket.close()
        except:
            pass
