# 银行账单自动提取系统 - OpenClaw 集成指南

## 📋 系统概述

本系统会自动从您的阿里云邮箱提取银行账单，并提供 API 接口供 OpenClaw 调用。

## 🚀 快速开始

### 1. 启动 API 服务器

```bash
# 启动服务器（默认端口 8765）
python openclaw_api.py

# 或者只运行一次提取
python openclaw_api.py --once
```

### 2. OpenClaw 集成

#### 方法一：HTTP API 调用（推荐）

在 OpenClaw 中配置定时任务，定期调用 API：

```python
# OpenClaw 任务示例
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

#### 方法二：读取 JSON 文件

OpenClaw 可以直接读取生成的 JSON 文件：

```python
# 读取账单数据
import json

with open('bill_data_history.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

# 获取待还款账单
upcoming = data['upcoming_bills']
```

#### 方法三：读取文本报告

```python
# 读取文本报告
with open('bill_summary.txt', 'r', encoding='utf-8') as f:
    report = f.read()

print(report)
```

## 📡 API 端点

### GET /api/status
获取系统状态

```bash
curl http://localhost:8765/api/status
```

响应示例：
```json
{
  "status": "ready",
  "last_check": "2026-03-12 00:19:45",
  "total_checks": 15,
  "upcoming_banks": 4,
  "total_amount": 15512.79,
  "timestamp": "2026-03-12 00:20:00"
}
```

### GET /api/bills
获取最新账单数据

```bash
curl http://localhost:8765/api/bills
```

### GET /api/upcoming
获取待还款账单

```bash
curl http://localhost:8765/api/upcoming
```

响应示例：
```json
{
  "success": true,
  "upcoming_bills": {
    "建设银行": {
      "total_amount": 1138.05,
      "earliest_due_date": {
        "date": "2026-03-15",
        "days_until": 2
      }
    },
    "交通银行": {
      "total_amount": 4169.77,
      "earliest_due_date": {
        "date": "2026-03-15",
        "days_until": 2
      }
    }
  },
  "total_amount": 15512.79,
  "bank_count": 4
}
```

### GET /api/report
获取文本格式报告

```bash
curl http://localhost:8765/api/report
```

### POST /api/extract
触发账单提取

```bash
curl -X POST http://localhost:8765/api/extract
```

### GET /api/errors
获取错误日志

```bash
curl http://localhost:8765/api/errors
```

## ⏰ OpenClaw 定时任务配置

### 方案一：使用 Cron（Linux/Mac）

```bash
# 编辑 crontab
crontab -e

# 添加每天上午 9 点执行的任务
0 9 * * * cd "/k:/Trae CN/R BANK" && python openclaw_api.py --once >> bill_cron.log 2>&1
```

### 方案二：使用 Windows 任务计划程序

1. 打开"任务计划程序"
2. 创建基本任务
3. 设置触发器（每天 9:00）
4. 设置操作：
   - 程序：`python.exe`
   - 参数：`openclaw_api.py --once`
   - 起始于：`k:\Trae CN\R BANK`

### 方案三：在 OpenClaw 中配置

```python
# OpenClaw 配置示例
from apscheduler.schedulers.blocking import BlockingScheduler
import requests

scheduler = BlockingScheduler()

@scheduler.scheduled_job('cron', hour=9, minute=0)
def daily_bill_check():
    """每天上午 9 点检查账单"""
    try:
        response = requests.post('http://localhost:8765/api/extract')
        result = response.json()
        
        if result['success']:
            if result['has_new_emails']:
                print(f"发现新邮件，共 {result['total_bills']} 封账单")
                
                # 发送通知
                send_notification(result)
            else:
                print("没有新邮件")
        else:
            print(f"提取失败：{result.get('error')}")
    
    except Exception as e:
        print(f"执行出错：{e}")

def send_notification(result):
    """发送通知（可以集成邮件、微信等）"""
    # TODO: 实现通知逻辑
    pass

scheduler.start()
```

## 🔔 错误通知配置

### 方案一：邮件通知

在 `openclaw_api.py` 的 `send_notification` 方法中添加：

```python
import smtplib
from email.mime.text import MIMEText

def send_email_notification(error_msg):
    """发送邮件通知"""
    msg = MIMEText(f"账单提取出错：{error_msg}")
    msg['Subject'] = '银行账单提取错误通知'
    msg['From'] = 'your_email@aliyun.com'
    msg['To'] = 'your_email@aliyun.com'
    
    server = smtplib.SMTP_SSL('smtp.aliyun.com', 465)
    server.login('your_email@aliyun.com', 'your_password')
    server.send_message(msg)
    server.quit()
```

### 方案二：微信通知

可以使用 Server 酱、PushPlus 等服务：

```python
import requests

def send_wechat_notification(error_msg):
    """发送微信通知（使用 Server 酱）"""
    send_key = 'YOUR_SEND_KEY'
    url = f'http://sc.ftqq.com/{send_key}.send'
    
    data = {
        'text': '银行账单提取错误',
        'desp': f"错误信息：{error_msg}"
    }
    
    requests.post(url, data=data)
```

### 方案三：钉钉通知

```python
import requests

def send_dingtalk_notification(error_msg):
    """发送钉钉通知"""
    webhook = 'YOUR_DINGTALK_WEBHOOK'
    
    data = {
        'msgtype': 'text',
        'text': {
            'content': f"银行账单提取错误\n{error_msg}"
        }
    }
    
    requests.post(webhook, json=data)
```

## 📊 数据文件说明

### bill_data_history.json
存储所有历史账单数据

```json
{
  "last_check_time": "2026-03-12 00:19:45",
  "last_email_count": 23,
  "last_email_ids": [...],
  "total_checks": 15,
  "bills_history": [
    {
      "check_time": "2026-03-12 00:19:45",
      "total_bills": 10,
      "bills": [...]
    }
  ],
  "upcoming_bills": {...}
}
```

### bill_summary.txt
文本格式的汇总报告（可直接阅读）

### error_log.json
错误日志文件

## 🛠️ 故障排查

### 1. 检查 API 服务器是否运行

```bash
curl http://localhost:8765/api/status
```

### 2. 查看错误日志

```bash
cat error_log.json
```

### 3. 手动运行一次提取

```bash
python bill_extractor_main.py
```

### 4. 检查邮箱连接

确保阿里云邮箱的 IMAP 服务已开启，密码正确。

## 📝 注意事项

1. **首次运行**：会初始化所有数据，之后每次都会检测新邮件
2. **新邮件判断**：通过邮件 ID 对比，不会重复处理
3. **数据保留**：保留最近 100 次提取记录
4. **错误处理**：出错时会记录到 error_log.json
5. **端口占用**：如果 8765 端口被占用，可以修改 openclaw_api.py 中的端口号

## 🎯 最佳实践

1. **每天定时执行**：建议设置在每天上午 9 点
2. **通知阈值**：可以设置金额阈值，超过才通知
3. **备份数据**：定期备份 bill_data_history.json
4. **监控日志**：定期检查 error_log.json

## 📞 支持

如有问题，请查看错误日志或联系技术支持。
