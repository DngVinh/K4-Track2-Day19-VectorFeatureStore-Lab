"""Fixed, label-blind NB2 diagnostics; never changes the production configuration.

Candidates are fixed before evaluation: original, BGE's documented query
instruction, NFC/punctuation lexical normalization, and their combination.
No model, depth, weight or query routing is tuned on the golden set.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import statistics
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
INSTRUCTION = "Represent this sentence for searching relevant passages: "
CONFIGS = (("original", False, False), ("query_instruction", True, False),
           ("nfc_punctuation", False, True), ("instruction_and_nfc", True, True))


def normalize(text: str) -> str:
    return unicodedata.normalize("NFC", text)


def tokens(text: str) -> list[str]:
    # Unicode letters/digits including Vietnamese marks; preserve accents.
    return re.findall(r"\w+", normalize(text).casefold())


def evaluate(output: Path | None = None) -> dict:
    from fastembed import TextEmbedding
    from qdrant_client import QdrantClient
    from qdrant_client.models import Distance, PointStruct, VectorParams
    from rank_bm25 import BM25Okapi

    os.environ.setdefault("FASTEMBED_CACHE_PATH", str(ROOT / ".cache/fastembed"))
    corpus = ROOT / "data/corpus_vn.jsonl"
    golden_file = ROOT / "data/golden_set.jsonl"
    docs = [json.loads(line) for line in corpus.read_text(encoding="utf-8").splitlines()]
    golden = [json.loads(line) for line in golden_file.read_text(encoding="utf-8").splitlines()]
    assert len(docs) == 1000 and len(golden) == 50
    texts = [d["title"] + " " + d["text"] for d in docs]
    queries = [q["query"] for q in golden]  # only text crosses ranking boundary
    model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
    vectors = list(model.embed(texts, batch_size=64))
    client = QdrantClient(":memory:")
    client.create_collection("audit", vectors_config=VectorParams(size=384, distance=Distance.COSINE))
    client.upsert("audit", points=[PointStruct(id=i, vector=v.tolist()) for i, v in enumerate(vectors)])
    # NFC makes no change to these corpus texts; assert that vector reuse is valid.
    assert all(normalize(t) == t for t in texts)
    lexical = [BM25Okapi([t.lower().split() for t in texts]), BM25Okapi([tokens(t) for t in texts])]
    ranks = {}
    for name, instruction, normalized in CONFIGS:
        qtexts = [(INSTRUCTION if instruction else "") + (normalize(q) if normalized else q) for q in queries]
        qvectors = list(model.embed(qtexts, batch_size=64))
        per_query = []
        for query, vector in zip(queries, qvectors):
            scores = lexical[int(normalized)].get_scores(tokens(query) if normalized else query.lower().split())
            sparse = sorted(range(len(docs)), key=lambda i: -scores[i])[:50]
            dense = [p.id for p in client.query_points("audit", query=vector.tolist(), limit=50).points]
            fused = {}
            for ranked in (sparse, dense):
                for rank, idx in enumerate(ranked, 1):
                    fused[idx] = fused.get(idx, 0.0) + 1 / (60 + rank)
            hybrid = sorted(fused, key=lambda i: -fused[i])[:10]
            per_query.append({"rankings": [[docs[i]["doc_id"] for i in rank[:10]] for rank in (sparse, dense, hybrid)],
                              "positive_bm25_candidates": int((scores > 0).sum())})
        ranks[name] = per_query

    # Evaluation begins only AFTER all candidates' rankings have been frozen.
    report = {"model": model.model_name, "rrf_k": 60, "depth": 50, "rank_base": 1,
              "protocol": "Four predeclared ablations; labels only used after ranking. No held-out claim or automatic selection.",
              "model_card": "https://huggingface.co/BAAI/bge-small-en-v1.5",
              "hashes": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (corpus, golden_file)},
              "configs": {}}
    for name, _, _ in CONFIGS:
        values = []
        for q, ranked in zip(golden, ranks[name]):
            relevant = set(q["relevant_doc_ids"])
            values.append([sum(doc in relevant for doc in hits) / 10 for hits in ranked["rankings"]])
        overall = [statistics.mean(row[i] for row in values) for i in range(3)]
        slices = {kind: [statistics.mean(row[i] for q, row in zip(golden, values) if q["mode_hint"] == kind)
                         for i in range(3)] for kind in ("exact", "paraphrase", "mixed")}
        checks = {"overall_hybrid_strict_win": overall[2] > max(overall[:2]),
                  "mixed_hybrid_strict_win": slices["mixed"][2] > max(slices["mixed"][:2]),
                  "paraphrase_vector_strict_win": slices["paraphrase"][1] > max(slices["paraphrase"][0], slices["paraphrase"][2]),
                  "exact_bm25_tied_or_best": slices["exact"][0] >= max(slices["exact"][1:])}
        report["configs"][name] = {"overall": overall, "slices": slices, "criteria": checks,
            "per_query": [{"query_id": q["query_id"], "precision": row, **ranked}
                          for q, row, ranked in zip(golden, values, ranks[name])]}
        print(name, "BM25 / Vector / Hybrid", flush=True)
        print("  overall", " / ".join(f"{v:.1%}" for v in overall))
        for kind, row in slices.items():
            print(f"  {kind:12}", " / ".join(f"{v:.1%}" for v in row))
        print("  criteria", checks, flush=True)
    print("No candidate is automatically adopted. Failures remain visible; no held-out generalization claim.")
    if output is not None:
        output = output.resolve()
        assert output.is_relative_to(ROOT) and not output.exists()
        with output.open("x", encoding="utf-8") as target:
            json.dump(report, target, ensure_ascii=False, indent=2)
    return report


if __name__ == "__main__":
    evaluate(Path(sys.argv[1]) if len(sys.argv) > 1 else None)
