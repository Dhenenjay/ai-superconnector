"""
Persistent user session tracking with file storage
"""
from datetime import datetime, timedelta
from typing import Dict, Optional
import logging
import json
import os
from pathlib import Path

logger = logging.getLogger(__name__)

class UserSessionManager:
    def __init__(self):
        self.session_timeout = timedelta(hours=24)  # Sessions expire after 24 hours
        
        # Create persistent storage directory
        self.storage_dir = Path("C:/Users/Dhenenjay/ai-superconnector/.data/sessions")
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.session_file = self.storage_dir / "user_sessions.json"
        
        # Load existing sessions from file
        self.sessions: Dict[str, Dict] = self._load_sessions()
    
    def get_session(self, phone_number: str) -> Optional[Dict]:
        """Get user session data"""
        phone_number = self._normalize_phone(phone_number)
        session = self.sessions.get(phone_number)
        
        if session:
            # Check if session expired
            if datetime.now() - session.get('last_activity', datetime.now()) > self.session_timeout:
                logger.info(f"Session expired for {phone_number}")
                del self.sessions[phone_number]
                return None
            
            # Update last activity
            session['last_activity'] = datetime.now()
            return session
        
        return None
    
    def create_or_update_session(self, phone_number: str, data: Dict) -> Dict:
        """Create or update user session"""
        phone_number = self._normalize_phone(phone_number)
        
        if phone_number in self.sessions:
            self.sessions[phone_number].update(data)
            self.sessions[phone_number]['last_activity'] = datetime.now()
        else:
            self.sessions[phone_number] = {
                **data,
                'created_at': datetime.now(),
                'last_activity': datetime.now(),
                'phone_number': phone_number
            }
        
        self._save_sessions()  # Save after update
        logger.info(f"Session updated for {phone_number}: {self.sessions[phone_number]}")
        return self.sessions[phone_number]
    
    def has_provided_info(self, phone_number: str) -> bool:
        """Check if user has already provided name and email"""
        session = self.get_session(phone_number)
        if session:
            return bool(session.get('name') and session.get('email'))
        return False
    
    def mark_call_initiated(self, phone_number: str):
        """Mark that a call has been initiated for this user"""
        phone_number = self._normalize_phone(phone_number)
        if phone_number in self.sessions:
            self.sessions[phone_number]['call_initiated'] = True
            self.sessions[phone_number]['call_time'] = datetime.now()
            self._save_sessions()  # Save after update
    
    def mark_call_completed(self, phone_number: str):
        """Mark that a call has been completed for this user"""
        phone_number = self._normalize_phone(phone_number)
        if phone_number in self.sessions:
            self.sessions[phone_number]['call_completed'] = True
            self.sessions[phone_number]['call_completed_time'] = datetime.now()
            self._save_sessions()  # Save after update
    
    def _normalize_phone(self, phone_number: str) -> str:
        """Normalize phone number by removing whatsapp: prefix"""
        return phone_number.replace('whatsapp:', '').strip()
    
    def clear_session(self, phone_number: str):
        """Clear a user's session"""
        phone_number = self._normalize_phone(phone_number)
        if phone_number in self.sessions:
            del self.sessions[phone_number]
            self._save_sessions()
            logger.info(f"Session cleared for {phone_number}")
    
    def _load_sessions(self) -> Dict:
        """Load sessions from file"""
        if self.session_file.exists():
            try:
                with open(self.session_file, 'r') as f:
                    data = json.load(f)
                    # Convert string dates back to datetime
                    for phone, session in data.items():
                        for key in ['created_at', 'last_activity', 'call_time', 'call_completed_time']:
                            if key in session and session[key]:
                                session[key] = datetime.fromisoformat(session[key])
                    logger.info(f"Loaded {len(data)} sessions from file")
                    return data
            except Exception as e:
                logger.error(f"Error loading sessions: {e}")
        return {}
    
    def _save_sessions(self):
        """Save sessions to file"""
        try:
            # Convert datetime to string for JSON serialization
            data = {}
            for phone, session in self.sessions.items():
                data[phone] = session.copy()
                for key in ['created_at', 'last_activity', 'call_time', 'call_completed_time']:
                    if key in data[phone] and isinstance(data[phone][key], datetime):
                        data[phone][key] = data[phone][key].isoformat()
            
            with open(self.session_file, 'w') as f:
                json.dump(data, f, indent=2)
            logger.info(f"Saved {len(data)} sessions to file")
        except Exception as e:
            logger.error(f"Error saving sessions: {e}")

# Global session manager instance
session_manager = UserSessionManager()
