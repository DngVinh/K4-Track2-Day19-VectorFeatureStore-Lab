"""Prefetch the exact FastEmbed Lite model into a workspace-local HF cache.

Uses an immutable Hugging Face revision and validates published size/hash.
Existing files are checked and preserved; a partial file is never overwritten.
"""
import hashlib
import argparse
import json
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPO = "Qdrant/bge-small-en-v1.5-onnx-Q"
FILES = {"config.json", "tokenizer.json", "tokenizer_config.json",
         "special_tokens_map.json", "model_optimized.onnx"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--multilingual", action="store_true",
                        help="Also-supported 384d multilingual MiniLM, for the NB2 comparison")
    args = parser.parse_args()
    repo = "qdrant/paraphrase-multilingual-MiniLM-L12-v2-onnx-Q" if args.multilingual else REPO
    with urllib.request.urlopen(f"https://huggingface.co/api/models/{repo}?blobs=true", timeout=60) as response:
        info = json.load(response)
    revision = info["sha"]
    assert len(revision) == 40 and all(c in "0123456789abcdef" for c in revision)
    cache = (ROOT / ".cache/fastembed" / ("models--" + repo.replace("/", "--"))).resolve()
    assert cache.is_relative_to(ROOT)
    snapshot = cache / "snapshots" / revision
    snapshot.mkdir(parents=True, exist_ok=True)
    print(f"Model: {repo}; immutable revision: {revision}", flush=True)
    for entry in info["siblings"]:
        name = entry["rfilename"]
        if name not in FILES:
            continue
        path = (snapshot / name).resolve()
        assert path.is_relative_to(snapshot)
        if not path.exists():
            print(f"Downloading {name} ({entry.get('size', 0):,} bytes)", flush=True)
            with urllib.request.urlopen(f"https://huggingface.co/{repo}/resolve/{revision}/{name}", timeout=120) as response:
                with path.open("xb") as target:
                    downloaded = 0
                    while chunk := response.read(1024 * 1024):
                        target.write(chunk)
                        downloaded += len(chunk)
                        if downloaded % (8 * 1024 * 1024) == 0:
                            print(f"  {downloaded // (1024 * 1024)} MiB", flush=True)
        if "size" in entry:
            assert path.stat().st_size == entry["size"], f"Size mismatch: {path} (preserved)"
        expected = entry.get("lfs", {}).get("sha256")
        if expected:
            digest = hashlib.sha256()
            with path.open("rb") as source:
                while chunk := source.read(1024 * 1024):
                    digest.update(chunk)
            assert digest.hexdigest() == expected
        print(f"Verified {name}", flush=True)
    refs = cache / "refs"
    refs.mkdir(exist_ok=True)
    ref = refs / "main"
    if ref.exists():
        assert ref.read_text() == revision, "Existing model revision preserved"
    else:
        with ref.open("x") as target:
            target.write(revision)
    print("PASS — Lite model files verified and ready in workspace cache", flush=True)


if __name__ == "__main__":
    main()
