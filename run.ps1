$ErrorActionPreference = "Stop"

$RootDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = Join-Path $RootDir ".venv\Scripts\python.exe"
$OfficerDir = Join-Path $RootDir "portals\officer"

if (-not (Test-Path $Python)) {
    throw "Missing .venv. Follow the Windows setup instructions in README.md first."
}

& $Python -c @"
import sys
if sys.version_info[:2] not in {(3, 11), (3, 12)}:
    raise SystemExit("Python 3.11 or 3.12 is required.")
"@

if (-not (Get-Command npm.cmd -ErrorAction SilentlyContinue)) {
    throw "npm is required. Install the current Node.js LTS release."
}

if (-not (Test-Path (Join-Path $OfficerDir "node_modules"))) {
    throw "Frontend packages are missing. Run: npm.cmd --prefix portals/officer ci"
}

$Backend = $null
$Frontend = $null

try {
    $Backend = Start-Process `
        -FilePath $Python `
        -ArgumentList "-m", "uvicorn", "backend.app.main:app", "--host", "127.0.0.1", "--port", "8000" `
        -WorkingDirectory $RootDir `
        -NoNewWindow `
        -PassThru

    Write-Host "Alcohol Label Validator: http://127.0.0.1:5174/"
    $Frontend = Start-Process `
        -FilePath "npm.cmd" `
        -ArgumentList "--prefix", "portals/officer", "run", "dev", "--", "--host", "127.0.0.1" `
        -WorkingDirectory $RootDir `
        -NoNewWindow `
        -PassThru

    Wait-Process -Id $Frontend.Id
}
finally {
    if ($Frontend -and -not $Frontend.HasExited) {
        Stop-Process -Id $Frontend.Id
    }
    if ($Backend -and -not $Backend.HasExited) {
        Stop-Process -Id $Backend.Id
    }
}
