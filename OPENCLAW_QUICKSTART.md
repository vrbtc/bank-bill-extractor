# 🤖 OpenClaw 银行账单系统 - 完整配置

## 📁 需要导入的文件

将以下文件放到你的 OpenClaw 可以访问的目录：

```
k:\Trae CN\R BANK\
├── openclaw_bill_reader.py    ← 核心读取模块（必须）
└── this_month_bills.json      ← 账单数据（自动更新）
```

---

## 📋 给 OpenClaw 的提示词

```python
# 任务：查询银行账单还款信息
# 调用模块：openclaw_bill_reader

from openclaw_bill_reader import get_upcoming_bills, check_urgent_bills

# 方法 1：获取所有未来账单
result = get_upcoming_bills(days=None)

# 方法 2：获取 15 天内账单
result = get_upcoming_bills(days=15)

# 方法 3：检查 3 天内紧急账单
urgent = check_urgent_bills()

# 返回格式示例：
{
    'success': True,
    'timestamp': '2026-03-20 13:49:52',
    'total_amount': 15890.11,      # 总金额
    'bank_count': 5,               # 银行数量
    'banks': [                      # 账单列表（按到期日排序）
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

## 🔧 完整代码示例

### 示例 1：查询并显示账单

```python
from openclaw_bill_reader import get_upcoming_bills

def query_bills():
    result = get_upcoming_bills(days=15)
    
    if result['success']:
        print(f"待还款总额：¥{result['total_amount']:,.2f}")
        print(f"银行数量：{result['bank_count']}")
        print()
        
        for bank, info in result['banks']:
            status = "⚠️ 紧急" if info['days_until'] <= 3 else ""
            print(f"{bank}: ¥{info['total_amount']:,.2f} | 到期: {info['earliest_due_date']} | 剩余 {info['days_until']} 天 {status}")
    else:
        print(f"错误：{result['error']}")

query_bills()
```

### 示例 2：检查紧急账单并通知

```python
from openclaw_bill_reader import check_urgent_bills

def check_and_notify():
    urgent = check_urgent_bills()
    
    if urgent:
        message = "⚠️ 紧急还款提醒\n\n"
        for bill in urgent:
            message += f"• {bill['bank']}: ¥{bill['amount']:,.2f} ({bill['days']}天后)\n"
        
        message += f"\n总计：¥{sum(b['amount'] for b in urgent):,.2f}"
        
        # 发送通知（这里添加你的通知逻辑）
        print(message)
        # send_wechat(message)  # 微信
        # send_dingtalk(message) # 钉钉
    else:
        print("✓ 无紧急账单")

check_and_notify()
```

### 示例 3：完整工作流

```python
from openclaw_bill_reader import get_upcoming_bills, check_urgent_bills

def main():
    print("="*60)
    print("银行账单查询")
    print("="*60)
    
    # 1. 检查紧急账单
    urgent = check_urgent_bills()
    if urgent:
        print("\n⚠️ 紧急账单（3天内）：")
        for bill in urgent:
            print(f"  • {bill['bank']}: ¥{bill['amount']:,.2f}")
    
    # 2. 显示所有未来账单
    result = get_upcoming_bills(days=None)
    if result['success']:
        print(f"\n待还款总额：¥{result['total_amount']:,.2f}")
        print(f"银行数量：{result['bank_count']}")
        
        print("\n账单明细：")
        for bank, info in result['banks']:
            print(f"  {bank}: ¥{info['total_amount']:,.2f} ({info['earliest_due_date']}, {info['days_until']}天后)")
    
    print("="*60)

main()
```

---

## ⚙️ 数据刷新

### 自动刷新（推荐）

每天自动运行一次提取脚本：

```bash
# Windows 任务计划程序
# 或添加到你的启动脚本
python "k:\Trae CN\R BANK\this_month_bills.py"
```

### 手动刷新

```python
import subprocess
subprocess.run(['python', 'this_month_bills.py'], cwd=r'k:\Trae CN\R BANK')
```

---

## 📊 当前数据状态

最后更新：2026-03-20 13:41:35

| 银行 | 金额 | 还款日 | 剩余天数 |
|------|------|--------|----------|
| 浦发银行 | ¥385.88 | 2026-03-24 | 3天 ⚠️ |
| 邮储银行 | ¥796.89 | 2026-03-26 | 5天 |
| 招商银行 | ¥10,038.99 | 2026-03-28 | 7天 |
| 兴业银行 | ¥116.88 | 2026-03-30 | 9天 |
| 广发银行 | ¥4,551.47 | 2026-04-06 | 16天 |

**总计：¥15,890.11**

---

## ❓ 常见问题

### Q: 文件路径怎么设置？
A: 在代码中修改 `BILL_FILE` 变量：
```python
BILL_FILE = Path(r'k:\Trae CN\R BANK\this_month_bills.json')
```

### Q: 如何定时刷新数据？
A: 使用系统定时任务或第三方调度库（如 APScheduler）

### Q: 需要安装什么依赖？
A: 只需要 Python 标准库（json, datetime, pathlib）
