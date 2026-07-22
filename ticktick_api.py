#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
滴答清单 API 封装模块
纯 API 调用，不包含业务逻辑，可独立使用。

官方 API 文档：https://developer.dida365.com/

使用方法：
    from ticktick_api import TickTickAPI
    
    api = TickTickAPI(api_key="your_api_key")
    
    # 获取项目列表
    projects = api.get_projects()
    
    # 创建项目
    project_id = api.create_project("我的清单")
    
    # 获取任务
    tasks = api.get_project_tasks(project_id)
    
    # 创建任务
    task = api.create_task(project_id, title="完成报告", due_date="2026-07-20")
    
    # 删除任务
    api.delete_task(task_id)
"""

import json
import os
import requests
from datetime import datetime, timedelta, timezone
from pathlib import Path


# 北京时区（UTC+8）
_BJ_TZ = timezone(timedelta(hours=8))


BASE_URL = "https://api.dida365.com/open/v1"


class TickTickAPI:
    def __init__(self, api_key=None):
        if api_key:
            self.api_key = api_key.strip()
        else:
            self.api_key = self._load_api_key()

        if not self.api_key:
            raise ValueError(
                "API Key not found. "
                "Set environment variable TICKTICK_API_KEY or pass api_key parameter."
            )

        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        })

    def _load_api_key(self):
        api_key = os.environ.get('TICKTICK_API_KEY', '').strip()
        if api_key:
            return api_key

        config_path = Path(__file__).parent / 'config.json'
        if config_path.exists():
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    return config.get('ticktick_api_key', '').strip()
            except Exception:
                pass

        return ''

    def get_projects(self):
        """获取所有项目列表"""
        resp = self.session.get(f"{BASE_URL}/project")
        resp.raise_for_status()
        return resp.json()

    def get_project(self, project_id):
        """获取单个项目详情"""
        resp = self.session.get(f"{BASE_URL}/project/{project_id}")
        resp.raise_for_status()
        return resp.json()

    def create_project(self, name, kind="TASK", view_mode="list"):
        """
        创建新项目
        
        Args:
            name: 项目名称
            kind: 类型，TASK 或 NOTE
            view_mode: 视图模式，list 或 board
            
        Returns:
            项目 ID
        """
        resp = self.session.post(f"{BASE_URL}/project", json={
            "name": name,
            "kind": kind,
            "viewMode": view_mode
        })
        resp.raise_for_status()
        return resp.json()["id"]

    def update_project(self, project_id, name=None, color=None, icon=None):
        """更新项目信息"""
        data = {}
        if name:
            data["name"] = name
        if color:
            data["color"] = color
        if icon:
            data["icon"] = icon

        resp = self.session.put(f"{BASE_URL}/project/{project_id}", json=data)
        resp.raise_for_status()
        return resp.json()

    def delete_project(self, project_id):
        """删除项目"""
        resp = self.session.delete(f"{BASE_URL}/project/{project_id}")
        resp.raise_for_status()
        return resp.status_code == 200

    def find_project(self, name):
        """查找项目，返回项目 ID，不存在返回 None"""
        projects = self.get_projects()
        for p in projects:
            if p.get("name") == name:
                return p["id"]
        return None

    def find_or_create_project(self, name):
        """查找项目，不存在则创建"""
        project_id = self.find_project(name)
        if project_id:
            return project_id
        return self.create_project(name)

    def get_project_tasks(self, project_id):
        """获取项目下所有任务"""
        resp = self.session.get(f"{BASE_URL}/project/{project_id}/data")
        resp.raise_for_status()
        data = resp.json()
        return data.get("tasks", [])

    def get_task(self, task_id):
        """获取单个任务详情"""
        resp = self.session.get(f"{BASE_URL}/task/{task_id}")
        resp.raise_for_status()
        return resp.json()

    def _bj_to_utc(self, date_str, hour=11):
        """将北京时间 YYYY-MM-DD 转换为 UTC ISO 格式

        Args:
            date_str: 日期字符串 YYYY-MM-DD（北京时间）
            hour: 北京时间的小时数（默认 11 = 上午11点），避免午夜 00:00 提醒
        """
        bj_time = datetime.strptime(date_str, "%Y-%m-%d").replace(hour=hour)
        utc_time = bj_time - timedelta(hours=8)
        return utc_time.strftime("%Y-%m-%dT%H:%M:%S.000+0000")

    def create_task(self, project_id, title, due_date=None, content=None,
                   priority=0, reminders=None, tags=None, time_zone="Asia/Shanghai",
                   due_hour=11):
        """
        创建任务

        Args:
            project_id: 项目 ID
            title: 任务标题
            due_date: 到期日期，格式 YYYY-MM-DD（北京时间）
            content: 任务内容
            priority: 优先级，0=无, 1=低, 3=中, 5=高
            reminders: 提醒列表，如 ["TRIGGER:-PT18H", "TRIGGER:PT0M"]
            tags: 标签列表
            time_zone: 时区，默认 Asia/Shanghai
            due_hour: 到期时间的小时（北京时间，默认 11 = 上午11点）

        Returns:
            创建的任务对象
        """
        task = {
            "title": title,
            "projectId": project_id,
            "timeZone": time_zone,
            "isAllDay": False,
            "priority": priority
        }

        if due_date:
            task["dueDate"] = self._bj_to_utc(due_date, hour=due_hour)

        if content:
            task["content"] = content

        if reminders:
            task["reminders"] = reminders

        if tags:
            task["tags"] = tags

        resp = self.session.post(f"{BASE_URL}/task", json=task)
        resp.raise_for_status()
        return resp.json()

    def update_task(self, task_id, project_id=None, title=None, due_date=None,
                    content=None, priority=None, status=None, due_hour=11,
                    reminders=None, is_all_day=None):
        """更新任务信息"""
        task = {"id": task_id}

        if project_id:
            task["projectId"] = project_id
        if title:
            task["title"] = title
        if due_date:
            task["dueDate"] = self._bj_to_utc(due_date, hour=due_hour)
        if content:
            task["content"] = content
        if priority is not None:
            task["priority"] = priority
        if status is not None:
            task["status"] = status
        if reminders is not None:
            task["reminders"] = reminders
        if is_all_day is not None:
            task["isAllDay"] = is_all_day

        resp = self.session.post(f"{BASE_URL}/task/{task_id}", json=task)
        resp.raise_for_status()
        return resp.json()

    def delete_task(self, task_id, project_id=None):
        """删除任务（TickTick OpenAPI 不支持 DELETE 方法，用 status=2 完成代替）

        完成后任务从 OpenAPI 列表中消失，等效于删除。
        需要传 project_id 才能正确更新（与 update_task 一致）。
        """
        task = {"id": task_id, "status": 2}
        if project_id:
            task["projectId"] = project_id
        resp = self.session.post(f"{BASE_URL}/task/{task_id}", json=task)
        resp.raise_for_status()
        return resp.status_code == 200

    def complete_task(self, task_id):
        """完成任务"""
        return self.update_task(task_id, status=2)

    def reopen_task(self, task_id):
        """重新打开任务"""
        return self.update_task(task_id, status=0)

    def get_user_info(self):
        """获取当前用户信息"""
        resp = self.session.get(f"{BASE_URL}/user")
        resp.raise_for_status()
        return resp.json()

    def get_inbox_tasks(self):
        """获取收件箱任务"""
        projects = self.get_projects()
        inbox_id = None
        for p in projects:
            if p.get("inbox"):
                inbox_id = p["id"]
                break
        if inbox_id:
            return self.get_project_tasks(inbox_id)
        return []

    def get_upcoming_tasks(self, days=1, include_overdue=True):
        """获取未来 N 天代办任务（跨所有项目 + 收集箱）

        筛选条件：未完成（status=0）且有 dueDate。
        - 逾期未完成：include_overdue=True 时全部纳入（单独分组）
        - 非逾期：到期日落在 [今天, 今天+days-1] 区间内（含两端）

        注意：滴答清单的"收集箱"（Inbox）不在 /project 列表里，
        需要用专门的 /project/inbox/data 端点获取，否则会漏任务。

        Args:
            days: 未来天数（含今天）。days=1 仅今天；days=4 = 今天+明天+后天+大后天
            include_overdue: 是否包含已逾期未完成的任务（默认 True）

        Returns:
            list[dict]，每项含 title/project_name/due_date_bj/priority/is_overdue/days_offset
            days_offset: 相对今天的天数偏移（0=今天, 1=明天, -1=昨天逾期）
        """
        today_bj = datetime.now(_BJ_TZ).date()
        result = []
        max_offset = max(days - 1, 0)  # days=4 → 允许 offset 0,1,2,3

        def _collect_tasks(tasks_iter, project_name, project_id):
            """内部方法：从任务列表中筛选符合日期范围的任务"""
            for t in tasks_iter:
                if t.get("status", 0) != 0:
                    continue  # 跳过已完成
                due = t.get("dueDate", "")
                if not due:
                    continue  # 无到期日，跳过

                try:
                    due_utc = datetime.strptime(due[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
                    due_bj_date = due_utc.astimezone(_BJ_TZ).date()
                except Exception:
                    continue

                offset = (due_bj_date - today_bj).days
                is_overdue = offset < 0

                if is_overdue:
                    if not include_overdue:
                        continue
                else:
                    if offset > max_offset:
                        continue  # 超出未来 N 天范围，跳过

                result.append({
                    "title": t.get("title", "") or "(无标题)",
                    "project_name": project_name,
                    "project_id": project_id,
                    "due_date_bj": due_bj_date.isoformat(),
                    "priority": t.get("priority", 0),
                    "is_overdue": is_overdue,
                    "days_offset": offset,
                    "task_id": t.get("id"),
                })

        # 1. 遍历普通项目（清单）
        for p in self.get_projects():
            pid = p.get("id")
            pname = p.get("name", "")
            try:
                resp = self.session.get(f"{BASE_URL}/project/{pid}/data")
                resp.raise_for_status()
                data = resp.json()
            except Exception:
                continue
            _collect_tasks(data.get("tasks", []), pname, pid)

        # 2. 遍历收集箱（Inbox）—— 滴答清单的特殊项目，不在 /project 列表里
        try:
            resp = self.session.get(f"{BASE_URL}/project/inbox/data")
            resp.raise_for_status()
            inbox_data = resp.json()
            _collect_tasks(inbox_data.get("tasks", []), "收集箱", "inbox")
        except Exception:
            pass  # 收集箱获取失败不阻断流程

        # 按相对天数升序、优先级降序排序
        result.sort(key=lambda x: (x["days_offset"], -x["priority"], x["project_name"], x["title"]))
        return result

    def get_today_tasks(self, include_overdue=True):
        """获取今日代办任务（含逾期）。days=1 的快捷方式。"""
        return self.get_upcoming_tasks(days=1, include_overdue=include_overdue)


if __name__ == "__main__":
    import sys

    try:
        api = TickTickAPI()
    except ValueError as e:
        print(f"❌ {e}")
        print("\n使用方法：")
        print("  1. 设置环境变量: export TICKTICK_API_KEY=your_key")
        print("  2. 或在 config.json 中添加: {\"ticktick_api_key\": \"your_key\"}")
        sys.exit(1)

    print("✅ 连接成功！")

    if len(sys.argv) > 1:
        if sys.argv[1] == "--projects":
            projects = api.get_projects()
            print(f"\n📋 项目列表 ({len(projects)}):")
            for p in projects:
                print(f"  - {p['name']} (ID: {p['id'][:8]}...)")

        elif sys.argv[1] == "--inbox":
            tasks = api.get_inbox_tasks()
            print(f"\n📥 收件箱任务 ({len(tasks)}):")
            for t in tasks[:10]:
                due = t.get("dueDate", "")[:10] if t.get("dueDate") else "无"
                print(f"  - {t['title']} (到期: {due})")
            if len(tasks) > 10:
                print(f"  ... 还有 {len(tasks) - 10} 个任务")

        elif sys.argv[1] == "--create":
            if len(sys.argv) < 3:
                print("用法: python ticktick_api.py --create '任务标题' [到期日期]")
                sys.exit(1)
            title = sys.argv[2]
            due_date = sys.argv[3] if len(sys.argv) > 3 else None

            inbox_id = None
            for p in api.get_projects():
                if p.get("inbox"):
                    inbox_id = p["id"]
                    break

            if inbox_id:
                task = api.create_task(inbox_id, title, due_date=due_date)
                print(f"\n✅ 创建成功: {task['title']} (ID: {task['id']})")
            else:
                print("❌ 未找到收件箱")

        elif sys.argv[1] == "--user":
            user = api.get_user_info()
            print(f"\n👤 用户信息:")
            print(f"  用户名: {user.get('nickname', '未知')}")
            print(f"  邮箱: {user.get('email', '未知')}")
            print(f"  用户ID: {user.get('id', '未知')}")
    else:
        print("\n📖 可用命令:")
        print("  python ticktick_api.py --projects    # 列出所有项目")
        print("  python ticktick_api.py --inbox       # 列出收件箱任务")
        print("  python ticktick_api.py --create '标题' [日期]  # 创建任务")
        print("  python ticktick_api.py --user        # 查看用户信息")
