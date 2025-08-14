"""
API Router for Twilio WhatsApp and Voice Integration
"""
from fastapi import APIRouter, HTTPException, Request, Response, Depends, Form
from fastapi.responses import PlainTextResponse, Response as FastAPIResponse
from pydantic import BaseModel
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from core.db import get_db
from services.connectors.twilio_connector import twilio_connector
from twilio.twiml.voice_response import VoiceResponse
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


def get_public_base_url(request: Request) -> str:
    """Resolve the public base URL for webhooks (ngrok or deployed).
    Prefers PUBLIC_BASE_URL from settings; falls back to request host.
    """
    from core.config import settings
    if getattr(settings, "public_base_url", None):
        return settings.public_base_url.rstrip("/")
    # Derive from request
    scheme = "https" if request.url.scheme == "https" else "http"
    host = request.headers.get("host") or request.url.netloc
    return f"{scheme}://{host}"


# Pydantic models for request/response
class WhatsAppMessage(BaseModel):
    to_number: str
    message: str
    media_url: Optional[str] = None


class VoiceCall(BaseModel):
    to_number: str
    message: Optional[str] = None
    twiml_url: Optional[str] = None


class MessageHistoryParams(BaseModel):
    limit: int = 20
    from_number: Optional[str] = None


class CallHistoryParams(BaseModel):
    limit: int = 20
    status: Optional[str] = None


@router.post("/whatsapp/send")
async def send_whatsapp_message(request: WhatsAppMessage):
    """
    Send a WhatsApp message via Twilio
    """
    try:
        result = twilio_connector.send_whatsapp_message(
            to_number=request.to_number,
            message=request.message,
            media_url=request.media_url
        )
        
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result.get("error", "Failed to send message"))
        
        return result
    except Exception as e:
        logger.error(f"Error sending WhatsApp message: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/voice/call")
async def make_voice_call(request: VoiceCall):
    """
    Initiate a voice call via Twilio
    """
    try:
        result = twilio_connector.make_voice_call(
            to_number=request.to_number,
            message=request.message,
            twiml_url=request.twiml_url
        )
        
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result.get("error", "Failed to make call"))
        
        return result
    except Exception as e:
        logger.error(f"Error making voice call: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/whatsapp/messages")
async def get_whatsapp_messages(
    limit: int = 20,
    from_number: Optional[str] = None
):
    """
    Retrieve WhatsApp message history
    """
    try:
        messages = twilio_connector.get_message_history(
            limit=limit,
            from_number=from_number
        )
        return {"messages": messages, "count": len(messages)}
    except Exception as e:
        logger.error(f"Error retrieving messages: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/voice/calls")
async def get_call_history(
    limit: int = 20,
    status: Optional[str] = None
):
    """
    Retrieve voice call history
    """
    try:
        calls = twilio_connector.get_call_history(
            limit=limit,
            status=status
        )
        return {"calls": calls, "count": len(calls)}
    except Exception as e:
        logger.error(f"Error retrieving call history: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/webhook/whatsapp")
async def whatsapp_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Webhook endpoint for incoming WhatsApp messages
    This endpoint receives messages from Twilio when someone sends a WhatsApp message
    """
    try:
        # Parse form data from Twilio
        form_data = await request.form()
        data = dict(form_data)
        
        # Process the webhook data
        processed_data = twilio_connector.handle_whatsapp_webhook(data)
        
        # Log the incoming message
        logger.info(f"Received WhatsApp message: {processed_data}")
        
        # Get message details
        message_body = data.get("Body", "")
        from_number = data.get("From", "").replace("whatsapp:", "")
        
# Generate intelligent response using OpenAI
        response_text = await generate_ai_response(message_body, from_number, db, request)
        
        # Generate TwiML response
        twiml = twilio_connector.generate_whatsapp_response(response_text)
        
        # Return with proper headers for TwiML
        return FastAPIResponse(
            content=twiml,
            media_type="text/xml",
            headers={"Content-Type": "text/xml"}
        )
        
    except Exception as e:
        logger.error(f"Error processing WhatsApp webhook: {str(e)}")
        # Return a friendly error message
        twiml = twilio_connector.generate_whatsapp_response(
            "I apologize, but I encountered an error processing your message. Please try again.")
        return FastAPIResponse(
            content=twiml,
            media_type="text/xml",
            headers={"Content-Type": "text/xml"}
        )


async def generate_ai_response(message: str, from_number: str, db: Session, request: Request) -> str:
    """
    Generate an intelligent response and trigger outbound calls
    """
    try:
        from core.config import settings
        # Use Convex session manager if available, otherwise fall back to local
        try:
            from services.convex_session import session_manager
        except ImportError:
            from services.user_session import session_manager
        import openai
        import re
        import urllib.parse
        
        # Check if user already has a session
        session = session_manager.get_session(from_number)
        
        # If user has completed a call recently, provide contextual response
        if session and session.get('call_completed'):
            logger.info(f"User {from_number} returning after call")
            user_name = session.get('name', 'there')
            user_email = session.get('email', '')
            
            # Check if they're asking for another call
            call_keywords = ['call me', 'can you call', 'give me a call', 'phone call', 'voice call', 'let\'s talk', 'prefer to talk', 'rather talk', 'switch to call', 'hop on a call', 'call you', 'discuss over a call', 'talk on the phone', 'speak with you']
            wants_call = any(keyword in message.lower() for keyword in call_keywords)
            
            if wants_call:
                # They want another call
                logger.info(f"User requested another call. Initiating...")
                
                # URL encode the parameters
                encoded_name = urllib.parse.quote(user_name) if user_name else ""
                encoded_email = urllib.parse.quote(user_email) if user_email else ""
                
                # Mark call as initiated
                session_manager.mark_call_initiated(from_number)
                
# Trigger outbound call
                base = get_public_base_url(request)
                result = twilio_connector.make_voice_call(
                    to_number=from_number,
                    twiml_url=f"{base}/twilio/webhook/voice/outbound?userName={encoded_name}\u0026userEmail={encoded_email}"
                )
                
                logger.info(f"Call initiation result: {result}")
                
                if user_name and user_name != "there":
                    return f"Of course, {user_name}! I'm calling you right now! 📞"
                else:
                    return f"Absolutely! I'm calling you right now! 📞"
            
            # Use OpenAI for continuing conversation
            if settings.openai_api_key:
                client = openai.OpenAI(api_key=settings.openai_api_key)
                system_prompt = f"""You are Eli, a warm AI Superconnector. 
                You just had a voice call with {user_name} about networking.
                Continue the conversation naturally on WhatsApp.
                Be helpful, warm, and focus on their networking goals.
                Keep responses short and conversational.
                Don't ask for their name/email again - you already have it.
                If they ask to call, you CAN call them - just let them know you're calling."""
                
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": message}
                    ],
                    max_tokens=100,
                    temperature=0.8
                )
                return response.choices[0].message.content.strip()
            else:
                return f"Great to continue our conversation, {user_name}! How can I help you build your network today?"
        
        # Regex to find email
        email_regex = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        emails = re.findall(email_regex, message)
        
        # Try to extract name (common patterns)
        name = None
        name_patterns = [
            r"(?:my name is|i'm|i am|this is|it's)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
            r"^([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+here",
            r"^([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)$"  # Just a name
        ]
        
        for pattern in name_patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                name = match.group(1).strip()
                break
        
        # Check if user explicitly wants a call
        call_keywords = ['call me', 'can you call', 'give me a call', 'phone call', 'voice call', 'let\'s talk', 'prefer to talk', 'rather talk', 'switch to call', 'hop on a call', 'call you', 'discuss over a call', 'talk on the phone', 'speak with you']
        wants_call = any(keyword in message.lower() for keyword in call_keywords)
        
        # Check if user provided email
        if emails:
            user_email = emails[0]
            
            # Extract name from email if not found
            if not name:
                # Try to get name from email (e.g., john.doe@example.com -> John)
                email_name = user_email.split('@')[0]
                email_name = email_name.replace('.', ' ').replace('_', ' ').replace('-', ' ')
                name = email_name.split()[0].capitalize() if email_name else "there"
            
            # Save to session
            session_manager.create_or_update_session(from_number, {
                'name': name,
                'email': user_email,
                'info_provided': True
            })
            
            logger.info(f"Email detected: {user_email}, Name: {name}")
            
            # Only make a call if user explicitly requested it
            if wants_call:
                logger.info(f"User requested a call. Initiating...")
                
                # URL encode the parameters
                encoded_name = urllib.parse.quote(name) if name else ""
                encoded_email = urllib.parse.quote(user_email)
                
                # Mark call as initiated
                session_manager.mark_call_initiated(from_number)
                
                # Trigger outbound call to the user with name parameter
                logger.info(f"Attempting to call {from_number} with TwiML URL")
                base = get_public_base_url(request)
                result = twilio_connector.make_voice_call(
                    to_number=from_number,
                    twiml_url=f"{base}/twilio/webhook/voice/outbound?userName={encoded_name}\u0026userEmail={encoded_email}"
                )
                
                logger.info(f"Call initiation result: {result}")
                
                # Return success message for call
                if name and name != "there":
                    return f"Perfect, {name}! I'm calling you right now! 📞"
                else:
                    return f"Great! I'm calling you right now! 📞"
            else:
                # Just acknowledge the email without calling
                if name and name != "there":
                    return f"Perfect, {name}! I have your email as {user_email}. Let's explore how I can help you build meaningful professional connections. What kind of networking goals do you have in mind?"
                else:
                    return f"Great! I have your email as {user_email}. Let's explore how I can help you build meaningful professional connections. What are your networking goals?"
        
        # Check if user wants a call - handle this BEFORE OpenAI
        if wants_call:
            # Check if we have their info from session
            if session and session.get('info_provided'):
                user_name = session.get('name', 'there')
                user_email = session.get('email', '')
                
                logger.info(f"User requested a call. Initiating with session info...")
                
                # URL encode the parameters
                encoded_name = urllib.parse.quote(user_name) if user_name else ""
                encoded_email = urllib.parse.quote(user_email) if user_email else ""
                
                # Mark call as initiated
                session_manager.mark_call_initiated(from_number)
                
# Trigger outbound call
                base = get_public_base_url(request)
                result = twilio_connector.make_voice_call(
                    to_number=from_number,
                    twiml_url=f"{base}/twilio/webhook/voice/outbound?userName={encoded_name}\u0026userEmail={encoded_email}"
                )
                
                logger.info(f"Call initiation result: {result}")
                
                if user_name and user_name != "there":
                    return f"Of course, {user_name}! I'm calling you right now! 📞"
                else:
                    return f"Absolutely! I'm calling you right now! 📞"
            else:
                # Need their info first
                return "I'd love to call you! Just need your email address first so I can connect with you."
        
        # If no contact info and not asking for a call, use OpenAI for chat
        if not settings.openai_api_key:
            # Fallback to rule-based responses
            return "Hello! I'm Eli, your AI Superconnector. To get started, please share your name and email address."
        
        client = openai.OpenAI(api_key=settings.openai_api_key)
        
        system_prompt = """You are Eli, a human-like AI Superconnector. Your goal is to:
        1. Get the user's name and email address naturally in conversation.
        2. Help them with networking goals via chat OR voice call (if they request it).
        3. Be warm, charismatic, and engaging.
        4. Keep your responses short, human, and conversational for WhatsApp.
        5. You CAN make voice calls if users ask - just say "I'm calling you now!"
        6. Do NOT automatically suggest calling when they give you their email.
        
        Example interactions:
        User: Hi
        Eli: Hey there! I'm Eli, your personal superconnector. To get started, could you tell me your name and email address?
        
        User: My name is Alex and my email is alex@example.com
        Eli: Perfect, Alex! I have your email. How can I help you build your professional network today?
        
        User: Can you call me?
        Eli: Absolutely! I'm calling you right now!
        
        User: What do you do?
        Eli: I help professionals like you build amazing connections! I can introduce you to the right people, help you expand your network, and open doors to new opportunities. What's your name and email so we can get started?
        """
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": message}
            ],
            max_tokens=100,
            temperature=0.8
        )
        
        return response.choices[0].message.content.strip()
        
    except Exception as e:
        logger.error(f"Error in AI response/call trigger: {str(e)}")
        return "I'm here to help you connect! Please start by sharing your name and email address."


@router.post("/webhook/voice")
async def voice_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Webhook endpoint for voice call handling
    This endpoint receives call events from Twilio
    """
    try:
        # Parse form data from Twilio
        form_data = await request.form()
        data = dict(form_data)
        
        # Log the call event
        logger.info(f"Received voice call event: {data}")
        
        # Get call details
        from_number = data.get("From", "")
        call_status = data.get("CallStatus", "")
        
# Generate intelligent voice response
        response_twiml = generate_voice_twiml(request, from_number, call_status)
        
        # Return TwiML response with proper headers
        return FastAPIResponse(
            content=response_twiml,
            media_type="text/xml",
            headers={"Content-Type": "text/xml"}
        )
        
    except Exception as e:
        logger.error(f"Error processing voice webhook: {str(e)}")
        # Return a basic response
        error_twiml = twilio_connector.generate_voice_response(
            "Sorry, there was an error processing your call. Please try again later.")
        return FastAPIResponse(
            content=error_twiml,
            media_type="text/xml",
            headers={"Content-Type": "text/xml"}
        )


def generate_voice_twiml(request: Request, from_number: str, call_status: str) -> str:
    """
    Generate natural, conversational TwiML for voice calls
    """
    from twilio.twiml.voice_response import VoiceResponse, Gather
    import random
    
    response = VoiceResponse()
    
    # Handle incoming call with natural conversation
    if call_status in ["ringing", "in-progress", "answered"]:
        # Natural, warm greeting with emotions
        greetings = [
            "Hey there! This is Eli. I'm so glad you called! What's your name?",
            "Hi! It's Eli here. Great to hear from you! May I ask who I'm speaking with?",
            "Hello! This is Eli, your superconnector. I'm excited to chat with you! What's your name?",
            "Hey! Eli here. Thanks for reaching out! I'd love to know your name."
        ]
        
        # Use Gather to collect speech input
        gather = Gather(
            input="speech",
            speechTimeout="3",
            timeout=10,
action=f"{get_public_base_url(request)}/twilio/webhook/voice/conversation",
            method="POST",
            language="en-US",
            enhanced=True,  # Better speech recognition
            speechModel="phone_call",  # Optimized for phone calls
            profanityFilter=False  # Allow natural speech
        )
        
        # Use Polly neural voice for more natural speech
        gather.say(
            random.choice(greetings),
            voice="Polly.Matthew-Neural",  # Most natural male voice
            language="en-US"
        )
        
        response.append(gather)
        
        # If no response, gently prompt again
        response.say(
            "Hmm, I didn't catch that. No worries! Feel free to tell me your name when you're ready.",
            voice="Polly.Matthew-Neural"
        )
        response.redirect(f"{get_public_base_url(request)}/twilio/webhook/voice")
        
    else:
        # Natural closing
        response.say(
            "It was great talking with you! Looking forward to connecting again soon. Have an amazing day!",
            voice="Polly.Matthew-Neural"
        )
        response.hangup()
        
    return str(response)


@router.post("/webhook/voice/conversation")
async def voice_conversation_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Handle natural voice conversations
    """
    try:
        form_data = await request.form()
        data = dict(form_data)
        
        # Get what the user said
        speech_result = data.get("SpeechResult", "")
        from_number = data.get("From", "")
        confidence = float(data.get("Confidence", 0.0))
        
        logger.info(f"Voice input from {from_number}: '{speech_result}' (confidence: {confidence})")
        
        response = VoiceResponse()
        
        if speech_result:
            # Generate AI response based on what they said
            ai_response = await generate_voice_ai_response(speech_result, from_number, db)
            
            # Natural conversation flow
            response.say(
                ai_response,
                voice="Polly.Matthew-Neural",
                language="en-US"
            )
            
            # Pause for natural flow
            response.pause(length=1)
            
            # Thank them and end naturally
            response.say(
                "It was really great talking with you! I'll follow up with you on WhatsApp. Have an amazing day!",
                voice="Polly.Matthew-Neural"
            )
            
            # Send follow-up WhatsApp message
            if from_number:
                follow_up = f"Hi {speech_result}! 👋 This is Eli following up from our call. I'm here to help you build meaningful connections. What kind of professional connections are you looking to make?"
                twilio_connector.send_whatsapp_message(
                    to_number=from_number,
                    message=follow_up
                )
        else:
            # Couldn't understand
            response.say(
                "I'm sorry, I couldn't quite catch that. Could you tell me your name again?",
                voice="Polly.Matthew-Neural"
            )
            response.redirect(f"{get_public_base_url(request)}/twilio/webhook/voice")
        
        response.hangup()
        
        return FastAPIResponse(
            content=str(response),
            media_type="text/xml",
            headers={"Content-Type": "text/xml"}
        )
        
    except Exception as e:
        logger.error(f"Error in voice conversation: {str(e)}")
        response = VoiceResponse()
        response.say(
            "Sorry about that! Let's continue on WhatsApp. I'll message you right away!",
            voice="Polly.Matthew-Neural"
        )
        response.hangup()
        return FastAPIResponse(
            content=str(response),
            media_type="text/xml"
        )


async def generate_voice_ai_response(speech: str, from_number: str, db: Session) -> str:
    """
    Generate natural AI response for voice conversation
    """
    try:
        from core.config import settings
        import openai
        
        if not settings.openai_api_key:
            # Fallback response
            return f"Nice to meet you, {speech}! I'm Eli, and I specialize in helping professionals like you expand their network and make meaningful connections. Let me follow up with you on WhatsApp where we can chat more about your networking goals."
        
        # Use OpenAI for natural response
        client = openai.OpenAI(api_key=settings.openai_api_key)
        
        system_prompt = """You are Eli, a warm, charismatic superconnector having a phone conversation. 
        You just asked for their name and they responded. 
        Your response should:
        1. Acknowledge their name warmly
        2. Briefly introduce yourself as someone who helps people build meaningful professional connections
        3. Mention you'll follow up on WhatsApp for a deeper conversation
        4. Keep it natural, conversational, and under 15 seconds of speaking
        5. Sound genuinely excited to help them
        Do NOT ask more questions - you'll continue on WhatsApp."""
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"My name is {speech}"}
            ],
            max_tokens=100,
            temperature=0.9  # More creative/natural
        )
        
        return response.choices[0].message.content.strip()
        
    except Exception as e:
        logger.error(f"Error generating voice AI response: {str(e)}")
        return f"Great to meet you, {speech}! I'm Eli, and I help professionals build amazing connections. Let me message you on WhatsApp right now so we can explore how I can help you expand your network!"


@router.post("/webhook/voice/outbound")
async def voice_outbound_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Handle outbound voice calls initiated from WhatsApp with proper voice interaction
    """
    try:
        from twilio.twiml.voice_response import Gather
        from services.user_session import session_manager
        import random
        
        # Parse form data and query params
        form_data = await request.form()
        data = dict(form_data)
        
        # Get user info from query params (passed from WhatsApp trigger)
        user_name = request.query_params.get("userName", "")
        user_email = request.query_params.get("userEmail", "")
        
        # Get call details
        call_status = data.get("CallStatus", "")
        to_number = data.get("To", "")
        direction = data.get("Direction", "")
        
        logger.info(f"Outbound call webhook - To: {to_number}, Status: {call_status}, Direction: {direction}")
        logger.info(f"User details - Name: {user_name}, Email: {user_email}")
        
        response = VoiceResponse()
        
        # Handle different call statuses
        if call_status == "initiated":
            logger.info("Call initiated, waiting...")
            response.pause(length=1)
            
        elif call_status in ["ringing", "in-progress", "answered"]:
            from core.config import settings as app_settings
            logger.info(f"Call {call_status} - Using {'TTS fallback' if app_settings.force_tts_fallback else 'hybrid TTS + Media Streams'}")
            
            # Start with TTS greeting to ensure immediate audio
            if user_name and user_name != "there":
                greeting = f"Hey {user_name}! This is Eli calling. One moment while I connect you."
            else:
                greeting = "Hey there! This is Eli. One moment while I connect you."
            
            response.say(greeting, voice="Polly.Matthew-Neural", language="en-US")
            
            if app_settings.force_tts_fallback or not app_settings.openai_api_key:
                # Fallback: simple TTS conversational flow without Media Streams
                gather = Gather(
                    input="speech",
                    speechTimeout="3",
                    timeout=10,
                    action=f"{get_public_base_url(request)}/twilio/webhook/voice/outbound/response?userName={user_name}&userEmail={user_email}",
                    method="POST",
                    language="en-US"
                )
                gather.say("I'd love to help you grow your network. Tell me briefly what kind of connections you're looking for.", voice="alice")
                response.append(gather)
                response.say("I'll also follow up with you on WhatsApp right after this call.", voice="alice")
                response.hangup()
            else:
                # Set up Media Streams for real-time conversation using Connect
                from twilio.twiml.voice_response import Connect
                
                try:
                    # Use Connect for bidirectional Media Streams
                    # Connect is the recommended way for bidirectional audio
                    connect = Connect()

                    # Build WebSocket URL for realtime bridge
                    base = get_public_base_url(request)
                    ws_scheme = "wss" if base.startswith("https://") else "ws"
                    host = base.split("://", 1)[1]
                    ws_url = f"{ws_scheme}://{host}/ws/realtime-bridge"
                    logger.info(f"Setting up Media Stream via Connect with URL: {ws_url}")
                    
                    # Configure the stream for bidirectional audio with BOTH tracks
                    stream = connect.stream(
                        url=ws_url,
                        track="both"  # Enable BOTH inbound and outbound audio tracks
                    )
                    
                    # Pass user information as custom parameters
                    stream.parameter(name="callSid", value=data.get('CallSid', ''))
                    if user_name:
                        stream.parameter(name="userName", value=user_name)
                    if user_email:
                        stream.parameter(name="userEmail", value=user_email)
                    
                    response.append(connect)
                    
                    logger.info(f"Media Stream via Connect configured for call {data.get('CallSid', 'unknown')}")
                    
                    # Add a fallback pause to prevent immediate hangup if WebSocket fails
                    # This gives time for the WebSocket to establish
                    response.pause(length=30)  # Keep call open for 30 seconds as fallback
                    
                    # Add a closing message
                    response.say(
                        "Thanks for the call! I'll follow up with you on WhatsApp.",
                        voice="Polly.Matthew-Neural",
                        language="en-US"
                    )
                
                except Exception as e:
                    logger.error(f"Failed to setup Media Stream via Connect: {str(e)}")
                    # Fallback to TTS if Media Stream fails
                    response.say(
                        "I'm having trouble with the real-time connection. Let me follow up with you on WhatsApp instead.",
                        voice="Polly.Matthew-Neural",
                        language="en-US"
                    )
            
            # Do NOT hang up here; Connect keeps the call open
            
        else:
            logger.info(f"Unexpected call status: {call_status}")
            response.say("Thank you for your time!", voice="alice")
            response.hangup()
        
        xml_response = str(response)
        logger.info(f"Returning TwiML: {xml_response[:200]}...")
        
        return FastAPIResponse(
            content=xml_response,
            media_type="text/xml",
            headers={"Content-Type": "text/xml"}
        )
        
    except Exception as e:
        logger.error(f"Critical error in outbound voice webhook: {str(e)}", exc_info=True)
        response = VoiceResponse()
        response.say(
            "I apologize for the technical issue. Let me follow up with you on WhatsApp instead!",
            voice="alice"
        )
        response.hangup()
        return FastAPIResponse(
            content=str(response),
            media_type="text/xml"
        )


@router.post("/webhook/voice/outbound/timeout")
async def voice_outbound_timeout_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Handle timeout when user doesn't respond during outbound call
    """
    try:
        # Use Convex session manager if available, otherwise fall back to local
        try:
            from services.convex_session import session_manager
        except ImportError:
            from services.user_session import session_manager
        
        form_data = await request.form()
        data = dict(form_data)
        
        # Get user info from query params
        user_name = request.query_params.get("userName", "")
        user_email = request.query_params.get("userEmail", "")
        
        to_number = data.get("To", "")
        
        logger.info(f"Call timeout for {to_number}")
        
        response = VoiceResponse()
        
        # Try once more with a simpler prompt
        gather = Gather(
            input="speech",
            speechTimeout="3",
            timeout=5,  # Shorter timeout
action=f"{get_public_base_url(request)}/twilio/webhook/voice/outbound/response?userName={user_name}&userEmail={user_email}",
            method="POST",
            language="en-US"
        )
        
        gather.say(
            "I'm here to help you expand your professional network. Just tell me what you're looking for!",
            voice="alice"
        )
        
        response.append(gather)
        
        # If still no response, gracefully end the call
        response.say(
            "No worries if now isn't a good time! I'll send you a message on WhatsApp where we can continue at your convenience. Have a great day!",
            voice="alice"
        )
        
        # Send WhatsApp follow-up
        if to_number:
            session_manager.mark_call_completed(to_number)
            follow_up = f"Hi {user_name}! 👋 I just tried calling but I think the timing wasn't ideal. No worries! Let's chat here on WhatsApp when you're ready. What kind of professional connections would help you most right now?"
            twilio_connector.send_whatsapp_message(
                to_number=to_number,
                message=follow_up
            )
        
        response.hangup()
        
        return FastAPIResponse(
            content=str(response),
            media_type="text/xml",
            headers={"Content-Type": "text/xml"}
        )
        
    except Exception as e:
        logger.error(f"Error in timeout handler: {str(e)}")
        response = VoiceResponse()
        response.say("Let's continue on WhatsApp!", voice="alice")
        response.hangup()
        return FastAPIResponse(
            content=str(response),
            media_type="text/xml"
        )


@router.post("/webhook/voice/outbound/response")
async def voice_outbound_response_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Handle user's speech response during outbound call
    """
    try:
        # Use Convex session manager if available, otherwise fall back to local
        try:
            from services.convex_session import session_manager
        except ImportError:
            from services.user_session import session_manager
        from services.openai_voice import openai_voice
        
        form_data = await request.form()
        data = dict(form_data)
        
        # Get user info from query params
        user_name = request.query_params.get("userName", "")
        user_email = request.query_params.get("userEmail", "")
        
        # Get what the user said
        speech_result = data.get("SpeechResult", "")
        to_number = data.get("To", "")
        confidence = float(data.get("Confidence", 0.0))
        
        logger.info(f"User responded: '{speech_result}' (confidence: {confidence})")
        
        response = VoiceResponse()
        
        if speech_result and confidence > 0.5:
            # Generate personalized AI response
            ai_response = await generate_outbound_ai_response(speech_result, user_name, user_email, db)
            
            # Try to use OpenAI voice
            audio_url = None
            if openai_voice.client:
                audio_url = await openai_voice.generate_conversation_audio(ai_response, "echo")
            
            if audio_url:
                response.play(audio_url)
            else:
                response.say(ai_response, voice="alice")
            
            response.pause(length=1)
            
            # Closing message
            closing = "This has been really great! I'll send you some personalized connection suggestions on WhatsApp. Looking forward to helping you grow your network!"
            
            closing_audio = None
            if openai_voice.client:
                closing_audio = await openai_voice.generate_conversation_audio(closing, "echo")
            
            if closing_audio:
                response.play(closing_audio)
            else:
                response.say(closing, voice="alice")
            
            # Mark call as completed
            if to_number:
                session_manager.mark_call_completed(to_number)
                
                # Send follow-up WhatsApp
                follow_up = f"Hi {user_name}! 🌟 Great talking with you just now! Based on what you shared about {speech_result[:50]}..., I'm already thinking of some amazing connections for you. What's your LinkedIn profile URL so I can find the best matches?"
                twilio_connector.send_whatsapp_message(
                    to_number=to_number,
                    message=follow_up
                )
        else:
            response.say(
                "I didn't quite catch that, but no worries! Let's continue our conversation on WhatsApp where it's easier to share details.",
                voice="alice"
            )
            
            if to_number:
                session_manager.mark_call_completed(to_number)
                follow_up = f"Hi {user_name}! I tried calling but couldn't hear your response clearly. Let's continue here on WhatsApp. What kind of professional connections are you looking to make?"
                twilio_connector.send_whatsapp_message(
                    to_number=to_number,
                    message=follow_up
                )
        
        response.hangup()
        
        return FastAPIResponse(
            content=str(response),
            media_type="text/xml",
            headers={"Content-Type": "text/xml"}
        )
        
    except Exception as e:
        logger.error(f"Error in voice response handler: {str(e)}")
        response = VoiceResponse()
        response.say("Let's continue on WhatsApp!", voice="alice")
        response.hangup()
        return FastAPIResponse(
            content=str(response),
            media_type="text/xml"
        )


@router.post("/webhook/voice/outbound/conversation")
async def voice_outbound_conversation_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Handle outbound call conversations
    """
    try:
        from services.user_session import session_manager
        
        form_data = await request.form()
        data = dict(form_data)
        
        # Get user info from query params
        user_name = request.query_params.get("userName", "")
        user_email = request.query_params.get("userEmail", "")
        
        # Get what the user said
        speech_result = data.get("SpeechResult", "")
        to_number = data.get("To", "")
        confidence = float(data.get("Confidence", 0.0))
        
        logger.info(f"Outbound conversation: '{speech_result}' (confidence: {confidence})")
        
        # Mark call as completed in session
        session_manager.mark_call_completed(to_number)
        
        response = VoiceResponse()
        
        if speech_result:
            # Generate personalized AI response
            ai_response = await generate_outbound_ai_response(speech_result, user_name, user_email, db)
            
            response.say(
                ai_response,
                voice="Polly.Matthew-Neural",
                language="en-US"
            )
            
            response.pause(length=1)
            
            # Close the call naturally
            response.say(
                "This has been really great! I'll send you some personalized connection suggestions on WhatsApp. Looking forward to helping you grow your network!",
                voice="Polly.Matthew-Neural"
            )
            
            # Send follow-up WhatsApp
            if to_number:
                follow_up = f"Hi {user_name}! 🌟 Great talking with you just now! Based on what you shared about {speech_result[:50]}..., I'm already thinking of some amazing connections for you. Let me put together some personalized introductions. What's your LinkedIn profile URL so I can find the best matches?"
                twilio_connector.send_whatsapp_message(
                    to_number=to_number,
                    message=follow_up
                )
        else:
            response.say(
                "I didn't quite catch that, but no worries! Let's continue our conversation on WhatsApp where it's easier to share details.",
                voice="Polly.Matthew-Neural"
            )
        
        response.hangup()
        
        return FastAPIResponse(
            content=str(response),
            media_type="text/xml",
            headers={"Content-Type": "text/xml"}
        )
        
    except Exception as e:
        logger.error(f"Error in outbound conversation: {str(e)}")
        response = VoiceResponse()
        response.say(
            "Let's continue on WhatsApp - I'll message you right now!",
            voice="Polly.Matthew-Neural"
        )
        response.hangup()
        return FastAPIResponse(
            content=str(response),
            media_type="text/xml"
        )


async def generate_outbound_ai_response(speech: str, user_name: str, user_email: str, db: Session) -> str:
    """
    Generate AI response for outbound call conversations
    """
    try:
        from core.config import settings
        import openai
        
        if not settings.openai_api_key:
            return f"That's fantastic! Based on what you're looking for, I can definitely help you connect with the right people. I work with a network of professionals across various industries, and I'll find the perfect matches for your goals."
        
        client = openai.OpenAI(api_key=settings.openai_api_key)
        
        system_prompt = f"""You are Eli, a warm, charismatic AI superconnector on a phone call with {user_name}.
        They just told you about their networking goals.
        Your response should:
        1. Show genuine enthusiasm about their goals
        2. Briefly mention how you can help them achieve those specific goals
        3. Build excitement about the connections you'll make for them
        4. Keep it natural, conversational, and under 15 seconds
        5. Do NOT ask more questions - you'll continue on WhatsApp
        6. Sound confident and knowledgeable about networking
        
        Their email: {user_email}
        What they said: {speech}
        """
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": speech}
            ],
            max_tokens=120,
            temperature=0.85
        )
        
        return response.choices[0].message.content.strip()
        
    except Exception as e:
        logger.error(f"Error generating outbound AI response: {str(e)}")
        return "That sounds amazing! I can definitely help you with that. I have connections across various industries and I'm already thinking of some perfect matches for you. This is going to be exciting!"


@router.post("/webhook/voice/menu")
async def voice_menu_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Handle voice menu selections
    """
    try:
        form_data = await request.form()
        data = dict(form_data)
        
        digits = data.get("Digits", "")
        from_number = data.get("From", "")
        
        logger.info(f"Voice menu selection: {digits} from {from_number}")
        
        response = VoiceResponse()
        
        if digits == "1":
            # Networking services
            response.say(
                "Eli helps you build meaningful professional connections through "
                "AI-powered matching, automated outreach, and intelligent conversation management. "
                "We integrate with LinkedIn, email, and WhatsApp to expand your network effectively. "
                "To get started, send us a WhatsApp message at this same number.",
                voice="alice"
            )
            response.pause(length=2)
            response.say("Thank you for calling Eli. Have a great day!", voice="alice")
            
        elif digits == "2":
            # Schedule a meeting
            response.say(
                "To schedule a meeting, please send us a WhatsApp message with your preferred dates and times. "
                "We'll coordinate with all participants and find the best time for everyone. "
                "You can reach us on WhatsApp at the same number you just called.",
                voice="alice"
            )
            response.pause(length=1)
            response.say("Thank you for choosing Eli!", voice="alice")
            
        elif digits == "3":
            # Leave a message (record voicemail)
            response.say(
                "Please leave your message after the beep. Press the pound key when finished.",
                voice="alice"
            )
            response.record(
                max_length=120,
                finish_on_key="#",
                transcribe=True,
                transcribe_callback="/twilio/webhook/voice/transcription"
            )
            response.say("Thank you for your message. We'll get back to you soon!", voice="alice")
            
        elif digits == "4":
            # WhatsApp support
            response.say(
                f"Great choice! You can reach Eli on WhatsApp at {from_number.replace('+', '')}. "
                "Send us a message saying 'Hi' to get started. "
                "We're available 24/7 to help you build meaningful connections.",
                voice="alice"
            )
            response.pause(length=1)
            response.say("Looking forward to connecting with you on WhatsApp!", voice="alice")
            
        else:
            # Invalid input
            response.say(
                "Sorry, that's not a valid option. Please call back to try again.",
                voice="alice"
            )
        
        response.hangup()
        
        return FastAPIResponse(
            content=str(response),
            media_type="text/xml",
            headers={"Content-Type": "text/xml"}
        )
        
    except Exception as e:
        logger.error(f"Error in voice menu: {str(e)}")
        response = VoiceResponse()
        response.say("Sorry, an error occurred. Please try again later.", voice="alice")
        response.hangup()
        return FastAPIResponse(
            content=str(response),
            media_type="text/xml"
        )


@router.post("/webhook/voice/transcription")
async def voice_transcription_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Handle voicemail transcriptions
    """
    try:
        form_data = await request.form()
        data = dict(form_data)
        
        transcription = data.get("TranscriptionText", "")
        from_number = data.get("From", "")
        recording_url = data.get("RecordingUrl", "")
        
        logger.info(f"Voicemail from {from_number}: {transcription}")
        
        # Here you could:
        # 1. Store the voicemail in database
        # 2. Send notification via WhatsApp
        # 3. Process with AI for follow-up
        
        # For now, just acknowledge
        return FastAPIResponse(
            content="",
            status_code=204
        )
        
    except Exception as e:
        logger.error(f"Error processing transcription: {str(e)}")
        return FastAPIResponse(content="", status_code=204)


@router.get("/status")
async def get_twilio_status():
    """
    Check Twilio integration status
    """
    return {
        "configured": twilio_connector.client is not None,
        "whatsapp_number": twilio_connector.whatsapp_number if twilio_connector.client else None,
        "phone_number": twilio_connector.phone_number if twilio_connector.client else None,
        "service": "Twilio",
        "features": ["WhatsApp", "Voice Calls"]
    }
