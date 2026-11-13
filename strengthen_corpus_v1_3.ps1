$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "Creating virtual environment..."
    python -m venv .venv
}
$Python = Join-Path $Root ".venv\Scripts\python.exe"

Write-Host "Ensuring dependencies..."
& $Python -m pip install requests beautifulsoup4 pymupdf truststore

Write-Host "`n1/3 Discovering CURRENT RBI NBFC directions and acquiring authoritative/verified content..."
& $Python scripts\download_current_rbi_nbfc.py --root .

Write-Host "`n2/3 Re-running canonical curation so successful RBI acquisitions enter index_manifest.jsonl..."
if (-not (Test-Path "scripts\curate_corpus.py")) {
    throw "scripts\curate_corpus.py not found. Apply Corpus Curation Patch v1.1 first."
}
& $Python scripts\curate_corpus.py --root .

Write-Host "`n3/3 Re-enriching metadata and rebuilding balanced core manifest..."
& $Python scripts\enrich_corpus_metadata_v1_3.py --root . --company-cap 18

Write-Host "`nDone. Review these reports:"
Write-Host "  data\reports\rbi_current_directions_acquisition_report.json"
Write-Host "  data\reports\metadata_coverage_report.json"
Write-Host "  data\reports\manual_metadata_review_queue.csv"
