# -*- coding: utf-8 -*-
# 注册 Windows 任务计划：每个工作日 15:35 运行本地更新（收盘后约半小时）。
# 以管理员身份运行一次即可：
#   powershell -ExecutionPolicy Bypass -File D:\astock-daily-alert\setup_task_scheduler.ps1
$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $MyInvocation.MyCommand.Definition
$script = Join-Path $repo "run_local.ps1"
$taskName = "AStockDailyAlert"

$action = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-ExecutionPolicy Bypass -WindowStyle Hidden -File `"$script`""
$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday `
    -At 3:35PM
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable `
    -DontStopOnIdleEnd -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 10)

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger `
    -Settings $settings -Description "A股每日风险预警：收盘后抓数据更新网页" -Force

Write-Host "已注册任务计划 '$taskName'，每工作日 15:35 运行。"
Write-Host "立即测试：Start-ScheduledTask -TaskName $taskName"
