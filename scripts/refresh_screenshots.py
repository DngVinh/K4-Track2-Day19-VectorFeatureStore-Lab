"""Refresh changed screenshot evidence from FINAL_EVIDENCE, preserving old PNGs.

The user accepts rendered outputs as submission screenshots. Renderer provenance
remains explicit; no browser capture is claimed and no notebook is executed.
"""
from __future__ import annotations

import hashlib
import html
import json
from pathlib import Path
import re
import subprocess

import nbformat
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent


def scoped(path):
    path = path.resolve()
    assert path.is_relative_to(ROOT) and path != ROOT, path
    return path


def sha(path):
    return hashlib.sha256(scoped(path).read_bytes()).hexdigest()


def output_blocks(path):
    """Apply the original screenshot excerpt rules to literal notebook outputs."""
    notebook = nbformat.read(scoped(path), as_version=4)
    blocks = []
    for cell in notebook.cells:
        if cell.cell_type != 'code':
            continue
        text = []
        for out in cell.get('outputs', []):
            assert out.output_type != 'error', path
            if out.output_type == 'stream':
                if out.get('name') == 'stdout':
                    text.append(out.text)
            else:
                text.append(out.get('data', {}).get('text/plain', ''))
        value = re.sub(r'\x1b\[[0-9;]*m', '', '\n'.join(text))
        value = '\n'.join(line for line in value.splitlines()
                          if not line.lstrip().startswith(('C:\\', 'UserWarning:', 'FutureWarning:')))
        if path.name.startswith('04') and 'Updated feature view' in value:
            prefixes = ('STDOUT:', 'No project', 'Applying', 'Created', 'Updated feature view',
                        'No changes', 'NAME', 'query_velocity_features ',
                        'item_popularity_features ', 'user_profile_features ')
            value = '\n'.join(line for line in value.splitlines() if line.startswith(prefixes))
        if path.name.startswith('03') and value.lstrip().startswith('{'):
            try:
                sample, _ = json.JSONDecoder().raw_decode(value.lstrip())
                if isinstance(sample, dict) and 'hits' in sample:
                    total = len(sample['hits'])
                    sample['hits'] = sample['hits'][:3]
                    value = (f'API response sample: first 3 of {total} hits (complete response in notebook)\n'
                             + json.dumps(sample, ensure_ascii=False, indent=2))
            except ValueError:
                pass
        if value.strip():
            blocks.append((cell.execution_count, value))
    assert blocks, path
    return blocks


def blocks_sha(blocks):
    return hashlib.sha256(json.dumps(blocks, ensure_ascii=False).encode('utf-8')).hexdigest()


def write_new(path, content):
    path = scoped(path)
    assert not path.exists(), f'Existing evidence preserved: {path}'
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as target:
        target.write(content)


def render(path, title, blocks):
    path = scoped(path)
    assert not path.exists()
    font = ImageFont.truetype(r'C:\Windows\Fonts\consola.ttf', 18)
    heading = ImageFont.truetype(r'C:\Windows\Fonts\arialbd.ttf', 28)
    small = ImageFont.truetype(r'C:\Windows\Fonts\arial.ttf', 16)
    prepared = []
    for count, value in blocks:
        lines = []
        for line in value.splitlines():
            # Wrap by actual font width, including Vietnamese and long paths.
            if not line:
                lines.append('')
            while line:
                end = min(len(line), 140)
                while font.getlength(line[:end]) > 1400:
                    end -= 1
                assert end > 0
                lines.append(line[:end])
                line = line[end:]
        prepared.append((count, lines))
    height = 145 + sum(76 + len(lines) * 26 for _, lines in prepared)
    canvas = Image.new('RGB', (1500, max(height, 900)), '#f5f7fa')
    draw = ImageDraw.Draw(canvas)
    draw.text((30, 24), f'Lab 19 | {title}', fill='#142033', font=heading)
    draw.text((30, 72), 'Screenshot evidence | Rendered from final executed notebook outputs',
              fill='#526174', font=small)
    draw.text((30, 97), 'Complete original outputs retained in .ipynb and execution logs',
              fill='#526174', font=small)
    y = 135
    for count, lines in prepared:
        block_height = 60 + len(lines) * 26
        draw.rounded_rectangle((25, y, 1475, y + block_height), radius=8,
                               fill='white', outline='#dde3ec', width=1)
        draw.text((45, y + 12), f'Output [{count}]', fill='#526174', font=small)
        for index, line in enumerate(lines):
            assert font.getlength(line) <= 1400
            draw.text((45, y + 40 + index * 26), line, fill='#142033', font=font)
        y += block_height + 16
    assert y <= canvas.height
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as target:
        canvas.save(target, format='PNG')


def main():
    subprocess.run(['git', 'status', '--short'], cwd=ROOT, check=True, capture_output=True)
    final = json.loads((ROOT / 'submission/FINAL_EVIDENCE.json').read_text(encoding='utf-8'))
    legacy = json.loads((ROOT / 'submission/screenshots/capture_manifest.json').read_text(encoding='utf-8'))
    folder = scoped(ROOT / 'submission/screenshots/final-20261005')
    target = ROOT / 'submission/screenshots/CURRENT_SCREENSHOTS.json'
    assert not target.exists() and not folder.exists()
    records = []
    for selected, old in zip(final['notebooks'], legacy, strict=True):
        path = scoped(ROOT / selected['notebook'])
        old_path = scoped(ROOT / old['notebook'].replace('\\', '/'))
        old_png = scoped(ROOT / old['png'].replace('\\', '/'))
        assert path.name == old_path.name
        assert sha(path) == selected['notebook_sha256']
        assert sha(old_path) == old['source_sha256']
        current = output_blocks(path)
        previous = output_blocks(old_path)
        changed = current != previous
        if changed:
            png = folder / (old_png.stem + '.png')
            render(png, path.stem, current)
            document = ('<!doctype html><meta charset="utf-8"><title>Lab 19 screenshot evidence</title>'
                        '<style>body{font:16px Arial;margin:24px}pre{white-space:pre-wrap;'
                        'font:16px/1.5 Consolas}section{border:1px solid #ccc;padding:18px;margin:18px 0}</style>'
                        f'<h1>{html.escape(path.stem)}</h1><p>Final executed output excerpts. '
                        'Rendered evidence accepted by the user as submission screenshots.</p>'
                        + ''.join(f'<section><h2>Output [{count}]</h2><pre>{html.escape(value)}</pre></section>'
                                  for count, value in current))
            write_new(png.with_suffix('.html'), document)
        else:
            png = old_png
        record = {'source': selected['source'], 'notebook': selected['notebook'],
                  'notebook_sha256': sha(path), 'render_input_notebook':
                  selected['notebook'] if changed else old['notebook'].replace('\\', '/'),
                  'render_input_notebook_sha256': sha(path if changed else old_path),
                  'displayed_output_sha256': blocks_sha(current),
                  'png': scoped(png).relative_to(ROOT).as_posix(), 'png_sha256': sha(png),
                  'action': 'regenerated' if changed else 'reused: displayed outputs identical',
                  'renderer': 'Pillow, literal executed output excerpts; not a browser capture'}
        records.append(record)
        print(f"{path.name}: {record['action']} -> {record['png']}")
    write_new(target, json.dumps({'accepted_as_submission_screenshots': True,
        'acceptance': 'User explicitly accepts existing rendered PNGs as screenshots, 2026-10-05',
        'selection_manifest': 'submission/FINAL_EVIDENCE.json', 'screenshots': records,
        'old_evidence_preserved': True}, ensure_ascii=False, indent=2))
    index = ('<!doctype html><meta charset="utf-8"><title>Lab 19 — current screenshots</title>'
             '<style>body{font:16px Arial;margin:24px;color:#142033}img{max-width:100%;height:auto}'
             'section{border-top:1px solid #ccd;padding-top:18px;margin-top:28px}</style>'
             '<h1>Lab 19 — bộ 8 screenshot hiện hành</h1><p>Đã đối chiếu output cuối. '
             'Ảnh render được người dùng chấp nhận làm screenshot bài nộp. NB2 vẫn thiếu '
             'tiêu chí Vector thắng paraphrase; không chỉnh số liệu.</p><ul>')
    for record in records:
        name = Path(record['png']).relative_to('submission/screenshots').as_posix()
        index += f'<li><a href="{name}">{html.escape(Path(record["source"]).stem)}</a></li>'
    index += '</ul>'
    for record in records:
        name = Path(record['png']).relative_to('submission/screenshots').as_posix()
        index += f'<section><h2>{html.escape(Path(record["source"]).stem)}</h2><p>{record["action"]}</p><img src="{name}"></section>'
    write_new(ROOT / 'submission/screenshots/CURRENT_SCREENSHOTS.html', index)
    print('PASS — current 8-image screenshot set prepared; old files preserved')


if __name__ == '__main__':
    main()
