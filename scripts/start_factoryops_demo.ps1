$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$frontend = Join-Path $repoRoot "frontend"
$server = Join-Path $frontend "demo_server.py"

if (-not (Test-Path -LiteralPath $server)) {
  throw "FactoryOps demo server was not found: $server"
}

Write-Host "FactoryOps Executive Demo (Chinese UI)"
Write-Host "Read-only recorded scenario. Dataset files are not modified."
Write-Host "Browser URL: http://127.0.0.1:4173/dashboard.html"
Write-Host "Press Ctrl+C in this window to stop."

Set-Location $frontend
python $server
