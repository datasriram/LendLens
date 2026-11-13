$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "Starting LendLens API..."
Write-Host ""

.\.venv\Scripts\python.exe -m uvicorn api.main:app `
    --host 127.0.0.1 `
    --port 8000
