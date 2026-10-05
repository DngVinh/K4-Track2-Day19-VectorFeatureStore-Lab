"""Execute numbered Jupytext notebooks, preserving outputs and failures.

Run with the lab's virtual-environment Python. Each run has a new evidence
directory, so prior notebook outputs and execution logs are preserved.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("numbers", nargs="*", help="Notebook prefixes, e.g. 01 04")
    args = parser.parse_args()
    import jupytext
    import nbformat
    from nbclient import NotebookClient
    from jupyter_client.kernelspec import KernelSpecManager

    run = ROOT / "submission" / "runs" / (
        datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "_" + uuid4().hex[:6]
    )
    run.mkdir(parents=True)
    os.environ["PATH"] = str(Path(sys.executable).parent) + os.pathsep + os.environ["PATH"]
    cache = ROOT / ".cache"
    for key, folder in (("FASTEMBED_CACHE_PATH", "fastembed"), ("HF_HOME", "huggingface"),
                        ("JUPYTER_RUNTIME_DIR", "jupyter/runtime"), ("IPYTHONDIR", "ipython"),
                        ("JUPYTER_CONFIG_DIR", "jupyter/config"), ("JUPYTER_DATA_DIR", "jupyter/data"),
                        ("TEMP", "tmp"), ("TMP", "tmp")):
        target = (cache / folder).resolve()
        assert target.is_relative_to(ROOT)
        target.mkdir(parents=True, exist_ok=True)
        os.environ[key] = str(target)
    os.environ["PYTHONUTF8"] = "1"
    os.environ["QDRANT_MODE"] = "memory"
    os.environ["EMBEDDING_BACKEND"] = "fastembed"
    sources = sorted((ROOT / "notebooks").glob("[0-9]*.py"))
    if args.numbers:
        sources = [p for p in sources if p.name[:2] in args.numbers]
    assert sources, "No matching notebooks"
    kernel_root = cache / "kernels" / run.name
    kernel_dir = kernel_root / "python3"
    kernel_dir.mkdir(parents=True)
    (kernel_dir / "kernel.json").write_text(json.dumps({
        "argv": [sys.executable, "-m", "ipykernel_launcher", "-f", "{connection_file}"],
        "display_name": "Lab .venv", "language": "python",
    }), encoding="utf-8")
    results = []
    for source in sources:
        print(f"Executing {source.name}", flush=True)
        notebook = jupytext.read(source)
        manager = KernelSpecManager(kernel_dirs=[str(kernel_root)])
        client = NotebookClient(notebook, timeout=900, kernel_name="python3",
                                resources={"metadata": {"path": str(source.parent)}})
        from jupyter_client import KernelManager
        client.km = KernelManager(kernel_name="python3", kernel_spec_manager=manager)
        error = None
        try:
            client.execute()
        except Exception as exc:
            error = str(exc)
        target = run / source.with_suffix(".ipynb").name
        nbformat.write(notebook, target)
        lines = []
        for cell in notebook.cells:
            if cell.cell_type != "code":
                continue
            for output in cell.get("outputs", []):
                if output.output_type == "stream":
                    lines.append(output.text)
                elif output.output_type in ("display_data", "execute_result"):
                    lines.append(output.get("data", {}).get("text/plain", ""))
                elif output.output_type == "error":
                    lines.append("\n".join(output.traceback))
        target.with_suffix(".txt").write_text("\n".join(lines), encoding="utf-8")
        published = source.with_suffix(".ipynb").resolve()
        assert published.is_relative_to(ROOT)
        if error is None and not published.exists():
            with published.open("x", encoding="utf-8") as output_file:
                nbformat.write(notebook, output_file)
        elif published.exists():
            print(f"Preserved existing {published.name}; fresh outputs are in {target}", flush=True)
        results.append({"notebook": source.stem, "passed": error is None,
                        "output": str(target.relative_to(ROOT)), "error": error})
        print(f"{'PASS' if error is None else 'FAIL'} {source.name}", flush=True)
        if error:
            print(error[-4000:], flush=True)
    (run / "results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Evidence: {run}", flush=True)
    return int(any(not r["passed"] for r in results))


if __name__ == "__main__":
    raise SystemExit(main())
