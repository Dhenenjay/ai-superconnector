from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from core.db import get_db
from core import models
from services.connectors.stubs import GmailConnector, SlackConnector, NotionConnector
from core.schemas import ObjectOut
from services.ai.embed import get_embedder
from services.ai.retrieve import upsert_embedding

router = APIRouter()

CONNECTORS = {
    "gmail": GmailConnector(),
    "slack": SlackConnector(),
    "notion": NotionConnector(),
}


@router.post("/{provider}/backfill/{user_id}")
def backfill(provider: str, user_id: int, db: Session = Depends(get_db)):
    if provider not in CONNECTORS:
        raise HTTPException(status_code=404, detail="Unknown provider")
    if not db.query(models.User).get(user_id):
        raise HTTPException(status_code=400, detail="Invalid user_id")
    embedder = get_embedder()

    created_ids: list[int] = []
    for item in CONNECTORS[provider].backfill(user_id):
        obj = models.UnifiedObject(user_id=user_id, **item)
        db.add(obj)
        db.commit()
        db.refresh(obj)
        text = "\n\n".join(filter(None, [obj.title, obj.body]))
        upsert_embedding(db, obj, embedder, text)
        created_ids.append(obj.id)

    return {"created": created_ids}


@router.post("/{provider}/send")
def send(provider: str, payload: dict):
    if provider not in CONNECTORS:
        raise HTTPException(status_code=404, detail="Unknown provider")
    return CONNECTORS[provider].send(payload)

