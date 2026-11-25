# -*- coding: utf-8 -*-
# 注册 RBANK 短信接入常驻任务（登录自启 + 每 30 分钟守护重启）
# 用法：pwsh -NoProfile -ExecutionPolicy Bypass -File "D:\RTRAECODE\RBANK\setup_sms_task.ps1"
$ErrorActionPreference = 'Stop'

$taskName = 'RBANK_SMS_Ingest'
$python = (Get-Command py).Source
$scriptDir = 'D:\RTRAECODE\RBANK'
$runnerPs1 = Join-Path $scriptDir 'sms_ingest_runner.ps1'

# runner 脚本：由计划任务调用，确保单实例 + 自动重启
@"
`$log = 'D:\RTRAECODE\RBANK\sms_ingest_console.log'
`$mutex = New-Object System.Threading.Mutex(`$false, 'Global\RBANK_SMS_Ingest')
if (-not `$mutex.WaitOne(0)) { exit 0 }
try {
  & py -3.11 -u 'D:\RTRAECODE\RBANK\sms_ingest.py' *>> `$log
} finally {
  `$mutex.ReleaseMutex()
}
"@ | Set-Content -Path $runnerPs1 -Encoding UTF8 -Force

# 已存在则先删
$existing = schtasks /Query /TN $taskName 2>$null
if ($LASTEXITCODE -eq 0) { schtasks /Delete /TN $taskName /F | Out-Null }

# 主任务：登录时启动（隐藏窗口，不设时限，失败自动重启）
# pwsh 用绝对路径：计划任务上下文 PATH 不含 PowerShell 7 安装目录（0x80070002）
$pwshPath = (Get-Command pwsh.exe).Source
$action = New-ScheduledTaskAction -Execute $pwshPath `
    -Argument "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$runnerPs1`"" `
    -WorkingDirectory $scriptDir
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit (New-TimeSpan -Days 3650) -StartWhenAvailable
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger `
    -Settings $settings -Description 'RBANK 银行短信接入：163 邮箱轮询解析，可用额度/OTP/复核告警' -Force | Out-Null

Write-Output "Task registered: $taskName"
schtasks /Query /TN $taskName /FO LIST | Select-String 'TaskName|Status|Next Run'
