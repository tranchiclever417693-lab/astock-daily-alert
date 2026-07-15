# -*- coding: utf-8 -*-
# 本地每日更新（Windows 任务计划兜底）。用真实 Python + UTF-8，抓数据→重算→提交推送。
# 手动运行：  powershell -ExecutionPolicy Bypass -File D:\astock-daily-alert\run_local.ps1
$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $repo

$py = "C:\Users\cindy\AppData\Local\Programs\Python\Python312\python.exe"
$env:PYTHONUTF8 = "1"

Write-Host "[$(Get-Date -Format s)] daily update start"
& $py "scripts\daily_update.py"
if ($LASTEXITCODE -ne 0) { Write-Host "update failed (likely data source); abort, no commit"; exit 1 }

# 仅在有改动时提交推送
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
