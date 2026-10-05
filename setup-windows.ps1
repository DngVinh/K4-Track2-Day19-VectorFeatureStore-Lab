$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (-not (Test-Path -LiteralPath '.venv')) { python -m venv .venv }
$labPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
$labUv = Join-Path $PSScriptRoot '.venv\Scripts\uv.exe'
if (-not (Test-Path -LiteralPath $labUv)) {
    & $labPython -m pip install --cache-dir .cache/pip uv
    if ($LASTEXITCODE -ne 0) { throw 'uv installation failed' }
}
$labVersion = & $labPython -c 'import sys; print(int(sys.version_info >= (3, 14)))'
if ($labVersion -eq '1') {
    & $labUv pip install --python $labPython --cache-dir .cache/uv --overrides overrides-py314.txt -r requirements.txt
} else {
    & $labUv pip install --python $labPython --cache-dir .cache/uv -r requirements.txt
}
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed' }
$env:PYTHONUTF8 = '1'
$env:FASTEMBED_CACHE_PATH = Join-Path $PSScriptRoot '.cache\fastembed'
$env:HF_HOME = Join-Path $PSScriptRoot '.cache\huggingface'
& $labPython -m ipykernel install --prefix .venv --name python3
if ($LASTEXITCODE -ne 0) { throw 'Kernel installation failed' }
if (-not (Test-Path -LiteralPath 'data/corpus_vn.jsonl') -and
    -not (Test-Path -LiteralPath 'data/golden_set.jsonl')) {
    & $labPython scripts/seed_corpus.py
    if ($LASTEXITCODE -ne 0) { throw 'Corpus generation failed' }
}
if (-not (Test-Path -LiteralPath 'data/agent_queries.jsonl')) {
    & $labPython scripts/gen_agent_queries.py
    if ($LASTEXITCODE -ne 0) { throw 'Advanced data generation failed' }
}
& $labPython scripts/verify_lite.py
if ($LASTEXITCODE -ne 0) { throw 'Lite smoke test failed' }
Write-Host 'Setup ready. Run .\.venv\Scripts\python.exe scripts/run_notebooks.py'
