from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from core.db import get_db
from core import models
from core.schemas import ObjectCreate, ObjectOut
from services.ai.embed import get_embedder
from services.ai.retrieve import upsert_embedding

router = APIRouter()


@router.post("/", response_model=ObjectOut)
def create_object(payload: ObjectCreate, db: Session = Depends(get_db)):
    user = db.query(models.User).get(payload.user_id)
    if not user:
        raise HTTPException(status_code=400, detail="Invalid user_id")

    obj = models.UnifiedObject(
        user_id=payload.user_id,
        provider=payload.provider,
        provider_type=payload.provider_type,
        provider_id=payload.provider_id,
        title=payload.title,
        body=payload.body,
        metadata_json=payload.metadata_json or {},
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)

    # create/update embedding
    text = "\n\n".join(filter(None, [obj.title, obj.body]))
    embedder = get_embedder()
    upsert_embedding(db, obj, embedder, text)

    return obj


@router.get("/{object_id}", response_model=ObjectOut)
def get_object(object_id: int, db: Session = Depends(get_db)):
    obj = db.query(models.UnifiedObject).get(object_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Not found")
    return obj

