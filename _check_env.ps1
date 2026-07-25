Write-Output "=== 用户级环境变量 ==="
Write-Output ("TICKTICK_API_KEY length: " + ($env:TICKTICK_API_KEY).Length)
Write-Output ("FEISHU_WEBHOOK_URL value: " + $env:FEISHU_WEBHOOK_URL)
Write-Output ""
Write-Output "=== 系统级环境变量 ==="
$sys = [System.Environment]::GetEnvironmentVariable('FEISHU_WEBHOOK_URL', 'Machine')
$sys2 = [System.Environment]::GetEnvironmentVariable('TICKTICK_API_KEY', 'Machine')
Write-Output ("System FEISHU_WEBHOOK_URL: " + $sys)
Write-Output ("System TICKTICK_API_KEY length: " + ($sys2).Length)
Write-Output ""
Write-Output "=== 用户级（User scope）环境变量 ==="
$usr = [System.Environment]::GetEnvironmentVariable('FEISHU_WEBHOOK_URL', 'User')
$usr2 = [System.Environment]::GetEnvironmentVariable('TICKTICK_API_KEY', 'User')
Write-Output ("User FEISHU_WEBHOOK_URL: " + $usr)
Write-Output ("User TICKTICK_API_KEY length: " + ($usr2).Length)
