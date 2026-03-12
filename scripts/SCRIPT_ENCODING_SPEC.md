# 脚本文件编码和特殊字符处理规范

## 目录

1. [概述](#概述)
2. [编码规范](#编码规范)
3. [PowerShell 转义字符规范](#powershell-转义字符规范)
4. [BAT 文件中文字符处理规范](#bat-文件中文字符处理规范)
5. [最佳实践](#最佳实践)
6. [问题排查指南](#问题排查指南)
7. [工具和自动化](#工具和自动化)

---

## 概述

本文档规定了项目中所有脚本文件（PowerShell、BAT 等）的编码标准和特殊字符处理规范，旨在：

- 确保脚本在不同 Windows 环境和区域设置下正常工作
- 防止中文字符显示乱码
- 确保特殊字符正确转义和处理
- 建立统一的编码质量标准

### 适用范围

- 所有 PowerShell 脚本（.ps1, .psm1, .psd1）
- 所有批处理脚本（.bat, .cmd）
- 其他包含中文或特殊字符的脚本文件

---

## 编码规范

### 1. 文件编码标准

#### PowerShell 脚本
- **强制要求**: 使用 UTF-8 编码（无 BOM 或有 BOM 均可）
- **推荐**: UTF-8 with BOM（提高兼容性）
- **禁止**: ANSI、GBK、UTF-16 等其他编码

#### BAT/CMD 脚本
- **强制要求**: 使用 UTF-8 with BOM 编码
- **原因**: Windows CMD 需要 BOM 来正确识别 UTF-8 编码
- **禁止**: ANSI、GBK 等本地编码

### 2. 编码检测方法

#### 使用 Python 工具检测
```bash
python scripts/encoding_checker.py .
```

#### 使用 PowerShell 检测
```powershell
# 检查文件编码
$encoding = Get-Content -Path "file.ps1" -Encoding Byte -TotalCount 3
if ($encoding[0] -eq 0xEF -and $encoding[1] -eq 0xBB -and $encoding[2] -eq 0xBF) {
    Write-Host "UTF-8 with BOM"
}
```

### 3. 编码转换方法

#### 使用记事本转换
1. 用记事本打开文件
2. 点击"文件" -> "另存为"
3. 在"编码"下拉框选择"UTF-8 with BOM"
4. 保存

#### 使用 Python 工具批量转换
```bash
python scripts/encoding_checker.py --batch-convert
```

#### 使用 PowerShell 转换
```powershell
$content = Get-Content -Path "input.bat" -Encoding Default
$content | Out-File -FilePath "output.bat" -Encoding UTF8BOM
```

---

## PowerShell 转义字符规范

### 1. PowerShell 转义字符（反引号 `）

PowerShell 使用反引号（`）作为转义字符。

#### 常见转义序列

| 转义序列 | 含义 | 示例 |
|---------|------|------|
| `` `` | 反引号本身 | ```` 输出 ` |
| `` "`` | 双引号 | ```"``` 输出 " |
| `` '`` | 单引号 | ```'``` 输出 ' |
| `` $`` | 美元符号 | ```$``` 输出 $ |
| `` ?`` | 问号 | ```?``` 输出 ? |
| `` n`` | 换行符 | `"Line1`nLine2"` |
| `` t`` | 制表符 | `"Col1`tCol2"` |
| `` r`` | 回车符 | `"Line1`rLine2"` |

### 2. 字符串引号使用

#### 双引号字符串（会扩展变量）
```powershell
$name = "World"
Write-Host "Hello $name"  # 输出：Hello World
```

#### 单引号字符串（不扩展变量）
```powershell
$name = "World"
Write-Host 'Hello $name'  # 输出：Hello $name
```

### 3. 路径处理

#### 推荐：使用单引号
```powershell
$path = 'C:\Users\test\file.txt'
```

#### 双引号需要转义
```powershell
$path = "C:\Users`\test`\file.txt"
```

#### 最佳实践：使用变量
```powershell
$path = Join-Path -Path $env:USERPROFILE -ChildPath "test\file.txt"
```

### 4. 特殊字符处理

#### 包含变量的字符串
```powershell
# 正确
$message = "Cost: `$100.00"
$message = 'Cost: $100.00'

# 错误
$message = "Cost: $100.00"  # $100 会被解析为变量
```

#### 包含中文的字符串
```powershell
# 推荐
$message = "中文消息：成功"
$message = '中文消息：成功'
```

### 5. 常见错误示例

#### 错误 1：未转义美元符号
```powershell
# 错误
$email = "user@domain.com"
Write-Host "Contact: $email"  # 如果$email 是变量会出错

# 正确
Write-Host "Contact: `$email"
Write-Host 'Contact: $email'
```

#### 错误 2：路径中的反斜杠
```powershell
# 可能出错
$path = "C:\new\folder"  # \n 可能被解释为换行

# 正确
$path = 'C:\new\folder'
$path = "C:\new`\folder"
```

---

## BAT 文件中文字符处理规范

### 1. 基本结构

所有包含中文的 BAT 文件必须包含以下头部：

```batch
@echo off
chcp 65001 >nul 2>&1
setlocal EnableDelayedExpansion

:: 设置控制台字体（可选，推荐）
:: 需要在脚本外手动设置或使用 mode 命令
```

### 2. 中文变量处理

#### 使用引号包裹
```batch
set "MESSAGE=中文消息"
echo %MESSAGE%
```

#### 延迟扩展
```batch
setlocal EnableDelayedExpansion
set "VAR=中文"
echo !VAR!
```

### 3. 中文路径处理

```batch
set "CHINESE_DIR=中文目录"
if not exist "%CHINESE_DIR%" mkdir "%CHINESE_DIR%"
```

### 4. 输出重定向

```batch
echo 中文内容 > output.txt
:: 确保输出文件也是 UTF-8 编码
```

### 5. 常见错误

#### 错误 1：缺少 chcp 65001
```batch
@echo off
:: 错误：没有设置代码页，中文会显示乱码
echo 中文测试
```

#### 错误 2：未使用引号
```batch
:: 错误：空格会导致问题
set MESSAGE=中文 消息

:: 正确
set "MESSAGE=中文 消息"
```

---

## 最佳实践

### 1. 脚本模板

#### PowerShell 脚本模板
```powershell
#!/usr/bin/env pwsh
# -*- coding: utf-8 -*-
<#
.SYNOPSIS
    脚本简介

.DESCRIPTION
    详细描述

.PARAMETER Param1
    参数 1 说明

.EXAMPLE
    .\script.ps1 -Param1 value
#>

param(
    [Parameter(Mandatory=$false)]
    [string]$Param1
)

# 设置输出编码
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# 错误处理
$ErrorActionPreference = 'Stop'

try {
    # 主要逻辑
    Write-Host "执行中..." -ForegroundColor Green
}
catch {
    Write-Error "发生错误：$_"
    exit 1
}
```

#### BAT 脚本模板
```batch
@echo off
chcp 65001 >nul 2>&1
setlocal EnableDelayedExpansion

:: ========================================
:: 脚本名称：script.bat
:: 功能描述：脚本功能说明
:: 创建日期：2024-01-01
:: 最后修改：2024-01-01
:: ========================================

title 脚本标题

:: 错误处理
set "ERROR_COUNT=0"

:: 主逻辑
echo 脚本开始执行...

:: 清理
endlocal
exit /b 0
```

### 2. 测试要求

所有脚本在发布前必须通过以下测试：

1. **编码检测**: 使用 encoding_checker.py 检测
2. **转义测试**: PowerShell 脚本运行转义字符测试
3. **中文显示**: BAT 脚本在 CMD 中中文显示正常
4. **跨环境测试**: 在不同 Windows 版本测试

### 3. 版本控制

- 在 Git 中正确配置编码处理：
```bash
# .gitattributes
*.ps1 text working-tree-encoding=UTF-8
*.bat text working-tree-encoding=UTF-8
*.cmd text working-tree-encoding=UTF-8
```

---

## 问题排查指南

### 常见问题 1: PowerShell 脚本中文显示乱码

**症状**: 运行 PowerShell 脚本时中文字符显示为乱码

**排查步骤**:
1. 检查文件编码：`encoding_checker.py script.ps1`
2. 检查控制台编码：`[Console]::OutputEncoding`
3. 检查 ISE/VSCode 设置

**解决方案**:
```powershell
# 在脚本开头添加
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
```

### 常见问题 2: BAT 文件中文乱码

**症状**: BAT 脚本执行时中文显示为"锟斤拷"或其他乱码

**排查步骤**:
1. 检查是否有 `chcp 65001`
2. 检查文件编码是否为 UTF-8 with BOM
3. 检查 CMD 区域设置

**解决方案**:
1. 添加 `chcp 65001 >nul 2>&1` 到脚本开头
2. 用 UTF-8 with BOM 重新保存文件

### 常见问题 3: 变量扩展问题

**症状**: PowerShell 中变量未正确替换

**排查步骤**:
1. 检查引号类型（单引号 vs 双引号）
2. 检查变量名是否正确
3. 检查是否需要转义$符号

**解决方案**:
```powershell
# 使用双引号扩展变量
$name = "value"
Write-Host "Value: $name"

# 使用单引号保持字面值
Write-Host 'Variable: $name'
```

### 常见问题 4: 路径转义错误

**症状**: 文件路径无法正确解析

**排查步骤**:
1. 检查是否使用了正确的引号
2. 检查反斜杠是否需要转义
3. 检查是否包含特殊字符

**解决方案**:
```powershell
# 使用单引号
$path = 'C:\path\to\file'

# 或使用 Join-Path
$path = Join-Path $env:USERPROFILE "file.txt"
```

---

## 工具和自动化

### 1. 编码检测工具

使用项目中的 `encoding_checker.py`:

```bash
# 检测当前目录
python scripts/encoding_checker.py

# 检测指定目录
python scripts/encoding_checker.py /path/to/scripts

# 批量转换问题文件
python scripts/encoding_checker.py --batch-convert

# 生成报告
python scripts/encoding_checker.py -o report.txt
```

### 2. PowerShell 转义测试

```bash
# 运行转义字符测试
pwsh scripts/test_powershell_escape.ps1

# 详细输出
pwsh scripts/test_powershell_escape.ps1 -Verbose
```

### 3. BAT 中文测试

```cmd
:: 运行中文显示测试
scripts\test_batch_chinese.bat
```

### 4. 自动化检查流程

建议将以下检查添加到 CI/CD 流程：

```yaml
# GitHub Actions 示例
- name: Check script encodings
  run: python scripts/encoding_checker.py --fail-on-issue
  
- name: Test PowerShell escapes
  run: pwsh scripts/test_powershell_escape.ps1
  
- name: Test BAT Chinese display
  run: scripts\test_batch_chinese.bat
```

---

## 附录

### A. 编码速查表

| 文件类型 | 推荐编码 | BOM 要求 | 检测命令 |
|---------|---------|---------|---------|
| PowerShell .ps1 | UTF-8 | 可选 | `file.ps1` |
| PowerShell .psm1 | UTF-8 | 可选 | `file.psm1` |
| BAT .bat | UTF-8 | 必须 | `file.bat` |
| CMD .cmd | UTF-8 | 必须 | `file.cmd` |

### B. 转义字符速查表

| 字符 | PowerShell | BAT | 说明 |
|-----|-----------|-----|------|
| " | ```"``` | ```\"``` | 双引号 |
| ' | ```'``` | `''` | 单引号 |
| $ | ```$``` | `%%` | 美元符号/百分号 |
| \ | `\\` 或单引号 | `\\` | 反斜杠 |
| % | `%%` (BAT 中) | `%%` | 百分号 |
| ! | ```!``` | `^!` | 感叹号 |
| ^ | ```^``` | `^^` | 脱字符 |

### C. 参考资源

- [PowerShell 转义字符官方文档](https://docs.microsoft.com/powershell/module/microsoft.powershell.core/about/about_special_characters)
- [Windows CMD 代码页文档](https://docs.microsoft.com/windows/console/chcp)
- [UTF-8 BOM 说明](https://en.wikipedia.org/wiki/Byte_order_mark)

---

**文档版本**: 1.0  
**最后更新**: 2024-01-01  
**维护者**: 项目管理团队
