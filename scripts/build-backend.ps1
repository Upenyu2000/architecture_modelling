$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Backend = Join-Path $Root "backend"
$Venv = Join-Path $Backend ".venv-build"

if (-not (Test-Path $Venv)) {
    python -m venv $Venv
}
$Python = Join-Path $Venv "Scripts\python.exe"
& $Python -m pip install --upgrade pip
& $Python -m pip install -r (Join-Path $Backend "requirements.txt") pyinstaller==6.14.1

Push-Location $Backend
try {
    & $Python -m PyInstaller --noconfirm --clean --onefile --name dreamhome-ai `
        --paths $Backend `
        --collect-all pypdfium2 `
        --collect-all cv2 `
        --hidden-import uvicorn.logging `
        --hidden-import uvicorn.loops.auto `
        --hidden-import uvicorn.protocols.http.auto `
        --hidden-import uvicorn.protocols.websockets.auto `
        --hidden-import uvicorn.lifespan.on `
        run.py
} finally {
    Pop-Location
}
Write-Host "Backend built at backend\dist\dreamhome-ai.exe"
