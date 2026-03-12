# 📋 TickTick 滴答清单技能指南

_精简版 - 快速上手_

---

## 🔑 一、API 认证

**API Key**: `dp_5dd5bf5607374d03bf0856775b94592f`

**基础 URL**: `https://api.dida365.com/open/v1`

**请求头**:
```
Authorization: Bearer dp_5dd5bf5607374d03bf0856775b94592f
Content-Type: application/json
```

---

## 🚀 二、快速开始

### 1. 获取项目列表
```python
import requests

headers = {"Authorization": "Bearer dp_5dd5bf5607374d03bf0856775b94592f"}
projects = requests.get("https://api.dida365.com/open/v1/project", headers=headers).json()
```

### 2. 创建任务
```python
task = requests.post(
    "https://api.dida365.com/open/v1/task",
    headers=headers,
    json={
        "title": "任务标题",
        "content": "任务描述",
        "dueDate": "2026-03-15T01:00:00.000+0000",  # UTC 时间
        "priority": 3  # 0=无，1=低，3=中，5=高
    }
).json()
print(f"任务 ID: {task['id']}")
```

### 3. 完成任务
```python
requests.post(
    f"https://api.dida365.com/open/v1/task/{task_id}",
    headers=headers,
    json={"id": task_id, "status": 2}
)
```

---

## 📡 三、常用 API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/project` | GET | 获取项目列表 |
| `/project/inbox/data` | GET | 获取收件箱任务 |
| `/project/{id}/data` | GET | 获取项目任务 |
| `/task` | POST | 创建任务 |
| `/task/{id}` | POST | 更新任务 |
| `/task/{id}` | DELETE | 删除任务 |

---

## 📝 四、任务字段说明

### 必填字段
| 字段 | 类型 | 说明 |
|------|------|------|
| `title` | string | 任务标题 |

### 常用字段
| 字段 | 类型 | 说明 |
|------|------|------|
| `content` | string | 任务描述 |
| `dueDate` | string | 到期时间 (UTC 格式) |
| `timeZone` | string | 时区 (Asia/Shanghai) |
| `priority` | number | 优先级 (0/1/3/5) |
| `reminders` | array | 提醒时间 |

### 时间格式
```
北京时间 2026-03-15 09:00
= UTC 2026-03-15 01:00
= "2026-03-15T01:00:00.000+0000"
```

### 提醒格式
```json
"reminders": [
    "TRIGGER:-P1D",   // 提前 1 天
    "TRIGGER:-PT2H",  // 提前 2 小时
    "TRIGGER:-PT30M"  // 提前 30 分钟
]
```

---

## 💡 五、完整示例（信用卡还款）

```python
import requests
from datetime import datetime, timedelta

API_KEY = "dp_5dd5bf5607374d03bf0856775b94592f"
BASE_URL = "https://api.dida365.com/open/v1"
HEADERS = {"Authorization": f"Bearer {API_KEY}"}

def create_bill_task(bank, amount, due_date):
    """创建还款任务"""
    # 北京时间转 UTC
    bj_time = datetime.strptime(due_date, "%Y-%m-%d")
    utc_time = bj_time - timedelta(hours=8)
    utc_str = utc_time.strftime("%Y-%m-%dT%H:%M:%S.000+0000")
    
    # 设置优先级
    days = (bj_time - datetime.now()).days
    priority = 5 if days <= 3 else 3 if days <= 7 else 1
    
    task = {
        "title": f"💳 {bank}信用卡还款",
        "content": f"金额：¥{amount:,.2f}",
        "dueDate": utc_str,
        "timeZone": "Asia/Shanghai",
        "isAllDay": False,
        "priority": priority,
        "reminders": ["TRIGGER:-P1D"]
    }
    
    response = requests.post(f"{BASE_URL}/task", headers=HEADERS, json=task)
    return response.json()

# 使用示例
task = create_bill_task("建设银行", 1138.05, "2026-03-15")
print(f"✅ 任务已创建：{task['id']}")
```

---

## ⚠️ 六、注意事项

1. **时间必须用 UTC**：北京时间 -8 小时
2. **收件箱单独获取**：`/project/inbox/data`
3. **优先级只有 4 档**：0、1、3、5
4. **完成状态 = 2**：`{"status": 2}`

---

## 🔗 七、参考链接

- 官方 API: https://github.com/ticktick/open
- 技能位置：`~/.openclaw/workspace/skills/ticktick/`
- 相关文档：`OPENCLAW_PROMPT.md` (账单获取)

---

_最后更新：2026-03-12_
_豆皮 🫘 整理`
