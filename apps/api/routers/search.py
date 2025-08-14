from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from core.db import get_db
from core.schemas import SearchQuery
from services.ai.embed import get_embedder
from services.ai.retrieve import hybrid_search

router = APIRouter()


@router.post("/")
def search(payload: SearchQuery, db: Session = Depends(get_db)):
    embedder = get_embedder()
    results = hybrid_search(db, payload, embedder)
    return {"results": results}

