"""
Persistent user session tracking with database storage for production
"""
from datetime import datetime, timedelta
from typing import Dict, Optional
import logging
import json
import os
from pathlib import Path
from sqlalchemy import create_engine, Column, String, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session as DBSession
from core.config import settings

logger = logging.getLogger(__name__)

Base = declarative_base()

class UserSession(Base):
    __tablename__ = "user_sessions"
    
    phone_number = Column(String(50), primary_key=True)
    session_data = Column(Text)  # JSON string
    created_at = Column(DateTime, default=datetime.now)
    last_activity = Column(DateTime, default=datetime.now)

class UserSessionManager:
    def __init__(self):
        self.session_timeout = timedelta(hours=24)  # Sessions expire after 24 hours
        
        # Temporarily disable database to fix immediate issue - use in-memory storage
        # TODO: Add proper database support later
        self.use_database = False  # Disabled for now due to SQLite issues on Render
        
        if self.use_database:
            # Initialize database connection
            # Fix SQLite URL format - needs sqlite:/// with absolute path or sqlite:// for relative
            if settings.database_url and "sqlite" in settings.database_url:
                # Fix malformed SQLite URLs
                database_url = settings.database_url.replace("sqlite+sqlite://", "sqlite:///")
            else:
                # Use a simple SQLite database for production if no database URL is set
                database_url = "sqlite:///data/sessions.db"
            
            logger.info(f"Attempting to use database URL: {database_url}")
            
            try:
                # Create data directory if it doesn't exist
                import os
                os.makedirs("data", exist_ok=True)
                
                self.engine = create_engine(database_url)
                Base.metadata.create_all(self.engine)
                self.SessionLocal = sessionmaker(bind=self.engine)
                logger.info("Successfully initialized database for session storage")
                self.sessions = {}  # Cache for performance
            except Exception as e:
                logger.error(f"Failed to initialize database: {e}")
                logger.info("Falling back to in-memory storage")
                self.use_database = False
                self.sessions = {}
        else:
            # Fallback to file storage for local development
            self.storage_dir = Path(".data/sessions")
            self.storage_dir.mkdir(parents=True, exist_ok=True)
            self.session_file = self.storage_dir / "user_sessions.json"
            logger.info("Using file storage for session storage")
            # Load existing sessions from file
            self.sessions: Dict[str, Dict] = self._load_sessions()
    
    def get_session(self, phone_number: str) -> Optional[Dict]:
        """Get user session data"""
        phone_number = self._normalize_phone(phone_number)
        
        if self.use_database:
            # Get from database
            db: DBSession = self.SessionLocal()
            try:
                db_session = db.query(UserSession).filter_by(phone_number=phone_number).first()
                if db_session:
                    # Check if session expired
                    if datetime.now() - db_session.last_activity > self.session_timeout:
                        logger.info(f"Session expired for {phone_number}")
                        db.delete(db_session)
                        db.commit()
                        return None
                    
                    # Update last activity
                    db_session.last_activity = datetime.now()
                    db.commit()
                    
                    # Parse and return session data
                    session_data = json.loads(db_session.session_data)
                    session_data['last_activity'] = db_session.last_activity
                    return session_data
            finally:
                db.close()
            return None
        else:
            # File-based storage (local dev)
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
        
        if self.use_database:
            # Database storage
            db: DBSession = self.SessionLocal()
            try:
                db_session = db.query(UserSession).filter_by(phone_number=phone_number).first()
                
                if db_session:
                    # Update existing session
                    existing_data = json.loads(db_session.session_data)
                    existing_data.update(data)
                    db_session.session_data = json.dumps(existing_data)
                    db_session.last_activity = datetime.now()
                else:
                    # Create new session
                    session_data = {
                        **data,
                        'created_at': datetime.now().isoformat(),
                        'phone_number': phone_number
                    }
                    db_session = UserSession(
                        phone_number=phone_number,
                        session_data=json.dumps(session_data),
                        created_at=datetime.now(),
                        last_activity=datetime.now()
                    )
                    db.add(db_session)
                
                db.commit()
                
                result = json.loads(db_session.session_data)
                result['last_activity'] = db_session.last_activity
                logger.info(f"Session updated for {phone_number}: {result}")
                return result
            finally:
                db.close()
        else:
            # File-based storage (local dev)
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
        # Get or create session
        session = self.get_session(phone_number) or {}
        session['call_initiated'] = True
        session['call_time'] = datetime.now()
        self.create_or_update_session(phone_number, session)
    
    def mark_call_completed(self, phone_number: str):
        """Mark that a call has been completed for this user"""
        phone_number = self._normalize_phone(phone_number)
        # Get or create session
        session = self.get_session(phone_number) or {}
        session['call_completed'] = True
        session['call_completed_time'] = datetime.now()
        self.create_or_update_session(phone_number, session)
    
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
