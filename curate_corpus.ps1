$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "Creating virtual environment..."
    python -m venv .venv
}

$Python = Join-Path $Root ".venv\Scripts\python.exe"

Write-Host "Ensuring corpus quality dependencies are installed..."
& $Python -m pip install -r requirements-corpus.txt

Write-Host "Running raw-corpus validation..."
& $Python scripts\validate_corpus.py --root .

Write-Host "Curating canonical, indexable corpus without modifying raw originals..."
& $Python scripts\curate_corpus.py --root .

Write-Host ""
Write-Host "LendLens corpus curation complete."
Write-Host "Raw originals remain unchanged: data\raw"
Write-Host "Indexable manifest: data\manifests\index_manifest.jsonl"
Write-Host "Full curation audit: data\manifests\curation_manifest.jsonl"
Write-Host "Curation report: data\reports\curation_report.json"
Write-Host "Inventory CSV: data\reports\indexable_corpus_inventory.csv"
