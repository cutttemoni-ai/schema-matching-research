$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$gcpConfig = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'config\gcp_research_v1.json') -Raw | ConvertFrom-Json
$env:LLM_PROVIDER = 'vertex'
$env:GOOGLE_CLOUD_PROJECT = $gcpConfig.project
$env:GOOGLE_CLOUD_LOCATION = $gcpConfig.location
$env:GEMINI_MODEL = $gcpConfig.model
$env:GOOGLE_APPLICATION_CREDENTIALS = Join-Path $PSScriptRoot '.runtime\gcloud-research\application_default_credentials.json'
$env:GOOGLE_GENAI_USE_VERTEXAI = 'true'
& (Join-Path $PSScriptRoot '.venv\Scripts\python.exe') -m streamlit run app.py --server.address=127.0.0.1 --server.port=8501 --server.headless=true
