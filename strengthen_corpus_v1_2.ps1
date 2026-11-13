$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "Creating virtual environment..."
    python -m venv .venv
}
$Python = Join-Path $Root ".venv\Scripts\python.exe"

Write-Host "Ensuring dependencies..."
& $Python -m pip install requests beautifulsoup4 pymupdf

Write-Host "`n1/4 Downloading priority RBI regulatory sources (append-only)..."
& $Python scripts\download_priority_rbi.py --root .

Write-Host "`n2/4 Re-running canonical curation..."
if (-not (Test-Path "scripts\curate_corpus.py")) {
    throw "scripts\curate_corpus.py not found. Apply Corpus Curation Patch v1.1 first."
}
& $Python scripts\curate_corpus.py --root .

Write-Host "`n3/4 Enriching generic discovered metadata and creating balanced core manifest..."
& $Python scripts\enrich_corpus_metadata.py --root .

Write-Host "`n4/4 Done. Review:"
Write-Host "  data\reports\metadata_coverage_report.json"
Write-Host "  data\reports\enriched_corpus_inventory.csv"
Write-Host "  data\manifests\enriched_index_manifest.jsonl"
Write-Host "  data\manifests\core_index_manifest.jsonl"
