$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

if (-not (Get-Command node -ErrorAction SilentlyContinue)) { throw "Node.js 22+ is required." }
if (-not (Get-Command python -ErrorAction SilentlyContinue)) { throw "Python 3.11+ is required." }

npm install
if ($LASTEXITCODE -ne 0) { throw "npm install failed." }

npm run dist:windows
if ($LASTEXITCODE -ne 0) { throw "Windows installer build failed." }

$Installer = Get-ChildItem (Join-Path $Root "release") -Filter "*.exe" -File -ErrorAction SilentlyContinue |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1

if (-not $Installer) {
    throw "Build finished without producing an installer in the release folder."
}

Write-Host "Installer created: $($Installer.FullName)"