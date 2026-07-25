$task = Get-ScheduledTask -TaskName 'BankBillDaily'
Write-Output "=== Principal ==="
$task.Principal | Format-List
Write-Output ""
Write-Output "=== Environment variables in user session ==="
Write-Output ("USERPROFILE: " + $env:USERPROFILE)
Write-Output ("USERNAME: " + $env:USERNAME)
Write-Output ("TICKTICK_API_KEY (user): " + ($env:TICKTICK_API_KEY -ne ''))
Write-Output ("FEISHU_WEBHOOK_URL (user): " + ($env:FEISHU_WEBHOOK_URL -ne ''))
Write-Output ""
Write-Output "=== config.json info ==="
$cfg = "K:\Trae CN\R BANK\config.json"
if (Test-Path $cfg) {
    $item = Get-Item $cfg
    Write-Output ("Path: " + $cfg)
    Write-Output ("Size: " + $item.Length)
    Write-Output ("LastWriteTime: " + $item.LastWriteTime)
    Write-Output ("Attributes: " + $item.Attributes)
    # 读取关键字段（不打印敏感值，只打印是否存在）
    try {
        $j = Get-Content $cfg -Raw | ConvertFrom-Json
        Write-Output ("email field exists: " + ($null -ne $j.email))
        Write-Output ("email field value (masked): " + ('*' * ([string]($j.email)).Length))
        Write-Output ("ticktick_api_key exists: " + ($null -ne $j.ticktick_api_key))
        Write-Output ("feishu_webhook_url exists: " + ($null -ne $j.feishu_webhook_url))
    } catch {
        Write-Output ("JSON parse error: " + $_.Exception.Message)
    }
} else {
    Write-Output "config.json NOT FOUND at $cfg"
}
