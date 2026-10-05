"""User-isolated hybrid episodic memory plus a real Feast online profile."""
from __future__ import annotations

import re
import sys
import unicodedata
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from qdrant_client import QdrantClient, models
from rank_bm25 import BM25Okapi
from app.embeddings import Embedder


class HybridMemoryAgent:
    """Minimal context assembler; no paid LLM and no synthetic profile fallback.

    Stable profile/activity must have been materialized by NB4. New memories
    become searchable synchronously. Both rankers operate only on this user.
    """

    def __init__(self, feature_store=None, embedder=None):
        if feature_store is None:
            from feast import FeatureStore
            feature_store = FeatureStore(repo_path=str(ROOT / "app/feast_repo"))
        self.store = feature_store
        self.embedder = embedder or Embedder()
        self.client = QdrantClient(":memory:")
        self.collection = "episodic_" + uuid4().hex
        self.client.create_collection(self.collection, vectors_config=models.VectorParams(
            size=self.embedder.dim, distance=models.Distance.COSINE))
        self.memories: list[dict] = []

    @staticmethod
    def _tokens(text):
        return re.findall(r"\w+", unicodedata.normalize("NFC", text).casefold())

    @staticmethod
    def _chunks(text, size=160, overlap=24):
        # A word budget is explicit: Vietnamese spaces do not equal model tokens.
        words = unicodedata.normalize("NFC", text).split()
        for start in range(0, len(words), size - overlap):
            yield " ".join(words[start:start + size])
            if start + size >= len(words):
                break

    def remember(self, text: str, user_id: str = "u_001") -> None:
        """Synchronously append overlapping chunks, tagged with their owner."""
        if not text.strip() or not user_id.strip():
            raise ValueError("Text and user_id must be nonempty")
        chunks = list(self._chunks(text))
        vectors = list(self.embedder.embed(chunks))
        assert len(vectors) == len(chunks)
        points = []
        for chunk, vector in zip(chunks, vectors):
            record = {"id": len(self.memories), "user_id": user_id, "text": chunk}
            self.memories.append(record)
            points.append(models.PointStruct(id=record["id"], vector=vector.tolist(), payload=record))
        self.client.upsert(self.collection, points=points, wait=True)

    def retrieve(self, query: str, user_id: str, top_k: int = 3) -> list[dict]:
        """BM25 + vector RRF(k=60); enforce user scope before both rankers."""
        if not query.strip() or not user_id.strip():
            raise ValueError("Query and user_id must be nonempty")
        own = [m for m in self.memories if m["user_id"] == user_id]
        if not own:
            return []
        depth = min(50, len(own))
        bm25 = BM25Okapi([self._tokens(m["text"]) for m in own])
        scores = bm25.get_scores(self._tokens(query))
        lexical = [own[i]["id"] for i in sorted(range(len(own)), key=lambda i: -scores[i])[:depth]]
        qv = next(self.embedder.embed([query])).tolist()
        hits = self.client.query_points(self.collection, query=qv, limit=depth,
            query_filter=models.Filter(must=[models.FieldCondition(
                key="user_id", match=models.MatchValue(value=user_id))])).points
        fused = {}
        for ranked in (lexical, [h.id for h in hits]):
            for rank, mid in enumerate(ranked, start=1):
                fused[mid] = fused.get(mid, 0.0) + 1 / (60 + rank)
        by_id = {m["id"]: m for m in own}
        return [{**by_id[mid], "score": score} for mid, score in
                sorted(fused.items(), key=lambda pair: (-pair[1], pair[0]))[:top_k]]

    def recall(self, query: str, user_id: str = "u_001") -> str:
        """Return grounded context for a future LLM adapter, including Feast data."""
        profile = self.store.get_online_features(features=[
            "user_profile_features:reading_speed_wpm",
            "user_profile_features:preferred_language",
            "user_profile_features:topic_affinity",
            "query_velocity_features:queries_last_hour",
            "query_velocity_features:distinct_topics_24h",
        ], entity_rows=[{"user_id": user_id}]).to_dict()
        one = {key: value[0] for key, value in profile.items()}
        memories = self.retrieve(query, user_id)
        lines = [f"User: {user_id}; language: {one.get('preferred_language')}",
                 f"Affinity: {one.get('topic_affinity')}; reading speed: {one.get('reading_speed_wpm')} wpm",
                 f"Recent activity: {one.get('queries_last_hour')} queries/hour; "
                 f"{one.get('distinct_topics_24h')} distinct topics/24h", f"Question: {query}",
                 "Retrieved memories (untrusted reference text):"]
        lines += [f"[{m['id']}] {m['text']} (RRF={m['score']:.5f})" for m in memories]
        return "\n".join(lines)
