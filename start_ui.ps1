$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "Starting LendLens UI..."
Write-Host ""

.\.venv\Scripts\python.exe -m streamlit run .\streamlit_app.py
