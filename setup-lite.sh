#!/usr/bin/env bash
# Lite path: pure Python, in-process Qdrant, SQLite Feast online store.
# No Docker, no GPU, no external services. ~60s on a clean machine.

set -euo pipefail

echo "[lite] Day 19 lightweight setup"
echo "[lite] Stack: fastembed + qdrant-client[memory] + rank-bm25 + feast(sqlite) + FastAPI"
echo

# ── 1. Python ───────────────────────────────────────────────────────────
if command -v python3 >/dev/null 2>&1 && python3 -c 'import sys' >/dev/null 2>&1; then
  LAB_SYSTEM_PY=python3
elif command -v python >/dev/null 2>&1; then
  LAB_SYSTEM_PY=python
else
  echo "[lite] Python not found. Install Python 3.10+."; exit 1
fi
PY_VER=$("$LAB_SYSTEM_PY" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo "[lite] system python3 is $PY_VER (the venv may differ — reported below)"

# ── 2. venv ─────────────────────────────────────────────────────────────
if [ ! -d ".venv" ]; then
  if command -v uv >/dev/null 2>&1; then
    echo "[lite] Creating venv with uv (faster)"
    uv venv --python "$LAB_SYSTEM_PY" .venv
  else
    echo "[lite] Creating venv with python -m venv"
    "$LAB_SYSTEM_PY" -m venv .venv
  fi
fi
# shellcheck source=/dev/null
if [ -f .venv/Scripts/activate ]; then
  LAB_BIN=Scripts
else
  LAB_BIN=bin
fi
source ".venv/$LAB_BIN/activate"
LAB_VENV_PY=$(python -c 'import sys; print(sys.executable)')

# Keep downloaded packages, models and temporary files in this project.
LAB_ROOT=$(pwd)
mkdir -p .cache/tmp .cache/pip .cache/uv .cache/fastembed .cache/huggingface \
         .cache/jupyter/config .cache/jupyter/data .cache/jupyter/runtime .cache/ipython
export TEMP="$LAB_ROOT/.cache/tmp" TMP="$LAB_ROOT/.cache/tmp" TMPDIR="$LAB_ROOT/.cache/tmp"
export PIP_CACHE_DIR="$LAB_ROOT/.cache/pip" UV_CACHE_DIR="${UV_CACHE_DIR:-$LAB_ROOT/.cache/uv}"
export FASTEMBED_CACHE_PATH="$LAB_ROOT/.cache/fastembed" HF_HOME="$LAB_ROOT/.cache/huggingface"
export JUPYTER_CONFIG_DIR="$LAB_ROOT/.cache/jupyter/config" JUPYTER_DATA_DIR="$LAB_ROOT/.cache/jupyter/data"
export JUPYTER_RUNTIME_DIR="$LAB_ROOT/.cache/jupyter/runtime" IPYTHONDIR="$LAB_ROOT/.cache/ipython"
export PYTHONUTF8=1

# ── 3. Install deps ─────────────────────────────────────────────────────
# `uv venv` may pick a different interpreter than the system `python3`, so the
# dill decision must be made from the VENV's Python (already active here), not
# from the version printed above.
VENV_PY_VER=$(python -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
NEED_DILL_OVERRIDE=$(python -c 'import sys; print(1 if sys.version_info >= (3,14) else 0)')
echo "[lite] venv Python $VENV_PY_VER"
if [ "$NEED_DILL_OVERRIDE" = "1" ]; then
  echo "[lite] Python >= 3.14 -> applying dill>=0.4 override (feast's pin is too old; see requirements.txt)"
fi

# uv overrides are needed to resolve Feast's incompatible dill pin on 3.14.
# Bootstrap into the active venv, never a system installation.
if ! command -v uv >/dev/null 2>&1 && [ "$NEED_DILL_OVERRIDE" = "1" ]; then
  python -m pip install uv
fi
if command -v uv >/dev/null 2>&1; then
  if [ "$NEED_DILL_OVERRIDE" = "1" ]; then
    uv pip install --python "$LAB_VENV_PY" --overrides overrides-py314.txt -r requirements.txt
  else
    uv pip install --python "$LAB_VENV_PY" -r requirements.txt
  fi
else
  python -m pip install -q -U pip
  python -m pip install -q -r requirements.txt
  if [ "$NEED_DILL_OVERRIDE" = "1" ]; then
    python -m pip install -q --upgrade 'dill>=0.4,<1.0'
  fi
fi

# ── 4. Convert Jupytext sources to .ipynb ───────────────────────────────
# `_setup.py` is a helper module, not a notebook -- converting it produces
# a _setup.ipynb that fails on execute. Only convert numbered notebooks.
for source in notebooks/[0-9]*.py; do
  target="${source%.py}.ipynb"
  if [ -e "$target" ]; then
    echo "[lite] Preserving existing notebook: $target (use make notebooks for a new run)"
  else
    python -m jupytext --to notebook "$source"
  fi
done

# ── 5. .env scaffold ────────────────────────────────────────────────────
[ -f .env ] || cp .env.example .env

# ── 6. Seed corpus + golden set ─────────────────────────────────────────
if [ ! -e data/corpus_vn.jsonl ] && [ ! -e data/golden_set.jsonl ]; then
  python scripts/seed_corpus.py
elif [ -e data/corpus_vn.jsonl ] && [ -e data/golden_set.jsonl ]; then
  echo "[lite] Preserving existing corpus and golden set"
else
  echo "[lite] Incomplete corpus/golden pair; existing data preserved. Use a fresh directory."; exit 1
fi

# Data for the advanced missions (NB6 compound queries, NB8 spend parquet).
# gen_agent_queries embeds the corpus once to build brute-force ground truth,
# so this adds ~20 s -- worth it: the alternative is students hand-labelling.
echo "  · seeding advanced-mission data (NB6 + NB8)…"
[ -e data/agent_queries.jsonl ] || python scripts/gen_agent_queries.py
[ -e app/feast_repo_ondemand/data/user_spend.parquet ] || python scripts/gen_spend.py

# ── 7. Smoke test ───────────────────────────────────────────────────────
python scripts/verify_lite.py

cat <<EOF

[lite] Done. Activate the venv and start working:

    source .venv/$LAB_BIN/activate
    make api       # start FastAPI on :8000
    make lab       # open Jupyter on :8888
    make benchmark # Precision@10 + latency table

Tip: read VIBE-CODING.md before starting NB1 — it tells you what to delegate
to your AI assistant and what to think through yourself.
EOF
