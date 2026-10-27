@echo off
chcp 65001 >nul 2>&1

REM RBANK 本地兜底看门狗启动器（2026-10-24）
REM GitHub Actions 延迟/漏跑时，本机开机则每 30 分钟检查并接管漏推的档位。
REM 只发送通知，不写滴答清单；推送标记回传 origin 防双推。

set "SCRIPT_DIR=%~dp0"

REM 优先用隔离 venv（含依赖），否则用系统 python
set "PY_EXE=python"
if exist "C:\Users\Administrator\.workbuddy\binaries\python\envs\default\Scripts\python.exe" (
    set "PY_EXE=C:\Users\Administrator\.workbuddy\binaries\python\envs\default\Scripts\python.exe"
)

where python >nul 2>&1
if %errorlevel% neq 0 (
    if not exist "%PY_EXE%" (
        echo [ERROR] Python not found
        exit /b 1
    )
)

cd /d "%SCRIPT_DIR%"
"%PY_EXE%" "%SCRIPT_DIR%local_fallback.py"

exit /b %errorlevel%
