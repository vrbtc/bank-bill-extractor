# R BANK 本地部署交接文档（换电脑专用）

> **用途**：换新电脑后，让新电脑（或任何 AI 助手）按本文档一步步部署「本地备用调度」。
> **最后更新**：2026-10-23（改为「文件夹直接复制」交接方式，去掉 git clone）
> **阅读对象**：用户本人 / 新电脑上的 AI 助手。全文约 10 分钟可部署完。

---

## 0. 一分钟理解架构

```
云端 GitHub Actions（主力，每天 4 次）              本地 Windows（备用，默认禁用）
  deploy.yml cron UTC 20/02/08/14                  BankBillDaily 计划任务（可选启用）
  全流程：抓邮件→提取→滴答同步→飞书推送              只抓邮件→提取→刷本地缓存
  →仪表盘部署→状态文件 commit 回 main                （RUN_ROLE=local，不写滴答不推飞书）
```

- **云端是权威数据源**：滴答完成状态、运行日志由云端独立维护，与本地无关。
- **本地只是备用 + 测试场**：本地电脑关机不影响任何事；本地开机跑一次只是刷新本地缓存，**绝不会**动滴答清单。
- **新电脑上的本地副本是「离线单机版」**：不需要 git、不联网同步、不参与任何云端流程。想更新本地数据，跑一次 `daily_run.bat` 即可（直连邮箱抓取）。
- 凭据只在本地 `config.json`（已 gitignore，严禁提交 git）；云端用 GitHub repo secrets。

---

## 1. 新电脑部署步骤

### Step 1 — 安装 Python 3.12+
- 官网下载 Python 3.12（或更高），安装时**勾选 "Add Python to PATH"**。
- 验证：打开 CMD 或 PowerShell，运行 `python --version`，应显示 3.12+。

### Step 2 — 复制文件夹（本交接方式的核心）

在**旧电脑**上，把 `K:\Trae CN\R BANK` 整个文件夹复制到新电脑的同一路径 `K:\Trae CN\R BANK`（路径含空格是正常的，所有脚本已兼容）。

**直接全选复制也行**（总共才 ~10MB），但建议排除以下 4 项（在旧电脑上先删掉或复制时排除）：

| 排除项 | 大小 | 原因 |
|--------|------|------|
| `.git\` | 1.9M | git 历史里含 2026-10-23 之前的**明文旧密码**；新电脑不需要 git |
| `__pycache__\` | 0.8M | 旧 Python 编译缓存，无价值，删掉避免版本混淆 |
| `.backups\` | 0.2M | 旧版本代码备份，可能含旧硬编码密码，无价值 |
| `.workbuddy\` | 0.1M | 历史审计记录，含敏感排查笔记，与运行无关 |
| `*.zip`（根目录 4 个） | 0.1M | openclaw skill 打包产物，与当前系统无关 |

排除式复制命令（旧电脑 PowerShell 或 CMD **管理员**运行，一条搞定）：

```bat
robocopy "K:\Trae CN\R BANK" "\\新电脑\共享目录\R BANK" /E /XD .git __pycache__ .backups .workbuddy /XF *.zip
```

> 局域网共享名替换成新电脑实际的共享路径；如果嫌麻烦，全选复制后到新电脑上手动删掉这 4 项也行。
> `samples\`（失败邮件样本）建议保留——以后修提取规则要用。

复制完成后，新电脑上项目根目录应包含：`daily_run.py`、`this_month_bills.py`、`bank_extractors.py`、`config.json`、`daily_run.bat`、`requirements.txt`、`BankBillDaily_task.xml`、`samples\`、`.github\` 等。

### Step 3 — 安装依赖

```bat
cd /d "K:\Trae CN\R BANK"
pip install -r requirements.txt
```

### Step 4 — config.json（已随文件夹复制到位，可直接用）

`config.json` 是**唯一凭据文件**，复制过来就已包含全部可用凭据（2 个邮箱授权码、滴答 API Key、飞书 webhook），**无需重新填写**。

- 要改凭据（邮箱授权码 / 滴答 Key / 飞书 webhook）：只编辑这一个文件，保存即生效。
- ⚠️ 该文件是明文密码：别把项目文件夹传到网盘/不可信的人手里；日常使用无碍（自己的电脑）。
- ⚠️ 历史上曾因 39 个脚本硬编码密码导致凭据公网暴露（2026-10-23 事故，已修复并轮换）——**任何脚本再出现硬编码密码都是回退，立即整改**。

### Step 5 — daily_run.bat（已随文件夹复制到位）

本地运行入口，内容已内置 `RUN_ROLE=local`（只提取+刷缓存，不写滴答不推飞书）和「无 .git 时跳过拉取」逻辑，**双击即可跑，无需改动**。

万一该文件丢失，在项目根目录新建 `daily_run.bat`，内容如下：

```bat
@echo off
chcp 65001 >nul 2>&1

set "SCRIPT_DIR=%~dp0"
set "PYTHON_EXE=python"

REM P0-7 云端优先：本地运行显式注入 local 角色（只提取+刷缓存，不写滴答不推飞书）
set "RUN_ROLE=local"

where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found in PATH
    exit /b 1
)

cd /d "%SCRIPT_DIR%"

REM 仅当本地是 git 仓库时才拉取云端状态；纯离线副本自动跳过
if exist "%SCRIPT_DIR%.git" (
    echo [%date% %time%] Pulling latest state from origin (cloud-first)...
    git pull --rebase origin main
    if %errorlevel% neq 0 (
        echo [WARN] git pull --rebase failed, continue with local state
    )
) else (
    echo [SKIP] Not a git repository, running with local state only.
)

echo [%date% %time%] Starting daily bill run (role=local)...
"%PYTHON_EXE%" "%SCRIPT_DIR%daily_run.py"

if %errorlevel% equ 0 (
    echo [%date% %time%] Completed successfully.
) else (
    echo [%date% %time%] Completed with errors.
)

exit /b %errorlevel%
```

### Step 6 — 手动验证（先别注册任务）

双击 `daily_run.bat`，预期看到：

- `[SKIP] Not a git repository, running with local state only.`（离线副本正常现象）
- `Starting daily bill run (role=local)...`
- `Step 3/4: local 角色跳过滴答同步与飞书推送`
- 结束后 `this_month_bills.json` 的 `generated_at` 是刚刚的时间

### Step 7 — 注册计划任务（可选，注册后默认不运行）

用**管理员身份**打开 CMD：

```bat
schtasks /Create /TN "BankBillDaily" /XML "K:\Trae CN\R BANK\BankBillDaily_task.xml" /F
```

- 仓库里的 XML 已设为 `<Enabled>false</Enabled>`：**注册后不会自动运行**（云端优先，本地兜底）。
- 确认本地跑几天没问题后，想启用自动每天 09:00 运行：

  ```bat
  schtasks /Change /TN "BankBillDaily" /ENABLE
  ```
- 常用命令：

  ```bat
  schtasks /Query /TN "BankBillDaily" /fo LIST /v   :: 看状态/上次运行/结果
  schtasks /Run /TN "BankBillDaily"                  :: 手动跑一次
  schtasks /Change /TN "BankBillDaily" /DISABLE      :: 重新禁用
  schtasks /Delete /TN "BankBillDaily" /F            :: 删除
  ```

---

## 2. 本地角色的行为边界（重要，防止双写）

| 行为 | local 角色 | cloud 角色 |
|------|-----------|-----------|
| 抓邮件 + 提取账单 | ✅ | ✅ |
| 刷新 this_month_bills.json | ✅ | ✅（CI 临时文件） |
| 写滴答清单（建/改任务） | ❌ 绝不 | ✅ |
| 推飞书 | ❌ | ✅ |
| 启动时 git pull --rebase | 仅当存在 .git 时 | — |
| push 滴答状态文件 | ❌ | ✅（云端 commit 回 main） |

**为什么**：滴答 OpenAPI 不返回已完成任务，双写会重建您已勾选还清的任务。完成状态只能由云端单边维护。

---

## 3. 云端信息（日常排查看这里，新电脑不参与）

云端由 GitHub 独立维护，新电脑上的本地副本与它**无任何数据交换**（离线单机版）。

- Workflow：`.github/workflows/deploy.yml`，cron 每天 4 次（UTC 20/02/08/14，GitHub cron 有 3-5 小时延迟）
- 手动触发一次：`gh workflow run deploy.yml --ref main`（在**有 git 的电脑**上执行）
- 看运行记录：`gh run list --workflow deploy.yml --limit 10`
- 仪表盘：https://vrbtc.github.io/bank-bill-extractor/
- 运行审计：仓库里 `run_log.jsonl`（云端每次运行追加）
- 云端凭据：GitHub 仓库 → Settings → Secrets（EMAILS_JSON / TICKTICK_API_KEY / FEISHU_WEBHOOK_URL 等）

---

## 4. 凭据轮换流程（出事时的标准动作）

1. 生成新凭据（邮箱授权码 / 滴答 Key / 飞书 webhook）
2. 更新本地 `config.json`（所有本地脚本的唯一凭据源）
3. 更新 GitHub secrets：`gh secret set EMAILS_JSON --body "..."` 等（在有 git 的电脑上执行）
4. 旧凭据作废即完成——**不需要**改 git 历史（除非旧值仍在 HEAD）
5. 验证：手动触发一次云端 workflow，看滴答/飞书是否正常

---

## 5. 常见问题

| 症状 | 处理 |
|------|------|
| `python 不是内部或外部命令` | Python 没装或没加 PATH，重装并勾选 Add to PATH |
| 路径含空格报错 | 所有命令/路径用双引号包裹（本仓库路径 `K:\Trae CN\R BANK` 含空格） |
| 本地跑完滴答多了任务 | 检查 daily_run.bat 是否设了 `RUN_ROLE=local`；误跑过 cloud 角色就去滴答手动删掉多余任务 |
| 某银行金额突然不对 | 银行改了邮件模板：用 `python scripts/dump_failed_samples.py` 存样本，再改 `bank_extractors.py` 对应提取器 |
| 提取失败告警刷屏（飞书） | 附件型账单（PDF 正文请查收类）需人工读取，属已知限制；本地副本不推飞书故不受影响 |
| 新电脑上 git 命令报错 | 正常，本方案不含 .git；daily_run.bat 已自动跳过拉取逻辑 |

---

## 6. 复制后的安全检查（新电脑上做一次）

```bat
cd /d "K:\Trae CN\R BANK"

:: 1. 确认排除了 .git / .backups（旧明文密码的仅存位置，不应出现在新电脑）
if exist .git echo [FAIL] .git 未排除
if exist .backups echo [FAIL] .backups 未排除
if not exist .git if not exist .backups echo [OK] 无旧密码目录

:: 2. 扫描是否还有「密码/Key 硬编码字面量」形态（应输出 OK；已内置占位符过滤）
python -c "import pathlib,re; q=chr(34)+chr(39); pat=r'(?i)(password|api_key|webhook)\s*=\s*['+q+r'](?!your_|xxx|example|<)[^'+q+r']{8,}'; bad=[str(p) for p in pathlib.Path('.').rglob('*.py') if re.search(pat,p.read_text(encoding='utf-8',errors='ignore'))]; print('[FAIL]',bad) if bad else print('[OK] 无硬编码')"

:: 3. 确认 config.json 存在且凭据可读
python -c "import json; c=json.load(open('config.json',encoding='utf-8')); print('[OK]', len(c.get('emails',[])), '个邮箱配置')"
```

> 说明：2026-10-23 之前曾有 39 个脚本硬编码邮箱密码/滴答 Key 且仓库公开导致泄露，现已全部改为从 `config.json` 导入。命令 2 只匹配「变量=字符串字面量」的硬编码形态，不包含也不需要任何真实密码值；docstring 中的 `"your_api_key"` 类占位符已过滤，不会误报。

---

## 7. 活路径文件速查（改代码只动这些）

| 文件 | 职责 |
|------|------|
| `this_month_bills.py` | 提取主引擎（多邮箱/聚合/告警） |
| `bank_extractors.py` | 11 家银行提取器 + 工厂 + 子账户 |
| `daily_run.py` | 运行入口（按 RUN_ROLE 分叉） |
| `generate_dashboard.py` | 云端入口（提取+同步+仪表盘） |
| `ticktick_sync.py` / `ticktick_api.py` | 滴答同步 / API 封装 |
| `feishu_notify.py` | 飞书推送（含提取告警卡片） |
| `email_client.py` / `email_decoder.py` / `config.py` | IMAP / 解码 / 配置 |
| `daily_run.bat` | 本地入口（RUN_ROLE=local） |
| `config.json` | 唯一凭据文件（勿提交、勿外传） |

根目录其余 `check_*` / `debug_*` / `save_*` / `find_*` 等均为历史一次性脚本（2026-10-23 已清除硬编码），仅调试参考，勿当活路径。
