from __future__ import annotations
from dataclasses import dataclass
from typing import Protocol, List
from core.config import settings
import numpy as np
import hashlib


class Embedder(Protocol):
    def embed(self, texts: List[str]) -> List[List[float]]: ...


@dataclass
class HashEmbedder:
    dims: int = 384

    def embed(self, texts: List[str]) -> List[List[float]]:
        vecs: list[list[float]] = []
        for t in texts:
            h = hashlib.sha256(t.encode("utf-8")).digest()
            rng = np.random.default_rng(int.from_bytes(h[:8], "big"))
            v = rng.normal(0, 1, self.dims)
            v = v / np.linalg.norm(v)
            vecs.append(v.astype(float).tolist())
        return vecs


try:
    import openai  # type: ignore
except Exception:  # pragma: no cover
    openai = None  # type: ignore


@dataclass
class OpenAIEmbedder:
    model: str = "text-embedding-3-small"

    def embed(self, texts: List[str]) -> List[List[float]]:
        if not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY not set")
        if openai is None:
            raise RuntimeError("openai package not installed")
        client = openai.OpenAI(api_key=settings.openai_api_key)
        resp = client.embeddings.create(model=self.model, input=texts)
        return [d.embedding for d in resp.data]


def get_embedder() -> Embedder:
    if settings.embeddings_provider == "openai":
        return OpenAIEmbedder()
    return HashEmbedder()

