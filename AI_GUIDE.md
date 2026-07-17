# 🏦 银行账单查询技能 - 大模型对接指南

## 一、这是什么

这是一个本地运行的银行信用卡账单查询系统，功能包括：
- 从阿里云邮箱自动提取多家银行的信用卡账单（金额、还款日）
- 查询待还款账单、紧急账单提醒
- 同步到滴答清单（TickTick）自动创建还款任务
- 支持 Windows 计划任务每日自动运行

---

## 二、文件结构

```
R BANK/
├── bill_skill.py           ← 主入口（CLI + Python API）
├── this_month_bills.py     ← 账单提取引擎（从邮箱获取）
├── bank_extractors.py      ← 9家银行专用提取器
├── email_client.py         ← IMAP邮箱客户端
├── email_decoder.py        ← 邮件解码器
├── ticktick_sync.py        ← 滴答清单同步模块
├── config.json             ← 邮箱IMAP配置（敏感信息）
├── this_month_bills.json   ← 缓存的账单数据
├── daily_run.py            ← 每日自动运行脚本
├── daily_run.bat           ← 批处理启动器
├── setup_task.py           ← 一键注册Windows计划任务
├── BankBillDaily_task.xml  ← 计划任务XML定义
├── requirements.txt        ← Python依赖
└── daily_run.log           ← 运行日志
```

---

## 三、环境准备

### 1. 安装 Python 依赖
```bash
pip install beautifulsoup4 lxml requests
```

### 2. 确认配置文件
`config.json` 内容格式：
```json
{
  "email": "xxx@aliyun.com",
  "password": "邮箱密码",
  "imap_server": "imap.aliyun.com",
  "imap_port": 993
}
```

### 3. 如果路径变了
需要修改 `BankBillDaily_task.xml` 中的两处路径：
- `<Arguments>/c "新路径\daily_run.bat"</Arguments>`
- `<WorkingDirectory>新路径</WorkingDirectory>`

---

## 四、CLI 命令速查

所有命令在 `R BANK` 目录下运行：

### 查询账单
```bash
# 查询未来15天待还款（默认）
python bill_skill.py query

# 查询未来30天
python bill_skill.py query --days 30

# 查询所有未来账单
python bill_skill.py query --days 999

# 只查某家银行
python bill_skill.py query --bank 招商

# JSON格式输出
python bill_skill.py query --format json
```

### 紧急账单
```bash
# 检查3天内到期的紧急账单
python bill_skill.py urgent

# 检查7天内
python bill_skill.py urgent --days 7
```

### 刷新数据（从邮箱重新获取）
```bash
python bill_skill.py refresh --force
```

### 生成报告
```bash
# 未来15天报告
python bill_skill.py report

# 未来30天报告
python bill_skill.py report --days 30
```

### 滴答清单同步
```bash
# 预览模式（不实际创建，先看看会创建什么）
python bill_skill.py sync --dry-run

# 实际同步到滴答清单
python bill_skill.py sync

# 清理滴答清单中的过期任务（还款日超过7天的）
python bill_skill.py cleanup
```

### 系统状态
```bash
python bill_skill.py status
```

---

## 五、Python API 调用

在 Python 代码中直接调用：

```python
from bill_skill import BillSkill

skill = BillSkill()

# 查询所有未来账单
result = skill.query()
# result = {
#   'success': True,
#   'total_amount': 45079.53,
#   'bank_count': 6,
#   'banks': [
#     {'name': '浦发银行', 'amount': 11840.13, 'due_date': '2026-05-24', 'days_until': 0},
#     ...
#   ]
# }

# 查询未来7天
result = skill.query(days=7)

# 检查紧急账单（3天内）
urgent = skill.check_urgent(days=3)
# urgent = [
#   {'bank': '浦发银行', 'amount': 11840.13, 'due_date': '2026-05-24', 'days': 0}
# ]

# 刷新数据
skill.refresh(force=True)

# 同步到滴答清单
result = skill.sync_to_ticktick()
# result = {
#   'success': True,
#   'total_created': 6,
#   'total_skipped': 0,
#   'created': [{'bank': '浦发银行', 'task_id': 'xxx', 'title': '💳 浦发银行信用卡还款 ¥11,840.13'}]
# }

# 预览同步（不实际创建）
result = skill.sync_to_ticktick(dry_run=True)

# 清理过期任务
result = skill.cleanup_ticktick()
```

---

## 六、滴答清单对接详解

### API 配置
滴答清单同步模块 `ticktick_sync.py` 内置了 API Key：
- **API Key**: `REDACTED_API_KEY`
- **Base URL**: `https://api.dida365.com/open/v1`

### 同步逻辑

1. **自动创建项目**：首次同步会在滴答清单中创建「信用卡还款」项目
2. **去重机制**：通过任务标题匹配，已存在的同名任务不会重复创建
3. **优先级自动设置**：
   - 3天内到期 → 高优先级(5) 🔴
   - 7天内到期 → 中优先级(3) 🟡
   - 其他 → 低优先级(1) 🟢
4. **自动提醒**：
   - 所有任务：提前1天提醒
   - 紧急任务(3天内)：额外提前2小时提醒
5. **任务标题格式**：`💳 {银行名}信用卡还款 ¥{金额}`
6. **任务内容**：包含还款金额、还款日、各子账单明细
7. **过期清理**：还款日超过7天的旧任务会被 `cleanup` 删除

### 滴答清单 API 速查

```python
from ticktick_sync import TickTickSync

sync = TickTickSync()

# 获取所有项目
projects = sync.get_projects()

# 查找或创建项目
project_id = sync.find_or_create_project("信用卡还款")

# 获取项目中的任务
tasks = sync.get_project_tasks(project_id)

# 同步账单
result = sync.sync_bills(bills_data, project_name="信用卡还款")

# 清理过期任务
result = sync.cleanup_old_tasks()
```

### 直接调用滴答清单 API

```python
import requests

API_KEY = "REDACTED_API_KEY"
BASE_URL = "https://api.dida365.com/open/v1"
HEADERS = {"Authorization": f"Bearer {API_KEY}"}

# 获取项目列表
requests.get(f"{BASE_URL}/project", headers=HEADERS).json()

# 获取项目任务
requests.get(f"{BASE_URL}/project/{project_id}/data", headers=HEADERS).json()

# 创建任务
requests.post(f"{BASE_URL}/task", headers={**HEADERS, "Content-Type": "application/json"}, json={
    "title": "任务标题",
    "content": "任务描述",
    "dueDate": "2026-05-31T01:00:00.000+0000",  # UTC时间！北京时间需-8小时
    "timeZone": "Asia/Shanghai",
    "priority": 3,  # 0=无, 1=低, 3=中, 5=高
    "reminders": ["TRIGGER:-P1D"]  # 提前1天提醒
}).json()

# 完成任务
requests.post(f"{BASE_URL}/task/{task_id}", headers={**HEADERS, "Content-Type": "application/json"}, json={
    "id": task_id, "status": 2  # 2=已完成
})

# 删除任务
requests.delete(f"{BASE_URL}/task/{task_id}", headers=HEADERS, params={"projectId": project_id})
```

---

## 七、每日自动运行

### 注册计划任务
```bash
# 方法1：Python脚本（会自动请求管理员权限）
python setup_task.py

# 方法2：直接用 schtasks（需管理员CMD）
schtasks /Create /TN "BankBillDaily" /XML "BankBillDaily_task.xml" /F
```

### 手动触发
```bash
schtasks /Run /TN "BankBillDaily"
```

### 查看日志
```bash
type daily_run.log
```

### 修改运行时间
```bash
schtasks /Change /TN "BankBillDaily" /ST 08:00
```

### 删除计划任务
```bash
schtasks /Delete /TN "BankBillDaily" /F
```

---

## 八、支持的银行

| 银行 | 提取器类 | 状态 |
|------|---------|------|
| 交通银行 | CommBankExtractor | ✅ |
| 招商银行 | CMBBankExtractor | ✅ |
| 建设银行 | CCBBankExtractor | ✅ |
| 浦发银行 | SPDBankExtractor | ✅ |
| 邮储银行 | PSBCBankExtractor | ✅ |
| 民生银行 | CMBCBankExtractor | ✅ |
| 广发银行 | GuangfaBankExtractor | ✅ |
| 平安银行 | PingAnBankExtractor | ✅ |
| 光大银行 | GuangDaBankExtractor | ✅ |
| 其他银行 | OtherBankExtractor | 通用匹配 |

---

## 九、⚠️ 注意事项

### 安全
1. **config.json 包含邮箱密码**，绝对不能上传到公开仓库或分享给他人
2. **ticktick_sync.py 包含滴答清单 API Key**，同样不能泄露
3. 所有数据仅存储在本地，不会上传外部服务器

### 运行
1. **必须联网**：需要连接邮箱IMAP服务器和滴答清单API
2. **邮箱IMAP需开启**：阿里云邮箱默认支持，其他邮箱需确认
3. **Python 版本**：3.7+，推荐 3.10+
4. **路径含空格**：当前路径 `K:\Trae CN\R BANK` 含空格，命令行中需用引号包裹

### 数据准确性
1. 账单金额以邮箱收到的银行账单邮件为准
2. 如果银行邮件格式变更，可能需要更新 `bank_extractors.py` 中对应的提取器
3. 信用额度 ≠ 账单金额，提取器已做区分处理
4. 广发/光大/平安银行的HTML格式特殊，有专用提取器处理

### 滴答清单同步
1. **时间必须用 UTC**：北京时间需减8小时
2. **优先级只有4档**：0、1、3、5
3. **去重基于标题**：如果手动改了滴答清单中的任务标题，下次同步会创建新任务
4. **API 限流**：滴答清单 API 有请求频率限制，不要频繁调用
5. **完成状态 = 2**：标记完成用 `{"status": 2}`

### 计划任务
1. **需要管理员权限**注册（setup_task.py 会自动请求提权）
2. 电脑关机时不会执行，开机后如果设置了 `StartWhenAvailable` 会补跑
3. 日志文件 `daily_run.log` 自动轮转（超过500行截断）

---

## 十、常见问题

**Q: 运行报错 "AuthenticationFailed"**
A: config.json 中的邮箱密码错误，或邮箱IMAP未开启

**Q: 某家银行金额提取不对**
A: 银行可能更新了邮件格式，需要更新 bank_extractors.py 中对应的提取器。可以用 `save_bank_html.py` 保存原始HTML分析格式

**Q: 滴答清单同步失败**
A: 检查网络连接，确认 API Key 有效（访问 https://api.dida365.com/open/v1/project 测试）

**Q: 计划任务没执行**
A: 用 `schtasks /Query /TN "BankBillDaily"` 检查任务状态，查看 `daily_run.log` 了解错误

**Q: 想添加新银行支持**
A: 在 bank_extractors.py 中新建一个继承 BaseBankExtractor 的类，实现 extract_amount 和 extract_due_date 方法，然后在 BankExtractorFactory._register_default_extractors 中注册
