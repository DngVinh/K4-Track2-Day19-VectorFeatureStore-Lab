"""Regression checks for preservation, correct fusion and bonus isolation."""
import numpy as np
import pytest
from qdrant_client import QdrantClient
from app.cache import SemanticCache
from app.search import SearchHit, Searcher
from app.agent import RuleBasedPlanner
from bonus.agent import HybridMemoryAgent


class TinyEmbedder:
    dim = 3

    def embed(self, texts):
        for text in texts:
            yield np.array([1.0, float("cloud" in text.lower()), float("secret" in text.lower())])


def test_cache_instances_preserve_each_others_data():
    client = QdrantClient(":memory:")
    first = SemanticCache(client, TinyEmbedder(), dim=3)
    first.put("a", "cloud", "original")
    second = SemanticCache(client, TinyEmbedder(), dim=3)
    second.put("a", "cloud", "new")
    assert first.get("a", "cloud").answer == "original"
    assert second.get("a", "cloud").answer == "new"
    first.advance(4000)
    assert first.get("a", "cloud") is None
    assert client.count(first.collection_name).count == 1  # expiry preserves audit data


def test_rrf_uses_rank_one_and_keeps_union_candidates(monkeypatch):
    searcher = Searcher()
    hit = lambda doc: SearchHit(doc, doc, doc, 99.0)
    monkeypatch.setattr(searcher, "_search_keyword", lambda *_: [hit("a"), hit("both")])
    monkeypatch.setattr(searcher, "_search_semantic", lambda *_: [hit("b"), hit("both")])
    result = searcher.search("query", "hybrid", top_k=3)
    assert result[0].doc_id == "both"
    assert result[0].score == pytest.approx(2 / 62)
    assert result[1].score == pytest.approx(1 / 61)


def test_planner_distributes_remainder_without_exceeding_budget():
    plan = RuleBasedPlanner(budget=16).plan("cloud computing và bảo mật dữ liệu và backend API")
    assert sum(p.top_k for p in plan) == 16
    assert sorted(p.top_k for p in plan) == [5, 5, 6]


def test_bonus_scope_is_applied_to_both_rankers():
    agent = HybridMemoryAgent(feature_store=object(), embedder=TinyEmbedder())
    agent.remember("cloud information", "a")
    agent.remember("secret cloud information", "b")
    hits = agent.retrieve("secret cloud", "a")
    assert hits and all(h["user_id"] == "a" for h in hits)
    assert all("secret" not in h["text"] for h in hits)
    assert agent.retrieve("cloud", "unknown") == []
