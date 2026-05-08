$ErrorActionPreference = "SilentlyContinue"

$processes = Get-Process CampusAutoLogin
if (-not $processes) {
    Write-Host "CampusAutoLogin is not running."
    exit 0
}

$processes | Stop-Process -Force
Write-Host ("Stopped {0} CampusAutoLogin process(es)." -f $processes.Count)
