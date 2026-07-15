# Local daily update (Windows Task Scheduler fallback).
# Uses the real Python + UTF-8, fetches data -> recompute -> commit & push.
# Manual run:
#   powershell -ExecutionPolicy Bypass -File D:\astock-daily-alert\run_local.ps1
$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $repo

$py = "C:\Users\cindy\AppData\Local\Programs\Python\Python312\python.exe"
$env:PYTHONUTF8 = "1"

Write-Host "[$(Get-Date -Format s)] daily update start"
& $py "scripts\daily_update.py"
if ($LASTEXITCODE -ne 0) { Write-Host "update failed (data source); abort, no commit"; exit 1 }

# commit & push only if something changed
git add -A
git diff --cached --quiet
if ($LASTEXITCODE -ne 0) {
    git commit -m "chore: local daily update $(Get-Date -Format yyyy-MM-dd)"
    git push
    Write-Host "pushed."
} else {
    Write-Host "no changes."
}
Write-Host "[$(Get-Date -Format s)] done"
