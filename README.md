# 🏦 银行账单自动提取系统

自动从阿里云邮箱提取银行信用卡账单邮件，解析金额和还款日，生成在线仪表盘部署到 GitHub Pages，并自动同步到滴答清单提醒还款。

## ✨ 核心特性

- 📧 **邮箱自动提取** — 通过 IMAP 协议从阿里云邮箱拉取银行账单邮件
- 🏦 **多银行解析** — 支持 12 家银行的金额和还款日提取
- 📊 **在线仪表盘** — 自动生成静态 HTML 仪表盘，部署到 GitHub Pages
- ⏰ **定时运行** — GitHub Actions 每天 2 次自动运行（北京时间 11:00 和 17:00）
- 📋 **滴答清单同步** — 自动将账单创建为滴答清单任务，含智能优先级和到期提醒
- 🔒 **安全配置** — 密码等敏感信息通过 GitHub Secrets 加密存储，不进入代码

## 🏦 支持的银行

| 银行 | 金额提取 | 还款日提取 | 状态 |
|------|---------|-----------|------|
| 交通银行 | ✅ | ✅ | 完美 |
| 建设银行 | ✅ | ✅ | 完美 |
| 民生银行 | ✅ | ✅ | 完美 |
| 邮储银行 | ✅ | ✅ | 完美 |
| 兴业银行 | ✅ | ✅ | 完美 |
| 招商银行 | ✅ | ✅ | 支持 |
| 光大银行 | ✅ | ✅ | 支持 |
| 广发银行 | ✅ | ✅ | 支持 |
| 平安银行 | ✅ | ✅ | 支持 |
| 中信银行 | ✅ | ✅ | 支持 |
| 浦发银行 | ✅ | ✅ | 支持 |
| 中银香港 | ✅ | ✅ | 支持 |

---

## 🚀 快速部署（GitHub Actions + Pages）

### 前置条件

- GitHub 账号
- 阿里云邮箱（已开启 IMAP 服务）
- 银行账单邮件已发送到该邮箱
- 滴答清单账号 + API Key（可选，不配置则跳过同步）

### 第 1 步：克隆仓库

```bash
git clone https://github.com/vrbtc/bank-bill-extractor.git
cd bank-bill-extractor
```

### 第 2 步：启用 GitHub Pages

1. 进入仓库 **Settings → Pages**
2. **Source** 选择 **GitHub Actions**（不是 Deploy from a branch）
3. 保存

### 第 3 步：配置 GitHub Secrets

进入仓库 **Settings → Secrets and variables → Actions → New repository secret**，添加以下 5 个密钥：

| Secret 名称 | 值 | 说明 |
|-------------|---|------|
| `EMAIL_ADDRESS` | `your_email@aliyun.com` | 阿里云邮箱地址 |
| `EMAIL_PASSWORD` | `your_password` | 邮箱登录密码（账号密码，非授权码） |
| `IMAP_SERVER` | `imap.aliyun.com` | IMAP 服务器地址 |
| `IMAP_PORT` | `993` | IMAP 端口 |
| `TICKTICK_API_KEY` | `dp_xxxxxxxxxxxxxxxx` | 滴答清单 API Key（可选，不配则跳过同步） |

> **注意**：阿里云邮箱用账号密码直接登录 IMAP，不需要像 QQ 邮箱/163 邮箱那样生成授权码。

> **滴答清单 API Key 获取**：访问 [滴答清单开放平台](https://developer.dida365.com/) 申请。

### 第 4 步：触发首次运行

进入仓库 **Actions → Deploy Bank Bill Dashboard → Run workflow** 手动触发一次。

### 第 5 步：访问仪表盘

运行成功后访问：

```
https://<你的用户名>.github.io/bank-bill-extractor/
```

例如：https://vrbtc.github.io/bank-bill-extractor/

---

## 🖥️ 本地运行

### 环境要求

- Python 3.8+
- 阿里云邮箱账户

### 安装依赖

```bash
pip install -r requirements.txt
```

依赖清单（requirements.txt）：
- `beautifulsoup4` — HTML 解析
- `html2text` — HTML 转文本
- `requests` — 滴答清单 API 调用

### 配置

**方式一：config.json（推荐本地使用）**

复制 `config.example.json` 为 `config.json`，填入你的信息：

```json
{
  "email_address": "your_email@aliyun.com",
  "email_password": "your_password",
  "imap_server": "imap.aliyun.com",
  "imap_port": 993,
  "ticktick_api_key": "dp_your_api_key_here"
}
```

> `config.json` 已在 `.gitignore` 中，不会被提交。

**方式二：环境变量（CI 环境推荐）**

```bash
export EMAIL_ADDRESS=your_email@aliyun.com
export EMAIL_PASSWORD=your_password
export IMAP_SERVER=imap.aliyun.com
export IMAP_PORT=993
export TICKTICK_API_KEY=dp_your_api_key_here
```

配置加载优先级（config.py）：环境变量 > config.json > 默认值

### 运行

```bash
# 生成仪表盘 HTML（输出到 gh-pages/ 目录，同时自动同步滴答清单）
python generate_dashboard.py

# 仅提取账单并输出 JSON
python this_month_bills.py

# 提取 + 紧急检查 + 滴答清单同步
python daily_run.py
```

---

## 📁 项目结构

```
bank-bill-extractor/
│
├── .github/workflows/
│   └── deploy.yml                  # GitHub Actions 工作流（定时 + 部署）
│
├── 核心模块
│   ├── email_client.py             # IMAP 邮箱连接（含阿里云登录修复）
│   ├── email_decoder.py            # 邮件 MIME 解码
│   ├── bank_extractors.py          # 银行账单提取器（策略模式）
│   ├── this_month_bills.py         # 账单提取核心逻辑
│   ├── generate_dashboard.py       # 仪表盘 HTML 生成（含滴答清单同步）
│   ├── config.py                   # 统一配置模块
│   └── config.example.json         # 配置模板
│
├── 滴答清单集成
│   ├── ticktick_sync.py            # 滴答清单同步模块
│   └── daily_run.py                # 每日运行脚本（提取+同步）
│
├── 配置文件
│   ├── requirements.txt            # Python 依赖
│   ├── .gitignore                  # Git 忽略规则
│   └── config.json                 # 本地配置（不提交，需自行创建）
│
└── 文档
    ├── README.md                   # 本文件
    └── TICKTICK_GUIDE.md           # 滴答清单 API 指南
```

---

## 🏗️ 架构说明

### 数据流程

```
GitHub Actions 定时触发（每天 11:00 / 17:00 北京时间）
        │
        ▼
┌──────────────────────────────────┐
│  generate_dashboard.py           │
│  ├─ config.py 读取环境变量/配置   │
│  ├─ this_month_bills.py          │
│  │   ├─ email_client.py          │
│  │   │   └─ IMAP 连接阿里云邮箱   │
│  │   │   └─ 获取最近 100 封邮件   │
│  │   ├─ email_decoder.py         │
│  │   │   └─ MIME 解码邮件内容     │
│  │   ├─ bank_extractors.py       │
│  │   │   └─ 识别银行 + 提取金额   │
│  │   │   └─ 提取还款日            │
│  │   └─ 筛选未来待还款账单        │
│  ├─ sync_to_ticktick()           │  ← 滴答清单同步
│  │   ├─ 清理过期任务（>7天）      │
│  │   ├─ 按银行创建任务            │
│  │   └─ 自动去重                  │
│  └─ 生成 index.html + data.json  │
└──────────────────────────────────┘
        │                          │
        ▼                          ▼
┌────────────────────┐  ┌────────────────────┐
│  GitHub Pages 部署  │  │  滴答清单 App       │
│  └─ 在线仪表盘     │  │  └─ 还款提醒任务    │
└────────────────────┘  └────────────────────┘
```

### 关键技术点

#### 阿里云邮箱 IMAP 登录修复

阿里云邮箱的 IMAP 服务器（`imap.aliyun.com`）要求 `LOGIN` 命令的用户名必须用双引号包裹。Python 标准库 `imaplib` 的 `login()` 方法只引用密码不引用用户名，导致 `BAD [b'invalid command or parameters']` 错误。

修复方案见 email_client.py：创建了 `AliyunIMAP4_SSL` 子类，重写 `login()` 方法，使用 `_command` + `_command_complete` 分步调用。

> **关键**：阿里云邮箱用账号密码直接登录，不需要授权码。与 QQ 邮箱/163 邮箱不同。

#### 银行提取器（策略模式）

bank_extractors.py 使用策略模式，每家银行有独立的提取器，支持自定义正则规则和预处理逻辑。添加新银行只需在 `BankExtractorFactory` 注册。

#### 滴答清单同步

generate_dashboard.py 在提取账单后、生成仪表盘前自动调用 `sync_to_ticktick()`。如果未配置 `TICKTICK_API_KEY`，会优雅跳过不影响仪表盘生成。

---

## ⏰ 定时任务说明

GitHub Actions 工作流（.github/workflows/deploy.yml）在以下时间自动运行：

| UTC 时间 | 北京时间 | 说明 |
|---------|---------|------|
| `03:00` | `11:00` | 上午检查 |
| `09:00` | `17:00` | 下午检查 |

也可通过 **Actions → Run workflow** 手动触发。

> **免费额度**：公开仓库 GitHub Actions 完全免费、无限分钟。

---

## 📋 滴答清单集成

项目已集成滴答清单同步功能（ticktick_sync.py），在每次提取账单后自动运行。

### 功能

- ✅ 自动创建"信用卡还款"清单
- ✅ 按银行创建任务（标题含金额，内容含明细）
- ✅ 智能优先级：3 天内 = 高，7 天内 = 中，其他 = 低
- ✅ 到期日提醒：提前 1 天，紧急账单额外提前 2 小时
- ✅ 自动去重：已存在的任务跳过
- ✅ 自动清理：超过还款日 7 天的任务自动删除

### API 认证

- API 地址：`https://api.dida365.com/open/v1`
- 认证方式：Bearer Token（API Key）
- 获取方式：在 [滴答清单开放平台](https://developer.dida365.com/) 申请

### 配置方式

**GitHub Actions 环境**：将 API Key 添加到 GitHub Secrets（名称：`TICKTICK_API_KEY`）

**本地环境**：在 `config.json` 中添加 `ticktick_api_key` 字段，或设置环境变量 `TICKTICK_API_KEY`

### 本地使用

```bash
# 预览将要创建的任务（不实际创建）
python ticktick_sync.py --dry-run

# 正式同步（需要先运行 this_month_bills.py 生成数据）
python ticktick_sync.py

# 清理过期任务
python ticktick_sync.py --cleanup

# 完整流程：提取账单 + 生成仪表盘 + 同步滴答清单
python generate_dashboard.py
```

---

## 🔧 故障排查

### 1. IMAP 登录失败

| 错误信息 | 原因 | 解决方法 |
|---------|------|---------|
| `BAD [b'invalid command or parameters']` | 用户名未引用 | 已在代码中修复，确保使用最新的 `email_client.py` |
| `LOGIN failed.` | 密码错误或 Secrets 未设置 | 检查 GitHub Secrets 中的 `EMAIL_PASSWORD` |
| `socket error` | 登录后连接断开 | 已在代码中修复，使用 `_command` + `_command_complete` 分步调用 |
| 连接超时 | 网络问题或 IMAP 未开启 | 登录阿里云邮箱网页版 → 设置 → POP3/IMAP/SMTP → 开启 IMAP |

### 2. GitHub Pages 显示 ¥0.00

检查 Actions 运行日志：
- 进入 **Actions** 页面
- 点击最新的运行记录
- 查看 **Generate dashboard** 步骤的输出
- 如果显示 `Login successful!` 和 `Extracted N bill emails`，说明提取成功
- 如果显示错误，根据错误信息排查

### 3. 滴答清单同步失败

| 错误信息 | 原因 | 解决方法 |
|---------|------|---------|
| `TICKTICK_API_KEY not configured` | 未配置 API Key | 添加 GitHub Secret 或在 config.json 中配置 |
| `import failed` | requests 库未安装 | 运行 `pip install requests` |
| `401 Unauthorized` | API Key 无效 | 检查 API Key 是否正确，或重新申请 |
| `TickTick sync: module not available` | 模块导入失败 | 检查 ticktick_sync.py 是否在项目根目录 |

### 4. 提取金额为 0

可能原因：
- 银行 HTML 模板更新，正则不匹配
- 邮件编码问题

解决方法：
- 运行 `python check_all_banks.py` 查看各银行提取情况
- 更新 bank_extractors.py 中的正则规则

### 5. Actions 未触发

- 确认 `deploy.yml` 在 `.github/workflows/` 目录下
- 确认仓库 Settings → Actions → General → Actions permissions 允许运行
- 定时任务可能有几分钟延迟，这是 GitHub 的正常行为

---

## 🔒 安全说明

### 敏感信息保护

- ✅ 邮箱密码通过 GitHub Secrets 加密存储，不会出现在代码中
- ✅ 滴答清单 API Key 通过 GitHub Secrets 加密存储
- ✅ `config.json` 在 `.gitignore` 中，不会被提交
- ✅ `.gitignore` 已配置忽略所有敏感文件（`.env`、`*.key`、`credentials.json` 等）

### 仓库可见性

本仓库为 **公开（public）**，任何人都能看到代码和 Pages 页面。

**哪些信息会被公开**：
- ❌ 不会泄露：邮箱密码、API Key（在 Secrets 中加密）
- ⚠️ 会公开：银行名称、还款金额、还款日期（在 Pages 仪表盘上）

如果介意账单数据公开，可选：
1. 将仓库改为 private（GitHub Pages 对 private 仓库需要 GitHub Pro，$4/月）
2. 保持现状（金额数据不含姓名、卡号，风险较低）

### 如果 API Key 意外泄露

1. 立即到对应平台撤销旧 Key，生成新 Key
2. 更新 GitHub Secrets 中的值
3. 用 `git filter-repo` 工具清理 git 历史中的泄露内容
4. Force push 到 GitHub
5. 删除所有旧的 Actions 运行记录（日志可能包含敏感信息）
6. 联系 GitHub Support 请求清除缓存的 git 对象

---

## 📝 开发指南

### 添加新银行支持

1. 在 bank_extractors.py 中创建新的提取器类，继承 `BankExtractor`
2. 实现 `extract_amount()` 和 `extract_due_date()` 方法
3. 在 `BankExtractorFactory` 中注册

```python
class NewBankExtractor(BankExtractor):
    def extract_amount(self, text, bill_info):
        # 金额提取逻辑
        patterns = [r'本期应还款.*?￥([0-9,]+\.?[0-9]*)']
        # ...

    def extract_due_date(self, text, bill_info):
        # 还款日提取逻辑
        patterns = [r'到期还款日.*?(\d{4}-\d{2}-\d{2})']
        # ...
```

4. 在 this_month_bills.py 的 `BANK_MAP` 中添加银行识别关键词

### 修改运行频率

编辑 .github/workflows/deploy.yml 中的 `schedule.cron`：

```yaml
schedule:
  - cron: '0 3 * * *'   # UTC 时间，北京时间 = UTC + 8
  - cron: '0 9 * * *'
```

### 修改仪表盘样式

编辑 generate_dashboard.py 中的 `build_html()` 函数。

### 修改滴答清单任务格式

编辑 ticktick_sync.py 中的 `_build_task()` 方法。

---

## 📞 参考链接

- 在线仪表盘：https://vrbtc.github.io/bank-bill-extractor/
- 仓库地址：https://github.com/vrbtc/bank-bill-extractor
- 滴答清单 API 指南：TICKTICK_GUIDE.md
- 滴答清单开放平台：https://developer.dida365.com/

---

## 📄 License

本系统仅供个人使用。
