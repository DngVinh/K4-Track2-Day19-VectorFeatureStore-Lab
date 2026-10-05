"""Check that the submission contains actual executed evidence for all missions."""
import argparse
import hashlib
import json
from pathlib import Path

import nbformat
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--require-screenshots", action="store_true")
    args = parser.parse_args()
    import jupytext
    manifest_path = ROOT / "submission/FINAL_EVIDENCE.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else None
    selected = {r["source"]: r for r in manifest["notebooks"]} if manifest else {}
    if manifest:
        for name, expected_hash in manifest.get("dependency_sha256", {}).items():
            dependency = (ROOT / name).resolve()
            assert dependency.is_relative_to(ROOT)
            assert hashlib.sha256(dependency.read_bytes()).hexdigest() == expected_hash, f"Changed dependency: {name}"
    sources = sorted((ROOT / "notebooks").glob("[0-9]*.py"))
    assert len(sources) == 8
    for source in sources:
        entry = selected.get(source.relative_to(ROOT).as_posix())
        path = (ROOT / entry["notebook"]).resolve() if entry else source.with_suffix(".ipynb")
        assert path.is_relative_to(ROOT)
        if entry:
            assert hashlib.sha256(source.read_bytes()).hexdigest() == entry["source_sha256"]
            assert hashlib.sha256(path.read_bytes()).hexdigest() == entry["notebook_sha256"]
        notebook = nbformat.read(path, as_version=4)
        source_notebook = jupytext.read(source)
        assert [(c.cell_type, c.source) for c in source_notebook.cells] == [(c.cell_type, c.source) for c in notebook.cells], f"Stale notebook text: {path}"
        expected = [c.source for c in source_notebook.cells if c.cell_type == "code"]
        assert expected == [c.source for c in notebook.cells if c.cell_type == "code"], f"Stale code: {path}"
        code = [cell for cell in notebook.cells if cell.cell_type == "code" and cell.source.strip()]
        assert code and all(cell.execution_count is not None for cell in code), path.name
        outputs = [out for cell in code for out in cell.get("outputs", [])]
        assert outputs and not any(out.output_type == "error" for out in outputs), path.name
        print(f"PASS {path.name}: {len(code)} executed code cells, no errors")
    legacy_manifest = json.loads((ROOT / "submission/screenshots/capture_manifest.json").read_text(encoding="utf-8"))
    screenshots = [(ROOT / entry["png"].replace("\\", "/")).resolve() for entry in legacy_manifest]
    assert len(screenshots) == 8
    for entry in legacy_manifest:
        original_notebook = (ROOT / entry["notebook"].replace("\\", "/")).resolve()
        assert original_notebook.is_relative_to(ROOT)
        assert hashlib.sha256(original_notebook.read_bytes()).hexdigest() == entry["source_sha256"], "Legacy notebook changed"
    for path in screenshots:
        assert path.is_relative_to(ROOT)
        with Image.open(path) as image:
            assert image.width >= 1000 and image.height >= 500
            image.verify()
    architecture = ROOT / "bonus/ARCHITECTURE.md"
    assert len(architecture.read_text(encoding="utf-8").split()) >= 600
    assert "```mermaid" in architecture.read_text(encoding="utf-8")
    reflection = (ROOT / "submission/REFLECTION.md").read_text(encoding="utf-8")
    assert "_Answer here._" not in reflection
    assert len(reflection.split()) <= 200
    corpus = [json.loads(line) for line in (ROOT / "data/corpus_vn.jsonl").read_text(encoding="utf-8").splitlines()]
    golden = [json.loads(line) for line in (ROOT / "data/golden_set.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(corpus) == 1000 and len({doc["doc_id"] for doc in corpus}) == 1000
    assert len(golden) == 50
    assert (ROOT / "submission/VALIDATION.md").is_file()
    assert (ROOT / "submission/bonus_demo.txt").is_file()
    print("PASS — notebook/source equality, eight legacy PNG renderings, architecture, reflection and data counts")
    current_path = ROOT / "submission/screenshots/CURRENT_SCREENSHOTS.json"
    if current_path.exists():
        from refresh_screenshots import blocks_sha, output_blocks
        current = json.loads(current_path.read_text(encoding="utf-8"))
        assert current["accepted_as_submission_screenshots"] is True
        records = current["screenshots"]
        assert len(records) == 8 and {r["source"] for r in records} == set(selected)
        for record in records:
            entry = selected[record["source"]]
            assert record["notebook"] == entry["notebook"]
            assert record["notebook_sha256"] == entry["notebook_sha256"]
            notebook_path = (ROOT / record["notebook"]).resolve()
            render_input = (ROOT / record["render_input_notebook"]).resolve()
            png_path = (ROOT / record["png"]).resolve()
            assert all(p.is_relative_to(ROOT) for p in (notebook_path, render_input, png_path))
            assert hashlib.sha256(render_input.read_bytes()).hexdigest() == record["render_input_notebook_sha256"]
            assert blocks_sha(output_blocks(notebook_path)) == record["displayed_output_sha256"]
            assert blocks_sha(output_blocks(render_input)) == record["displayed_output_sha256"]
            assert hashlib.sha256(png_path.read_bytes()).hexdigest() == record["png_sha256"]
            with Image.open(png_path) as picture:
                assert picture.width >= 1000 and picture.height >= 500
                picture.verify()
        print("PASS — 8/8 accepted submission screenshots match final notebook output excerpts and PNG hashes")
        print("Renderer provenance: rendered executed outputs, accepted by user; browser capture is not claimed")
    else:
        print("Current screenshot manifest not available")
        if args.require_screenshots:
            raise AssertionError("Current screenshot manifest required")
    print("NB2 slice criterion is incomplete; artifact checks do not award rubric points")


if __name__ == "__main__":
    main()
