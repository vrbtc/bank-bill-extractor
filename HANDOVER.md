# R BANK 本地部署交接文档（换电脑专用）

> **用途**：换新电脑后，让新电脑（或任何 AI 助手）按本文档一步步部署「本地备用调度」。
> **最后更新**：2026-10-23（P0 修复 + 云端优先架构落地后）
> **阅读对象**：用户本人 / 新电脑上的 AI 助手。全文约 10 分钟可部署完。

---

## 0. 一分钟理解架构

```
云端 GitHub Actions（主力，每天 4 次）                本地 Windows（备用，默认禁用）
  deploy.yml cron UTC 20/02/08/14        ←git 回传     BankBillDaily 计划任务（可选启用）
  全流程：抓邮件→提取→滴答同步→飞书推送    ─────────→   只抓邮件→提取→刷本地缓存/仪表盘
  →仪表盘部署→状态文件 commit 回 main                    （RUN_ROLE=local，不写滴答不推飞书）
```

- **云端是权威数据源**：滴答完成状态、运行日志都在 git 里由云端维护。
- **本地只是备用 + 测试场**：本地电脑关机不影响任何事；本地开机跑一次只是刷新本地缓存，**绝不会**动滴答清单。
- 凭据只在本地 `config.json`（已 gitignore，严禁提交）；云端用 GitHub repo secrets。

---

## 1. 新电脑部署步骤

### Step 1 — 安装 Python 3.12+
- 官网下载 Python 3.12（或更高），安装时**勾选 "Add Python to PATH"**。
- 验证：打开 CMD 或 PowerShell，运行 `python --version`，应显示 3.12+。

### Step 2 — 获取代码
```bat
git clone https://github.com/vrbtc/bank-bill-extractor.git "K:\Trae CN\R BANK"
cd /d "K:\Trae CN\R BANK"
```
（或把旧电脑的整个文件夹拷贝过来，但要保留 `.git` 目录。）

### Step 3 — 安装依赖
```bat
pip install -r requirements.txt
```

### Step 4 — 创建 config.json（唯一凭据文件，勿提交 git）
把 `config.example.json` 复制为 `config.json`，填入真实值：
- 主邮箱（阿里云）地址 + 授权码（非登录密码！在阿里云邮箱 → 设置 → 账户安全 → 授权码管理生成）
- QQ 邮箱地址 + 授权码（QQ 邮箱 → 设置 → 账户 → IMAP 服务开启后生成），label 固定填 `"YY"`
- 滴答 API Key（dida365 开放平台）
- 飞书群机器人 webhook

> ⚠️ `config.json` 已在 .gitignore 中，不会进仓库。历史上曾因 39 个脚本硬编码密码导致凭据公网暴露（2026-10-23 事故），现已全部改为从本文件导入——**任何脚本再出现硬编码密码都是回退，立即整改**。

### Step 5 — 创建 daily_run.bat（本地入口，已 gitignore 需手工创建）
在项目根目录新建 `daily_run.bat`，内容：

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

REM 启动时拉取云端最新状态（完成检测基准/账单数据），失败不阻断本地运行
echo [%date% %time%] Pulling latest state from origin (cloud-first)...
git pull --rebase origin main
if %errorlevel% neq 0 (
    echo [WARN] git pull --rebase failed, continue with local state
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
- `Pulling latest state from origin (cloud-first)...`
- `Starting daily bill run (role=local)...`
- `Step 3/4: local 角色跳过滴答同步与飞书推送`
- 结束后 `this_month_bills.json` 的 `generated_at` 是刚刚的时间

### Step 7 — 注册计划任务（注册后默认不运行，确认无误再启用）
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
| 启动时 git pull --rebase | ✅ | — |
| push 滴答状态文件 | ❌（auto-sync 已排除） | ✅（云端 commit 回 main） |

**为什么**：滴答 OpenAPI 不返回已完成任务，双写会重建您已勾选还清的任务。完成状态只能由云端单边维护。

---

## 3. 云端信息（日常排查看这里）

- Workflow：`.github/workflows/deploy.yml`，cron 每天 4 次（UTC 20/02/08/14，GitHub cron 有 3-5 小时延迟）
- 手动触发一次：`gh workflow run deploy.yml --ref main`（需本机有 gh 且已登录）
- 看运行记录：`gh run list --workflow deploy.yml --limit 10`
- 仪表盘：https://vrbtc.github.io/bank-bill-extractor/
- 运行审计：仓库里 `run_log.jsonl`（云端每次运行追加，本地启动时会 pull）
- 云端凭据：GitHub 仓库 → Settings → Secrets（EMAILS_JSON / TICKTICK_API_KEY / FEISHU_WEBHOOK_URL 等）

---

## 4. 凭据轮换流程（出事时的标准动作）

1. 生成新凭据（邮箱授权码 / 滴答 Key / 飞书 webhook）
2. 更新本地 `config.json`
3. 更新 GitHub secrets：`gh secret set EMAILS_JSON --body "..."` 等
4. 旧凭据作废即完成——**不需要**改 git 历史（除非仓库转公开且旧值仍在 HEAD）
5. 验证：手动触发一次云端 workflow，看滴答/飞书是否正常

---

## 5. 常见问题

| 症状 | 处理 |
|------|------|
| `python 不是内部或外部命令` | Python 没装或没加 PATH，重装并勾选 Add to PATH |
| 路径含空格报错 | 所有命令/路径用双引号包裹（本仓库路径 `K:\Trae CN\R BANK` 含空格） |
| `git pull --rebase` 冲突 | `git stash && git pull --rebase origin main && git stash pop`；本地改动优先提交后再 pull |
| 本地跑完滴答多了任务 | 检查 daily_run.bat 是否设了 `RUN_ROLE=local`；误跑过 cloud 角色就去滴答手动删掉多余任务 |
| 某银行金额突然不对 | 银行改了邮件模板：用 `python scripts/dump_failed_samples.py` 存样本，再改 `bank_extractors.py` 对应提取器 |
| 提取失败告警刷屏 | 飞书会推「待人工提取」卡片——附件型账单（PDF）需人工读取，属已知限制 |

---

## 6. 活路径文件速查（改代码只动这些）

| 文件 | 职责 |
|------|------|
| `this_month_bills.py` | 提取主引擎（多邮箱/聚合/告警） |
| `bank_extractors.py` | 11 家银行提取器 + 工厂 + 子账户 |
| `daily_run.py` | 运行入口（按 RUN_ROLE 分叉） |
| `generate_dashboard.py` | 云端入口（提取+同步+仪表盘） |
| `ticktick_sync.py` / `ticktick_api.py` | 滴答同步 / API 封装 |
| `feishu_notify.py` | 飞书推送（含提取告警卡片） |
| `email_client.py` / `email_decoder.py` / `config.py` | IMAP / 解码 / 配置 |

根目录其余 `check_*` / `debug_*` / `save_*` / `find_*` 等均为历史一次性脚本（2026-10-23 已清除硬编码），仅调试参考，勿当活路径。
