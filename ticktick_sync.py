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
- 已完成感知：用户在滴答清单里勾选完成的任务不会被重建
  （滴答清单 OpenAPI 不返回已完成任务，需用本地状态文件记录）

依赖：ticktick_api.py（纯 API 封装）
"""

import json
import os
from datetime import datetime
from pathlib import Path

from ticktick_api import TickTickAPI


SCRIPT_DIR = Path(__file__).parent
SYNC_STATE_FILE = SCRIPT_DIR / "ticktick_sync_state.json"
# 用户已手动完成的任务标题集合：{title: completed_at_str}
# 用于防止重建已完成的任务（OpenAPI 不返回 status=2 的任务，只能本地感知）
COMPLETED_TITLES_FILE = SCRIPT_DIR / "ticktick_completed_titles.json"


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

    # 银行全称 -> 最短中文缩写（用于任务标题）
    BANK_ABBR = {
        '招商银行': '招行', '广发银行': '广发', '平安银行': '平安',
        '光大银行': '光大', '兴业银行': '兴业', '邮储银行': '邮储',
        '浦发银行': '浦发', '民生银行': '民生', '交通银行': '交行',
        '建设银行': '建行', '工商银行': '工行', '中国银行': '中行', '农业银行': '农行',
        '长安银行': '长安',
    }

    @staticmethod
    def _bank_abbr(bank_name):
        """获取银行最短中文缩写（招行/建行/工行...），未匹配则原样返回"""
        for full, abbr in TickTickSync.BANK_ABBR.items():
            if full in bank_name:
                return abbr
        return bank_name

    @staticmethod
    def _label_suffix(label):
        """生成 YY 后缀字符串，空 label 返回空字符串"""
        if label and label.strip():
            return f" ({label.strip()})"
        return ""

    def _build_task(self, bank, amount, due_date, days_until, bill_details=None, source_label=''):
        priority = self._calc_priority(days_until)

        # 标题格式：💳 银行缩写 金额 元 (YY)（不带¥和千分位逗号，有 label 加后缀）
        bank_abbr = self._bank_abbr(bank)
        label_suffix = self._label_suffix(source_label)
        # content 里不再写"（X天后）"，只保留日期
        content_parts = [f"还款金额：¥{amount:,.2f}", f"还款日：{due_date}"]
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
            "title": f"💳 {bank_abbr} {amount:.2f} 元{label_suffix}",
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

        # 按「日期」比较；逾期账单也一直保留，直到用户在滴答清单里手动勾选完成
        # （completed_titles.json 机制保证用户完成后不会被重建）
        try:
            from datetime import timezone, timedelta as _td
            today = datetime.now(timezone(_td(hours=8))).date()
        except Exception:
            today = datetime.now().date()
        upcoming = {}
        for bill in bills:
            bank_name = bill.get("bank_name")
            if not bank_name:
                continue

            # 多邮箱模式：同银行不同邮箱分开存（用 bank_name|label 作为 key）
            source_label = bill.get("source_label", "")
            upcoming_key = f"{bank_name}|{source_label}"

            best_due_date = None
            best_days = None
            for due_date_str in bill.get("due_dates", []):
                due_date_str = due_date_str.replace("/", "-")
                try:
                    due_date = datetime.strptime(due_date_str, "%Y-%m-%d").date()
                    days_until = (due_date - today).days
                    # 不再过滤逾期账单：保留所有账单，由用户在滴答清单手动完成
                    if best_days is None or abs(days_until) < abs(best_days) or (
                        abs(days_until) == abs(best_days) and days_until > best_days
                    ):
                        best_days = days_until
                        best_due_date = due_date_str
                except:
                    continue

            if best_due_date and best_days is not None:
                if upcoming_key not in upcoming:
                    upcoming[upcoming_key] = {
                        "bank_name": bank_name,
                        "source_label": source_label,
                        "total_amount": 0,
                        "due_date": best_due_date,
                        "days_until": best_days,
                        "details": []
                    }
                for amount_info in bill.get("amounts", []):
                    upcoming[upcoming_key]["total_amount"] += amount_info["value"]
                    upcoming[upcoming_key]["details"].append({
                        "subject": bill["subject"],
                        "amount": amount_info["value"]
                    })

        if not upcoming:
            return {"success": False, "message": "没有未来待还款账单"}

        if dry_run:
            tasks = []
            for key, info in sorted(upcoming.items(), key=lambda x: x[1]["days_until"]):
                if info["total_amount"] > 0:
                    task = self._build_task(
                        info["bank_name"], info["total_amount"],
                        info["due_date"], info["days_until"],
                        info["details"],
                        source_label=info.get("source_label", "")
                    )
                    tasks.append(task)
            return {"success": True, "dry_run": True, "tasks": tasks, "count": len(tasks)}

        project_id = self.api.find_or_create_project(project_name)
        existing_tasks = self.api.get_project_tasks(project_id)
        existing_map = {t["title"]: t for t in existing_tasks}
        current_titles_set = set(existing_map.keys())

        # 已完成感知：对比「上次同步时存在的标题」与「本次拉取到的标题」
        # 消失的标题 = 用户手动完成（或手动删除）→ 加入本地 completed_titles
        # 后续同步跳过这些标题，避免重建已完成的任务
        # （OpenAPI /project/{pid}/data 不返回 status=2 的任务，只能靠本地状态感知）
        completed_titles = self._load_completed_titles()
        newly_completed = self._detect_newly_completed(current_titles_set)
        if newly_completed:
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            for title in newly_completed:
                if title not in completed_titles:
                    print(f"  ✓ 检测到用户已手动完成，跳过重建: {title}")
                    completed_titles[title] = now_str
            self._save_completed_titles(completed_titles)

        created = []
        skipped = []
        updated = []
        skipped_completed = []
        for key, info in sorted(upcoming.items(), key=lambda x: x[1]["days_until"]):
            if info["total_amount"] <= 0:
                continue

            bank_name = info["bank_name"]
            task = self._build_task(
                bank_name, info["total_amount"],
                info["due_date"], info["days_until"],
                info["details"],
                source_label=info.get("source_label", "")
            )

            # 跳过用户已手动完成的任务（防止重建）
            if task["title"] in completed_titles:
                skipped_completed.append({"bank": bank_name, "title": task["title"]})
                continue

            if task["title"] in existing_map:
                existing = existing_map[task["title"]]
                # 总是更新已存在任务的 dueDate/reminders，确保提醒时间正确（修复旧午夜提醒）
                try:
                    self.api.update_task(
                        existing["id"],
                        project_id=existing.get("projectId", project_id),
                        due_date=task["due_date"],
                        priority=task["priority"],
                        due_hour=task.get("due_hour", 11),
                        reminders=task["reminders"],
                        is_all_day=False
                    )
                    updated.append({"bank": bank_name, "task_id": existing["id"], "title": task["title"]})
                except Exception as e:
                    print(f"  Update failed for {bank_name}: {e}")
                    skipped.append({"bank": bank_name, "reason": f"更新失败: {e}"})
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
                    "bank": bank_name,
                    "task_id": result.get("id"),
                    "title": task["title"]
                })
            except Exception as e:
                created.append({"bank": bank_name, "error": str(e)})

        # 更新 last_seen_titles = 当前未完成的 + 本次新建的（供下次同步对比）
        all_current_titles = current_titles_set | {c["title"] for c in created if "title" in c}
        self._save_sync_state(created, skipped, all_current_titles)

        return {
            "success": True,
            "project_id": project_id,
            "project_name": project_name,
            "created": created,
            "skipped": skipped,
            "updated": updated,
            "skipped_completed": skipped_completed,
            "total_created": len([c for c in created if "error" not in c]),
            "total_skipped": len(skipped),
            "total_updated": len(updated),
            "total_skipped_completed": len(skipped_completed),
            "errors": len([c for c in created if "error" in c])
        }

    def _save_sync_state(self, created, skipped, current_titles=None):
        state = {
            "last_sync": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "created_count": len(created),
            "skipped_count": len(skipped),
            "created_tasks": created,
            "last_seen_titles": list(current_titles) if current_titles else []
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

    def _load_completed_titles(self):
        """读取用户已手动完成的任务标题集合。

        返回 dict: {title: completed_at_str}，completed_at 记录完成时间。
        标题里含金额，月份变了金额变，标题自然不再命中，无需额外清理。
        """
        if COMPLETED_TITLES_FILE.exists():
            try:
                with open(COMPLETED_TITLES_FILE, "r", encoding="utf-8") as f:
                    return json.load(f).get("completed_titles", {})
            except Exception:
                pass
        return {}

    def _save_completed_titles(self, completed_titles):
        """保存已完成的任务标题集合"""
        try:
            with open(COMPLETED_TITLES_FILE, "w", encoding="utf-8") as f:
                json.dump({
                    "completed_titles": completed_titles,
                    "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _detect_newly_completed(self, current_titles_set):
        """对比上次同步时存在的标题与本次拉取到的标题集合，
        检测用户手动完成的任务（上次存在，本次不存在 = 已完成或已删除）。

        返回 list[str]: 新完成的标题列表
        """
        state = self.load_sync_state()
        if not state:
            return []
        last_seen = set(state.get("last_seen_titles", []))
        if not last_seen:
            return []
        disappeared = last_seen - current_titles_set
        return list(disappeared)

    def cleanup_old_tasks(self, project_name="信用卡还款"):
        """保留所有任务，不再自动删除逾期任务。

        逾期账单会一直保留在滴答清单里，直到用户手动勾选完成。
        用户完成后由 completed_titles.json 机制防止重建。
        此方法保留为兼容入口（daily_run.py 会调用），但不再做任何删除。
        """
        project_id = self.api.find_or_create_project(project_name)
        tasks = self.api.get_project_tasks(project_id)
        return {"deleted": 0, "remaining": len(tasks)}


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
