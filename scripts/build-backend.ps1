$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Backend = Join-Path $Root "backend"
$Venv = Join-Path $Backend ".venv-build"
$Python = Join-Path $Venv "Scripts\python.exe"
$BackendExe = Join-Path $Backend "dist\dreamhome-ai.exe"

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw "Python 3.11+ is required and must be available on PATH."
}

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
    & $Python -m tests.smoke_freeform
    if ($LASTEXITCODE -ne 0) { throw "Free-form geometry smoke test failed." }
    & $Python -m tests.smoke_openings
    if ($LASTEXITCODE -ne 0) { throw "Interactive opening smoke test failed." }
    & $Python -m tests.smoke_shared_portals
    if ($LASTEXITCODE -ne 0) { throw "Shared portal smoke test failed." }
    & $Python -m tests.smoke_exterior_space
    if ($LASTEXITCODE -ne 0) { throw "Exterior white-space smoke test failed." }
    & $Python -m tests.smoke_plan_boundary
    if ($LASTEXITCODE -ne 0) { throw "Image-derived plan-boundary smoke test failed." }
    & $Python -m tests.smoke_interiors
    if ($LASTEXITCODE -ne 0) { throw "Interior design smoke test failed." }
    & $Python -m tests.smoke_presentation
    if ($LASTEXITCODE -ne 0) { throw "Architectural presentation preparation smoke test failed." }
} finally {
    Pop-Location
}

Remove-Item -Recurse -Force (Join-Path $Backend "build") -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force (Join-Path $Backend "dist") -ErrorAction SilentlyContinue

Push-Location $Backend
try {
    & $Python -m PyInstaller --noconfirm --clean --onefile --name dreamhome-ai `
        --paths $Backend `
        --collect-submodules app `
        --collect-all pypdfium2 `
        --collect-all cv2 `
        --collect-all trimesh `
        --collect-all pytesseract `
        --add-data "app\prompts;app\prompts" `
        --add-data "app\blender;app\blender" `
        --hidden-import app.main `
        --hidden-import app.asgi `
        --hidden-import app.architecture_api `
        --hidden-import app.opening_api `
        --hidden-import app.interior_api `
        --hidden-import app.presentation_api `
        --hidden-import app.services.architecture `
        --hidden-import app.services.openings `
        --hidden-import app.services.shared_portals `
        --hidden-import app.services.strict_geometry `
        --hidden-import app.services.plan_boundary `
        --hidden-import app.services.opening_symbols `
        --hidden-import app.services.furniture_detection `
        --hidden-import app.services.rendering_v15 `
        --hidden-import app.services.rendering_v20 `
        --hidden-import app.services.presentation `
        --hidden-import app.services.segmentation `
        --hidden-import app.services.training_data `
        --hidden-import app.services.drawings `
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

if (-not (Test-Path $BackendExe)) {
    throw "Backend build completed without producing $BackendExe"
}

$TestPort = 18765
$TestData = Join-Path $Backend ".backend-self-test"
$StdOut = Join-Path $Backend "backend-self-test.stdout.log"
$StdErr = Join-Path $Backend "backend-self-test.stderr.log"
$PreviousPort = $env:DREAMHOME_PORT
$PreviousData = $env:DREAMHOME_DATA_DIR
$BackendProcess = $null
$Healthy = $false

Remove-Item -Recurse -Force $TestData -ErrorAction SilentlyContinue
Remove-Item -Force $StdOut, $StdErr -ErrorAction SilentlyContinue

try {
    $env:DREAMHOME_PORT = [string]$TestPort
    $env:DREAMHOME_DATA_DIR = $TestData
    $BackendProcess = Start-Process -FilePath $BackendExe -PassThru -WindowStyle Hidden `
        -RedirectStandardOutput $StdOut -RedirectStandardError $StdErr

    for ($Attempt = 0; $Attempt -lt 60; $Attempt++) {
        Start-Sleep -Milliseconds 500

        if ($BackendProcess.HasExited) { break }

        try {
            $Response = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:$TestPort/health" -TimeoutSec 2
            if ($Response.StatusCode -eq 200) {
                $Payload = $Response.Content | ConvertFrom-Json
                if ($Payload.version -ne "2.0.0") {
                    throw "Packaged backend reported version $($Payload.version), expected 2.0.0."
                }
                $Healthy = $true
                break
            }
        } catch {
            # The single-file executable may still be unpacking and starting.
        }
    }
} finally {
    if ($BackendProcess -and -not $BackendProcess.HasExited) {
        Stop-Process -Id $BackendProcess.Id -Force -ErrorAction SilentlyContinue
        $BackendProcess.WaitForExit()
    }

    $env:DREAMHOME_PORT = $PreviousPort
    $env:DREAMHOME_DATA_DIR = $PreviousData
}

if (-not $Healthy) {
    $ErrorLog = if (Test-Path $StdErr) { Get-Content $StdErr -Raw } else { "No stderr log was produced." }
    $OutputLog = if (Test-Path $StdOut) { Get-Content $StdOut -Raw } else { "No stdout log was produced." }
    throw "Packaged backend self-test failed.`nSTDERR:`n$ErrorLog`nSTDOUT:`n$OutputLog"
}

Remove-Item -Recurse -Force $TestData -ErrorAction SilentlyContinue
Remove-Item -Force $StdOut, $StdErr -ErrorAction SilentlyContinue
Write-Host "Packaged backend health check passed with version 2.0.0."
Write-Host "Backend built at backend\dist\dreamhome-ai.exe"
