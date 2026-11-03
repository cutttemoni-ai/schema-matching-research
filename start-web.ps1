$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$researchAdc = Join-Path $PSScriptRoot '.runtime\gcloud-research\application_default_credentials.json'
if (Test-Path -LiteralPath $researchAdc) { $env:GOOGLE_APPLICATION_CREDENTIALS = $researchAdc }
$env:GOOGLE_CLOUD_PROJECT = 'schema-match-gemini-261103'
$env:GOOGLE_CLOUD_LOCATION = 'global'
& (Join-Path $PSScriptRoot '.venv\Scripts\python.exe') -m streamlit run cloud_app.py --server.address=127.0.0.1 --server.port=8502 --server.headless=true --server.maxUploadSize=1 --browser.gatherUsageStats=false
