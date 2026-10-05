"""Run a Python validation command and keep its real stdout, stderr and exit code."""
import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parent.parent


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("label")
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    assert args.label.replace("_", "").isalnum() and args.command
    cache = ROOT / ".cache"
    temporary = (cache / "tmp" / ("check_" + uuid4().hex)).resolve()
    assert temporary.is_relative_to(ROOT) and not temporary.exists()
    temporary.mkdir(parents=True)
    for key, folder in (("FASTEMBED_CACHE_PATH", "fastembed"), ("HF_HOME", "huggingface"),
                        ("TEMP", "tmp"), ("TMP", "tmp")):
        target = (cache / folder).resolve()
        if key in ("TEMP", "TMP"):
            target = temporary
        assert target.is_relative_to(ROOT)
        target.mkdir(parents=True, exist_ok=True)
        os.environ[key] = str(target)
    os.environ["PYTHONUTF8"] = "1"
    command = [sys.executable, *args.command]
    start = datetime.now(timezone.utc)
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    folder = (ROOT / "submission/checks").resolve()
    assert folder.is_relative_to(ROOT)
    folder.mkdir(parents=True, exist_ok=True)
    name = f"{args.label}_{start.strftime('%Y%m%dT%H%M%SZ')}_{uuid4().hex[:6]}"
    (folder / (name + ".txt")).write_text(result.stdout + "\nSTDERR:\n" + result.stderr, encoding="utf-8")
    (folder / (name + ".json")).write_text(json.dumps({
        "command": command, "started_utc": start.isoformat(),
        "finished_utc": datetime.now(timezone.utc).isoformat(), "exit_code": result.returncode,
        "workspace_temp": str(temporary),
    }, indent=2), encoding="utf-8")
    print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)
    print(f"Recorded {name}: exit {result.returncode}")
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
