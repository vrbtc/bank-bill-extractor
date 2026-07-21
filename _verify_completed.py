#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""验证 completed_titles 机制：工行应被跳过，其他任务应被更新"""
import json
import os
from ticktick_sync import TickTickSync

os.environ['TICKTICK_API_KEY'] = 'dp_5dd5bf5607374d03bf0856775b94592f'

# 读取真实账单数据
with open("this_month_bills.json", "r", encoding="utf-8") as f:
    bills_data = json.load(f)

# 列出账单里所有银行
print("📋 账单数据中的银行：")
for b in bills_data.get("bills", []):
    bank = b.get("bank_name", "")
    amounts = [a["value"] for a in b.get("amounts", [])]
    due_dates = b.get("due_dates", [])
    print(f"  - {bank}: 金额={amounts}, 到期={due_dates}")

# 读取 completed_titles
with open("ticktick_completed_titles.json", "r", encoding="utf-8") as f:
    ct = json.load(f)
print(f"\n📋 completed_titles 里的标题：")
for title, ts in ct.get("completed_titles", {}).items():
    print(f"  - {title}  (完成时间: {ts})")

# 真实同步（非 dry_run）
print("\n--- 运行 sync_bills ---")
sync = TickTickSync()
result = sync.sync_bills(bills_data)

print(f"\n✅ 同步结果：")
print(f"  创建: {result.get('total_created', 0)} 个")
print(f"  跳过(已存在): {result.get('total_skipped', 0)} 个")
print(f"  更新: {result.get('total_updated', 0)} 个")
print(f"  跳过(用户已完成): {result.get('total_skipped_completed', 0)} 个")

print("\n  已跳过的已完成任务：")
for sc in result.get("skipped_completed", []):
    print(f"    🚫 {sc['title']} (银行: {sc['bank']})")

print("\n  已更新的任务：")
for u in result.get("updated", []):
    print(f"    ↻ {u['title']}")

# 验证：工行任务不应该在 created 里
created_titles = [c.get("title", "") for c in result.get("created", [])]
assert "💳 工行 22212.13 元" not in created_titles, "❌ 工行任务被错误创建！"
print("\n✅ 验证通过：工行任务未被重建")
