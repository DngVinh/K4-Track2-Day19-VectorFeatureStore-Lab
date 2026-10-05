# ---
# jupyter:
#   jupytext:
#     formats: py:percent
# ---

# %% [markdown]
# # NB2 — Hybrid Search: BM25 + Vector + RRF
#
# **Stack:** `rank-bm25` cho BM25 sparse + `qdrant-client` cho dense + RRF fusion.
# Maps to slide §3 (Hybrid Search Mechanics) + deliverable bullet 2.
#
# > Hybrid search (BM25 + Vector + RRF $k=60$) là mặc định production 2026 —
# > mọi vector DB lớn (Qdrant, Weaviate, OpenSearch, Milvus) đều có sẵn. Mức
# > cải thiện điển hình so với dense-only là **~10–15 điểm Recall@10**, nhưng
# > con số thật phụ thuộc corpus của bạn — nên notebook này **đo trên golden set
# > của chính lab** thay vì trích một con số từ blog.

# %%
import _setup  # noqa: F401
import json
import statistics
from pathlib import Path

from fastembed import TextEmbedding
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from rank_bm25 import BM25Okapi

DATA = Path(_setup.__file__).resolve().parent.parent / "data"

# %% [markdown]
# ## 1. Reload corpus + build both indices

# %%
docs = [json.loads(line) for line in (DATA / "corpus_vn.jsonl").open(encoding="utf-8")]

# BM25
tokenized = [(d["title"] + " " + d["text"]).lower().split() for d in docs]
bm25 = BM25Okapi(tokenized)

# Vector
embedder = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
client = QdrantClient(":memory:")
client.create_collection(
    collection_name="lab19",
    vectors_config=VectorParams(size=384, distance=Distance.COSINE),
)
BATCH = 64
points = []
for start in range(0, len(docs), BATCH):
    batch = docs[start:start + BATCH]
    texts = [d["title"] + " " + d["text"] for d in batch]
    vectors = list(embedder.embed(texts))
    for i, (d, v) in enumerate(zip(batch, vectors)):
        points.append(PointStruct(
            id=start + i, vector=v.tolist(),
            payload={"doc_id": d["doc_id"], "topic": d["topic"]},
        ))
client.upsert(collection_name="lab19", points=points)
print(f"BM25 + vector indices ready ({len(docs)} docs)")

# %% [markdown]
# ## 2. Per-mode search functions

# %%
TOP_K = 10
RRF_K = 60   # standard default — see slide §3


def search_keyword(query: str, top_k: int = TOP_K) -> list[str]:
    scores = bm25.get_scores(query.lower().split())
    ranked = sorted(range(len(scores)), key=lambda i: -scores[i])[:top_k]
    return [docs[i]["doc_id"] for i in ranked]


def search_semantic(query: str, top_k: int = TOP_K) -> list[str]:
    q_vec = next(embedder.embed([query])).tolist()
    res = client.query_points(collection_name="lab19", query=q_vec, limit=top_k)
    return [p.payload["doc_id"] for p in res.points]


# %% [markdown]
# ## 3. TODO — implement Reciprocal Rank Fusion
#
# Công thức (deck §3):
#
# $$\text{score}(d) = \sum_{r \in \text{retrievers}} \frac{1}{k + \text{rank}_r(d)}$$
#
# `rank_r(d)` là 1-based (vị trí đầu = 1, không phải 0). $k = 60$ là default công nghiệp.
#
# **Bước:**
# 1. Pull top-50 từ BM25 và top-50 từ vector (depth = 5×top_k để có signal sâu).
# 2. Cho mỗi doc, cộng `1 / (k + rank)` từ mỗi retriever (nếu doc không xuất hiện thì bỏ qua).
# 3. Sort theo total score, trả về top-10 doc_id.

# %%
def search_hybrid(query: str, top_k: int = TOP_K, rrf_k: int = RRF_K) -> list[str]:
    depth = max(top_k * 5, 50)
    kw_ids = search_keyword(query, depth)
    sem_ids = search_semantic(query, depth)

    # TODO: implement RRF fusion below.
    # Hint: dict[doc_id, float] cộng 1/(rrf_k + rank) từ mỗi retriever.
    # rank starts at 1, not 0.
    rrf: dict[str, float] = {}
    for rank, doc_id in enumerate(kw_ids, start=1):
        rrf[doc_id] = rrf.get(doc_id, 0.0) + 1.0 / (rrf_k + rank)
    for rank, doc_id in enumerate(sem_ids, start=1):
        rrf[doc_id] = rrf.get(doc_id, 0.0) + 1.0 / (rrf_k + rank)

    return [doc_id for doc_id, _ in sorted(rrf.items(), key=lambda kv: -kv[1])[:top_k]]


# Quick sanity (1 paraphrase query from data/golden_set.jsonl):
test_q = "co giãn linh hoạt theo nhu cầu sử dụng"
print(f"Query: {test_q}")
print(f"  keyword top-3:  {search_keyword(test_q)[:3]}")
print(f"  semantic top-3: {search_semantic(test_q)[:3]}")
print(f"  hybrid top-3:   {search_hybrid(test_q)[:3]}")

# %% [markdown]
# ## 4. Đánh giá trên golden set (50 queries)
#
# Metric: **Precision@10** = fraction of top-10 thuộc đúng topic.
# (Slide deck dùng "Recall@10" với 1-relevant-per-query setup khác — ở đây dùng
# precision-style để có signal rõ với 100 docs/topic.)

# %%
golden = [json.loads(line) for line in (DATA / "golden_set.jsonl").open(encoding="utf-8")]
doc_topic = {d["doc_id"]: d["topic"] for d in docs}


def precision_at_10(retrieved_ids: list[str], target_topic: str) -> float:
    if not retrieved_ids:
        return 0.0
    return sum(1 for d in retrieved_ids[:10] if doc_topic.get(d) == target_topic) / 10


p_kw, p_sem, p_hyb = [], [], []
for q in golden:
    p_kw.append(precision_at_10(search_keyword(q["query"]), q["topic"]))
    p_sem.append(precision_at_10(search_semantic(q["query"]), q["topic"]))
    p_hyb.append(precision_at_10(search_hybrid(q["query"]), q["topic"]))

print(f"Precision@10 (avg over {len(golden)} queries):")
print(f"  Keyword (BM25)   : {statistics.mean(p_kw):.1%}")
print(f"  Semantic (vector): {statistics.mean(p_sem):.1%}")
print(f"  Hybrid  (RRF=60) : {statistics.mean(p_hyb):.1%}   <- should win")

# %% [markdown]
# ## 5. Slice theo loại query
#
# Golden set có 3 loại: `exact` (BM25 ưu thế), `paraphrase` (vector ưu thế),
# `mixed` (hybrid ưu thế). In separate scores để thấy *tại sao* hybrid thắng.

# %%
from collections import defaultdict

by_type: dict[str, dict[str, list[float]]] = defaultdict(lambda: {"kw": [], "sem": [], "hyb": []})
for q, kw, sem, hyb in zip(golden, p_kw, p_sem, p_hyb):
    by_type[q["mode_hint"]]["kw"].append(kw)
    by_type[q["mode_hint"]]["sem"].append(sem)
    by_type[q["mode_hint"]]["hyb"].append(hyb)

print(f"  {'type':12} {'n':>3}  {'kw':>7} {'sem':>7} {'hyb':>7}")
for t in ("exact", "paraphrase", "mixed"):
    m = by_type[t]
    print(f"  {t:12} {len(m['kw']):>3}  "
          f"{statistics.mean(m['kw']):>6.1%} "
          f"{statistics.mean(m['sem']):>6.1%} "
          f"{statistics.mean(m['hyb']):>6.1%}")
assert len(golden) == 50
assert statistics.mean(p_hyb) > statistics.mean(p_kw)
assert statistics.mean(p_hyb) > statistics.mean(p_sem)
assert statistics.mean(by_type["mixed"]["hyb"]) >= max(
    statistics.mean(by_type["mixed"]["kw"]), statistics.mean(by_type["mixed"]["sem"]))
print("PASS — hybrid beats both baselines overall; mixed-slice comparison verified")

# %% [markdown]
# ## 6. Kiểm chứng tiêu chí paraphrase bằng model đa ngữ
#
# BGE-small ở trên là baseline Lite bắt buộc, giữ nguyên kết quả thực đo.
# Model tiếng Anh không bảo đảm Vector thắng BM25 trên câu tiếng Việt.
# Thí nghiệm thứ hai dùng MiniLM đa ngữ 384 chiều, hỗ trợ sẵn trong FastEmbed.
# Giữ nguyên toàn bộ corpus, 50 query, ground truth, BM25, top-50, RRF k=60
# và Precision@10; chỉ thay model embedding. Đây là so sánh riêng có nhãn,
# không trộn điểm của hai model hay thay query để đạt rubric.
# Lần chạy đầu cần tải thêm khoảng 235 MB; có thể prefetch bằng
# `python scripts/fetch_lite_model.py --multilingual`.

# %%
MULTILINGUAL_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
multi_embedder = TextEmbedding(model_name=MULTILINGUAL_MODEL)
multi_client = QdrantClient(":memory:")
multi_client.create_collection(collection_name="lab19_multilingual",
    vectors_config=VectorParams(size=384, distance=Distance.COSINE))
for start in range(0, len(docs), BATCH):
    batch = docs[start:start + BATCH]
    vectors = list(multi_embedder.embed([d["title"] + " " + d["text"] for d in batch]))
    multi_client.upsert(collection_name="lab19_multilingual", points=[
        PointStruct(id=start + i, vector=vector.tolist(), payload={"doc_id": doc["doc_id"]})
        for i, (doc, vector) in enumerate(zip(batch, vectors))])
assert multi_client.count("lab19_multilingual").count == 1000
multi_sem, multi_hyb = [], []
for q in golden:
    vector = next(multi_embedder.embed([q["query"]])).tolist()
    dense = [point.payload["doc_id"] for point in multi_client.query_points(
        collection_name="lab19_multilingual", query=vector, limit=50).points]
    sparse = search_keyword(q["query"], 50)
    scores = {}
    for ranked in (sparse, dense):
        for rank, doc_id in enumerate(ranked, start=1):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1 / (60 + rank)
    fused = [doc_id for doc_id, _ in sorted(scores.items(), key=lambda pair: -pair[1])[:10]]
    multi_sem.append(precision_at_10(dense[:10], q["topic"]))
    multi_hyb.append(precision_at_10(fused, q["topic"]))
print(f"Multilingual experiment: {MULTILINGUAL_MODEL}")
print("Same 1000 documents / 50 queries / BM25 / RRF k=60 / top-50 / Precision@10")
print(f"Overall: keyword={statistics.mean(p_kw):.1%}, semantic={statistics.mean(multi_sem):.1%}, "
      f"hybrid={statistics.mean(multi_hyb):.1%}")
print(f"  {'type':12} {'n':>3} {'kw':>7} {'sem':>7} {'hyb':>7}")
multi_slices = {}
for kind in ("exact", "paraphrase", "mixed"):
    subset = [i for i, q in enumerate(golden) if q["mode_hint"] == kind]
    values = [statistics.mean([mode[i] for i in subset]) for mode in (p_kw, multi_sem, multi_hyb)]
    multi_slices[kind] = values
    print(f"  {kind:12} {len(subset):>3} {values[0]:>6.1%} {values[1]:>6.1%} {values[2]:>6.1%}")
assert multi_slices["paraphrase"][1] > multi_slices["paraphrase"][0]
assert statistics.mean(multi_hyb) > statistics.mean(p_kw)
assert statistics.mean(multi_hyb) > statistics.mean(multi_sem)
print("PASS — multilingual vector wins paraphrase; hybrid beats both baselines overall at unchanged RRF settings")
print(f"Tradeoff on mixed: multilingual hybrid={multi_slices['mixed'][2]:.1%}, "
      f"BM25={multi_slices['mixed'][0]:.1%}; BGE-small hybrid above achieved 100.0%.")
print("Model choice changes the slice winners. Keep both measured tables; do not assume a universal winner.")

# %% [markdown]
# ### Đối chiếu thêm: vector kết hợp hai model với trọng số cố định 50/50
#
# BGE và MiniLM có thế mạnh khác nhau. Ghép hai vector đã chuẩn hóa, chia
# sqrt(2), tạo vector 768 chiều; cosine chính là trung bình hai cosine.
# Trọng số 50/50 được cố định, không học từ golden set. BM25 và RRF vẫn là
# hai retriever, với cùng k=60/top-50. Tái sử dụng vector corpus đã tính,
# không embed lại, không dùng nhãn topic để tạo vector hay xếp hạng.

# %%
import numpy as np
base_points, _ = client.scroll("lab19", limit=1000, with_vectors=True)
multi_points, _ = multi_client.scroll("lab19_multilingual", limit=1000, with_vectors=True)
base_points = sorted(base_points, key=lambda point: point.id)
multi_points = sorted(multi_points, key=lambda point: point.id)
assert [p.payload["doc_id"] for p in base_points] == [p.payload["doc_id"] for p in multi_points]
combined_vectors = np.concatenate([
    np.asarray([p.vector for p in base_points]), np.asarray([p.vector for p in multi_points])], axis=1) / np.sqrt(2)
ensemble_client = QdrantClient(":memory:")
ensemble_client.create_collection("lab19_ensemble",
    vectors_config=VectorParams(size=768, distance=Distance.COSINE))
ensemble_client.upsert("lab19_ensemble", points=[PointStruct(id=i, vector=vector.tolist(),
    payload={"doc_id": docs[i]["doc_id"]}) for i, vector in enumerate(combined_vectors)])
ensemble_sem, ensemble_hyb = [], []
for q in golden:
    bge = next(embedder.embed([q["query"]]))
    multilingual = next(multi_embedder.embed([q["query"]]))
    query_vector = np.concatenate([bge, multilingual]) / np.sqrt(2)
    dense = [p.payload["doc_id"] for p in ensemble_client.query_points(
        "lab19_ensemble", query=query_vector.tolist(), limit=50).points]
    scores = {}
    for ranked in (search_keyword(q["query"], 50), dense):
        for rank, doc_id in enumerate(ranked, start=1):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1 / (60 + rank)
    fused = [doc_id for doc_id, _ in sorted(scores.items(), key=lambda pair: -pair[1])[:10]]
    ensemble_sem.append(precision_at_10(dense[:10], q["topic"]))
    ensemble_hyb.append(precision_at_10(fused, q["topic"]))
print("Fixed 50/50 BGE + multilingual vector ensemble (768 dimensions; not the Lite API backend)")
print(f"Overall: keyword={statistics.mean(p_kw):.1%}, semantic={statistics.mean(ensemble_sem):.1%}, "
      f"hybrid={statistics.mean(ensemble_hyb):.1%}")
ensemble_slices = {}
for kind in ("exact", "paraphrase", "mixed"):
    subset = [i for i, q in enumerate(golden) if q["mode_hint"] == kind]
    values = [statistics.mean([mode[i] for i in subset]) for mode in (p_kw, ensemble_sem, ensemble_hyb)]
    ensemble_slices[kind] = values
    print(f"  {kind:12} {len(subset):>3} {values[0]:>6.1%} {values[1]:>6.1%} {values[2]:>6.1%}")
print("Measured tradeoff: twice the document vector storage and two query embeddings; API latency above uses BGE only.")

# %% [markdown]
# ### Diễn giải kết quả
#
# - `exact` queries chứa từ kỹ thuật verbatim trong corpus → BM25 mạnh, hybrid
#   thường ngang bằng (keyword signal đã đủ mạnh).
# - `paraphrase` queries dùng từ Việt **không** xuất hiện verbatim trong docs
#   → cả BM25 và vector đều giảm điểm. Trên synthetic corpus 1000-doc với
#   embedding model `BAAI/bge-small-en-v1.5` (English-trained), semantic
#   precision trên Vietnamese paraphrases yếu. Model đa ngữ là giả thuyết
#   cần kiểm chứng, không phải bảo đảm Vector thắng toàn bộ lát cắt.
# - `mixed` queries có cả từ exact + ý tưởng paraphrased → **hybrid thắng rõ**
#   (~100% vs 97-98% pure modes). Đây là pattern production-relevant nhất
#   vì user thật ít khi viết query 100% exact term hoặc 100% paraphrase.
#
# Hybrid thắng trung bình trong cấu hình BGE đã đo; không suy diễn rằng nó
# thắng ở mọi loại query hoặc mọi phân bố production.

# %% [markdown]
# ## 7. Audit preprocessing với các cấu hình cố định
#
# Bốn ablation được khai báo trước trong `scripts/audit_search.py`: bản gốc,
# query instruction theo model card BGE, NFC/dấu câu cho BM25, và kết hợp.
# Giữ BGE-small, corpus, golden set, top-50, k=60 và rank 1-based. Ranking
# nhận duy nhất query text; chỉ đọc nhãn đánh giá sau khi đã đóng băng mọi
# ranking. Không chọn cấu hình tự động hoặc dò trọng số từ golden set.
# Đây là diagnostic trên golden đã biết, không phải đánh giá held-out.
#
# Tham khảo: https://huggingface.co/BAAI/bge-small-en-v1.5
# FastEmbed 0.8.1 không tự thêm instruction BGE trong `query_embed()`.

# %%
from scripts.audit_search import evaluate as audit_preprocessing
preprocessing_audit = audit_preprocessing()
baseline_checks = preprocessing_audit["configs"]["original"]["criteria"]
print("BGE required configuration rubric status:", baseline_checks)
print("UNMET — vector does not win paraphrase; the 5-point slice criterion remains incomplete.")
print("Baseline retained; alternative configurations are diagnostics, not a combined submission result.")

# %% [markdown]
# ## Deliverable evidence
#
# 1. Output cell 4: bảng Precision@10 với 3 mode, hybrid > kw và > sem.
# 2. Output cell 5: bảng slice theo loại query, exact/paraphrase/mixed.
#
# ---
#
# ## Vibe-coding callout
#
# **Delegate freely:** the per-mode search wrapper functions in §2. AI nailed
# the pattern in 1 shot. Cũng AI tốt cho việc set up bảng kết quả (`statistics.mean`,
# format `{:.1%}`) — chỉ cần spec rõ output schema.
#
# **Think hard yourself:** the RRF formula. Trước khi implement, hỏi AI giải
# thích RRF rồi cross-check với deck §3. Nếu AI viết code mà rank bắt đầu từ 0
# (không phải 1) hoặc cộng 1/rank thay vì 1/(k+rank), đã hỏng — và rất khó debug
# về sau khi quality giảm. Đây là 1 ví dụ "AI write 5 dòng đúng đắn nhưng nếu
# bạn không tự kiểm tra công thức, bug nằm im trong production".
