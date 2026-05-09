param(
    [switch]$SkipInstall,
    [string]$PythonPath = "python"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root
$OutDir = Join-Path $Root "dist\CampusAutoLogin"
$DataDir = Join-Path $OutDir "data"
$BackupDir = Join-Path $Root ".build_data_backup"

if ($PythonPath -eq "python") {
    $LocalPython312 = Join-Path $env:LOCALAPPDATA "Programs\Python\Python312\python.exe"
    if (Test-Path -LiteralPath $LocalPython312) {
        $PythonPath = $LocalPython312
    }
}

Write-Host ("Using Python: {0}" -f $PythonPath)
& $PythonPath -c "import ctypes, PySide6, PyInstaller, requests; import win32crypt; print('build preflight ok')"
if ($LASTEXITCODE -ne 0) {
    throw "Build Python preflight failed. Use a complete Python installation, preferably the official Python 3.12 x64 runtime."
}

if (Test-Path -LiteralPath $BackupDir) {
    $resolvedBackup = (Resolve-Path -LiteralPath $BackupDir).Path
    $resolvedRoot = (Resolve-Path -LiteralPath $Root).Path
    if (-not $resolvedBackup.StartsWith($resolvedRoot)) {
        throw "Refusing to remove backup outside workspace: $resolvedBackup"
    }
    Remove-Item -LiteralPath $BackupDir -Recurse -Force
}

if (Test-Path -LiteralPath $DataDir) {
    Copy-Item -LiteralPath $DataDir -Destination $BackupDir -Recurse -Force
}

if (-not $SkipInstall) {
    & $PythonPath -m pip install -r requirements.txt
}

& $PythonPath -m PyInstaller `
    --clean `
    --noconfirm `
    --onedir `
    --windowed `
    --name CampusAutoLogin `
    --add-data "README.md;." `
    main.py
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller failed with exit code $LASTEXITCODE"
}

if (Test-Path -LiteralPath $BackupDir) {
    Copy-Item -LiteralPath $BackupDir -Destination $DataDir -Recurse -Force
    Remove-Item -LiteralPath $BackupDir -Recurse -Force
}

Copy-Item -LiteralPath (Join-Path $Root "stop_campus_auto_login.ps1") -Destination $OutDir -Force
Set-Content -LiteralPath (Join-Path $OutDir "open_safe_mode.bat") -Encoding ASCII -Value @(
    "@echo off",
    "cd /d ""%~dp0""",
    "CampusAutoLogin.exe --safe-mode --no-single-instance"
)

Write-Host ("Green build created: {0}" -f $OutDir)
