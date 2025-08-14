from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from core.config import settings
from core.db import engine
from core.db import Base
from apps.api.routers import users, objects, search, connectors, twilio, websocket
from pathlib import Path
import logging
import os
from datetime import datetime

# Create logs directory if it doesn't exist
log_dir = "logs"
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

# Create a log file with timestamp
log_filename = os.path.join(log_dir, f"realtime_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")

# Configure logging for debugging - log to both file and console
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_filename, encoding='utf-8'),  # Log to file
        logging.StreamHandler()  # Also log to console
    ]
)
logger = logging.getLogger(__name__)
logger.info(f"Logging to file: {log_filename}")

Base.metadata.create_all(bind=engine)

app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(users.router, prefix="/users", tags=["users"])
app.include_router(objects.router, prefix="/objects", tags=["objects"])
app.include_router(search.router, prefix="/search", tags=["search"])
app.include_router(connectors.router, prefix="/connectors", tags=["connectors"])
app.include_router(twilio.router, prefix="/twilio", tags=["twilio"])
app.include_router(websocket.router, tags=["websocket"])  # WebSocket routes


@app.get("/")
def root():
    return {"name": settings.app_name, "env": settings.env}


@app.get("/audio/{file_name}")
async def serve_audio(file_name: str):
    """Serve cached audio files for Twilio calls"""
    audio_path = Path(f"C:/Users/Dhenenjay/ai-superconnector/.data/audio_cache/{file_name}")
    
    if not audio_path.exists():
        raise HTTPException(status_code=404, detail="Audio file not found")
    
    return FileResponse(
        path=str(audio_path),
        media_type="audio/mpeg",
        headers={
            "Cache-Control": "public, max-age=3600",
            "Content-Disposition": f"inline; filename={file_name}"
        }
    )

