# auto_sync.ps1 - 检查本地变更并自动提交推送到 GitHub
# 供定时任务调用，无需人工干预。
$ErrorActionPreference = "Stop"
Set-Location "k:\Trae CN\R BANK"

$branch = git rev-parse --abbrev-ref HEAD
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: 无法获取当前分支"
    exit 1
}

# 检查是否有未提交的变更（尊重 .gitignore）
$dirty = git status --porcelain
# 检查是否有未推送的本地提交
$unpushed = git log "@{u}.." --oneline 2>$null

if (-not $dirty -and -not $unpushed) {
    Write-Host "NO_CHANGES: 无变更，跳过同步"
    exit 0
}

# 暂存所有变更
if ($dirty) {
    git add -A
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $fileCount = ($dirty | Measure-Object).Count
    git commit -m "Auto-sync: $timestamp ($fileCount 个文件变更)"
    if ($LASTEXITCODE -ne 0) {
        Write-Host "WARN: 提交失败，可能无实际变更"
    }
}

# 推送（若失败则先 rebase 远程再推送）
git push origin $branch 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "推送失败，尝试 rebase 后重试..."
    git pull --rebase origin $branch 2>&1
    git push origin $branch 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: 推送失败，需人工介入"
        exit 1
    }
}

Write-Host "SYNCED: 已同步到 origin/$branch"
