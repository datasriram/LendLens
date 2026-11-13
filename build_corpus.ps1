param(
    [switch]$DirectOnly,
    [double]$SleepSeconds = 0.8
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "Creating virtual environment..."
    python -m venv .venv
}

$Python = Join-Path $Root ".venv\Scripts\python.exe"

Write-Host "Installing corpus-builder dependencies..."
& $Python -m pip install --upgrade pip
& $Python -m pip install -r requirements-corpus.txt

$DownloadArgs = @("scripts\download_corpus.py", "--root", ".", "--sleep", "$SleepSeconds")
if ($DirectOnly) {
    $DownloadArgs += "--direct-only"
}

Write-Host "Downloading original public sources..."
& $Python @DownloadArgs

Write-Host "Validating downloaded corpus..."
& $Python scripts\validate_corpus.py --root .

Write-Host "Refreshing source-catalog summary..."
& $Python scripts\summarize_sources.py

Write-Host ""
Write-Host "LendLens corpus build complete."
Write-Host "Raw originals: data\raw"
Write-Host "Download audit trail: data\manifests\download_manifest.jsonl"
Write-Host "Validation report: data\reports\corpus_validation.json"
