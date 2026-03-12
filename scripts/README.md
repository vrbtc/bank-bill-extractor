# 脚本编码和转义字符问题解决方案

本目录包含了一套完整的工具和测试套件，用于解决 PowerShell 脚本和 BAT 文件中的编码、转义字符和中文字符显示问题。

## 📁 文件清单

### 测试工具

1. **test_powershell_escape.ps1** - PowerShell 转义字符兼容性测试套件
2. **test_batch_chinese.bat** - BAT 文件中文字符显示测试套件

### 检测和修复工具

3. **encoding_checker.py** - 脚本文件编码检测和转换工具
4. **fix_encodings.py** - 脚本编码批量修复工具
5. **validate_scripts.py** - 脚本验证和 CI/CD 检查工具

### 文档

6. **SCRIPT_ENCODING_SPEC.md** - 脚本编码和转义字符处理规范（完整文档）
7. **README.md** - 本文件，工具使用说明

---

## 🚀 快速开始

### 1. 检测现有脚本的编码问题

```bash
# 检测当前目录下的所有脚本
python scripts/encoding_checker.py

# 检测指定目录
python scripts/encoding_checker.py /path/to/scripts

# 生成详细报告
python scripts/encoding_checker.py -o report.txt
```

### 2. 批量修复编码问题

```bash
# 修复当前目录（自动创建备份）
python scripts/fix_encodings.py

# 修复指定目录
python scripts/fix_encodings.py /path/to/scripts

# 仅检测不修复（dry-run 模式）
python scripts/fix_encodings.py --dry-run

# 不创建备份
python scripts/fix_encodings.py --no-backup
```

### 3. 运行测试验证

```bash
# PowerShell 转义字符测试
pwsh scripts/test_powershell_escape.ps1

# 或详细输出
pwsh scripts/test_powershell_escape.ps1 -Verbose

# BAT 中文显示测试
scripts\test_batch_chinese.bat
```

### 4. 完整验证流程

```bash
# 运行所有验证检查
python scripts/validate_scripts.py

# CI/CD 模式（失败时返回非零退出码）
python scripts/validate_scripts.py --ci
```

---

## 📋 工具详细说明

### encoding_checker.py - 编码检测工具

**功能**:
- 检测脚本文件的编码格式（UTF-8、UTF-8 with BOM、UTF-16、ANSI 等）
- 识别包含中文字符的文件
- 自动判断编码是否符合规范
- 批量转换问题文件

**使用示例**:
```bash
# 基本检测
python scripts/encoding_checker.py

# 检测并生成报告
python scripts/encoding_checker.py -o encoding_report.txt

# 批量转换所有问题文件
python scripts/encoding_checker.py --batch-convert

# 转换指定文件
python scripts/encoding_checker.py -c file1.ps1 file2.bat
```

**输出示例**:
```
扫描目录：K:\Trae CN\R BANK\scripts
================================================================================
找到 5 个脚本文件

检测：test_powershell_escape.ps1
  ✓ 编码：utf-8-sig (UTF-8 BOM) [含中文]

检测：test_batch_chinese.bat
  ⚠ 编码：utf-8 [含中文]
     问题：BAT/CMD 含中文但无 BOM

统计信息:
  总文件数：5
  UTF-8 无 BOM: 2
  UTF-8 with BOM: 2
  发现问题：1
```

---

### fix_encodings.py - 编码修复工具

**功能**:
- 自动将脚本文件转换为 UTF-8 with BOM 编码
- 为 BAT 文件添加 `chcp 65001` 命令
- 为 PowerShell 脚本添加编码设置行
- 自动创建备份文件

**使用示例**:
```bash
# 基本修复（推荐）
python scripts/fix_encodings.py

# 修复指定目录
python scripts/fix_encodings.py /path/to/scripts

# 不创建备份
python scripts/fix_encodings.py --no-backup

# 仅检测（dry-run）
python scripts/fix_encodings.py --dry-run
```

**修复内容**:
1. **BAT/CMD 文件**:
   - 转换为 UTF-8 with BOM 编码
   - 在 `@echo off` 后添加 `chcp 65001 >nul 2>&1`

2. **PowerShell 文件**:
   - 转换为 UTF-8 编码（推荐 with BOM）
   - 添加 `[Console]::OutputEncoding = [System.Text.Encoding]::UTF8`

---

### validate_scripts.py - 验证工具

**功能**:
- 运行所有编码检测
- 执行 PowerShell 转义测试
- 执行 BAT 中文测试
- 检查 Git 配置
- 检查脚本头部注释
- 生成完整报告

**使用示例**:
```bash
# 基本验证
python scripts/validate_scripts.py

# CI/CD 模式
python scripts/validate_scripts.py --ci

# 跳过某些测试
python scripts/validate_scripts.py --skip-ps
python scripts/validate_scripts.py --skip-bat
```

**检查项目**:
1. ✅ 文件编码检测
2. ✅ PowerShell 转义字符测试
3. ✅ BAT 文件中文字符测试
4. ✅ .gitattributes 配置检查
5. ✅ 脚本头部注释检查

---

### test_powershell_escape.ps1 - PowerShell 转义测试

**测试内容**:
- 反引号转义（`", `', ``, `$, `?）
- 变量扩展（双引号 vs 单引号）
- 特殊字符（换行、制表符、回车）
- 路径处理（反斜杠转义）
- 中文字符和 Unicode
- 命令参数处理

**使用示例**:
```powershell
# 基本测试
pwsh scripts/test_powershell_escape.ps1

# 详细输出
pwsh scripts/test_powershell_escape.ps1 -Verbose

# 导出结果
pwsh scripts/test_powershell_escape.ps1 | Out-File test_result.txt
```

**输出示例**:
```
========================================
PowerShell 转义字符兼容性测试
========================================

1. 反引号 (`) 转义测试
----------------------------------------
[✓ 通过] 反引号转义双引号
  期望：""
  实际：""

[✓ 通过] 反引号转义单引号
  期望：'
  实际：'

...

测试结果汇总
========================================
总测试数：18
通过：18
失败：0

所有测试通过！
```

---

### test_batch_chinese.bat - BAT 中文测试

**测试内容**:
- 基础中文显示
- 简体中文文本
- 特殊字符混合（中文 + 英文 + 符号）
- 中文路径处理
- 中文标点符号
- 数字和中文混合
- 环境变量中的中文
- 文件操作中的中文

**使用示例**:
```cmd
:: 运行测试
scripts\test_batch_chinese.bat

:: 在不同代码页下测试
chcp 65001 && scripts\test_batch_chinese.bat
chcp 936 && scripts\test_batch_chinese.bat
```

---

## 🔧 常见问题解决流程

### 问题 1: BAT 文件中文显示乱码

**解决步骤**:
```bash
# 1. 检测编码
python scripts/encoding_checker.py

# 2. 修复编码
python scripts/fix_encodings.py

# 3. 验证修复
scripts\test_batch_chinese.bat
```

### 问题 2: PowerShell 脚本特殊字符错误

**解决步骤**:
```bash
# 1. 运行转义测试
pwsh scripts/test_powershell_escape.ps1

# 2. 查看失败测试，定位问题

# 3. 参考 SCRIPT_ENCODING_SPEC.md 修复代码

# 4. 重新测试验证
pwsh scripts/test_powershell_escape.ps1
```

### 问题 3: 多个脚本文件需要批量修复

**解决步骤**:
```bash
# 1. 检测所有文件
python scripts/encoding_checker.py

# 2. 批量修复（自动备份）
python scripts/fix_encodings.py

# 3. 验证修复结果
python scripts/validate_scripts.py

# 4. 确认无误后删除备份文件
find . -name "*.bak" -delete  # Linux/Mac
del /S *.bak                   # Windows CMD
```

---

## 📊 CI/CD 集成

### GitHub Actions 示例

```yaml
name: Script Validation

on: [push, pull_request]

jobs:
  validate-scripts:
    runs-on: windows-latest
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.x'
    
    - name: Install dependencies
      run: pip install chardet
    
    - name: Check script encodings
      run: python scripts/encoding_checker.py
    
    - name: Validate all scripts
      run: python scripts/validate_scripts.py --ci
    
    - name: Test PowerShell escapes
      run: pwsh scripts/test_powershell_escape.ps1
    
    - name: Test BAT Chinese display
      run: scripts\test_batch_chinese.bat
```

### Azure DevOps 示例

```yaml
trigger:
- main

pool:
  vmImage: 'windows-latest'

steps:
- script: |
    pip install chardet
    python scripts/encoding_checker.py
    python scripts/validate_scripts.py --ci
  displayName: 'Validate Script Encodings'

- script: |
    pwsh scripts/test_powershell_escape.ps1
  displayName: 'PowerShell Escape Tests'

- script: |
    call scripts\test_batch_chinese.bat
  displayName: 'BAT Chinese Tests'
```

---

## 📖 最佳实践

### 1. 新脚本开发

- 创建新脚本时使用提供的模板（见 SCRIPT_ENCODING_SPEC.md）
- 立即运行测试验证
- 添加到版本控制前运行完整验证

### 2. 现有脚本维护

- 定期（如每月）运行编码检测
- 发现问题的脚本立即修复
- 记录修复历史

### 3. 团队协作

- 所有成员阅读 SCRIPT_ENCODING_SPEC.md
- 在 PR 检查中包含脚本验证
- 使用 CI/CD 自动化检查

### 4. 备份策略

- 修复前自动创建备份（.bak 文件）
- 验证修复成功后保留备份 7 天
- 确认无问题后批量删除备份

---

## 🎯 编码规范速查

### PowerShell 文件

```powershell
# 文件开头添加
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# 字符串使用
$message = "包含变量：$var"      # 双引号 - 扩展变量
$message = '字面值：$var'        # 单引号 - 不扩展

# 特殊字符转义
$path = 'C:\path\to\file'       # 单引号 - 无需转义
$path = "C:\path`to`file"       # 双引号 - 需要转义
$price = "Cost: `$100.00"       # 转义美元符号
```

### BAT 文件

```batch
@echo off
chcp 65001 >nul 2>&1
setlocal EnableDelayedExpansion

:: 中文字符
set "MESSAGE=中文消息"
echo %MESSAGE%

:: 路径处理
set "PATH_VAR=C:\路径\到\文件"
```

---

## 📚 相关资源

- [SCRIPT_ENCODING_SPEC.md](./SCRIPT_ENCODING_SPEC.md) - 完整规范文档
- [PowerShell 转义字符官方文档](https://docs.microsoft.com/powershell/module/microsoft.powershell.core/about/about_special_characters)
- [Windows CMD 代码页文档](https://docs.microsoft.com/windows/console/chcp)

---

## ⚙️ 系统要求

- Python 3.6+
- PowerShell 5.1+ 或 PowerShell Core 6.0+
- Windows 7 或更高版本
- 需要 Python 库：chardet

### 安装依赖

```bash
pip install chardet
```

---

## 📝 更新日志

### v1.0.0 (2024-01-01)
- 初始版本
- 包含完整的测试、检测和修复工具
- 支持 PowerShell 和 BAT 脚本
- 提供 CI/CD 集成方案

---

## 🤝 贡献

欢迎提交问题和改进建议！

---

## 📄 许可证

本项目遵循 MIT 许可证。
