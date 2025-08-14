"""
Twilio Connector for WhatsApp and Voice Integration
"""
from typing import Dict, Any, Optional, List
from datetime import datetime
import httpx
from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse
from twilio.twiml.messaging_response import MessagingResponse
from core.config import settings
import logging

logger = logging.getLogger(__name__)


class TwilioConnector:
    """Handles Twilio integration for WhatsApp and Voice calls"""
    
    def __init__(self):
        """Initialize Twilio client with credentials"""
        if not settings.twilio_account_sid or not settings.twilio_auth_token:
            logger.warning("Twilio credentials not configured")
            self.client = None
        else:
            self.client = Client(
                settings.twilio_account_sid,
                settings.twilio_auth_token
            )
            self.whatsapp_number = settings.twilio_whatsapp_number
            self.phone_number = settings.twilio_phone_number
    
    def send_whatsapp_message(
        self,
        to_number: str,
        message: str,
        media_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send a WhatsApp message via Twilio
        
        Args:
            to_number: Recipient's WhatsApp number (format: +1234567890)
            message: Text message to send
            media_url: Optional URL of media to attach
        
        Returns:
            Dictionary with message status and SID
        """
        if not self.client:
            return {
                "success": False,
                "error": "Twilio client not initialized"
            }
        
        try:
            # Format the recipient number for WhatsApp
            if not to_number.startswith("whatsapp:"):
                to_number = f"whatsapp:{to_number}"
            
            # Prepare message parameters
            msg_params = {
                "body": message,
                "from_": self.whatsapp_number,
                "to": to_number
            }
            
            # Add media if provided
            if media_url:
                msg_params["media_url"] = [media_url]
            
            # Send the message
            message = self.client.messages.create(**msg_params)
            
            return {
                "success": True,
                "message_sid": message.sid,
                "status": message.status,
                "to": message.to,
                "from": message.from_,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to send WhatsApp message: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def make_voice_call(
        self,
        to_number: str,
        twiml_url: Optional[str] = None,
        message: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Initiate a voice call via Twilio
        
        Args:
            to_number: Recipient's phone number (format: +1234567890)
            twiml_url: URL that returns TwiML instructions for the call
            message: Optional text message to be spoken (if twiml_url not provided)
        
        Returns:
            Dictionary with call status and SID
        """
        if not self.client:
            return {
                "success": False,
                "error": "Twilio client not initialized"
            }
        
        try:
            # If no TwiML URL provided, create a simple message response
            if not twiml_url and message:
                # You would need to host this TwiML somewhere
                # For now, we'll use Twilio's echo TwiML as a placeholder
                twiml_url = "http://demo.twilio.com/docs/voice.xml"
            
            # Make the call
            call = self.client.calls.create(
                to=to_number,
                from_=self.phone_number,
                url=twiml_url or "http://demo.twilio.com/docs/voice.xml"
            )
            
            return {
                "success": True,
                "call_sid": call.sid,
                "status": call.status,
                "to": call.to,
                "from": getattr(call, 'from_', getattr(call, 'from', self.phone_number)),
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to make voice call: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def get_message_history(
        self,
        limit: int = 20,
        from_number: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieve WhatsApp message history
        
        Args:
            limit: Maximum number of messages to retrieve
            from_number: Optional filter by sender number
        
        Returns:
            List of message dictionaries
        """
        if not self.client:
            return []
        
        try:
            # Prepare filter parameters
            filter_params = {
                "limit": limit,
                "to": self.whatsapp_number
            }
            
            if from_number:
                filter_params["from_"] = f"whatsapp:{from_number}" if not from_number.startswith("whatsapp:") else from_number
            
            # Fetch messages
            messages = self.client.messages.list(**filter_params)
            
            return [
                {
                    "sid": msg.sid,
                    "from": msg.from_,
                    "to": msg.to,
                    "body": msg.body,
                    "status": msg.status,
                    "date_sent": msg.date_sent.isoformat() if msg.date_sent else None,
                    "direction": msg.direction
                }
                for msg in messages
            ]
            
        except Exception as e:
            logger.error(f"Failed to retrieve message history: {str(e)}")
            return []
    
    def get_call_history(
        self,
        limit: int = 20,
        status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieve voice call history
        
        Args:
            limit: Maximum number of calls to retrieve
            status: Optional filter by call status (completed, busy, failed, etc.)
        
        Returns:
            List of call dictionaries
        """
        if not self.client:
            return []
        
        try:
            # Prepare filter parameters
            filter_params = {"limit": limit}
            
            if status:
                filter_params["status"] = status
            
            # Fetch calls
            calls = self.client.calls.list(**filter_params)
            
            return [
                {
                    "sid": call.sid,
                    "from": call.from_,
                    "to": call.to,
                    "status": call.status,
                    "duration": call.duration,
                    "start_time": call.start_time.isoformat() if call.start_time else None,
                    "end_time": call.end_time.isoformat() if call.end_time else None,
                    "direction": call.direction
                }
                for call in calls
            ]
            
        except Exception as e:
            logger.error(f"Failed to retrieve call history: {str(e)}")
            return []
    
    def handle_whatsapp_webhook(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process incoming WhatsApp webhook data
        
        Args:
            data: Webhook payload from Twilio
        
        Returns:
            Processed webhook data
        """
        try:
            return {
                "message_sid": data.get("MessageSid"),
                "from": data.get("From"),
                "to": data.get("To"),
                "body": data.get("Body"),
                "media_urls": [
                    data.get(f"MediaUrl{i}")
                    for i in range(int(data.get("NumMedia", 0)))
                ],
                "timestamp": datetime.now().isoformat(),
                "processed": True
            }
        except Exception as e:
            logger.error(f"Failed to process WhatsApp webhook: {str(e)}")
            return {"error": str(e), "processed": False}
    
    def generate_voice_response(self, text: str) -> str:
        """
        Generate TwiML for voice response
        
        Args:
            text: Text to be spoken
        
        Returns:
            TwiML XML string
        """
        response = VoiceResponse()
        response.say(text, voice='alice', language='en-US')
        return str(response)
    
    def generate_whatsapp_response(self, text: str) -> str:
        """
        Generate TwiML for WhatsApp response
        
        Args:
            text: Text message to send
        
        Returns:
            TwiML XML string
        """
        response = MessagingResponse()
        response.message(text)
        return str(response)


# Singleton instance
twilio_connector = TwilioConnector()
