$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$frontend = Join-Path $repoRoot "frontend"
$server = Join-Path $frontend "demo_server.py"

if (-not (Test-Path -LiteralPath $server)) {
  throw "FactoryOps demo server was not found: $server"
}

Write-Host "FactoryOps Executive Demo"
Write-Host "Read-only recorded scenario; dataset files are not modified."
Write-Host "Dashboard: http://127.0.0.1:4173/dashboard.html"
Write-Host "Stop with Ctrl+C in the server window."

Set-Location $frontend
python $server
