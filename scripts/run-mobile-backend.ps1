param(
    [int]$Port = 8765,
    [string]$ApiToken = "",
    [string]$PythonPath = ""
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Backend = Join-Path $Root "backend"

if (-not $PythonPath) {
    $ProjectPython = Join-Path $Backend ".venv\Scripts\python.exe"
    $PythonPath = if (Test-Path $ProjectPython) { $ProjectPython } else { "python" }
}

$env:DREAMHOME_HOST = "0.0.0.0"
$env:DREAMHOME_PORT = [string]$Port
if ($ApiToken) {
    $env:DREAMHOME_API_TOKEN = $ApiToken
} else {
    Remove-Item Env:DREAMHOME_API_TOKEN -ErrorAction SilentlyContinue
    Write-Warning "No API token was supplied. Use this only on a trusted private network."
}

Write-Host "Starting Roomify Studio mobile rendering server..." -ForegroundColor Cyan
Write-Host "Port: $Port"
Write-Host "Android server addresses on this computer:" -ForegroundColor Green

try {
    Get-NetIPAddress -AddressFamily IPv4 -ErrorAction Stop |
        Where-Object {
            $_.IPAddress -notlike "127.*" -and
            $_.IPAddress -notlike "169.254.*" -and
            $_.AddressState -eq "Preferred"
        } |
        ForEach-Object { Write-Host "  http://$($_.IPAddress):$Port" }
} catch {
    Write-Host "  Find this computer's IPv4 address with: ipconfig"
}

Write-Host "Keep this window open while the Android app is rendering." -ForegroundColor Yellow
Push-Location $Root
try {
    & $PythonPath (Join-Path $Backend "run.py")
    exit $LASTEXITCODE
} finally {
    Pop-Location
}
