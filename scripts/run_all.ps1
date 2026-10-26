# FixForge AI — Unified Startup Script
# Starts Backend (FastAPI :8000) and Frontend (Vite :5173)

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "       Starting FixForge AI Orchestrator & UI             " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

$WorkspaceRoot = (Get-Item $PSScriptRoot).Parent.FullName
Set-Location $WorkspaceRoot

# 1. Check Python Environment
$venvPython = Join-Path $WorkspaceRoot ".venv\Scripts\python.exe"
if (Test-Path $venvPython) {
    $PythonPath = $venvPython
} else {
    $PythonPath = (Get-Command python -ErrorAction SilentlyContinue).Source
}
if (-not $PythonPath) {
    Write-Host "[ERROR] Python was not found in PATH or .venv." -ForegroundColor Red
    exit 1
}
Write-Host "[INFO] Python executable: $PythonPath" -ForegroundColor Green

# 2. Check Docker Desktop Status
Write-Host "[INFO] Checking Docker daemon status..." -ForegroundColor Gray
$dockerCheck = docker ps 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "[WARNING] Docker Desktop daemon is not running." -ForegroundColor Yellow
    Write-Host "          FixForge will operate in graceful UNVERIFIED sandbox mode." -ForegroundColor Yellow
    Write-Host "          Start Docker Desktop to enable live container test verification." -ForegroundColor Yellow
} else {
    Write-Host "[INFO] Docker daemon is running and healthy." -ForegroundColor Green
}

# 3. Check .env
$envFile = Join-Path $WorkspaceRoot "fixforge\.env"
if (-not (Test-Path $envFile)) {
    $envExample = Join-Path $WorkspaceRoot "fixforge\.env.example"
    if (Test-Path $envExample) {
        Copy-Item $envExample $envFile
        Write-Host "[INFO] Created .env from .env.example." -ForegroundColor Green
    }
}

# 4. Start Backend Service
Write-Host "[INFO] Starting FastAPI Backend on http://127.0.0.1:8000..." -ForegroundColor Cyan
$backendJob = Start-Process -FilePath $PythonPath -ArgumentList "run_backend.py" -WorkingDirectory (Join-Path $WorkspaceRoot "fixforge") -PassThru

# Wait 3 seconds for backend to boot
Start-Sleep -Seconds 3

# 5. Start Frontend Service
$frontendDir = Join-Path $WorkspaceRoot "frontend"
if (Test-Path $frontendDir) {
    Write-Host "[INFO] Starting Vite Frontend on http://127.0.0.1:5173..." -ForegroundColor Cyan
    Set-Location $frontendDir
    npm run dev
} else {
    Write-Host "[INFO] Frontend directory not found. Backend running under PID $($backendJob.Id)." -ForegroundColor Yellow
    Wait-Process -Id $backendJob.Id
}
