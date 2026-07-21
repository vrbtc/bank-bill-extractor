# fix-task.ps1 - 修复 AutoGitHubSync-R BANK 任务计划
# 用 Register-ScheduledTask 替代 schtasks，正确处理含空格路径
$ErrorActionPreference = "Continue"
$ProjectPath = "k:\Trae CN\R BANK"
$taskName = "AutoGitHubSync-R BANK"
$wrapperBat = Join-Path $ProjectPath ".auto-sync-runner.bat"

# 删除旧任务
$existing = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($existing) {
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
    Write-Host "[OK] 已删除旧任务"
}

# 用 PowerShell cmdlet 重建（正确处理空格路径 + 设置工作目录）
$action = New-ScheduledTaskAction -Execute $wrapperBat -WorkingDirectory $ProjectPath

$startTime = (Get-Date).AddMinutes(1)
$trigger = New-ScheduledTaskTrigger -Once -At $startTime
$trigger.Repetition = (New-ScheduledTaskTrigger -Once -At $startTime -RepetitionInterval (New-TimeSpan -Minutes 10)).Repetition

$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -DontStopOnIdleEnd `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 5)

Register-ScheduledTask -TaskName $taskName `
    -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null

Write-Host "[OK] 任务已重建（含 WorkingDirectory）"
Write-Host "任务名: $taskName"
Write-Host "执行: $wrapperBat"
Write-Host "工作目录: $ProjectPath"
