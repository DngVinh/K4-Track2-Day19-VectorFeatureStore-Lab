"""Render actual executed notebook outputs to HTML and PNG evidence.

No result values are invented. Default PNGs render saved notebook outputs
directly; --renderer browser captures the HTML when headless Chrome is allowed.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import subprocess
import textwrap
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parent.parent
NAMES = {"01": "nb1_indexed_1000", "02": "nb2_precision_table", "03": "nb3_latency_p99",
         "04": "nb4_feast_materialize", "05": "nb5_filtered_search",
         "06": "nb6_agent_retrieval", "07": "nb7_semantic_cache", "08": "nb8_feature_engineering"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--browser", type=Path, default=Path(
        r"C:\Program Files\Google\Chrome\Application\chrome.exe"))
    parser.add_argument("--renderer", choices=("pillow", "browser"), default="pillow")
    args = parser.parse_args()
    if args.renderer == "browser" and not args.browser.is_file():
        raise FileNotFoundError("Pass --browser with the installed Chrome/Chromium executable")
    import nbformat
    folder = ROOT / "submission" / "screenshots"
    folder.mkdir(parents=True, exist_ok=True)
    manifest = []
    for path in sorted((ROOT / "notebooks").glob("[0-9]*.ipynb")):
        notebook = nbformat.read(path, as_version=4)
        blocks = []
        rendered_blocks = []
        for cell in notebook.cells:
            outputs = cell.get("outputs", [])
            if cell.cell_type != "code" or not outputs:
                continue
            text = []
            for out in outputs:
                if out.output_type == "error":
                    raise RuntimeError(f"Cannot certify a failed notebook: {path.name}")
                if out.output_type == "stream":
                    if out.get("name") == "stdout":
                        text.append(out.text)
                else:
                    text.append(out.get("data", {}).get("text/plain", ""))
            value = re.sub(r"\x1b\[[0-9;]*m", "", "\n".join(text))
            # Keep full execution output in .ipynb and .txt; omit library warning
            # streams in the screenshot so the measured tables stay readable.
            value = "\n".join(line for line in value.splitlines()
                              if not line.lstrip().startswith(("C:\\", "UserWarning:", "FutureWarning:")))
            if path.name.startswith("04") and "Updated feature view" in value:
                # Feast's update log contains lengthy protobuf timestamp diffs.
                # Show the actual operation lines and registry table; full diffs
                # remain in the executed notebook and raw execution log.
                prefixes = ("STDOUT:", "No project", "Applying", "Created", "Updated feature view",
                            "No changes", "NAME", "query_velocity_features ",
                            "item_popularity_features ", "user_profile_features ")
                value = "\n".join(line for line in value.splitlines() if line.startswith(prefixes))
            if path.name.startswith("03") and value.lstrip().startswith("{"):
                try:
                    sample, _ = json.JSONDecoder().raw_decode(value.lstrip())
                    if isinstance(sample, dict) and "hits" in sample:
                        total = len(sample["hits"])
                        sample["hits"] = sample["hits"][:3]
                        value = f"API response sample: first 3 of {total} hits (complete response in notebook)\n" + json.dumps(
                            sample, ensure_ascii=False, indent=2)
                except ValueError:
                    pass
            if value.strip():
                rendered_blocks.append((cell.execution_count, value))
                blocks.append(f"<section><h2>Output [{cell.execution_count}]</h2>"
                              f"<pre>{html.escape(value)}</pre></section>")
        name = NAMES[path.name[:2]]
        evidence_html = (folder / (name + ".html")).resolve()
        png = (folder / (name + ".png")).resolve()
        assert evidence_html.is_relative_to(ROOT) and png.is_relative_to(ROOT)
        document = ("<!doctype html><meta charset='utf-8'><style>"
                    "body{font-family:Arial;background:#f5f7fa;color:#142033;padding:28px;margin:0}"
                    "h1{font-size:28px;margin:0 0 12px}h2{font-size:15px;color:#526174;margin:0 0 10px}"
                    "section{background:white;border:1px solid #dde3ec;border-radius:8px;padding:18px;margin:14px 0}"
                    "pre{font:16px/1.55 Consolas,monospace;white-space:pre-wrap;overflow-wrap:anywhere;margin:0}"
                    "p{font-size:14px}</style>"
                    f"<h1>Lab 19 · {html.escape(path.stem)}</h1>"
                    "<p>Actual executed notebook outputs · Lite / Python 3.14 · "
                    "Saved output evidence; complete outputs are retained in the notebook.</p>"
                    + "".join(blocks))
        evidence_html.write_text(document, encoding="utf-8")
        if args.renderer == "pillow":
            from PIL import Image, ImageDraw, ImageFont
            font = ImageFont.truetype(r"C:\Windows\Fonts\consola.ttf", 18)
            heading = ImageFont.truetype(r"C:\Windows\Fonts\arialbd.ttf", 28)
            small = ImageFont.truetype(r"C:\Windows\Fonts\arial.ttf", 16)
            prepared = []
            for count, value in rendered_blocks:
                wrapped = []
                for line in value.splitlines():
                    wrapped.extend(textwrap.wrap(line, width=130, replace_whitespace=False,
                                                 drop_whitespace=False) or [""])
                prepared.append((count, wrapped))
            height = 145 + sum(76 + len(lines) * 26 for _, lines in prepared)
            canvas = Image.new("RGB", (1500, max(height, 900)), "#f5f7fa")
            draw = ImageDraw.Draw(canvas)
            draw.text((30, 24), f"Lab 19 | {path.stem}", fill="#142033", font=heading)
            draw.text((30, 72), "Rendered directly from actual executed notebook outputs | Lite / Python 3.14",
                      fill="#526174", font=small)
            draw.text((30, 97), "PNG evidence rendering; complete original outputs retained in .ipynb and execution logs",
                      fill="#526174", font=small)
            y = 135
            for count, lines in prepared:
                block_height = 60 + len(lines) * 26
                draw.rounded_rectangle((25, y, 1475, y + block_height), radius=8,
                                       fill="white", outline="#dde3ec", width=1)
                draw.text((45, y + 12), f"Output [{count}]", fill="#526174", font=small)
                for j, line in enumerate(lines):
                    draw.text((45, y + 40 + j * 26), line, fill="#142033", font=font)
                y += block_height + 16
            canvas.save(png)
            manifest.append({"notebook": str(path.relative_to(ROOT)), "source_sha256":
                hashlib.sha256(path.read_bytes()).hexdigest(), "png": str(png.relative_to(ROOT)),
                "renderer": "Pillow: direct rendering of actual notebook outputs; not a browser screenshot"})
            print(f"Rendered {png.relative_to(ROOT)} ({png.stat().st_size:,} bytes)")
            continue
        lines = sum(block.count("\n") + 6 for block in blocks)
        height = min(14000, max(900, 200 + lines * 27))
        profile = (ROOT / ".cache" / "evidence-browser" / uuid4().hex).resolve()
        assert profile.is_relative_to(ROOT)
        profile.mkdir(parents=True)
        result = subprocess.run([str(args.browser), "--headless", "--disable-gpu",
            "--no-first-run", "--disable-background-networking", "--hide-scrollbars",
            f"--user-data-dir={profile}", f"--screenshot={png}",
            f"--window-size=1440,{height}", "--virtual-time-budget=3000", evidence_html.as_uri()],
            capture_output=True, timeout=60)
        if not png.is_file():
            raise RuntimeError(result.stderr.decode(errors="replace"))
        print(f"Captured {png.relative_to(ROOT)} ({png.stat().st_size:,} bytes)")
        manifest.append({"notebook": str(path.relative_to(ROOT)), "source_sha256":
            hashlib.sha256(path.read_bytes()).hexdigest(), "png": str(png.relative_to(ROOT)),
            "renderer": "Headless browser screenshot of saved output HTML"})
    (folder / "capture_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
