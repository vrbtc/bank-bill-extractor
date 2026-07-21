<#
.SYNOPSIS
    通用项目自动同步到 GitHub 脚本（零依赖、可移植）
.PARAMETER ProjectPath
    要同步的项目根目录（必须已 git init 并配置好 GitHub 远程）
.PARAMETER LogFile
    可选日志文件路径，默认写入项目目录下的 .auto-sync.log
.EXAMPLE
    powershell -ExecutionPolicy Bypass -File auto-sync.ps1 -ProjectPath "D:\my-project"
#>
param(
    [Parameter(Mandatory = $true)]
    [string]$ProjectPath,
    [string]$LogFile
)

$ErrorActionPreference = "Continue"

# --- 路径规范化 ---
if (-not (Test-Path $ProjectPath)) {
    Write-Output "ERROR: 项目路径不存在: $ProjectPath"
    exit 1
}
$ProjectPath = (Resolve-Path $ProjectPath).Path

if (-not $LogFile) {
    $LogFile = Join-Path $ProjectPath ".auto-sync.log"
}

function Write-Log {
    param([string]$Message)
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $line = "[$timestamp] $Message"
    try {
        Add-Content -Path $LogFile -Value $line -Encoding UTF8 -ErrorAction Stop
    } catch {
        Write-Output $line
    }
}

Set-Location $ProjectPath

# --- 验证 git 仓库 ---
if (-not (Test-Path ".git")) {
    Write-Log "ERROR: 不是 git 仓库: $ProjectPath"
    exit 1
}

# --- 获取当前分支 ---
$branch = git rev-parse --abbrev-ref HEAD 2>$null
if ($LASTEXITCODE -ne 0 -or -not $branch) {
    Write-Log "ERROR: 无法获取当前分支"
    exit 1
}

# --- 验证有远程 ---
$remote = git remote 2>$null
if (-not $remote) {
    Write-Log "ERROR: 未配置远程仓库"
    exit 1
}

# --- 检查未提交变更 ---
$dirty = git status --porcelain 2>$null

# --- 检查未推送的本地提交 ---
$hasUpstream = $true
$upstream = git rev-parse "@{u}" 2>$null
if ($LASTEXITCODE -ne 0) { $hasUpstream = $false }

$unpushed = ""
if ($hasUpstream) {
    $unpushed = git log "@{u}.." --oneline 2>$null
}

# --- 无变更则跳过 ---
if (-not $dirty -and -not $unpushed) {
    Write-Log "NO_CHANGES"
    exit 0
}

# --- 设置上游（首次推送） ---
if (-not $hasUpstream) {
    git push --set-upstream origin $branch 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Write-Log "SYNCED (首次设置上游)"
        exit 0
    }
}

# --- 提交变更 ---
if ($dirty) {
    git add -A 2>&1 | Out-Null
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $fileCount = ($dirty | Measure-Object).Count
    git commit -m "Auto-sync: $timestamp ($fileCount files)" 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Log "WARN: commit 失败（可能无实际变更）"
    }
}

# --- 推送（失败则 rebase 重试） ---
git push origin $branch 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Log "推送失败，尝试 rebase 后重试..."
    git pull --rebase origin $branch 2>&1 | Out-Null
    git push origin $branch 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Log "ERROR: 推送失败，需人工介入"
        exit 1
    }
}

Write-Log "SYNCED"
exit 0
