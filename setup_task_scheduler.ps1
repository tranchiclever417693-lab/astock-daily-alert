# Register a Windows Scheduled Task that runs the local update ~30 min after the
# A-share close (Beijing 15:35), TRANSLATED INTO THIS MACHINE'S LOCAL TIME.
#
# The machine may be in any timezone (e.g. US Pacific). We compute the local
# clock time that corresponds to Beijing 15:35 today and trigger DAILY at it.
# Running daily (incl. weekends) is safe: daily_update.py skips when the latest
# session isn't newer than what's stored (non-trading days / reruns are no-ops).
# This also stays correct across DST because we run every day and guard in code.
#
# Run once:
#   powershell -ExecutionPolicy Bypass -File D:\astock-daily-alert\setup_task_scheduler.ps1
$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $MyInvocation.MyCommand.Definition
$script = Join-Path $repo "run_local.ps1"
$taskName = "AStockDailyAlert"

# Beijing 15:35 today -> UTC (-8h) -> this machine's local time (+current offset)
$offset = [System.TimeZoneInfo]::Local.GetUtcOffset((Get-Date))
$beijing1535 = (Get-Date -Hour 15 -Minute 35 -Second 0)
$localEquiv = $beijing1535.AddHours(-8).Add($offset)
$triggerTime = $localEquiv.ToString("HH:mm")

$action = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-ExecutionPolicy Bypass -WindowStyle Hidden -File `"$script`""
$trigger = New-ScheduledTaskTrigger -Daily -At $triggerTime
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable `
    -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 10) `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 30)

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger `
    -Settings $settings -Description "A-share daily risk alert: run ~30min after Beijing close" -Force | Out-Null

Write-Host ("Machine timezone : " + [System.TimeZoneInfo]::Local.Id + " (UTC" + $offset.ToString() + ")")
Write-Host ("Beijing 15:35  ==  machine-local " + $triggerTime + "  (daily trigger)")
Write-Host ("Registered '" + $taskName + "'. Test now: Start-ScheduledTask -TaskName " + $taskName)
