# 🏦 银行账单自动提取系统

完全自动化的银行账单提取、分析和提醒系统，支持 OpenClaw 集成。

## 📁 文件说明

### 核心文件

1. **this_month_bills.py** - 账单提取核心逻辑
   - 从阿里云邮箱提取账单
   - 支持多家银行（交通、建设、民生、邮储、兴业等）
   - HTML 转 Markdown 技术
   - 多编码支持

2. **bill_storage.py** - 数据持久化存储
   - 保存历史账单数据
   - 新邮件检测
   - 生成文本报告

3. **bill_extractor_main.py** - 主程序
   - 整合提取和存储
   - 新邮件判断
   - 错误处理

4. **openclaw_api.py** - OpenClaw API 接口
   - REST API 服务
   - 支持 HTTP 调用
   - 错误通知接口

### 数据文件

- **bill_data_history.json** - 所有历史账单数据
- **bill_summary.txt** - 文本格式汇总报告
- **error_log.json** - 错误日志

### 文档

- **OPENCLAW_INTEGRATION.md** - OpenClaw 集成详细指南
- **README.md** - 本文件

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

### 方法 3：OpenClaw 调用

```python
import requests

# 获取待还款账单
response = requests.get('http://localhost:8765/api/upcoming')
data = response.json()

print(f"待还款总额：¥{data['total_amount']:,.2f}")
```

## 📊 支持的银行

已测试并完美支持：

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

## 🔧 配置

### 邮箱配置

在 `this_month_bills.py` 中修改：

```python
EMAIL_ADDRESS = "rrking@aliyun.com"
PASSWORD = "Aa2599589"
IMAP_SERVER = "imap.aliyun.com"
IMAP_PORT = 993
```

### API 端口配置

在 `openclaw_api.py` 中修改：

```python
run_server(port=8765)  # 修改端口号
```

## 📡 API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/status` | GET | 获取系统状态 |
| `/api/bills` | GET | 获取最新账单 |
| `/api/upcoming` | GET | 获取待还款账单 |
| `/api/report` | GET | 获取文本报告 |
| `/api/extract` | POST | 触发提取 |
| `/api/errors` | GET | 获取错误日志 |

### 使用示例

```bash
# 获取系统状态
curl http://localhost:8765/api/status

# 获取待还款账单
curl http://localhost:8765/api/upcoming

# 触发提取
curl -X POST http://localhost:8765/api/extract

# 获取文本报告
curl http://localhost:8765/api/report
```

## ⏰ 定时任务

### Windows 任务计划程序

1. 打开"任务计划程序"
2. 创建基本任务
3. 设置每天 9:00
4. 程序：`python.exe`
5. 参数：`bill_extractor_main.py`
6. 起始于：`k:\Trae CN\R BANK`

### Linux Cron

```bash
crontab -e
0 9 * * * cd "/path/to/bank" && python bill_extractor_main.py
```

## 🔔 错误通知

在 `openclaw_api.py` 的 `send_notification` 方法中集成通知：

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

## 📈 工作流程

```
1. 连接阿里云邮箱
   ↓
2. 获取邮件 ID 列表
   ↓
3. 对比是否有新邮件
   ├─ 没有新邮件 → 返回"无新邮件"
   └─ 有新邮件 → 继续
   ↓
4. 提取账单信息
   ├─ HTML 转 Markdown
   ├─ 识别银行
   ├─ 提取金额
   └─ 提取还款日
   ↓
5. 筛选未来 15 天待还款
   ↓
6. 保存数据到 JSON
   ↓
7. 生成文本报告
   ↓
8. 返回结果
```

## 🛠️ 故障排查

### 1. 连接邮箱失败

检查：
- 邮箱账号密码是否正确
- IMAP 服务是否开启
- 网络连接是否正常

### 2. 提取金额为 0

可能原因：
- 银行 HTML 模板更新
- 编码问题
- 正则表达式不匹配

解决方法：
- 查看原始 HTML 文件
- 更新提取规则
- 添加新的银行特定处理

### 3. API 无法访问

检查：
- 服务器是否运行
- 端口是否被占用
- 防火墙设置

### 4. JSON 序列化错误

确保所有数据都是可序列化的类型：
- bytes 转 str
- datetime 转字符串

## 📝 最佳实践

1. **每天定时执行** - 设置每天上午 9 点自动检查
2. **监控错误日志** - 定期检查 error_log.json
3. **备份数据** - 定期备份 bill_data_history.json
4. **设置通知阈值** - 超过一定金额才通知
5. **测试新邮件检测** - 确保不会重复处理

## 🎯 扩展功能

### 添加新银行支持

在 `this_month_bills.py` 中添加银行特定规则：

```python
if bank_name == '新银行':
    # 金额提取
    amount_patterns = [
        r'本期应还款.*?￥([0-9,]+\.?[0-9]*)',
    ]
    
    # 还款日提取
    due_patterns = [
        r'到期还款日.*?([0-9]{4}年 [0-9]{1,2}月 [0-9]{1,2}日)',
    ]
```

### 自定义报告格式

修改 `bill_storage.py` 中的 `generate_text_report` 函数。

### 集成其他通知方式

在 `openclaw_api.py` 的 `send_notification` 方法中添加。

## 📞 支持

如有问题，请查看：
1. error_log.json - 错误日志
2. bill_summary.txt - 最新报告
3. OPENCLAW_INTEGRATION.md - 详细文档

## 📄 License

本系统仅供个人使用。
