"""
Session management using Convex database
"""
from datetime import datetime, timedelta
from typing import Dict, Optional
import logging
import os
from services.convex_client import convex_client

logger = logging.getLogger(__name__)


class ConvexSessionManager:
    """Manages user sessions using Convex database"""
    
    def __init__(self):
        self.session_timeout = timedelta(hours=24)  # Sessions expire after 24 hours
        self.client = convex_client
        logger.info("Initialized Convex session manager")
    
    def get_session(self, phone_number: str) -> Optional[Dict]:
        """Get user session data from Convex"""
        phone_number = self._normalize_phone(phone_number)
        
        try:
            # Query Convex for the session
            result = self.client.query("sessions:get", {"phoneNumber": phone_number})
            
            if result:
                # Check if session expired
                last_activity = datetime.fromisoformat(result.get('lastActivity', datetime.now().isoformat()))
                if datetime.now() - last_activity > self.session_timeout:
                    logger.info(f"Session expired for {phone_number}")
                    # Delete expired session
                    self.client.mutation("sessions:deleteSession", {"phoneNumber": phone_number})
                    return None
                
                # Update last activity
                self.client.mutation("sessions:updateActivity", {
                    "phoneNumber": phone_number,
                    "lastActivity": datetime.now().isoformat()
                })
                
                return result
        except Exception as e:
            logger.error(f"Error getting session from Convex: {e}")
        
        return None
    
    def create_or_update_session(self, phone_number: str, data: Dict) -> Dict:
        """Create or update user session in Convex"""
        phone_number = self._normalize_phone(phone_number)
        
        try:
            session_data = {
                "phoneNumber": phone_number,
                "name": data.get('name', ''),
                "email": data.get('email', ''),
                "callInitiated": data.get('call_initiated', False),
                "callCompleted": data.get('call_completed', False),
                "infoProvided": data.get('info_provided', False),
                "lastActivity": datetime.now().isoformat(),
                "createdAt": data.get('created_at', datetime.now().isoformat())
            }
            
            # Upsert session in Convex
            result = self.client.mutation("sessions:upsert", session_data)
            
            logger.info(f"Session updated in Convex for {phone_number}: {result}")
            return result if result else session_data
            
        except Exception as e:
            logger.error(f"Error updating session in Convex: {e}")
            # Return the data even if Convex fails
            return data
    
    def has_provided_info(self, phone_number: str) -> bool:
        """Check if user has already provided name and email"""
        session = self.get_session(phone_number)
        if session:
            return bool(session.get('name') and session.get('email'))
        return False
    
    def mark_call_initiated(self, phone_number: str):
        """Mark that a call has been initiated for this user"""
        phone_number = self._normalize_phone(phone_number)
        session = self.get_session(phone_number) or {}
        session['call_initiated'] = True
        session['call_time'] = datetime.now().isoformat()
        self.create_or_update_session(phone_number, session)
    
    def mark_call_completed(self, phone_number: str):
        """Mark that a call has been completed for this user"""
        phone_number = self._normalize_phone(phone_number)
        session = self.get_session(phone_number) or {}
        session['call_completed'] = True
        session['call_completed_time'] = datetime.now().isoformat()
        self.create_or_update_session(phone_number, session)
    
    def _normalize_phone(self, phone_number: str) -> str:
        """Normalize phone number by removing whatsapp: prefix"""
        return phone_number.replace('whatsapp:', '').strip()
    
    def clear_session(self, phone_number: str):
        """Clear a user's session"""
        phone_number = self._normalize_phone(phone_number)
        try:
            self.client.mutation("sessions:deleteSession", {"phoneNumber": phone_number})
            logger.info(f"Session cleared in Convex for {phone_number}")
        except Exception as e:
            logger.error(f"Error clearing session in Convex: {e}")


# Create appropriate session manager based on environment
def get_session_manager():
    """Get the appropriate session manager based on environment"""
    # Check if we have Convex credentials
    if os.getenv("CONVEX_URL") and os.getenv("CONVEX_DEPLOY_KEY"):
        logger.info("Using Convex for session management")
        return ConvexSessionManager()
    else:
        logger.info("Using local session management")
        # Fall back to the regular session manager
        from services.user_session import UserSessionManager
        return UserSessionManager()


# Global session manager instance
session_manager = get_session_manager()
