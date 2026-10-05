"""Select source-matching executed notebooks and build HTML for manual screenshots.

All outputs remain literal notebook outputs. HTML is preparation, not a screenshot.
Existing evidence, manifests and renderings are never overwritten.
"""
from __future__ import annotations
import hashlib
import html
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parent.parent


def write_new(path, value):
    path = path.resolve()
    assert path.is_relative_to(ROOT) and path != ROOT and not path.exists()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as target:
        target.write(value)


def main():
    import jupytext
    import nbformat
    manifest_path = ROOT / "submission/FINAL_EVIDENCE.json"
    assert not manifest_path.exists(), "Existing final manifest preserved; use a new name for a later review"
    evidence = []
    for source in sorted((ROOT / "notebooks").glob("[0-9]*.py")):
        expected = [c.source for c in jupytext.read(source).cells if c.cell_type == "code"]
        candidates = [source.with_suffix(".ipynb"), *(ROOT / "submission/runs").rglob(source.with_suffix(".ipynb").name)]
        valid = []
        for path in candidates:
            path = path.resolve()
            assert path.is_relative_to(ROOT)
            nb = nbformat.read(path, as_version=4)
            code = [c for c in nb.cells if c.cell_type == "code"]
            if ([c.source for c in code] == expected and
                all(c.execution_count is not None for c in code if c.source.strip()) and
                not any(o.output_type == "error" for c in code for o in c.get("outputs", []))):
                valid.append(path)
        assert valid, f"No source-matching executed notebook: {source}"
        path = max(valid, key=lambda p: p.stat().st_mtime_ns)
        nb = nbformat.read(path, as_version=4)
        record = {"source": source.relative_to(ROOT).as_posix(), "notebook": path.relative_to(ROOT).as_posix(),
                  "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                  "notebook_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        evidence.append(record)
        title = ""
        sections = []
        links = []
        for index, cell in enumerate(nb.cells):
            if cell.cell_type == "markdown":
                headings = [line.lstrip("# ") for line in cell.source.splitlines() if line.startswith("#")]
                if headings:
                    title = headings[-1]
                continue
            values = []
            for out in cell.get("outputs", []):
                if out.output_type == "stream":
                    values.append(out.text)
                elif out.output_type in ("display_data", "execute_result"):
                    values.append(out.get("data", {}).get("text/plain", ""))
            if not values:
                continue
            value = re.sub(r"\x1b\[[0-9;]*m", "", "\n".join(values))
            identifier = f"cell-{index}"
            links.append(f'<li><a href="#{identifier}">{html.escape(title)} · Out[{cell.execution_count}]</a></li>')
            sections.append(f'<section id="{identifier}"><h2>{html.escape(title)} · Out[{cell.execution_count}]</h2>'
                f'<details><summary>Code nguồn</summary><pre>{html.escape(cell.source)}</pre></details>'
                f'<pre>{html.escape(value)}</pre></section>')
        document = ('<!doctype html><html lang="vi"><meta charset="utf-8"><title>Lab 19 evidence</title><style>'
                    'body{font-family:Arial,sans-serif;margin:24px;color:#152338;background:#f4f6f9}'
                    'section{background:white;border:1px solid #b8c1cc;padding:16px;margin:20px 0;scroll-margin-top:12px}'
                    'pre{font:14px/1.5 Consolas,monospace;white-space:pre-wrap;overflow-wrap:anywhere}'
                    'h1{font-size:24px}h2{font-size:18px}summary{cursor:pointer;color:#47586e}</style>'
                    f'<h1>Lab 19 · {html.escape(source.stem)}</h1>'
                    '<p>Output notebook đã thực thi; trang HTML chuẩn bị để chụp trực tiếp trong trình duyệt. '
                    'Trang này chưa phải screenshot. NB2 chưa đạt Vector thắng paraphrase.</p>'
                    f'<p>Notebook: {html.escape(record["notebook"])}<br>SHA-256: {record["notebook_sha256"]}</p>'
                    '<nav><ul>' + ''.join(links) + '</ul></nav>' + ''.join(sections) + '</html>')
        record["capture_html"] = f"submission/screenshots/manual-20261005/{source.stem}.html"
        write_new(ROOT / record["capture_html"], document)
    dependencies = [*(ROOT / "app").glob("*.py"), *(ROOT / "bonus").glob("*.py"),
                    ROOT / "notebooks/_setup.py", ROOT / "scripts/audit_search.py"]
    dependency_hashes = {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                         for p in sorted(dependencies)}
    write_new(manifest_path, json.dumps({"notebooks": evidence, "dependency_sha256": dependency_hashes,
        "browser_screenshots": [], "screenshot_status": "BLOCKED: cua inventory has no browsers; IAB unavailable",
        "old_notebooks_and_rendered_pngs_preserved": True}, indent=2, ensure_ascii=False))
    index = '<!doctype html><meta charset="utf-8"><h1>Lab 19 · chụp bằng chứng</h1><p>Mở từng trang, dùng Win+Shift+S để chụp output trong cửa sổ trình duyệt. PNG render cũ không tính là screenshot thật.</p><ul>'
    index += ''.join(f'<li><a href="{Path(r["capture_html"]).name}">{Path(r["source"]).stem}</a></li>' for r in evidence)
    index += '</ul><p>Lưu ảnh mới trong submission/screenshots/, tên nb1_window.png … nb8_window.png. Nếu nhiều tiêu chí không vừa một ảnh, chụp thêm; giữ tiêu đề, bảng và kết quả đọc được.</p>'
    write_new(ROOT / "submission/screenshots/manual-20261005/index.html", index)
    for record in evidence:
        print(record["notebook"])
    print("PASS — eight source-matching executed notebooks selected. Browser screenshots still pending.")


if __name__ == "__main__":
    main()
