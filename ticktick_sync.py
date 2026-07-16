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

依赖：ticktick_api.py（纯 API 封装）
"""

import json
import os
from datetime import datetime
from pathlib import Path

from ticktick_api import TickTickAPI


SCRIPT_DIR = Path(__file__).parent
SYNC_STATE_FILE = SCRIPT_DIR / "ticktick_sync_state.json"


class TickTickSync:
    def __init__(self, api_key=None):
        self.api = TickTickAPI(api_key=api_key)

    def _calc_priority(self, days_until):
        if days_until <= 3:
            return 5
        elif days_until <= 7:
            return 3
        else:
            return 1

    def _build_task(self, bank, amount, due_date, days_until, bill_details=None):
        priority = self._calc_priority(days_until)

        content_parts = [f"还款金额：¥{amount:,.2f}", f"还款日：{due_date}（{days_until}天后）"]
        if bill_details:
            content_parts.append("")
            content_parts.append("明细：")
            for detail in bill_details:
                content_parts.append(f"  • {detail['subject']}: ¥{detail['amount']:,.2f}")

        # 到期时间设为上午 11:00（北京时间），isAllDay=False
        # 提前提醒：TRIGGER:-PT18H → 前 18 小时 = 前一天下午 5 点
        # 当天提醒：TRIGGER:PT0M   → 到期时刻 = 当天上午 11 点
        # 紧急账单（≤3天）额外加当天 11 点提醒
        reminders = ["TRIGGER:-PT18H"]
        if days_until <= 3:
            reminders.append("TRIGGER:PT0M")

        return {
            "title": f"💳 {bank}信用卡还款 ¥{amount:,.2f}",
            "content": "\n".join(content_parts),
            "due_date": due_date,
            "due_hour": 11,
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

        project_id = self.api.find_or_create_project(project_name)
        existing_tasks = self.api.get_project_tasks(project_id)
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

            try:
                result = self.api.create_task(
                    project_id,
                    title=task["title"],
                    due_date=task["due_date"],
                    content=task["content"],
                    priority=task["priority"],
                    reminders=task["reminders"],
                    due_hour=task.get("due_hour", 11)
                )
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
            pass

    def load_sync_state(self):
        if SYNC_STATE_FILE.exists():
            with open(SYNC_STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        return None

    def cleanup_old_tasks(self, project_name="信用卡还款"):
        project_id = self.api.find_or_create_project(project_name)
        tasks = self.api.get_project_tasks(project_id)
        today = datetime.now()
        deleted = 0

        for task in tasks:
            due_date_str = task.get("dueDate", "")
            if due_date_str:
                try:
                    due_date = datetime.strptime(due_date_str[:10], "%Y-%m-%d")
                    if (today - due_date).days > 7:
                        if self.api.delete_task(task["id"]):
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
            print(f"    优先级: {task['priority']}, 到期: {task['due_date']}")
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
