#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""核实当前 TickTick 任务状态"""
from ticktick_api import TickTickAPI

api = TickTickAPI(api_key='dp_5dd5bf5607374d03bf0856775b94592f')
projects = api.get_projects()
project_id = None
for p in projects:
    if p.get("name") == "信用卡还款":
        project_id = p["id"]

data = api.session.get(f"https://api.dida365.com/open/v1/project/{project_id}/data").json()
tasks = data.get("tasks", [])
print(f"📋 滴答清单任务列表 ({len(tasks)} 个)：")
for t in sorted(tasks, key=lambda x: x.get('dueDate', '')):
    print(f"  - {t.get('dueDate', '')[:10]}  {t['title']}  (id={t['id'][:12]})")
