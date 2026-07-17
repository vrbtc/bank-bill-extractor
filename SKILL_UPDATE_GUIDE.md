# 🔄 技能维护与更新指南

> **如何后期更新代码、修复Bug、添加新功能**

---

## 📌 更新方式总览

| 方式 | 适用场景 | 难度 | 推荐度 |
|------|---------|------|--------|
| **方式A: 手动替换文件** | 小改动、快速修复 | ⭐ 简单 | ✅ 日常使用 |
| **方式B: 使用 update_skill.py** | 正式更新、需要备份 | ⭐⭐ 中等 | ✅✅ 推荐 |
| **方式C: 重新打包发给OpenClaw** | 大版本升级 | ⭐⭐⭐ 较复杂 | 大更新时 |

---

## 🎯 方式A：手动替换文件（最快）

### 适用场景
- 修改某个银行提取逻辑
- 修复小bug
- 调整参数

### 操作步骤

#### 1️⃣ 直接编辑源码

```bash
# 用你喜欢的编辑器打开文件
# 例如：修改招商银行的提取逻辑
notepad this_month_bills.py

# 或者用 VSCode
code this_month_bills.py
```

#### 2️⃣ 测试修改是否生效

```bash
# 刷新数据测试
python bill_skill.py refresh --force

# 查询账单验证
python bill_skill.py query --days 15
```

#### 3️⃣ 如果出错了？回滚！

**方法1：用Git回滚（如果你用了Git）**
```bash
git checkout this_month_bills.py  # 恢复到上次提交的版本
```

**方法2：用备份工具回滚（推荐）**
```bash
python update_skill.py rollback
```

---

## 🔧 方式B：使用更新工具（推荐）

### 适用场景
- 正式发布新版本
- 需要保留旧版本备份
- 多个文件同时更新
- 要记录更新日志

### 核心命令速查

```bash
# ✅ 查看当前版本
python update_skill.py status

# ✅ 创建备份（更新前必做！）
python update_skill.py backup --label "更新前备份"

# ✅ 从目录更新文件
python update_skill.py update ./new_files/ --version "1.1.0" --changelog "修复XX银行提取逻辑"

# ✅ 查看所有备份
python update_skill.py list

# ✅ 回滚到上一个版本
python update_skill.py rollback

# ✅ 创建新的发布包（给OpenClaw用）
python update_skill.py pack
```

### 完整更新流程示例

#### 场景：修复招商银行金额提取问题

```bash
# ===== 第1步：查看当前状态 =====
python update_skill.py status
# 输出：
# 当前版本：v1.0.0
# 构建号：20260409

# ===== 第2步：备份当前版本 =====
python update_skill.py backup --label "修复招行前"
# 输出：
# ✅ 备份完成：v1.0.0_20260409_140000_修复招行前

# ===== 第3步：修改代码 =====
# 编辑 this_month_bills.py 或其他文件...
notepad this_month_bills.py

# ===== 第4步：测试修改 =====
python bill_skill.py refresh --force
python bill_skill.py query --bank 招商

# ===== 第5步：如果测试通过，更新版本号 =====
python update_skill.py update . --version "1.0.1" --changelog "修复招商银行金额提取"
# 输出：
# ✓ this_month_bills.py
# ✓ bank_extractors.py
# ✅ 版本已更新: v1.0.0 → v1.0.1

# ===== 第6步：创建新发布包 =====
python update_skill.py pack
# 输出：
# ✅ 发布包已创建：bank-bill-skill_v1.0.1_20260409_140100.zip

# ===== 第7步：把新包发给 OpenClaw =====
# （见下方「方式C」）
```

---

## 📦 方式C：重新打包发给OpenClaw（大版本更新）

### 适用场景
- 添加新银行支持
- 重构核心架构
- OpenClaw 需要完整更新

### 操作步骤

#### 1️⃣ 在本地完成所有修改和测试

（参考方式A或B完成代码修改）

#### 2️⃣ 创建带版本号的发布包

```bash
# 方法1：使用工具自动打包（推荐）
python update_skill.py pack --output ./releases/

# 方法2：手动选择文件打包
python update_skill.py pack --include-cache  # 包含缓存数据
```

#### 3️⃣ 你会得到一个新压缩包

```
bank-bill-skill_v1.1.0_20260409.zip  (23KB)
```

**包含内容：**
- 所有更新的代码文件
- 新的 VERSION.json（版本号已更新）
- 更新的 SKILL.md 文档
- 完整的 OPENCLAW_DEPLOY_GUIDE.md

#### 4️⃣ 发送给OpenClaw + 更新提示词

**👇 把这个提示词发给OpenClaw：**

```
# 🔄 技能更新通知

我有一个新版本的银行账单查询技能需要更新。

## 请执行以下操作：

### 1. 接收新文件包
我已经发送了新版本的压缩包，请解压覆盖原有文件。

### 2. 查看版本信息
运行：python update_skill.py status
确认版本号已经更新。

### 3. 安装依赖（如果有新增）
运行：pip install -r requirements.txt

### 4. 测试功能
依次运行以下命令验证：
- python bill_skill.py status
- python bill_skill.py refresh --force
- python bill_skill.py query --days 15
- python bill_skill.py urgent

### 5. 确认就绪
如果所有测试都通过，回复：
"✅ 技能已更新到 v[X.X.X] 版本，可以正常使用！"

## 本次更新内容
[在这里填写你的更新说明]
```

---

## 🐛 常见更新场景

### 场景1：添加新银行支持

**需要修改的文件：**
1. `this_month_bills.py` - 添加新的银行提取逻辑
2. `bank_extractors.py` - （可选）创建专用提取器类
3. `SKILL.md` - 更新支持的银行列表
4. `VERSION.json` - 更新版本号

**步骤：**
```bash
# 1. 备份
python update_skill.py backup --label "添加XX银行前"

# 2. 修改代码
# 在 this_month_bills.py 的 extract_from_html() 中添加新银行的 if 分支

# 3. 测试
python bill_skill.py refresh --force
python bill_skill.py query --bank XX银行

# 4. 更新版本
python update_skill.py update . --version "1.1.0" --changelog "新增XX银行支持"

# 5. 打包发布
python update_skill.py pack
```

### 场景2：修复某银行金额错误

**例如：交通银行金额显示为实际的3倍**

**步骤：**
```bash
# 1. 先定位问题
python bill_skill.py query --bank 交通 --format json
# 查看 raw_data 找到问题原因

# 2. 备份
python update_skill.py backup --label "修复交行金额前"

# 3. 修改 this_month_bills.py 中交通银行的处理逻辑
# 添加去重检查或修正解析规则

# 4. 测试
python bill_skill.py refresh --force
python bill_skill.py query --bank 交通

# 5. 确认修复后更新版本
python update_skill.py update . --version "1.0.2" --changelog "修复交通银行金额重复问题"
```

### 场景3：调整日期过滤逻辑

**例如：从15天改为30天默认范围**

**步骤：**
```bash
# 只需修改 bill_skill.py 中的默认值
# 找到 def query(self, days=None, ...) 
# 将默认值从 15 改为 30

# 测试
python bill_skill.py query  # 应该显示30天内的账单
```

### 场景4：更新邮箱密码

**步骤：**
```bash
# 直接编辑 config.json
notepad config.json

# 修改 password 字段为新密码

# 测试连接
python bill_skill.py refresh --force
```

---

## 📊 版本管理最佳实践

### 版本号规范

采用 **语义化版本 (Semantic Versioning)**：

```
主版本.次版本.修订号
 │      │       └── Bug修复（不破坏兼容性）
 │      └───────── 新功能（向后兼容）
 └───────────────── 不兼容的大改动
```

**示例：**
- `1.0.0` → `1.0.1` 修复了招商银行金额bug
- `1.0.1` → `1.1.0` 添加了广发银行支持
- `1.1.0` → `2.0.0` 重构了整个提取引擎

### 更新日志模板

每次更新都应该记录：

```json
{
  "version": "1.1.0",
  "build": "20260415",
  "release_date": "2026-04-15",
  "changelog": "新增功能\n- 添加广发银行支持\n- 优化HTML解析速度\n- 修复日期格式识别问题"
}
```

### 备份策略建议

| 时间点 | 操作 | 说明 |
|--------|------|------|
| 每次修改前 | `backup --label "描述"` | 必须做！ |
| 每周定期 | 自动清理旧备份 | 保留最近10个 |
| 大版本发布前 | 完整备份 + 打包 | 用于回滚 |

---

## 🆘 紧急回滚指南

### 如果更新后出问题了？

```bash
# 1. 不要慌！立即查看备份列表
python update_skill.py list

# 2. 回滚到最近的稳定版本
python update_skill.py rollback

# 3. 验证回滚成功
python bill_skill.py status
python bill_skill.py query --days 15

# 4. 如果还有问题，继续回滚更早的版本
python update_skill.py rollback v1.0.0_xxx
```

### 如果备份也坏了？

**终极方案：从原始部署包重新安装**

```bash
# 解压最初的 bank-bill-skill-for-openclaw.zip
# 覆盖所有文件
# 重新运行部署流程
```

---

## 📝 给开发者的高级技巧

### 技巧1：使用 Git 进行版本控制（强烈推荐）

```bash
# 初始化仓库
git init

# 创建 .gitignore
echo "*.pyc\n__pycache__/\n.this_month_bills.json\n.backups/" > .gitignore

# 首次提交
git add .
git commit -m "初始版本 v1.0.0"

# 每次修改后
git add .
git commit -m "v1.0.1: 修复招商银行金额"

# 查看历史
git log --oneline

# 回滚到任意版本
git checkout <commit-hash>
```

### 技巧2：自动化测试脚本

创建 `test_skill.sh`：

```bash
#!/bin/bash
echo "🧪 开始测试..."
echo ""

echo "1. 检查状态..."
python bill_skill.py status || exit 1

echo ""
echo "2. 刷新数据..."
python bill_skill.py refresh --force || exit 1

echo ""
echo "3. 查询账单..."
python bill_skill.py query --days 15 || exit 1

echo ""
echo "4. 紧急检测..."
python bill_skill.py urgent || exit 1

echo ""
echo "✅ 所有测试通过！"
```

使用：
```bash
chmod +x test_skill.sh
./test_skill.sh
```

### 技巧3：多环境管理

如果你有开发环境和生产环境：

```
project/
├── dev/           # 开发环境（测试用）
│   ├── config.json    # 测试邮箱
│   └── ...
└── prod/          # 生产环境（正式用）
    ├── config.json    # 真实邮箱
    └── ...
```

---

## 🎓 OpenClaw 端如何接收更新？

### OpenClaw 收到新包后的操作

当 OpenClaw 收到你发送的新版本压缩包后，它会：

1. **解压并对比版本**
   ```bash
   python update_skill.py status  # 查看旧版本
   # 解压新文件
   python update_skill.py status  # 查看新版本
   ```

2. **自动备份旧版本**
   ```bash
   python update_skill.py backup --label "更新前自动备份"
   ```

3. **覆盖文件**
   ```bash
   # 将新文件复制到技能目录
   ```

4. **运行测试验证**
   ```bash
   python bill_skill.py status
   python bill_skill.py query --days 15
   ```

5. **报告结果**
   ```
   ✅ 已从 v1.0.0 更新到 v1.1.0
   
   更新内容：
   - 新增广发银行支持
   - 优化解析速度
   
   测试结果：全部通过 ✓
   ```

### 给 OpenClaw 的更新提示词模板

```
# 📦 技能更新指令

## 任务
将银行账单查询技能从 v{OLD_VERSION} 更新到 v{NEW_VERSION}。

## 操作步骤

1. 解压我发送的新版本压缩包
2. 运行 `python update_skill.py status` 查看新旧版本对比
3. 运行 `python update_skill.py backup --label "auto-backup"` 备份旧版本
4. 用新文件覆盖旧文件（同名文件直接替换）
5. 如果有新增依赖，运行 `pip install -r requirements.txt`
6. 运行完整测试：
   - `python bill_skill.py status`
   - `python bill_skill.py refresh --force`
   - `python bill_skill.py query --days 15`
   - `python bill_skill.py urgent`
   - `python bill_skill.py report --days 30`
7. 确认全部通过后报告更新结果

## 本次更新内容
{CHANGELOG}

## 注意事项
- 更新前会自动备份，如果出错可以回滚
- config.json 通常不需要替换（除非明确说明）
- 更新后首次 refresh 可能较慢（需要重新连接邮箱）
```

---

## 📞 快速参考卡

### 日常维护命令

```bash
# 查看版本
python update_skill.py status

# 备份（改代码前必做！）
python update_skill.py backup --label "原因"

# 更新版本号
python update_skill.py update . --version "X.X.X" --changelog "说明"

# 回滚（出错时救命）
python update_skill.py rollback

# 打包发布
python update_skill.py pack

# 查看备份
python update_skill.py list
```

### 文件修改频率参考

| 文件 | 修改频率 | 修改原因 |
|------|---------|---------|
| `this_month_bills.py` | 🔴 高 | 银行提取逻辑调整 |
| `bill_skill.py` | 🟡 中 | 功能增强 |
| `config.json` | 🟡 中 | 密码变更 |
| `SKILL.md` | 🟢 低 | 文档更新 |
| `requirements.txt` | 🟢 低 | 依赖变更 |
| `email_client.py` | ⚪ 几乎不改 | 基础设施层 |

---

## ❓ FAQ

### Q1: 我不懂Python，怎么更新？
**A**: 最简单的方式是告诉我你要改什么（比如"招商银行金额不对"），我来帮你改好，然后给你一个新压缩包，你直接发给OpenClaw就行。

### Q2: 更新后会丢失数据吗？
**A**: 不会。账单数据存储在 `this_month_bills.json`，下次 refresh 会自动更新。但建议更新前先备份。

### Q3: 可以同时运行多个版本吗？
**A**: 可以。把不同版本放在不同目录即可。但不建议这样做，容易混淆。

### Q4: OpenClaw 需要重启吗？
**A**: 不需要。只要文件被替换，OpenClaw 下次调用时会自动使用新代码。

### Q5: 如何知道哪个版本最稳定？
**A**: 查看备份列表中的标签，带有"稳定"、"final"标记的通常是经过测试的版本。

---

**文档版本**: v1.0.0  
**最后更新**: 2026-04-09  
**相关工具**: [update_skill.py](./update_skill.py) | [VERSION.json](./VERSION.json)

---

> 💡 **记住这个流程：备份 → 修改 → 测试 → 更新版本 → 打包 → 发给OpenClaw**  
> 养成好习惯，永远不怕改坏代码！
