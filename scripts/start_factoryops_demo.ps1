$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$frontend = Join-Path $repoRoot "frontend"
$server = Join-Path $frontend "demo_server.py"

if (-not (Test-Path -LiteralPath $server)) {
  throw "FactoryOps demo server was not found: $server"
}

Write-Host "FactoryOps 中文老板演示版"
Write-Host "本地只读录制场景；不会修改 dataset 图片。"
Write-Host "浏览器地址：http://127.0.0.1:4173/dashboard.html"
Write-Host "验收结束后，在本窗口按 Ctrl+C 停止。"

Set-Location $frontend
python $server
