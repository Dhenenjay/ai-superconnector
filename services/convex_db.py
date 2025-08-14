"""
Convex Database Integration for AI Superconnector
"""
import os
import httpx
from typing import Dict, Any, Optional, List
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class ConvexDB:
    """Handle all Convex database operations"""
    
    def __init__(self):
        self.convex_url = os.getenv("CONVEX_URL", "")
        self.deploy_key = os.getenv("CONVEX_DEPLOY_KEY", "")
        
        if not self.convex_url:
            logger.warning("Convex URL not configured")
    
    async def query(self, function_name: str, args: Dict[str, Any] = {}) -> Any:
        """Execute a Convex query function"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.convex_url}/query",
                    json={
                        "path": function_name,
                        "args": args
                    },
                    headers={
                        "Authorization": f"Bearer {self.deploy_key}",
                        "Content-Type": "application/json"
                    }
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Convex query error: {str(e)}")
            return None
    
    async def mutation(self, function_name: str, args: Dict[str, Any] = {}) -> Any:
        """Execute a Convex mutation function"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.convex_url}/mutation",
                    json={
                        "path": function_name,
                        "args": args
                    },
                    headers={
                        "Authorization": f"Bearer {self.deploy_key}",
                        "Content-Type": "application/json"
                    }
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Convex mutation error: {str(e)}")
            return None
    
    # User management functions
    async def create_user(self, phone_number: str, name: str, email: str) -> Optional[str]:
        """Create a new user in Convex"""
        return await self.mutation(
            "users:create",
            {
                "phoneNumber": phone_number,
                "name": name,
                "email": email,
                "createdAt": datetime.now().isoformat()
            }
        )
    
    async def get_user(self, phone_number: str) -> Optional[Dict]:
        """Get user by phone number"""
        return await self.query(
            "users:getByPhone",
            {"phoneNumber": phone_number}
        )
    
    async def update_user(self, user_id: str, updates: Dict[str, Any]) -> bool:
        """Update user information"""
        result = await self.mutation(
            "users:update",
            {
                "id": user_id,
                **updates
            }
        )
        return result is not None
    
    # Conversation management
    async def create_conversation(self, user_id: str, channel: str = "whatsapp") -> Optional[str]:
        """Create a new conversation"""
        return await self.mutation(
            "conversations:create",
            {
                "userId": user_id,
                "channel": channel,
                "startedAt": datetime.now().isoformat()
            }
        )
    
    async def add_message(
        self, 
        conversation_id: str, 
        content: str, 
        role: str = "user",
        metadata: Dict = {}
    ) -> Optional[str]:
        """Add a message to a conversation"""
        return await self.mutation(
            "messages:create",
            {
                "conversationId": conversation_id,
                "content": content,
                "role": role,
                "metadata": metadata,
                "timestamp": datetime.now().isoformat()
            }
        )
    
    async def get_conversation_history(
        self, 
        user_id: str, 
        limit: int = 50
    ) -> List[Dict]:
        """Get conversation history for a user"""
        result = await self.query(
            "conversations:getHistory",
            {
                "userId": user_id,
                "limit": limit
            }
        )
        return result or []
    
    # Call records
    async def create_call_record(
        self,
        user_id: str,
        call_sid: str,
        duration: int = 0,
        status: str = "initiated"
    ) -> Optional[str]:
        """Create a call record"""
        return await self.mutation(
            "calls:create",
            {
                "userId": user_id,
                "callSid": call_sid,
                "duration": duration,
                "status": status,
                "timestamp": datetime.now().isoformat()
            }
        )
    
    async def update_call_status(
        self,
        call_sid: str,
        status: str,
        duration: Optional[int] = None
    ) -> bool:
        """Update call status"""
        args = {
            "callSid": call_sid,
            "status": status
        }
        if duration is not None:
            args["duration"] = duration
            
        result = await self.mutation("calls:updateStatus", args)
        return result is not None
    
    # Network/Connection management
    async def add_connection(
        self,
        user_id: str,
        connection_data: Dict[str, Any]
    ) -> Optional[str]:
        """Add a professional connection for a user"""
        return await self.mutation(
            "connections:create",
            {
                "userId": user_id,
                **connection_data,
                "createdAt": datetime.now().isoformat()
            }
        )
    
    async def get_user_connections(
        self,
        user_id: str,
        limit: int = 100
    ) -> List[Dict]:
        """Get all connections for a user"""
        result = await self.query(
            "connections:getByUser",
            {
                "userId": user_id,
                "limit": limit
            }
        )
        return result or []
    
    # Analytics
    async def log_event(
        self,
        event_type: str,
        user_id: Optional[str] = None,
        metadata: Dict = {}
    ) -> Optional[str]:
        """Log an analytics event"""
        return await self.mutation(
            "analytics:logEvent",
            {
                "eventType": event_type,
                "userId": user_id,
                "metadata": metadata,
                "timestamp": datetime.now().isoformat()
            }
        )


# Global instance
convex_db = ConvexDB()
