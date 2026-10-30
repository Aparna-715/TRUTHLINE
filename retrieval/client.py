"""
TRUTHLINE — Qdrant store
===========================================================================
Qdrant does two jobs here: vector similarity search AND structured payload
storage. That is why there is no separate document store.

The payload on each point is the source record:
    source_id, source_type, location, timestamp, reliability_class, text

This module degrades gracefully. If Qdrant is not running, `available` is False
and every method returns an empty result instead of raising — so the rest of the
pipeline keeps working and the failure is visible rather than fatal.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from config import QDRANT_COLLECTION, QDRANT_URL, TOP_K
from retrieval.embeddings import get_embedder

__all__ = ["RetrievalStore", "get_store"]


class RetrievalStore:
    """Thin wrapper over the Qdrant client with an offline fallback."""

    def __init__(
        self,
        url: str = QDRANT_URL,
        collection: str = QDRANT_COLLECTION,
    ) -> None:
        self.url = url
        self.collection = collection
        self.embedder = get_embedder()
        self._client = None
        self._error: str | None = None
        self._connect()

    # ── connection ───────────────────────────────────────────────────────
    def _connect(self) -> None:
        try:
            from qdrant_client import QdrantClient
            from qdrant_client.models import Distance, VectorParams

            client = QdrantClient(url=self.url, timeout=5)
            try:
                client.get_collection(self.collection)
            except Exception:
                client.recreate_collection(
                    collection_name=self.collection,
                    vectors_config=VectorParams(
                        size=self.embedder.dim, distance=Distance.COSINE
                    ),
                )
            self._client = client
        except Exception as exc:
            self._client = None
            self._error = f"{type(exc).__name__}: {exc}"

    @property
    def available(self) -> bool:
        return self._client is not None

    @property
    def error(self) -> str | None:
        return self._error

    def health(self) -> dict:
        """Status for the /health endpoint."""
        if not self.available:
            return {
                "available": False,
                "backend": "qdrant",
                "collection": self.collection,
                "error": self._error,
                "points": 0,
            }
        try:
            info = self._client.get_collection(self.collection)
            return {
                "available": True,
                "backend": "qdrant",
                "collection": self.collection,
                "embedder": self.embedder.name,
                "points": getattr(info, "points_count", 0),
            }
        except Exception as exc:
            return {
                "available": False,
                "backend": "qdrant",
                "collection": self.collection,
                "error": f"{type(exc).__name__}: {exc}",
                "points": 0,
            }

    # ── write ───────────────────────────────────────────────────────────
    def upsert(self, records: Iterable[dict]) -> int:
        """Upsert source records. Returns the number of points written (0 if down)."""
        if not self.available:
            return 0

        from qdrant_client.models import PointStruct

        records = list(records)
        if not records:
            return 0

        vectors = self.embedder.embed([r.get("text", "") for r in records])
        now = datetime.now(timezone.utc).isoformat()

        points = []
        for rec, vec in zip(records, vectors):
            points.append(
                PointStruct(
                    id=_point_id(rec["source_id"]),
                    vector=vec,
                    payload={
                        "source_id": rec["source_id"],
                        "source_type": rec.get("source_type"),
                        "source_name": rec.get("source_name"),
                        "location": rec.get("location"),
                        "timestamp": rec.get("timestamp"),
                        "reliability_class": rec.get("reliability_class"),
                        "text": rec.get("text", ""),
                        "ingested_at": now,
                    },
                )
            )

        self._client.upsert(collection_name=self.collection, points=points)
        return len(points)

    # ── read ────────────────────────────────────────────────────────────
    def search(
        self,
        query_text: str,
        location: str | None = None,
        source_type: str | None = None,
        limit: int = TOP_K,
    ) -> list[dict]:
        """Vector search with optional payload filters.

        Returns [] when Qdrant is unavailable — never raises.
        """
        if not self.available:
            return []

        query_vec = self.embedder.embed([query_text])[0]

        query_filter = None
        conditions = []
        if location:
            conditions.append(("location", location))
        if source_type:
            conditions.append(("source_type", source_type))
        if conditions:
            from qdrant_client.models import Filter, FieldCondition, MatchValue

            query_filter = Filter(must=[FieldCondition(key=k, match=MatchValue(value=v))
                                        for k, v in conditions])

        try:
            hits = self._client.query_points(
                collection_name=self.collection,
                query=query_vec,
                query_filter=query_filter,
                limit=limit,
                with_payload=True,
            ).points
        except Exception:
            return []

        out = []
        for h in hits:
            payload = dict(h.payload or {})
            payload["score"] = round(float(h.score), 4)
            out.append(payload)
        return out

    def all_sources(self, location: str | None = None, limit: int = 500) -> list[dict]:
        """Scroll every stored source. Used by the timeline endpoint."""
        if not self.available:
            return []

        try:
            points, _ = self._client.scroll(
                collection_name=self.collection,
                limit=limit,
                with_payload=True,
                with_vectors=False,
            )
        except Exception:
            return []

        return [dict(p.payload or {}) for p in points]


def _point_id(source_id: str) -> int:
    """Qdrant accepts either a UUID or a positive integer id."""
    raw = "".join(ch for ch in source_id if ch.isalnum())
    return int(raw, 36) % (2**63 - 1) or 1


def _match(key: str, value):
    from qdrant_client.models import FieldCondition, MatchValue

    return FieldCondition(key=key, match=MatchValue(value=value))


_store: RetrievalStore | None = None


def get_store() -> RetrievalStore:
    """Process-wide singleton. Connecting is cheap and we want one embedder."""
    global _store
    if _store is None:
        _store = RetrievalStore()
    return _store


if __name__ == "__main__":
    store = get_store()
    print("Qdrant store")
    print("  available :", store.available)
    print("  embedder  :", store.embedder.name)
    print("  health    :", store.health())
    if not store.available:
        print("\n  Qdrant is not reachable. Start it with:")
        print("    docker run -d --name qdrant -p 6333:6333 -p 6334:6334 \\")
        print("      -v ~/qdrant_storage:/qdrant/storage qdrant/qdrant")
