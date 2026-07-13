$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

if (-not (Get-Command node -ErrorAction SilentlyContinue)) { throw "Node.js 22+ is required." }
if (-not (Get-Command python -ErrorAction SilentlyContinue)) { throw "Python 3.11+ is required." }

Write-Host "Stopping previous Dream Home Visualizer processes..."
Get-Process -Name "Dream Home Visualizer" -ErrorAction SilentlyContinue | Stop-Process -Force
Get-Process -Name "dreamhome-ai" -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Seconds 2

function Remove-BuildPath {
    param([Parameter(Mandatory = $true)][string]$Path)

    if (-not (Test-Path $Path)) { return }

    for ($attempt = 1; $attempt -le 5; $attempt++) {
        try {
            Remove-Item -LiteralPath $Path -Recurse -Force -ErrorAction Stop
            return
        } catch {
            if ($attempt -eq 5) {
                throw "Could not remove locked build path '$Path'. Close the app and File Explorer windows using that folder, then try again. $($_.Exception.Message)"
            }
            Start-Sleep -Seconds 2
        }
    }
}

Remove-BuildPath (Join-Path $Root "dist-electron")
Remove-BuildPath (Join-Path $Root "release")

npm install
if ($LASTEXITCODE -ne 0) { throw "npm install failed." }

npm run dist:windows
if ($LASTEXITCODE -ne 0) { throw "Windows installer build failed." }

$Installer = Get-ChildItem (Join-Path $Root "release") -Filter "Dream-Home-Visualizer-*-Setup.exe" -File -ErrorAction SilentlyContinue |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1

if (-not $Installer) {
    throw "Build finished without producing an installer in the release folder."
}

Write-Host "Installer created: $($Installer.FullName)"
