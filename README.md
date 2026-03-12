# 🏦 银行账单自动提取系统

一个完全自动化的银行账单提取、分析和智能提醒系统，支持 OpenClaw 集成和多银行数据提取。

## ✨ 特性

- 🔍 **自动提取** - 从邮箱自动提取多家银行账单
- 📊 **智能分析** - 提取金额、还款日等关键信息
- 🔔 **还款提醒** - 智能识别近期待还款账单
- 🌐 **API 服务** - 提供 REST API 供 OpenClaw 等系统集成
- 💾 **数据持久化** - 自动保存历史账单数据
- 📝 **多格式报告** - 支持 JSON 和文本格式报告

## 🏦 支持的银行

已测试并完美支持的银行：

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

## 📦 安装

### 环境要求

- Python 3.7+
- 阿里云邮箱账户（支持 IMAP）
- 网络连接

### 克隆项目

```bash
git clone git@github.com:vrbtc/bank-bill-extractor.git
cd bank-bill-extractor
```

### 依赖安装

本项目使用 Python 标准库，无需额外安装依赖。

## 🚀 快速开始

### 方法 1：运行一次提取

```bash
python bill_extractor_main.py
```

### 方法 2：启动 API 服务器

```bash
python openclaw_api.py
```

然后访问：http://localhost:8765

### 方法 3：OpenClaw 集成调用

```python
import requests

# 获取待还款账单
response = requests.get('http://localhost:8765/api/upcoming')
data = response.json()

print(f"待还款总额：¥{data['total_amount']:,.2f}")
print(f"银行数量：{data['bank_count']}")

for bank, info in data['upcoming_bills'].items():
    if info['total_amount'] > 0:
        due_date = info['earliest_due_date']['date']
        days = info['earliest_due_date']['days_until']
        print(f"{bank}: ¥{info['total_amount']:,.2f} | {due_date} ({days}天)")
```

## 📁 项目结构

```
bank-bill-extractor/
├── bill_extractor_main.py      # 主程序入口
├── this_month_bills.py         # 账单提取核心逻辑
├── bill_storage.py             # 数据持久化存储
├── openclaw_api.py             # OpenClaw API 接口
├── email_bill_extractor.py     # 邮件账单提取器
├── organize_bills.py           # 账单整理工具
├── reextract_bills.py          # 重新提取工具
│
├── scripts/                    # 辅助脚本
│   ├── encoding_checker.py     # 编码检查
│   ├── fix_encodings.py        # 编码修复
│   └── validate_scripts.py     # 脚本验证
│
├── bill_data_history.json      # 历史账单数据
├── bill_summary.txt            # 文本格式汇总报告
├── error_log.json              # 错误日志
├── organized_bills.json        # 整理后的账单
├── this_month_bills.json       # 本月账单
│
├── README.md                   # 本文件
├── OPENCLAW_INTEGRATION.md     # OpenClaw 集成指南
├── TICKTICK_GUIDE.md           # TickTick 集成指南
└── .gitignore                  # Git 忽略文件
```

## 📡 API 端点

系统提供以下 REST API 端点：

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/status` | GET | 获取系统状态 |
| `/api/bills` | GET | 获取最新账单 |
| `/api/upcoming` | GET | 获取待还款账单 |
| `/api/report` | GET | 获取文本报告 |
| `/api/extract` | POST | 触发账单提取 |
| `/api/errors` | GET | 获取错误日志 |

### API 使用示例

```bash
# 获取系统状态
curl http://localhost:8765/api/status

# 获取待还款账单
curl http://localhost:8765/api/upcoming

# 触发账单提取
curl -X POST http://localhost:8765/api/extract

# 获取文本报告
curl http://localhost:8765/api/report
```

## ⚙️ 配置

### 邮箱配置

在 `this_month_bills.py` 中修改邮箱设置：

```python
EMAIL_ADDRESS = "your_email@aliyun.com"
PASSWORD = "your_password"
IMAP_SERVER = "imap.aliyun.com"
IMAP_PORT = 993
```

### API 端口配置

在 `openclaw_api.py` 中修改服务端口：

```python
run_server(port=8765)  # 修改端口号
```

## ⏰ 定时任务配置

### Windows 任务计划程序

1. 打开"任务计划程序"
2. 创建基本任务
3. 设置每天 9:00 执行
4. 程序：`python.exe`
5. 参数：`bill_extractor_main.py`
6. 起始于：`k:\Trae CN\R BANK`

### Linux Cron

```bash
crontab -e
0 9 * * * cd "/path/to/bank-bill-extractor" && python bill_extractor_main.py
```

## 🔔 错误通知

系统支持多种通知方式，在 `openclaw_api.py` 的 `send_notification` 方法中配置：

### 邮件通知

```python
import smtplib
from email.mime.text import MIMEText

def send_email(error_msg):
    msg = MIMEText(f"账单提取出错：{error_msg}")
    msg['Subject'] = '银行账单提取错误'
    msg['From'] = 'your_email@aliyun.com'
    msg['To'] = 'your_email@aliyun.com'
    
    server = smtplib.SMTP_SSL('smtp.aliyun.com', 465)
    server.login('your_email@aliyun.com', 'your_password')
    server.send_message(msg)
    server.quit()
```

### 微信通知（Server 酱）

```python
import requests

def send_wechat(error_msg):
    send_key = 'YOUR_SEND_KEY'
    url = f'http://sc.ftqq.com/{send_key}.send'
    data = {'text': '账单提取错误', 'desp': error_msg}
    requests.post(url, data=data)
```

### 钉钉通知

```python
import requests

def send_dingtalk(error_msg):
    webhook = 'YOUR_DINGTALK_WEBHOOK'
    data = {'msgtype': 'text', 'text': {'content': error_msg}}
    requests.post(webhook, json=data)
```

## � 工作流程

```
1. 连接阿里云邮箱 (IMAP)
   ↓
2. 获取邮件 ID 列表
   ↓
3. 对比是否有新邮件
   ├─ 没有新邮件 → 返回"无新邮件"
   └─ 有新邮件 → 继续
   ↓
4. 提取账单信息
   ├─ HTML 转 Markdown
   ├─ 识别银行类型
   ├─ 提取账单金额
   └─ 提取还款日期
   ↓
5. 筛选未来 15 天待还款账单
   ↓
6. 保存数据到 JSON 文件
   ↓
7. 生成文本格式报告
   ↓
8. 返回结果/发送通知
```

## 🛠️ 故障排查

### 1. 连接邮箱失败

**检查项：**
- 邮箱账号密码是否正确
- IMAP 服务是否已开启
- 网络连接是否正常
- 防火墙设置

### 2. 提取金额为 0

**可能原因：**
- 银行 HTML 模板更新
- 编码问题
- 正则表达式不匹配

**解决方法：**
- 查看原始 HTML 文件
- 更新提取规则
- 添加新的银行特定处理逻辑

### 3. API 无法访问

**检查项：**
- 服务器是否运行
- 端口是否被占用
- 防火墙设置
- 使用 `curl http://localhost:8765/api/status` 测试

### 4. JSON 序列化错误

确保所有数据都是可序列化的类型：
- bytes 类型转 str
- datetime 类型转字符串

## 📝 最佳实践

1. **每天定时执行** - 设置每天上午 9 点自动检查账单
2. **监控错误日志** - 定期检查 `error_log.json`
3. **备份数据** - 定期备份 `bill_data_history.json`
4. **设置通知阈值** - 超过一定金额才发送通知
5. **测试新邮件检测** - 确保不会重复处理同一封邮件
6. **编码统一** - 所有文件使用 UTF-8 编码

## 🔧 扩展功能

### 添加新银行支持

在 `this_month_bills.py` 中添加银行特定的提取规则：

```python
if bank_name == '新银行':
    # 金额提取规则
    amount_patterns = [
        r'本期应还款.*?￥([0-9,]+\.?[0-9]*)',
        r'账单金额.*?CNY([0-9,]+\.?[0-9]*)',
    ]
    
    # 还款日提取规则
    due_patterns = [
        r'到期还款日.*?([0-9]{4}年 [0-9]{1,2}月 [0-9]{1,2}日)',
        r'最后还款日：(\d{4}-\d{2}-\d{2})',
    ]
```

### 自定义报告格式

修改 `bill_storage.py` 中的 `generate_text_report` 函数，自定义输出格式。

### 集成其他通知方式

在 `openclaw_api.py` 的 `send_notification` 方法中添加自定义通知逻辑。

## 📄 数据文件说明

### bill_data_history.json
存储所有历史账单数据和提取记录

### bill_summary.txt
文本格式的汇总报告，可直接阅读

### error_log.json
错误日志文件，记录所有异常信息

### organized_bills.json
按银行分类整理的账单数据

### this_month_bills.json
本月提取的账单数据

## 📞 支持

如有问题，请查看：
1. `error_log.json` - 错误日志
2. `bill_summary.txt` - 最新报告
3. `OPENCLAW_INTEGRATION.md` - OpenClaw 集成详细文档
4. `TICKTICK_GUIDE.md` - TickTick 集成指南

## 📄 License

本系统仅供个人使用，不得用于商业用途。

## 🙏 致谢

感谢使用本系统！如有任何问题或建议，欢迎反馈。
