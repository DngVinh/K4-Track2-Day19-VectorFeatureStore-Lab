"""Read-only tokenization/truncation diagnostics for the mandatory BGE corpus."""
from collections import Counter
import json
from pathlib import Path
import statistics
from tokenizers import Tokenizer

ROOT = Path(__file__).resolve().parent.parent


def main():
    cache = ROOT / ".cache/fastembed/models--Qdrant--bge-small-en-v1.5-onnx-Q"
    revision = (cache / "refs/main").read_text().strip()
    assert len(revision) == 40 and all(c in "0123456789abcdef" for c in revision)
    tokenizer = Tokenizer.from_file(str(cache / "snapshots" / revision / "tokenizer.json"))
    tokenizer.no_truncation()
    tokenizer.no_padding()
    docs = [json.loads(line) for line in (ROOT / "data/corpus_vn.jsonl").read_text(encoding="utf-8").splitlines()]
    golden = [json.loads(line) for line in (ROOT / "data/golden_set.jsonl").read_text(encoding="utf-8").splitlines()]
    texts = [doc["title"] + " " + doc["text"] for doc in docs]
    encoded = tokenizer.encode_batch(texts)
    lengths = [len(e.ids) for e in encoded]
    queries = tokenizer.encode_batch([q["query"] for q in golden])
    print("BGE revision", revision)
    print("Documents: count/min/median/max tokens", len(lengths), min(lengths), statistics.median(lengths), max(lengths))
    print("Documents exceeding 512 tokens:", sum(length > 512 for length in lengths))
    print("Unknown tokens in documents:", sum(e.tokens.count("[UNK]") for e in encoded), "of", sum(lengths))
    print("Unknown tokens in queries:", sum(e.tokens.count("[UNK]") for e in queries), "of", sum(len(e.ids) for e in queries))
    print("Corpus topic counts", dict(Counter(d["topic"] for d in docs)))
    print("Duplicate title+text:", len(texts) - len(set(texts)))
    print("All query relevance sets exactly equal their 100-doc topic:", all(
        set(q["relevant_doc_ids"]) == {d["doc_id"] for d in docs if d["topic"] == q["topic"]} for q in golden))
    print("P10 uses fixed denominator 10. Query mode labels only describe evaluation slices.")
    print("No file, corpus, query, model, ranking or ground truth is modified.")


if __name__ == "__main__":
    main()
