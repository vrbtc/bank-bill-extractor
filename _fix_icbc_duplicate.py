#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""临时脚本：处理工行重复任务，初始化 completed_titles 状态。

1. 列出当前所有未完成的信用卡还款任务
2. 删除工行重复任务（用户已还款，被错误重建）
3. 在 completed_titles.json 里预置工行标题
4. 更新 last_seen_titles 为剩余7个任务的标题
"""
import json
from datetime import datetime
from ticktick_api import TickTickAPI

API_KEY = 'dp_5dd5bf5607374d03bf0856775b94592f'
PROJECT_NAME = "信用卡还款"
COMPLETED_TITLES_FILE = "ticktick_completed_titles.json"
SYNC_STATE_FILE = "ticktick_sync_state.json"
ICBC_TITLE = "💳 工行 22212.13 元"

api = TickTickAPI(api_key=API_KEY)

# 1. 找到信用卡还款项目
projects = api.get_projects()
project_id = None
for p in projects:
    if p.get("name") == PROJECT_NAME:
        project_id = p["id"]
        break
if not project_id:
    print("❌ 找不到项目")
    exit(1)

# 2. 获取所有未完成任务
data = api.session.get(f"https://api.dida365.com/open/v1/project/{project_id}/data").json()
tasks = data.get("tasks", [])
print(f"📋 当前未完成任务 {len(tasks)} 个：")
for t in tasks:
    print(f"  - id={t['id'][:8]}  title={t['title']}  dueDate={t.get('dueDate', '')[:10]}")

# 3. 找到工行任务并删除
icbc_task = None
for t in tasks:
    if t["title"] == ICBC_TITLE:
        icbc_task = t
        break

if icbc_task:
    print(f"\n🗑️  删除工行重复任务: {ICBC_TITLE} (id={icbc_task['id']})")
    # 用 DELETE /project/{pid}/task/{tid} 这个 endpoint（之前试出来 OpenAPI 的 /task/{tid} 返回 500）
    resp = api.session.delete(
        f"https://api.dida365.com/open/v1/project/{project_id}/task/{icbc_task['id']}"
    )
    print(f"   删除结果: status={resp.status_code}")
else:
    print(f"\n⚠️  未找到工行任务: {ICBC_TITLE}")

# 4. 重新获取任务列表（删除后的状态）
data2 = api.session.get(f"https://api.dida365.com/open/v1/project/{project_id}/data").json()
remaining_tasks = data2.get("tasks", [])
remaining_titles = [t["title"] for t in remaining_tasks]
print(f"\n📋 删除后剩余 {len(remaining_titles)} 个任务：")
for title in remaining_titles:
    print(f"  - {title}")

# 5. 初始化 completed_titles.json，预置工行标题
completed_titles = {ICBC_TITLE: datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
with open(COMPLETED_TITLES_FILE, "w", encoding="utf-8") as f:
    json.dump({
        "completed_titles": completed_titles,
        "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "note": "初始化时预置工行标题，避免重建"
    }, f, ensure_ascii=False, indent=2)
print(f"\n✅ 已创建 {COMPLETED_TITLES_FILE}，预置工行标题")

# 6. 更新 ticktick_sync_state.json 的 last_seen_titles 为剩余7个任务的标题
state = {
    "last_sync": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    "created_count": 0,
    "skipped_count": 0,
    "created_tasks": [],
    "last_seen_titles": remaining_titles
}
with open(SYNC_STATE_FILE, "w", encoding="utf-8") as f:
    json.dump(state, f, ensure_ascii=False, indent=2)
print(f"\n✅ 已更新 {SYNC_STATE_FILE}，last_seen_titles={len(remaining_titles)} 个标题")
print(f"\n🎯 完成！下次同步将跳过工行任务，不会重建。")
