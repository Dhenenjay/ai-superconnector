from __future__ import annotations
from sqlalchemy.orm import Session
from core import models
from core.schemas import SearchQuery
from services.ai.embed import Embedder
import math


def upsert_embedding(db: Session, obj: models.UnifiedObject, embedder: Embedder, text: str):
    if not text:
        return
    vec = embedder.embed([text])[0]
    emb = db.query(models.ObjectEmbedding).get(obj.id)
    if emb:
        emb.vector = vec
        emb.dims = len(vec)
    else:
        emb = models.ObjectEmbedding(object_id=obj.id, dims=len(vec), vector=vec)
        db.add(emb)
    db.commit()


def cosine_sim(a: list[float], b: list[float]) -> float:
    dot = sum(x*y for x, y in zip(a, b))
    na = math.sqrt(sum(x*x for x in a))
    nb = math.sqrt(sum(x*x for x in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def hybrid_search(db: Session, q: SearchQuery, embedder: Embedder):
    # naive hybrid: cosine on embeddings + keyword score on title/body
    query_vec = embedder.embed([q.query])[0]

    objs = db.query(models.UnifiedObject).filter(models.UnifiedObject.user_id == q.user_id)
    if q.provider:
        objs = objs.filter(models.UnifiedObject.provider == q.provider)
    if q.provider_type:
        objs = objs.filter(models.UnifiedObject.provider_type == q.provider_type)

    objs = objs.all()

    results = []
    query_lower = q.query.lower()
    for obj in objs:
        emb = db.query(models.ObjectEmbedding).get(obj.id)
        vec_score = cosine_sim(query_vec, emb.vector) if emb else 0.0
        text = "\n\n".join(filter(None, [obj.title or "", obj.body or ""]))
        keyword_score = 1.0 if query_lower in text.lower() else 0.0
        score = 0.7 * vec_score + 0.3 * keyword_score
        results.append({
            "object": {
                "id": obj.id,
                "title": obj.title,
                "provider": obj.provider,
                "provider_type": obj.provider_type,
            },
            "score": score,
        })

    results.sort(key=lambda r: r["score"], reverse=True)
    return results[: q.top_k]

