"""
Synchronous Convex Client for Python
Handles HTTP API calls to Convex backend
"""
import os
import requests
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class ConvexClient:
    """Synchronous client for Convex HTTP API"""
    
    def __init__(self):
        self.url = os.getenv("CONVEX_URL", "")
        self.deploy_key = os.getenv("CONVEX_DEPLOY_KEY", "")
        
        if not self.url:
            logger.warning("CONVEX_URL not configured")
        if not self.deploy_key:
            logger.warning("CONVEX_DEPLOY_KEY not configured")
        
        # Ensure URL ends with /api if not already
        if self.url and not self.url.endswith('/api'):
            if not self.url.endswith('/'):
                self.url += '/'
            self.url += 'api'
        
        logger.info(f"Convex client initialized with URL: {self.url[:30]}...")
    
    def query(self, function_path: str, args: Dict[str, Any] = None) -> Any:
        """Execute a Convex query function"""
        if not self.url or not self.deploy_key:
            logger.error("Convex not properly configured")
            return None
        
        try:
            # Format the function path (e.g., "sessions:get" -> "sessions/get")
            path = function_path.replace(":", "/")
            
            # Convex HTTP API endpoint for queries
            endpoint = f"{self.url}/query"
            
            headers = {
                "Authorization": f"Bearer {self.deploy_key}",
                "Content-Type": "application/json"
            }
            
            # Prepare the request body
            body = {
                "path": path,
                "args": args or {}
            }
            
            logger.debug(f"Convex query: {path} with args: {args}")
            
            response = requests.post(endpoint, json=body, headers=headers)
            
            if response.status_code == 200:
                result = response.json()
                logger.debug(f"Convex query result: {result}")
                return result.get("value")
            else:
                logger.error(f"Convex query failed: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Convex query error: {str(e)}")
            return None
    
    def mutation(self, function_path: str, args: Dict[str, Any] = None) -> Any:
        """Execute a Convex mutation function"""
        if not self.url or not self.deploy_key:
            logger.error("Convex not properly configured")
            return None
        
        try:
            # Format the function path (e.g., "sessions:upsert" -> "sessions/upsert")
            path = function_path.replace(":", "/")
            
            # Convex HTTP API endpoint for mutations
            endpoint = f"{self.url}/mutation"
            
            headers = {
                "Authorization": f"Bearer {self.deploy_key}",
                "Content-Type": "application/json"
            }
            
            # Prepare the request body
            body = {
                "path": path,
                "args": args or {}
            }
            
            logger.debug(f"Convex mutation: {path} with args: {args}")
            
            response = requests.post(endpoint, json=body, headers=headers)
            
            if response.status_code == 200:
                result = response.json()
                logger.debug(f"Convex mutation result: {result}")
                return result.get("value")
            else:
                logger.error(f"Convex mutation failed: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Convex mutation error: {str(e)}")
            return None


# Global instance
convex_client = ConvexClient()
