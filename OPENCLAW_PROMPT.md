# 🤖 OpenClaw 调用银行账单系统 - 完整提示词

## 📋 给 OpenClaw 的完整提示词

```markdown
你是一个银行账单查询助手，需要调用本地的银行账单 API 系统来获取用户的信用卡账单信息。

## 任务目标
1. 查询用户未来 15 天内需要还款的所有银行账单
2. 提取每家银行的还款金额、还款日期、剩余天数
3. 识别紧急账单（3 天内需要还款的）
4. 生成清晰的汇总报告

## API 调用方法

### 1. 获取待还款账单（主要接口）
```python
import requests

# 调用本地 API 获取待还款账单
response = requests.get('http://localhost:8765/api/upcoming', timeout=10)
data = response.json()

# 检查是否成功
if data.get('success'):
    # 获取账单数据
    upcoming_bills = data['upcoming_bills']
    total_amount = data['total_amount']
    bank_count = data['bank_count']
else:
    # 处理错误
    print(f"获取失败：{data.get('message', '未知错误')}")
```

### 2. 获取系统状态
```python
response = requests.get('http://localhost:8765/api/status')
status = response.json()
```

### 3. 触发新的提取（如果需要最新数据）
```python
response = requests.post('http://localhost:8765/api/extract')
result = response.json()
```

### 4. 获取文本报告
```python
response = requests.get('http://localhost:8765/api/report')
report_text = response.text
```

## 数据处理示例

### 完整调用代码
```python
import requests
from datetime import datetime

def query_bank_bills():
    """查询银行账单"""
    try:
        # 1. 获取待还款账单
        response = requests.get('http://localhost:8765/api/upcoming', timeout=10)
        
        if response.status_code != 200:
            return {
                'success': False,
                'error': f'API 返回错误状态码：{response.status_code}'
            }
        
        data = response.json()
        
        if not data.get('success'):
            return {
                'success': False,
                'error': data.get('message', '获取账单失败')
            }
        
        # 2. 解析数据
        upcoming_bills = data['upcoming_bills']
        total_amount = data['total_amount']
        bank_count = data['bank_count']
        
        # 3. 分类账单
        urgent_bills = []  # 3 天内
        soon_bills = []    # 7 天内
        normal_bills = []  # 15 天内
        
        for bank_name, info in upcoming_bills.items():
            if info['total_amount'] <= 0:
                continue
            
            days = info['earliest_due_date']['days_until']
            due_date = info['earliest_due_date']['date']
            amount = info['total_amount']
            
            bill = {
                'bank': bank_name,
                'amount': amount,
                'due_date': due_date,
                'days': days
            }
            
            if days <= 3:
                urgent_bills.append(bill)
            elif days <= 7:
                soon_bills.append(bill)
            else:
                normal_bills.append(bill)
        
        # 4. 生成报告
        report = {
            'success': True,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'summary': {
                'total_amount': total_amount,
                'bank_count': bank_count,
                'urgent_count': len(urgent_bills),
                'soon_count': len(soon_bills),
                'normal_count': len(normal_bills)
            },
            'urgent_bills': urgent_bills,
            'soon_bills': soon_bills,
            'normal_bills': normal_bills
        }
        
        return report
        
    except requests.exceptions.ConnectionError:
        return {
            'success': False,
            'error': '无法连接到账单 API 服务器，请确保 openclaw_api.py 正在运行'
        }
    except requests.exceptions.Timeout:
        return {
            'success': False,
            'error': 'API 请求超时'
        }
    except Exception as e:
        return {
            'success': False,
            'error': f'发生错误：{str(e)}'
        }

# 执行查询
result = query_bank_bills()

# 输出结果
if result['success']:
    print("="*80)
    print("银行账单查询结果")
    print("="*80)
    print(f"查询时间：{result['timestamp']}")
    print(f"待还款总额：¥{result['summary']['total_amount']:,.2f}")
    print(f"银行数量：{result['summary']['bank_count']}")
    print(f"紧急账单：{result['summary']['urgent_count']} 个")
    print(f"近期账单：{result['summary']['soon_count']} 个")
    print(f"普通账单：{result['summary']['normal_count']} 个")
    print()
    
    if result['urgent_bills']:
        print("⚠️⚠️⚠️ 紧急账单（3 天内）")
        print("-"*80)
        for bill in result['urgent_bills']:
            print(f"{bill['bank']}: ¥{bill['amount']:,.2f} | {bill['due_date']} ({bill['days']}天后)")
        print()
    
    if result['soon_bills']:
        print("⚠️ 近期账单（7 天内）")
        print("-"*80)
        for bill in result['soon_bills']:
            print(f"{bill['bank']}: ¥{bill['amount']:,.2f} | {bill['due_date']} ({bill['days']}天后)")
        print()
    
    if result['normal_bills']:
        print("普通账单（15 天内）")
        print("-"*80)
        for bill in result['normal_bills']:
            print(f"{bill['bank']}: ¥{bill['amount']:,.2f} | {bill['due_date']} ({bill['days']}天后)")
    
    print("="*80)
else:
    print(f"❌ 查询失败：{result['error']}")
```

## OpenClaw 配置示例

### 方式 1：Python 脚本调用
在你的 OpenClaw 脚本中直接调用：

```python
# OpenClaw 任务：银行账单查询
from bill_query import query_bank_bills

def main():
    # 查询账单
    result = query_bank_bills()
    
    if result['success']:
        # 处理结果
        send_notification(result)
    else:
        # 处理错误
        log_error(result['error'])

def send_notification(result):
    """发送通知"""
    # 这里可以集成邮件、微信、钉钉等通知方式
    pass
```

### 方式 2：HTTP 请求调用
使用 OpenClaw 的 HTTP 节点：

```yaml
# OpenClaw 工作流配置
nodes:
  - name: "查询账单"
    type: "http"
    config:
      url: "http://localhost:8765/api/upcoming"
      method: "GET"
      timeout: 10
    
  - name: "处理结果"
    type: "script"
    config:
      language: "python"
      code: |
        import json
        
        # 解析 API 响应
        data = json.loads(input['response'])
        
        if data['success']:
            total = data['total_amount']
            banks = data['bank_count']
            
            # 生成报告
            report = f"待还款总额：¥{total:,.2f}\n银行数量：{banks}"
            
            # 检查紧急账单
            urgent = []
            for bank, info in data['upcoming_bills'].items():
                if info['total_amount'] > 0:
                    days = info['earliest_due_date']['days_until']
                    if days <= 3:
                        urgent.append(f"{bank}: ¥{info['total_amount']:,.2f} ({days}天)")
            
            if urgent:
                report += f"\n\n⚠️ 紧急账单：\n" + "\n".join(urgent)
            
            output['report'] = report
        else:
            output['error'] = data.get('message', '查询失败')
```

### 方式 3：定时任务配置
```python
# OpenClaw 定时任务：每天早上 9 点查询账单
from apscheduler.schedulers.blocking import BlockingScheduler
import requests
import json

scheduler = BlockingScheduler()

@scheduler.scheduled_job('cron', hour=9, minute=0)
def daily_bill_check():
    """每天上午 9 点检查账单"""
    try:
        # 调用 API
        response = requests.get('http://localhost:8765/api/upcoming', timeout=10)
        data = response.json()
        
        if data['success']:
            # 检查是否有紧急账单
            urgent_bills = []
            for bank, info in data['upcoming_bills'].items():
                if info['total_amount'] > 0:
                    days = info['earliest_due_date']['days_until']
                    if days <= 3:
                        urgent_bills.append({
                            'bank': bank,
                            'amount': info['total_amount'],
                            'days': days
                        })
            
            # 发送通知
            if urgent_bills:
                message = "⚠️ 紧急还款提醒\n\n"
                for bill in urgent_bills:
                    message += f"{bill['bank']}: ¥{bill['amount']:,.2f} ({bill['days']}天后)\n"
                
                message += f"\n总计：¥{data['total_amount']:,.2f}"
                
                # TODO: 调用通知服务
                print(message)
                send_wechat(message)  # 微信通知
                send_email(message)   # 邮件通知
            else:
                print(f"✓ 账单检查完成，无紧急还款。总计：¥{data['total_amount']:,.2f}")
        else:
            print(f"❌ 查询失败：{data.get('message')}")
    
    except Exception as e:
        print(f"❌ 执行出错：{e}")
        # 发送错误通知
        send_error_notification(str(e))

def send_wechat(message):
    """发送微信通知（Server 酱）"""
    send_key = 'YOUR_SEND_KEY'
    url = f'http://sc.ftqq.com/{send_key}.send'
    data = {'text': '银行账单提醒', 'desp': message}
    requests.post(url, data=data)

def send_email(message):
    """发送邮件通知"""
    import smtplib
    from email.mime.text import MIMEText
    
    msg = MIMEText(message)
    msg['Subject'] = '银行账单还款提醒'
    msg['From'] = 'your_email@aliyun.com'
    msg['To'] = 'your_email@aliyun.com'
    
    server = smtplib.SMTP_SSL('smtp.aliyun.com', 465)
    server.login('your_email@aliyun.com', 'your_password')
    server.send_message(msg)
    server.quit()

def send_error_notification(error_msg):
    """发送错误通知"""
    message = f"银行账单系统错误\n\n{error_msg}"
    # 发送错误通知
    send_wechat(message)

# 启动调度器
scheduler.start()
```

## 错误处理

### 常见错误及解决方案

1. **ConnectionError**
   ```python
   try:
       response = requests.get('http://localhost:8765/api/upcoming')
   except requests.exceptions.ConnectionError:
       print("错误：无法连接到 API 服务器")
       print("解决方案：运行 python openclaw_api.py 启动服务器")
   ```

2. **Timeout**
   ```python
   try:
       response = requests.get('http://localhost:8765/api/upcoming', timeout=10)
   except requests.exceptions.Timeout:
       print("错误：请求超时")
       print("解决方案：检查 API 服务器是否正常运行")
   ```

3. **API 返回错误**
   ```python
   response = requests.get('http://localhost:8765/api/upcoming')
   data = response.json()
   
   if not data.get('success'):
       print(f"错误：{data.get('message')}")
       # 查看详细错误
       error_response = requests.get('http://localhost:8765/api/errors')
       errors = error_response.json()
       print(f"错误日志：{errors}")
   ```

## 测试命令

### 1. 测试 API 连接
```bash
curl http://localhost:8765/api/status
```

### 2. 测试账单查询
```bash
curl http://localhost:8765/api/upcoming
```

### 3. 测试文本报告
```bash
curl http://localhost:8765/api/report
```

### 4. 触发新的提取
```bash
curl -X POST http://localhost:8765/api/extract
```

## 快速测试脚本

保存为 `test_openclaw.py` 并运行：

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
OpenClaw 银行账单查询测试脚本
"""

import requests
import json

def test_api():
    print("="*80)
    print("OpenClaw 银行账单 API 测试")
    print("="*80)
    
    # 测试 1：获取状态
    print("\n[测试 1] 获取系统状态...")
    try:
        response = requests.get('http://localhost:8765/api/status')
        print(f"状态码：{response.status_code}")
        print(f"响应：{json.dumps(response.json(), ensure_ascii=False, indent=2)}")
    except Exception as e:
        print(f"❌ 失败：{e}")
    
    # 测试 2：获取待还款账单
    print("\n[测试 2] 获取待还款账单...")
    try:
        response = requests.get('http://localhost:8765/api/upcoming')
        data = response.json()
        print(f"状态码：{response.status_code}")
        
        if data['success']:
            print(f"待还款总额：¥{data['total_amount']:,.2f}")
            print(f"银行数量：{data['bank_count']}")
            
            for bank, info in data['upcoming_bills'].items():
                if info['total_amount'] > 0:
                    days = info['earliest_due_date']['days_until']
                    print(f"  - {bank}: ¥{info['total_amount']:,.2f} ({days}天后)")
        else:
            print(f"❌ 失败：{data.get('message')}")
    except Exception as e:
        print(f"❌ 失败：{e}")
    
    # 测试 3：获取文本报告
    print("\n[测试 3] 获取文本报告...")
    try:
        response = requests.get('http://localhost:8765/api/report')
        print(response.text)
    except Exception as e:
        print(f"❌ 失败：{e}")
    
    print("\n" + "="*80)
    print("测试完成！")
    print("="*80)

if __name__ == "__main__":
    test_api()
```

运行测试：
```bash
python test_openclaw.py
```

## 预期输出示例

```
================================================================================
OpenClaw 银行账单 API 测试
================================================================================

[测试 1] 获取系统状态...
状态码：200
响应：{
  "status": "ready",
  "last_check": "2026-03-12 00:25:28",
  "total_checks": 1,
  "upcoming_banks": 4,
  "total_amount": 15512.79,
  "timestamp": "2026-03-12 00:26:00"
}

[测试 2] 获取待还款账单...
状态码：200
待还款总额：¥15,512.79
银行数量：4
  - 建设银行：¥1,138.05 (2 天后)
  - 交通银行：¥4,169.77 (2 天后)
  - 民生银行：¥9,901.28 (6 天后)
  - 邮储银行：¥303.69 (13 天后)

[测试 3] 获取文本报告...
================================================================================
银行账单汇总报告
================================================================================
生成时间：2026-03-12 00:26:00
...

================================================================================
测试完成！
================================================================================
```
