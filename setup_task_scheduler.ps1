# Register a Windows Scheduled Task: run the local update every weekday at 15:35
# (about 30 min after the 15:00 A-share close).
# Run once (elevation not required for a per-user task):
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
    -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 10)

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger `
    -Settings $settings -Description "A-share daily risk alert: fetch after close and update the site" -Force

Write-Host "Registered scheduled task '$taskName' (weekdays 15:35)."
Write-Host "Test now: Start-ScheduledTask -TaskName $taskName"
