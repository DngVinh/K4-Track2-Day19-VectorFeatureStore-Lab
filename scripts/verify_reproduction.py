"""Run the literal Bash/Make rubric commands in a fresh, allowlisted copy.

No environment, model/pip cache, Git metadata, credentials or generated data
are copied. Each invocation creates a new directory and retains every log.
Use --prepare-only to inspect the copy without installing dependencies.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from uuid import uuid4

ROOT = Path(__file__).resolve().parent.parent


def safe(path: Path) -> Path:
    path = path.resolve()
    if not path.is_relative_to(ROOT) or path == ROOT:
        raise ValueError(f"Outside scoped workspace: {path}")
    return path


def run_logged(command, cwd, env, folder, label):
    stdout_path = safe(folder / (label + ".stdout.txt"))
    stderr_path = safe(folder / (label + ".stderr.txt"))
    started = datetime.now(timezone.utc).isoformat()
    print(f"RUN {label}: {command}", flush=True)
    with stdout_path.open("xb") as out, stderr_path.open("xb") as err:
        result = subprocess.run(command, cwd=cwd, env=env, stdout=out, stderr=err)
    record = {"command": command, "cwd": str(cwd), "started_utc": started,
              "finished_utc": datetime.now(timezone.utc).isoformat(), "exit_code": result.returncode,
              "stdout": stdout_path.name, "stderr": stderr_path.name}
    with safe(folder / (label + ".json")).open("x", encoding="utf-8") as target:
        json.dump(record, target, indent=2)
    print(f"EXIT {label}: {result.returncode}", flush=True)
    print(stdout_path.read_text(encoding="utf-8", errors="replace")[-3500:], flush=True)
    if result.returncode:
        print(stderr_path.read_text(encoding="utf-8", errors="replace")[-3500:], flush=True)
    return record


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--notebooks", action="store_true", help="Execute all notebooks and bonus in the isolated copy")
    parser.add_argument("--notebook-numbers", nargs="+", default=[],
                        help="Limit execution to affected prefixes; include 04 before running the bonus")
    parser.add_argument("--package-cache", type=Path,
                        help="Optional workspace wheel cache; no venv, model cache or generated data is copied")
    args = parser.parse_args()
    status = subprocess.check_output(["git", "status", "--short"], cwd=ROOT, text=True)
    run = safe(ROOT / "submission/runs" / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "_reproduction_" + uuid4().hex[:6]))
    run.mkdir(parents=True)
    with (run / "initial_status.txt").open("x", encoding="utf-8") as target:
        target.write(status)
    fresh = safe(ROOT / ".cache/reproduction" / run.name)
    fresh.mkdir(parents=True)
    selected = [ROOT / p for p in ("Makefile", "setup-lite.sh", "requirements.txt", "overrides-py314.txt",
                                  "pyproject.toml", "README.md", ".env.example")]
    for folder in ("app", "notebooks", "scripts", "tests", "bonus"):
        selected.extend(p for p in (ROOT / folder).rglob("*")
                        if p.is_file() and p.suffix in (".py", ".yaml") and "__pycache__" not in p.parts)
    copies = []
    for source in sorted(set(selected)):
        source = safe(source)
        relative = source.relative_to(ROOT)
        assert source.is_file() and not any(part in (".git", ".venv", ".cache", "data") for part in relative.parts)
        destination = safe(fresh / relative)
        assert not destination.exists() and destination.is_relative_to(fresh)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        copies.append({"path": relative.as_posix(), "sha256": hashlib.sha256(source.read_bytes()).hexdigest()})
    with (run / "copy_manifest.json").open("x", encoding="utf-8") as target:
        json.dump({"fresh_root": str(fresh), "files": copies, "copied_generated_data": False,
                   "copied_environment_or_cache": False,
                   "installer_package_cache": str(safe(args.package_cache)) if args.package_cache else "empty cache inside fresh root",
                   "model_cache_shared": False}, target, indent=2)
    print(f"Evidence: {run}\nFresh root: {fresh}", flush=True)
    if args.prepare_only:
        return 0
    bash = Path(r"C:\Program Files\Git\bin\bash.exe")
    make_folder = safe(ROOT / ".cache/tools/gnu-make-4.4.1-5")
    assert bash.is_file() and (make_folder / "make.exe").is_file(), "Run scripts/portable_make.py first"
    env = os.environ.copy()
    # Force Lite, empty local caches, and local temp dirs. Never print inherited env/credentials.
    for key, directory in (("TEMP", "tmp"), ("TMP", "tmp"), ("TMPDIR", "tmp"),
                           ("UV_CACHE_DIR", "uv"), ("PIP_CACHE_DIR", "pip"),
                           ("HF_HOME", "huggingface"), ("FASTEMBED_CACHE_PATH", "fastembed"),
                           ("JUPYTER_CONFIG_DIR", "jupyter/config"), ("JUPYTER_DATA_DIR", "jupyter/data"),
                           ("JUPYTER_RUNTIME_DIR", "jupyter/runtime"), ("IPYTHONDIR", "ipython")):
        target = safe(fresh / ".cache" / directory)
        target.mkdir(parents=True, exist_ok=True)
        env[key] = str(target)
    if args.package_cache:
        package_cache = safe(args.package_cache)
        assert package_cache.is_dir()
        env["UV_CACHE_DIR"] = str(package_cache)
    installer = safe(ROOT / ".venv/Scripts/uv.exe")
    # Reuse a standalone installer executable as a tool, not its Python environment.
    installer_bin = str(installer.parent) + os.pathsep if installer.is_file() else ""
    env["PATH"] = str(make_folder) + os.pathsep + r"C:\Program Files\Git\mingw64\bin" + os.pathsep + installer_bin + env["PATH"]
    env["PYTHONUTF8"] = "1"
    env["PYTHONUNBUFFERED"] = "1"
    env["EMBEDDING_BACKEND"] = "fastembed"
    env["QDRANT_MODE"] = "memory"
    records = []
    command = [str(bash), "--noprofile", "--norc", "-c"]
    version_command = "bash --version; make --version; python --version"
    if installer.is_file():
        version_command += "; uv --version"
    records.append(run_logged(command + [version_command], fresh, env, run, "tools"))
    records.append(run_logged(command + ["bash setup-lite.sh && make benchmark"], fresh, env, run, "setup_benchmark"))
    python = fresh / ".venv/Scripts/python.exe"
    if python.exists():
        records.append(run_logged(command + ["make test"], fresh, env, run, "make_test"))
        records.append(run_logged(command + ["make verify-lite"], fresh, env, run, "make_verify_lite"))
        records.append(run_logged([str(python), "-c", "import sys,platform,importlib.metadata as m,json; print(json.dumps({'python':sys.version,'platform':platform.platform(),'packages':{p:m.version(p) for p in ('fastembed','qdrant-client','feast','dill','pyarrow','numpy','pytest','jupytext')}},indent=2))"], fresh, env, run, "environment"))
        hashes = {}
        for name in ("corpus_vn.jsonl", "golden_set.jsonl"):
            generated = fresh / "data" / name
            if generated.exists():
                hashes[name] = {"original": hashlib.sha256((ROOT / "data" / name).read_bytes()).hexdigest(),
                                "fresh": hashlib.sha256(generated.read_bytes()).hexdigest()}
                assert hashes[name]["original"] == hashes[name]["fresh"], "Corpus/golden changed; stop"
        with (run / "data_hashes.json").open("x", encoding="utf-8") as target:
            json.dump(hashes, target, indent=2)
        if args.notebooks and records[1]["exit_code"] == 0:
            records.append(run_logged([str(python), "scripts/run_notebooks.py", *args.notebook_numbers], fresh, env, run, "notebooks"))
            records.append(run_logged([str(python), "bonus/demo.py"], fresh, env, run, "bonus"))
            # Copy only new executed artifacts from this fresh run, keeping old outputs.
            for source in (fresh / "submission/runs").rglob("*"):
                if source.is_file() and source.suffix in (".ipynb", ".txt", ".json"):
                    destination = safe(run / "notebooks" / source.relative_to(fresh / "submission/runs"))
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    assert not destination.exists()
                    shutil.copyfile(safe(source), destination)
    with (run / "results.json").open("x", encoding="utf-8") as target:
        json.dump(records, target, indent=2)
    print(f"Evidence: {run}", flush=True)
    return int(any(record["exit_code"] for record in records))


if __name__ == "__main__":
    raise SystemExit(main())
