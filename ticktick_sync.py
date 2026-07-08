#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
滴答清单同步模块
将待还款账单自动创建为滴答清单任务。

功能：
- 自动创建"信用卡还款"清单
- 按银行创建任务（标题含金额，内容含明细）
- 智能优先级（3天内=高，7天内=中，其他=低）
- 到期提醒（提前1天，紧急的额外提前2小时）
- 自动去重（已存在的任务跳过）
- 自动清理过期任务（超过还款日7天的删除）

API Key 配置：
- 环境变量 TICKTICK_API_KEY（推荐，CI 环境）
- config.json 中的 ticktick_api_key（本地运行）
"""

import json
import os
import requests
from datetime import datetime, timedelta
from pathlib import Path


SCRIPT_DIR = Path(__file__).parent
BASE_URL = "https://api.dida365.com/open/v1"
SYNC_STATE_FILE = SCRIPT_DIR / "ticktick_sync_state.json"


def _load_api_key():
    """从环境变量或 config.json 读取 API Key"""
    # 1. 环境变量优先（CI 环境）
    api_key = os.environ.get('TICKTICK_API_KEY', '')
    if api_key:
        return api_key.strip()

    # 2. 回退到 config.json（本地运行）
    config_path = SCRIPT_DIR / 'config.json'
    if config_path.exists():
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                return config.get('ticktick_api_key', '').strip()
        except Exception:
            pass

    return ''


class TickTickSync:
    def __init__(self, api_key=None):
        self.api_key = api_key or _load_api_key()
        if not self.api_key:
            raise ValueError(
                "TICKTICK_API_KEY not found. "
                "Set environment variable TICKTICK_API_KEY or add 'ticktick_api_key' to config.json"
            )
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        })

    def get_projects(self):
        resp = self.session.get(f"{BASE_URL}/project")
        resp.raise_for_status()
        return resp.json()

    def find_or_create_project(self, name="信用卡还款"):
        projects = self.get_projects()
        for p in projects:
            if p["name"] == name:
                return p["id"]

        resp = self.session.post(f"{BASE_URL}/project", json={
            "name": name,
            "kind": "TASK",
            "viewMode": "list"
        })
        resp.raise_for_status()
        return resp.json()["id"]

    def get_project_tasks(self, project_id):
        resp = self.session.get(f"{BASE_URL}/project/{project_id}/data")
        resp.raise_for_status()
        data = resp.json()
        return data.get("tasks", [])

    def _bj_to_utc(self, date_str):
        bj_time = datetime.strptime(date_str, "%Y-%m-%d")
        utc_time = bj_time - timedelta(hours=8)
        return utc_time.strftime("%Y-%m-%dT%H:%M:%S.000+0000")

    def _calc_priority(self, days_until):
        if days_until <= 3:
            return 5
        elif days_until <= 7:
            return 3
        else:
            return 1

    def _build_task(self, bank, amount, due_date, days_until, bill_details=None):
        priority = self._calc_priority(days_until)
        utc_due = self._bj_to_utc(due_date)

        content_parts = [f"还款金额：¥{amount:,.2f}", f"还款日：{due_date}（{days_until}天后）"]
        if bill_details:
            content_parts.append("")
            content_parts.append("明细：")
            for detail in bill_details:
                content_parts.append(f"  • {detail['subject']}: ¥{detail['amount']:,.2f}")

        reminders = ["TRIGGER:-P1D"]
        if days_until <= 3:
            reminders.append("TRIGGER:-PT2H")

        return {
            "title": f"💳 {bank}信用卡还款 ¥{amount:,.2f}",
            "content": "\n".join(content_parts),
            "dueDate": utc_due,
            "timeZone": "Asia/Shanghai",
            "isAllDay": False,
            "priority": priority,
            "reminders": reminders
        }

    def sync_bills(self, bills_data, project_name="信用卡还款", dry_run=False):
        bills = bills_data.get("bills", [])
        if not bills:
            return {"success": False, "message": "没有账单数据可同步"}

        today = datetime.now()
        upcoming = {}
        for bill in bills:
            bank_name = bill.get("bank_name")
            if not bank_name:
                continue

            best_due_date = None
            best_days = None
            for due_date_str in bill.get("due_dates", []):
                due_date_str = due_date_str.replace("/", "-")
                try:
                    due_date = datetime.strptime(due_date_str, "%Y-%m-%d")
                    days_until = (due_date - today).days
                    if days_until >= 0:
                        if best_days is None or days_until < best_days:
                            best_days = days_until
                            best_due_date = due_date_str
                except:
                    continue

            if best_due_date and best_days is not None:
                if bank_name not in upcoming:
                    upcoming[bank_name] = {
                        "total_amount": 0,
                        "due_date": best_due_date,
                        "days_until": best_days,
                        "details": []
                    }
                for amount_info in bill.get("amounts", []):
                    upcoming[bank_name]["total_amount"] += amount_info["value"]
                    upcoming[bank_name]["details"].append({
                        "subject": bill["subject"],
                        "amount": amount_info["value"]
                    })

        if not upcoming:
            return {"success": False, "message": "没有未来待还款账单"}

        if dry_run:
            tasks = []
            for bank, info in sorted(upcoming.items(), key=lambda x: x[1]["days_until"]):
                if info["total_amount"] > 0:
                    task = self._build_task(
                        bank, info["total_amount"],
                        info["due_date"], info["days_until"],
                        info["details"]
                    )
                    tasks.append(task)
            return {"success": True, "dry_run": True, "tasks": tasks, "count": len(tasks)}

        project_id = self.find_or_create_project(project_name)
        existing_tasks = self.get_project_tasks(project_id)
        existing_titles = {t["title"] for t in existing_tasks}

        created = []
        skipped = []
        for bank, info in sorted(upcoming.items(), key=lambda x: x[1]["days_until"]):
            if info["total_amount"] <= 0:
                continue

            task = self._build_task(
                bank, info["total_amount"],
                info["due_date"], info["days_until"],
                info["details"]
            )

            if task["title"] in existing_titles:
                skipped.append({"bank": bank, "reason": "已存在"})
                continue

            if not dry_run:
                try:
                    task["projectId"] = project_id
                    resp = self.session.post(f"{BASE_URL}/task", json=task)
                    resp.raise_for_status()
                    result = resp.json()
                    created.append({
                        "bank": bank,
                        "task_id": result.get("id"),
                        "title": task["title"]
                    })
                except Exception as e:
                    created.append({"bank": bank, "error": str(e)})

        self._save_sync_state(created, skipped)

        return {
            "success": True,
            "project_id": project_id,
            "project_name": project_name,
            "created": created,
            "skipped": skipped,
            "total_created": len([c for c in created if "error" not in c]),
            "total_skipped": len(skipped),
            "errors": len([c for c in created if "error" in c])
        }

    def _save_sync_state(self, created, skipped):
        state = {
            "last_sync": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "created_count": len(created),
            "skipped_count": len(skipped),
            "created_tasks": created
        }
        try:
            with open(SYNC_STATE_FILE, "w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
        except Exception:
            pass  # CI 环境可能无法写入

    def load_sync_state(self):
        if SYNC_STATE_FILE.exists():
            with open(SYNC_STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        return None

    def cleanup_old_tasks(self, project_name="信用卡还款"):
        project_id = self.find_or_create_project(project_name)
        tasks = self.get_project_tasks(project_id)
        today = datetime.now()
        deleted = 0

        for task in tasks:
            due_date_str = task.get("dueDate", "")
            if due_date_str:
                try:
                    due_date = datetime.strptime(due_date_str[:10], "%Y-%m-%d")
                    if (today - due_date).days > 7:
                        resp = self.session.delete(
                            f"{BASE_URL}/task/{task['id']}",
                            params={"projectId": project_id}
                        )
                        if resp.status_code == 200:
                            deleted += 1
                except:
                    pass

        return {"deleted": deleted, "remaining": len(tasks) - deleted}


if __name__ == "__main__":
    import sys

    data_file = SCRIPT_DIR / "this_month_bills.json"
    if not data_file.exists():
        print("❌ 账单数据文件不存在，请先运行 this_month_bills.py")
        sys.exit(1)

    with open(data_file, "r", encoding="utf-8") as f:
        bills_data = json.load(f)

    try:
        sync = TickTickSync()
    except ValueError as e:
        print(f"❌ {e}")
        sys.exit(1)

    if len(sys.argv) > 1 and sys.argv[1] == "--dry-run":
        result = sync.sync_bills(bills_data, dry_run=True)
        print(f"📋 预览模式 - 将创建 {result['count']} 个任务：\n")
        for task in result["tasks"]:
            print(f"  {task['title']}")
            print(f"    优先级: {task['priority']}, 到期: {task['dueDate']}")
            print()
    elif len(sys.argv) > 1 and sys.argv[1] == "--cleanup":
        result = sync.cleanup_old_tasks()
        print(f"🧹 清理完成：删除 {result['deleted']} 个过期任务，剩余 {result['remaining']} 个")
    else:
        result = sync.sync_bills(bills_data)
        if result["success"]:
            print(f"✅ 同步完成！")
            print(f"   创建: {result['total_created']} 个任务")
            print(f"   跳过: {result['total_skipped']} 个（已存在）")
            if result["errors"]:
                print(f"   错误: {result['errors']} 个")
            for c in result["created"]:
                if "error" not in c:
                    print(f"   ✓ {c['title']}")
                else:
                    print(f"   ✗ {c['bank']}: {c['error']}")
        else:
            print(f"❌ {result['message']}")
