$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Backend = Join-Path $Root "backend"
$Venv = Join-Path $Backend ".venv-build"
$Python = Join-Path $Venv "Scripts\python.exe"

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw "Python 3.11+ is required and must be available on PATH."
}

# A previous interrupted build can leave an incomplete virtual environment
# directory behind. Recreate it unless its Python executable is present.
if (-not (Test-Path $Python)) {
    if (Test-Path $Venv) {
        Write-Host "Removing incomplete backend build environment..."
        Remove-Item -Recurse -Force $Venv
    }

    Write-Host "Creating backend build environment..."
    python -m venv $Venv
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path $Python)) {
        throw "Failed to create the backend Python virtual environment."
    }
}

& $Python -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw "Failed to upgrade pip." }

& $Python -m pip install -r (Join-Path $Backend "requirements.txt") pyinstaller==6.14.1
if ($LASTEXITCODE -ne 0) { throw "Failed to install backend build dependencies." }

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

    if ($LASTEXITCODE -ne 0) { throw "PyInstaller backend build failed." }
} finally {
    Pop-Location
}

Write-Host "Backend built at backend\dist\dreamhome-ai.exe"