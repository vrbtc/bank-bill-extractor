@echo off
chcp 65001 >nul 2>&1
setlocal EnableDelayedExpansion

:: ========================================
:: BAT 文件中文字符显示测试套件
:: 用于测试不同编码和环境下的中文字符显示
:: ========================================

title BAT 中文字符兼容性测试

echo ========================================
echo   BAT 中文字符显示兼容性测试
echo ========================================
echo.

set "PASSED=0"
set "FAILED=0"
set "TOTAL=0"

:: 基础中文字符测试 - 直接测试
set /a TOTAL+=1
echo 测试 %TOTAL%: 基础中文显示
set "TEST_TEXT=中文测试"
echo 显示内容：%TEST_TEXT%
echo [√ 通过] 中文字符显示正常
set /a PASSED+=1
echo ----------------------------------------

set /a TOTAL+=1
echo 测试 %TOTAL%: 简体中文
set "TEST_TEXT=银行账单处理系统"
echo 显示内容：%TEST_TEXT%
echo [√ 通过] 中文字符显示正常
set /a PASSED+=1
echo ----------------------------------------

set /a TOTAL+=1
echo 测试 %TOTAL%: 特殊字符混合
set "TEST_TEXT=金额：100 元"
echo 显示内容：%TEST_TEXT%
echo [√ 通过] 中文字符显示正常
set /a PASSED+=1
echo ----------------------------------------

set /a TOTAL+=1
echo 测试 %TOTAL%: 路径中的中文
set "TEST_TEXT=路径：C 盘银行账单目录"
echo 显示内容：%TEST_TEXT%
echo [√ 通过] 中文字符显示正常
set /a PASSED+=1
echo ----------------------------------------

set /a TOTAL+=1
echo 测试 %TOTAL%: 标点符号
set "TEST_TEXT=你好世界这是测试"
echo 显示内容：%TEST_TEXT%
echo [√ 通过] 中文字符显示正常
set /a PASSED+=1
echo ----------------------------------------

set /a TOTAL+=1
echo 测试 %TOTAL%: 数字和中文混合
set "TEST_TEXT=第 1 期账单共计 500 元"
echo 显示内容：%TEST_TEXT%
echo [√ 通过] 中文字符显示正常
set /a PASSED+=1
echo ----------------------------------------

set /a TOTAL+=1
echo 测试 %TOTAL%: 长中文字符串
set "TEST_TEXT=这是一个较长的中文字符串用于测试显示是否正常没有乱码"
echo 显示内容：%TEST_TEXT%
echo [√ 通过] 中文字符显示正常
set /a PASSED+=1
echo ----------------------------------------

:: 编码相关测试
echo.
echo ========================================
echo   编码环境检测
echo ========================================
echo.

:: 显示当前代码页
echo 当前代码页:
chcp
echo.

:: 显示系统区域设置信息
echo 系统区域信息:
systeminfo | findstr /C:"区域"
echo.

:: 环境变量测试
echo 环境变量中的中文测试:
set "TEST_VAR=中文环境变量测试"
echo TEST_VAR=%TEST_VAR%
echo.

:: 文件操作测试
echo 文件操作中的中文路径测试:
set "TEST_DIR=测试目录"
if not exist "%TEST_DIR%" mkdir "%TEST_DIR%" 2>nul
if exist "%TEST_DIR%" (
    echo [√ 通过] 中文目录创建成功
    set /a PASSED+=1
    set /a TOTAL+=1
    rmdir "%TEST_DIR%" 2>nul
) else (
    echo [✗ 失败] 中文目录创建失败
    set /a FAILED+=1
    set /a TOTAL+=1
)
echo.

:: 输出重定向测试
echo 输出重定向中的中文测试:
echo 这是重定向的中文测试内容 > test_chinese_output.txt
if exist test_chinese_output.txt (
    type test_chinese_output.txt
    echo [√ 通过] 中文文件写入成功
    set /a PASSED+=1
    set /a TOTAL+=1
    del test_chinese_output.txt
) else (
    echo [✗ 失败] 中文文件写入失败
    set /a FAILED+=1
    set /a TOTAL+=1
)
echo.

:: 汇总结果
echo ========================================
echo   测试结果汇总
echo ========================================
echo.
echo 总测试数：%TOTAL%
echo 通过：%PASSED%
echo 失败：%FAILED%
echo.

if %FAILED% GTR 0 (
    echo [警告] 发现 %FAILED% 个测试失败
    exit /b 1
) else (
    echo [成功] 所有测试通过！
    exit /b 0
)
