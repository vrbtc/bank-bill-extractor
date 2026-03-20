# OpenClaw 银行账单集成指南

## 📋 推荐方案：读取本地 JSON 文件

### 为什么选择本地文件方案？

✅ **简单快速** - 不需要启动额外服务  
✅ **稳定可靠** - 不依赖 API 服务器  
✅ **离线可用** - 数据已缓存到本地  
✅ **易于集成** - OpenClaw 直接读取 JSON  
✅ **性能优秀** - 毫秒级响应  

---

## 🚀 快速开始

### 1. 确保账单数据已生成

运行提取脚本（每天一次）：
```bash
cd "k:\Trae CN\R BANK"
python this_month_bills.py
```

这会生成 `this_month_bills.json` 文件。

### 2. OpenClaw 调用示例

#### 方式 A：Python 脚本调用（推荐）

在你的 OpenClaw 任务中：

```python
# OpenClaw 任务：银行账单查询
from openclaw_bill_reader import get_upcoming_bills, check_urgent_bills, send_notification

def main():
    # 获取所有未来账单
    result = get_upcoming_bills(days=None)
    
    if result['success']:
        print(f"待还款总额：¥{result['total_amount']:,.2f}")
        print(f"银行数量：{result['bank_count']}")
        
        for bank_name, info in result['banks']:
            print(f"{bank_name}: ¥{info['total_amount']:,.2f} - {info['earliest_due_date']} ({info['days_until']}天后)")
    
    # 检查紧急账单
    urgent = check_urgent_bills()
    if urgent:
        print("\n⚠️ 紧急账单：")
        for bill in urgent:
            print(f"  {bill['bank']}: ¥{bill['amount']:,.2f} ({bill['days']}天后)")
        
        # 发送通知
        send_notification()

if __name__ == "__main__":
    main()
```

#### 方式 B：直接读取 JSON

```python
import json

# 读取账单文件
with open(r'k:\Trae CN\R BANK\this_month_bills.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

# 解析数据
print(f"生成时间：{data['generated_at']}")
print(f"待还款总额：¥{data['upcoming_total']:,.2f}")
print(f"账单数量：{data['total_bills']}")

for bill in data['bills']:
    bank = bill['bank_name']
    amount = bill['amounts'][0]['value'] if bill['amounts'] else 0
    due_date = bill['due_dates'][0] if bill['due_dates'] else '未知'
    print(f"{bank}: ¥{amount:,.2f} - {due_date}")
```

---

## 📁 文件说明

### 核心文件

1. **`this_month_bills.py`** - 账单提取主程序
   - 登录邮箱提取所有账单
   - 生成 JSON 数据文件
   - 运行时间：约 2-5 秒

2. **`this_month_bills.json`** - 账单数据文件
   - 包含所有提取的账单
   - JSON 格式，易于解析
   - 自动覆盖更新

3. **`openclaw_bill_reader.py`** - OpenClaw 读取模块
   - 提供简单的 API 接口
   - 包含错误处理
   - 支持紧急账单检测

### 配置文件

- **`bill_data_history.json`** - 历史数据备份
- **`bill_summary.txt`** - 文本格式报告

---

## 🔧 OpenClaw 集成方案

### 方案 1：定时任务（推荐）

创建定时任务，每天早上 9 点自动检查：

```python
# openclaw_daily_check.py
from openclaw_bill_reader import get_upcoming_bills, check_urgent_bills, send_notification
from apscheduler.schedulers.blocking import BlockingScheduler
from datetime import datetime

def daily_bill_check():
    """每天早上 9 点执行"""
    print(f"\n[{datetime.now()}] 开始检查账单...")
    
    # 先刷新数据
    import subprocess
    subprocess.run(['python', 'this_month_bills.py'], cwd=r'k:\Trae CN\R BANK')
    
    # 检查紧急账单
    urgent = check_urgent_bills()
    
    if urgent:
        message = "⚠️ 紧急还款提醒\n\n"
        for bill in urgent:
            message += f"{bill['bank']}: ¥{bill['amount']:,.2f} ({bill['days']}天后)\n"
        
        message += f"\n总计：¥{sum(b['amount'] for b in urgent):,.2f}"
        
        # TODO: 调用通知服务
        print(message)
        # send_wechat(message)  # 微信
        # send_dingtalk(message) # 钉钉
        # send_email(message)    # 邮件
    else:
        print("✓ 无紧急账单")

# 创建调度器
scheduler = BlockingScheduler()
scheduler.add_job(daily_bill_check, 'cron', hour=9, minute=0)

print("定时任务已启动，每天 9:00 检查账单")
scheduler.start()
```

### 方案 2：按需查询

在 OpenClaw 工作流中直接调用：

```python
# openclaw_workflow.py
from openclaw_bill_reader import get_upcoming_bills

def query_bills():
    """查询账单并返回结果"""
    result = get_upcoming_bills(days=15)
    
    if not result['success']:
        return {'error': result['error']}
    
    # 格式化结果
    output = {
        'timestamp': result['timestamp'],
        'total': result['total_amount'],
        'banks': []
    }
    
    for bank_name, info in result['banks']:
        output['banks'].append({
            'name': bank_name,
            'amount': info['total_amount'],
            'due_date': info['earliest_due_date'],
            'days': info['days_until']
        })
    
    return output

# 执行查询
result = query_bills()
print(result)
```

### 方案 3：命令行调用

在 OpenClaw 的 Shell 节点中：

```bash
# 查询 15 天内账单
cd "k:\Trae CN\R BANK"
python openclaw_bill_reader.py
```

---

## 📊 数据格式

### JSON 文件结构

```json
{
  "generated_at": "2026-03-20 13:41:35",
  "total_bills": 12,
  "upcoming_total": 4132.98,
  "bills": [
    {
      "subject": "招商银行信用卡电子账单",
      "date": "Thu, 19 Mar 2026 12:13:53 +0800 (CST)",
      "amounts": [
        {
          "value": 1244.68,
          "currency": "CNY"
        }
      ],
      "due_dates": [
        "2026-04-06"
      ],
      "bank_name": "招商银行"
    }
  ]
}
```

### openclaw_bill_reader 返回格式

```python
{
    'success': True,
    'timestamp': '2026-03-20 13:49:52',
    'total_amount': 4132.98,
    'bank_count': 4,
    'banks': [
        ('浦发银行', {
            'total_amount': 385.88,
            'earliest_due_date': '2026/03/24',
            'days_until': 3,
            'bills': [...]
        }),
        ...
    ]
}
```

---

## 🔔 通知集成

### 微信通知（Server 酱）

```python
def send_wechat(message):
    """发送微信通知"""
    import requests
    
    send_key = 'YOUR_SEND_KEY'  # 替换为你的 Server 酱 KEY
    url = f'http://sc.ftqq.com/{send_key}.send'
    data = {
        'text': '银行账单还款提醒',
        'desp': message
    }
    requests.post(url, data=data)
```

### 钉钉通知

```python
def send_dingtalk(message):
    """发送钉钉通知"""
    import requests
    import json
    
    webhook = 'YOUR_DINGTALK_WEBHOOK'  # 替换为你的钉钉机器人 webhook
    
    data = {
        "msgtype": "text",
        "text": {
            "content": message
        }
    }
    
    headers = {'Content-Type': 'application/json'}
    response = requests.post(webhook, headers=headers, data=json.dumps(data))
    return response.json()
```

### 邮件通知

```python
def send_email(message):
    """发送邮件通知"""
    import smtplib
    from email.mime.text import MIMEText
    
    msg = MIMEText(message)
    msg['Subject'] = '银行账单还款提醒'
    msg['From'] = 'rrking@aliyun.com'
    msg['To'] = 'rrking@aliyun.com'
    
    # 配置 SMTP
    server = smtplib.SMTP_SSL('smtp.aliyun.com', 465)
    server.login('rrking@aliyun.com', 'Aa2599589')
    server.send_message(msg)
    server.quit()
```

---

## ⚠️ 错误处理

### 常见问题

1. **文件不存在**
   ```python
   result = get_upcoming_bills()
   if not result['success']:
       print(f"错误：{result['error']}")
       # 运行提取脚本
       import subprocess
       subprocess.run(['python', 'this_month_bills.py'])
   ```

2. **数据过期**
   ```python
   from datetime import datetime, timedelta
   
   result = load_bills()
   if result['success']:
       file_time = datetime.fromtimestamp(
           os.path.getmtime(BILL_FILE)
       )
       if datetime.now() - file_time > timedelta(days=1):
           print("数据可能过期，建议刷新")
   ```

3. **解析错误**
   ```python
   try:
       data = json.load(open(BILL_FILE, 'r', encoding='utf-8'))
   except json.JSONDecodeError:
       print("JSON 文件损坏，重新生成")
       subprocess.run(['python', 'this_month_bills.py'])
   ```

---

## 📝 完整示例

### OpenClaw 完整任务脚本

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
OpenClaw 银行账单管理任务
- 每天自动检查账单
- 发送还款提醒
- 记录历史数据
"""

import sys
import json
from datetime import datetime
from pathlib import Path

# 添加路径
sys.path.insert(0, r'k:\Trae CN\R BANK')

from openclaw_bill_reader import (
    get_upcoming_bills,
    check_urgent_bills,
    send_notification,
    load_bills
)

def main():
    print("="*80)
    print("OpenClaw 银行账单管理")
    print("="*80)
    print(f"执行时间：{datetime.now()}")
    print()
    
    # 1. 加载数据
    print("[1] 加载账单数据...")
    result = load_bills()
    
    if not result['success']:
        print(f"    ❌ {result['error']}")
        print("    尝试重新生成...")
        
        # 运行提取脚本
        import subprocess
        subprocess.run(['python', 'this_month_bills.py'])
        
        # 重新加载
        result = load_bills()
        if not result['success']:
            print(f"    ❌ 仍然失败：{result['error']}")
            return
    
    print(f"    ✓ 加载成功：{result['file_path']}")
    
    # 2. 检查紧急账单
    print("\n[2] 检查紧急账单...")
    urgent = check_urgent_bills()
    
    if urgent:
        print(f"    ⚠️ 发现 {len(urgent)} 个紧急账单")
        for bill in urgent:
            print(f"       {bill['bank']}: ¥{bill['amount']:,.2f} ({bill['days']}天后)")
        
        # 3. 发送通知
        print("\n[3] 发送通知...")
        message = send_notification()
        if message:
            print("    ✓ 通知已发送")
    else:
        print("    ✓ 无紧急账单")
    
    # 4. 显示汇总
    print("\n[4] 账单汇总")
    all_bills = get_upcoming_bills(days=None)
    
    if all_bills['success']:
        print(f"    待还款总额：¥{all_bills['total_amount']:,.2f}")
        print(f"    银行数量：{all_bills['bank_count']}")
        
        for bank_name, info in all_bills['banks'][:5]:  # 只显示前 5 个
            print(f"      {bank_name}: ¥{info['total_amount']:,.2f}")
    
    print("\n" + "="*80)
    print("任务完成")
    print("="*80)

if __name__ == "__main__":
    main()
```

---

## 🎯 总结

**推荐方案：本地 JSON 文件 + 定时刷新**

1. **日常使用**：OpenClaw 读取 `this_month_bills.json`
2. **数据刷新**：定时运行 `this_month_bills.py`（每天一次）
3. **紧急提醒**：使用 `check_urgent_bills()` 检测并通知
4. **灵活集成**：提供多种调用方式（Python、命令行、API）

这种方案简单、可靠、易于维护，非常适合 OpenClaw 集成！
