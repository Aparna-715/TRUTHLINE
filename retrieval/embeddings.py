"""
TRUTHLINE — Embedding helpers
===========================================================================
One interface, two backends.

  SentenceEmbedder  sentence-transformers — real semantic search
  HashingEmbedder   deterministic hashing  — offline fallback

The fallback matters: it means the retrieval layer still runs (and the demo
still works) on a machine where the model weights are not downloaded. It is NOT
semantic — it matches on shared tokens — but it degrades gracefully instead of
crashing, which is the right behaviour for a hackathon demo.
"""

from __future__ import annotations

import hashlib
import math
from typing import List, Protocol

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from config import EMBEDDING_MODEL

__all__ = ["Embedder", "SentenceEmbedder", "HashingEmbedder", "get_embedder"]


class Embedder(Protocol):
    def embed(self, texts: List[str]) -> List[List[float]]: ...

    @property
    def dim(self) -> int: ...


class HashingEmbedder:
    """Deterministic offline fallback. Token-overlap vectors, L2 normalised.

    Not semantic — "3 vehicles detected" and "3 vehicles spotted" will NOT be
    close. Use only when sentence-transformers is unavailable.
    """

    def __init__(self, dim: int = 384) -> None:
        self._dim = dim

    @property
    def dim(self) -> int:
        return self._dim

    @property
    def name(self) -> str:
        return f"hashing(dim={self._dim})"

    def embed(self, texts: List[str]) -> List[List[float]]:
        out: List[List[float]] = []
        for text in texts:
            vec = [0.0] * self._dim
            for token in (text or "").lower().split():
                digest = hashlib.md5(token.encode("utf-8")).hexdigest()
                vec[int(digest, 16) % self._dim] += 1.0
            norm = math.sqrt(sum(v * v for v in vec)) or 1.0
            out.append([round(v / norm, 6) for v in vec])
        return out


class SentenceEmbedder:
    """Real semantic embeddings via sentence-transformers."""

    def __init__(self, model_name: str = EMBEDDING_MODEL) -> None:
        from sentence_transformers import SentenceTransformer

        self._model = SentenceTransformer(model_name)
        self._dim = int(self._model.get_sentence_embedding_dimension())

    @property
    def dim(self) -> int:
        return self._dim

    @property
    def name(self) -> str:
        return f"sentence-transformers({EMBEDDING_MODEL})"

    def embed(self, texts: List[str]) -> List[List[float]]:
        return self._model.encode(
            list(texts), normalize_embeddings=True
        ).tolist()


def get_embedder() -> Embedder:
    """Return the best available embedder, falling back to hashing."""
    try:
        return SentenceEmbedder()
    except Exception:
        return HashingEmbedder()


if __name__ == "__main__":
    emb = get_embedder()
    print(f"embedder: {emb.name}  dim={emb.dim}")
    for v in emb.embed(["3 vehicles detected", "3 vehicles spotted", "weather report"])[:3]:
        print(f"  vector len={len(v)} first3={v[:3]}")
