$ErrorActionPreference = "Stop"

$RootDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = Join-Path $RootDir ".venv\Scripts\python.exe"
$Frontend = Join-Path $RootDir "portals\officer\dist\index.html"
$HostAddress = if ($env:ALV_HOST) { $env:ALV_HOST } else { "127.0.0.1" }
$Port = if ($env:ALV_PORT) { $env:ALV_PORT } else { "8000" }
$env:ALV_OCR_ENGINE = "paddle"
if (-not $env:ALV_FIXTURE_DIR) {
    $env:ALV_FIXTURE_DIR = Join-Path $RootDir "fixtures\evaluation-real"
}

if (-not (Test-Path $Python)) {
    throw "Missing .venv. Follow the Windows setup instructions in README.md first."
}

Set-Location $RootDir

if (-not (Test-Path $Frontend)) {
    if (-not (Get-Command npm.cmd -ErrorAction SilentlyContinue)) {
        throw "The frontend is not built and npm is unavailable."
    }
    & npm.cmd --prefix portals/officer run build
}

Write-Host "Alcohol Label Validator: http://${HostAddress}:${Port}/ (PaddleOCR enabled)"
& $Python -m uvicorn backend.app.main:app --host $HostAddress --port $Port
