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
from bank_extractors import get_sub_account
from run_logger import log_event


SCRIPT_DIR = Path(__file__).parent
SYNC_STATE_FILE = SCRIPT_DIR / "ticktick_sync_state.json"
# 用户已手动完成的任务标题集合：{title: completed_at_str}
# 用于防止重建已完成的任务（OpenAPI 不返回 status=2 的任务，只能本地感知）
COMPLETED_TITLES_FILE = SCRIPT_DIR / "ticktick_completed_titles.json"
# 用户已手动完成的账单明细（账单级）：[{bank, label, sub_account, amount, due_date, ...}]
# 用于从聚合结果中剔除已还款账单，避免旧邮件金额污染新任务
# （标题级 completed_titles 只能跳过整任务，无法剔除组内混入的已还旧账单）
COMPLETED_AMOUNTS_FILE = SCRIPT_DIR / "ticktick_completed_amounts.json"


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

    @staticmethod
    def _task_title(bank, amount, source_label='', sub_account=''):
        """构造任务标题：💳 银行缩写[子账户] 金额 元 (YY)

        子账户（如招行车贷）拼在银行缩写后，如「💳 招行车贷 2833.33 元」。
        generate_dashboard 的任务完成检测也用此方法，保证标题一致。
        """
        bank_abbr = TickTickSync._bank_abbr(bank)
        if sub_account:
            bank_abbr += sub_account
        label_suffix = TickTickSync._label_suffix(source_label)
        return f"💳 {bank_abbr} {amount:.2f} 元{label_suffix}"

    @staticmethod
    def _parse_task_title(title):
        """反解任务标题「💳 银行缩写[子账户] 金额 元 (label)」。

        Returns:
            dict: {abbr, sub_account, amount, label}，无法解析返回 None
        """
        import re
        m = re.match(r'^💳\s+(.+?)\s+([\d,]+(?:\.\d+)?)\s*元(?:\s+\((.+)\))?$', title or "")
        if not m:
            return None
        abbr_part = m.group(1)
        amount = float(m.group(2).replace(",", ""))
        label = (m.group(3) or "").strip()
        # 拆出子账户：按银行缩写表做前缀匹配，剩余部分为 sub_account
        abbr, sub_account = abbr_part, ""
        for full, a in TickTickSync.BANK_ABBR.items():
            if abbr_part.startswith(a):
                abbr = a
                sub_account = abbr_part[len(a):]
                break
        return {"abbr": abbr, "sub_account": sub_account, "amount": amount, "label": label}

    def _load_completed_amounts(self):
        """读取账单级已完成记录列表"""
        if COMPLETED_AMOUNTS_FILE.exists():
            try:
                with open(COMPLETED_AMOUNTS_FILE, "r", encoding="utf-8") as f:
                    return json.load(f).get("completed_amounts", [])
            except Exception:
                pass
        return []

    def _save_completed_amounts(self, records):
        """保存账单级已完成记录列表"""
        try:
            with open(COMPLETED_AMOUNTS_FILE, "w", encoding="utf-8") as f:
                json.dump({
                    "completed_amounts": records,
                    "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    @staticmethod
    def _same_completed_record(r1, r2):
        """判断两条账单级完成记录是否为同一笔（银行+邮箱+子账户+金额+还款日）"""
        return (r1.get("bank") == r2.get("bank")
                and (r1.get("label") or "") == (r2.get("label") or "")
                and (r1.get("sub_account") or "") == (r2.get("sub_account") or "")
                and abs(float(r1.get("amount", 0)) - float(r2.get("amount", 0))) < 0.005
                and (r1.get("due_date") or "") == (r2.get("due_date") or ""))

    @staticmethod
    def _fuzzy_title_matches(title, source_label, sub_account):
        """fuzzy 匹配一致性检查：候选任务标题的邮箱 label 和子账户必须与目标一致。

        - label：标题尾部 (YY) 后缀的有无必须一致，防止 YY 邮箱任务错配主邮箱任务
        - 子账户：标题反解出的 sub_account 必须一致，防止车贷任务错配普通信用卡任务
          （无法反解的旧格式标题不拦截，保持原有清理行为）
        """
        import re
        if not title:
            return False
        has_label = bool(re.search(r'\s\([^)]+\)$', title))
        want_label = bool(source_label and source_label.strip())
        if has_label != want_label:
            return False
        parsed = TickTickSync._parse_task_title(title)
        if parsed and parsed["sub_account"] != (sub_account or ""):
            return False
        return True

    def _migrate_completed_titles(self):
        """一次性迁移：把标题级 completed_titles.json 转成账单级 completed_amounts.json。

        历史记录标题里没有还款日，从 this_month_bills.json 里找同银行同金额的
        账单补 due_date；找不到则 due_date 置空（匹配时只对已过期账单生效，
        避免误杀未来同金额的新账单，如车贷每月固定金额）。
        """
        if COMPLETED_AMOUNTS_FILE.exists():
            return
        completed_titles = self._load_completed_titles()
        records = []
        if completed_titles:
            # 加载账单数据用于补 due_date
            bills = []
            bills_file = SCRIPT_DIR / "this_month_bills.json"
            if bills_file.exists():
                try:
                    with open(bills_file, "r", encoding="utf-8") as f:
                        bills = json.load(f).get("bills", [])
                except Exception:
                    pass
            for title, completed_at in completed_titles.items():
                parsed = self._parse_task_title(title)
                if not parsed:
                    continue
                due_date = None
                for b in bills:
                    if self._bank_abbr(b.get("bank_name", "")) != parsed["abbr"]:
                        continue
                    if (b.get("source_label") or "") != parsed["label"]:
                        continue
                    if any(abs(a["value"] - parsed["amount"]) < 0.005 for a in b.get("amounts", [])):
                        dds = b.get("due_dates") or []
                        if dds:
                            due_date = dds[0].replace("/", "-")
                            break
                records.append({
                    "bank": parsed["abbr"],
                    "label": parsed["label"],
                    "sub_account": parsed["sub_account"],
                    "amount": parsed["amount"],
                    "due_date": due_date,
                    "title": title,
                    "completed_at": completed_at
                })
        self._save_completed_amounts(records)

    def _build_task(self, bank, amount, due_date, days_until, bill_details=None, source_label='', sub_account=''):
        priority = self._calc_priority(days_until)

        # 标题格式：💳 银行缩写[子账户] 金额 元 (YY)（不带¥和千分位逗号，有 label 加后缀）
        bank_abbr = self._bank_abbr(bank)
        if sub_account:
            bank_abbr += sub_account
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

        # 一次性迁移：标题级完成记录 → 账单级完成记录
        self._migrate_completed_titles()

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

            # 跳过无金额的账单（提取失败或纯通知邮件，会污染 due_date）
            amounts = bill.get("amounts", [])
            if not amounts:
                continue

            # 多邮箱模式：同银行不同邮箱分开存（用 bank_name|label 作为 key）
            source_label = bill.get("source_label", "")
            # 子账户拆分：还款日不同的账户（如招行车贷 28 日 vs 信用卡 6 日）分开建任务
            sub_account = get_sub_account(bank_name, bill.get("subject", ""))
            upcoming_key = f"{bank_name}|{sub_account}|{source_label}" if sub_account else f"{bank_name}|{source_label}"

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
                # 按还款日分组建任务：同银行不同还款日的账单分开（如邮储两张卡
                # 还款日 27 号和 7 号、工行旧账单 09-19 与新账单 10-19），
                # 避免合并成错误总额+还款日错乱，也避免用户还完其中一张卡勾选完成时
                # 把同组其他还款日的账单连带标记为已完成
                # （招行分期卡已按子账户单独拆分，即使与信用卡同日还款也不合并）
                group_key = f"{upcoming_key}|{best_due_date}"
                if group_key not in upcoming:
                    upcoming[group_key] = {
                        "bank_name": bank_name,
                        "source_label": source_label,
                        "sub_account": sub_account,
                        "total_amount": 0,
                        "due_date": best_due_date,
                        "days_until": best_days,
                        "details": []
                    }
                else:
                    # 同组多条账单（同还款日）：金额累加，due_date/days_until 一致无需更新
                    pass
                for amount_info in amounts:
                    # 去重：同一银行同一 label 下，金额+还款日完全相同视为重复账单
                    # （常见于原件 + Fw: 转发件内容一致，会导致金额翻倍）
                    is_dup = any(
                        d["amount"] == amount_info["value"] and d.get("due_date") == best_due_date
                        for d in upcoming[group_key]["details"]
                    )
                    if is_dup:
                        continue
                    upcoming[group_key]["total_amount"] += amount_info["value"]
                    upcoming[group_key]["details"].append({
                        "subject": bill["subject"],
                        "amount": amount_info["value"],
                        "due_date": best_due_date,
                        "days_until": best_days
                    })

        if not upcoming:
            return {"success": False, "message": "没有未来待还款账单"}

        # 账单级剔除：去掉用户已在滴答清单完成的旧账单（银行+邮箱+子账户+金额+还款日匹配），
        # 避免已还款的旧邮件金额污染新任务（如上月账单混进本月任务导致金额虚高）
        upcoming = self._filter_completed_amounts(upcoming)
        if not upcoming:
            return {"success": False, "message": "所有账单均已处理完成"}

        if dry_run:
            tasks = []
            for key, info in sorted(upcoming.items(), key=lambda x: x[1]["days_until"]):
                if info["total_amount"] > 0:
                    task = self._build_task(
                        info["bank_name"], info["total_amount"],
                        info["due_date"], info["days_until"],
                        info["details"],
                        source_label=info.get("source_label", ""),
                        sub_account=info.get("sub_account", "")
                    )
                    tasks.append(task)
            return {"success": True, "dry_run": True, "tasks": tasks, "count": len(tasks)}

        project_id = self.api.find_or_create_project(project_name)
        existing_tasks = self.api.get_project_tasks(project_id)

        # 主动清理旧格式任务：标题含"银行信用卡还款"或"¥+千分位逗号"的视为旧格式
        # 根因：新格式任务命中精确匹配后直接 continue，旧格式任务永远到不了 fuzzy 清理分支
        # 这里在所有匹配逻辑之前主动扫描并清理，确保新旧格式不会并存
        cleaned_legacy = self._cleanup_legacy_format_tasks(existing_tasks, project_id)
        if cleaned_legacy:
            # 清理后重新拉取一次，避免对已删除任务做后续匹配
            existing_tasks = self.api.get_project_tasks(project_id)

        existing_map = {t["title"]: t for t in existing_tasks}
        current_titles_set = set(existing_map.keys())

        # 模糊匹配索引：银行缩写 → [task]，用于标题格式变更后仍能匹配到旧任务
        # 避免重复创建任务（之前标题格式从"💳 浦发银行信用卡还款 ¥..."变成"💳 浦发 ... 元"
        # 导致精确匹配失败，旧任务残留并在午夜提醒）
        fuzzy_index = {}
        for t in existing_tasks:
            ttitle = t.get("title", "")
            for full, abbr in self.BANK_ABBR.items():
                if full in ttitle or abbr in ttitle:
                    fuzzy_index.setdefault(abbr, []).append(t)
                    break

        # 预先保留本轮将被「精确匹配」占用的任务 id：
        # 按还款日分组后同一银行可能有多个组（如平安逾期组 09-07 与未来组 10-07），
        # 每个组只能消费属于自己的任务。若不保留，处理顺序靠前的组（逾期组排最前）
        # 会把其他组的精确匹配任务模糊改名吞掉，导致两个组合并成一个错乱任务
        reserved_task_ids = set()
        for _info in upcoming.values():
            if _info["total_amount"] <= 0:
                continue
            _title = self._task_title(
                _info["bank_name"], _info["total_amount"],
                source_label=_info.get("source_label", ""),
                sub_account=_info.get("sub_account", "")
            )
            if _title in existing_map:
                reserved_task_ids.add(existing_map[_title]["id"])

        # 已完成感知：对比「上次同步时存在的标题」与「本次拉取到的标题」
        # 消失的标题 = 用户手动完成（或手动删除）→ 加入本地 completed_titles
        # 后续同步跳过这些标题，避免重建已完成的任务
        # （OpenAPI /project/{pid}/data 不返回 status=2 的任务，只能靠本地状态感知）
        completed_titles = self._load_completed_titles()
        newly_completed = self._detect_newly_completed(current_titles_set)
        if newly_completed:
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            completed_amounts = self._load_completed_amounts()
            for title, tc_info in newly_completed.items():
                if title not in completed_titles:
                    print(f"  ✓ 检测到用户已手动完成，跳过重建: {title}")
                    completed_titles[title] = now_str
                # 账单级记录：优先用 last_seen 里的结构化信息（含每笔金额+还款日），
                # 旧格式状态无 info 时从标题反解（无还款日，仅对过期账单生效）
                if tc_info and tc_info.get("details"):
                    for d in tc_info["details"]:
                        rec = {
                            "bank": tc_info.get("abbr") or self._bank_abbr(tc_info.get("bank_name", "")),
                            "label": tc_info.get("label", ""),
                            "sub_account": tc_info.get("sub_account", ""),
                            "amount": d["amount"],
                            "due_date": d.get("due_date"),
                            "title": title,
                            "completed_at": now_str
                        }
                        if not any(self._same_completed_record(r, rec) for r in completed_amounts):
                            completed_amounts.append(rec)
                else:
                    parsed = self._parse_task_title(title)
                    if parsed:
                        rec = {
                            "bank": parsed["abbr"],
                            "label": parsed["label"],
                            "sub_account": parsed["sub_account"],
                            "amount": parsed["amount"],
                            "due_date": None,
                            "title": title,
                            "completed_at": now_str
                        }
                        if not any(self._same_completed_record(r, rec) for r in completed_amounts):
                            completed_amounts.append(rec)
            self._save_completed_titles(completed_titles)
            self._save_completed_amounts(completed_amounts)
            # 日志留存：用户手动完成是账单生命周期的关键节点
            log_event("detect_completed", titles=sorted(newly_completed.keys()))

        created = []
        skipped = []
        updated = []
        skipped_completed = []
        # 已被 fuzzy 匹配消费的任务 id（防止拆分后的多个新任务同时更新同一个旧任务）
        consumed_task_ids = set()
        # 本次被系统重命名的旧标题（避免下次误判为"用户手动完成"）
        renamed_old_titles = []
        # 本次确认存在于滴答清单的任务：{title: 结构化info}（供下次同步检测用户完成 + 账单级记录）
        confirmed = {}

        def _confirm(task_title, group_info):
            confirmed[task_title] = {
                "bank_name": group_info["bank_name"],
                "abbr": self._bank_abbr(group_info["bank_name"]),
                "label": group_info.get("source_label", ""),
                "sub_account": group_info.get("sub_account", ""),
                "total_amount": group_info["total_amount"],
                "due_date": group_info["due_date"],
                "details": group_info["details"]
            }
        for key, info in sorted(upcoming.items(), key=lambda x: x[1]["days_until"]):
            if info["total_amount"] <= 0:
                continue

            bank_name = info["bank_name"]
            source_label = info.get("source_label", "")
            sub_account = info.get("sub_account", "")
            task = self._build_task(
                bank_name, info["total_amount"],
                info["due_date"], info["days_until"],
                info["details"],
                source_label=source_label,
                sub_account=sub_account
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
                    _confirm(task["title"], info)
                    log_event("update_task", bank=bank_name, title=task["title"],
                              due_date=task["due_date"], task_id=existing["id"])
                except Exception as e:
                    print(f"  Update failed for {bank_name}: {e}")
                    skipped.append({"bank": bank_name, "reason": f"更新失败: {e}"})
                continue

            # 模糊匹配：精确标题没匹配到时，按银行缩写找同银行的任务
            # 防止标题格式变更导致旧任务残留（午夜提醒 bug 的根因）
            bank_abbr = self._bank_abbr(bank_name)
            fuzzy_matches = [t for t in fuzzy_index.get(bank_abbr, [])
                             if t["title"] not in completed_titles
                             and t["id"] not in consumed_task_ids
                             # 已被其他组精确匹配保留的任务不可消费（防跨组吞任务）
                             and t["id"] not in reserved_task_ids
                             # label（邮箱）一致性：防止 YY 邮箱任务错配主邮箱任务（反之亦然）
                             and self._fuzzy_title_matches(t["title"], source_label, sub_account)]

            if fuzzy_matches:
                if len(fuzzy_matches) == 1:
                    # 恰好1个同银行任务：update它（包括标题、reminders、dueDate）
                    existing = fuzzy_matches[0]
                    consumed_task_ids.add(existing["id"])
                    renamed_old_titles.append(existing["title"])
                    try:
                        self.api.update_task(
                            existing["id"],
                            project_id=existing.get("projectId", project_id),
                            title=task["title"],
                            content=task["content"],
                            due_date=task["due_date"],
                            priority=task["priority"],
                            due_hour=task.get("due_hour", 11),
                            reminders=task["reminders"],
                            is_all_day=False
                        )
                        updated.append({"bank": bank_name, "task_id": existing["id"],
                                        "title": task["title"], "fuzzy": True})
                        _confirm(task["title"], info)
                        log_event("rename_task", bank=bank_name, old_title=existing["title"],
                                  new_title=task["title"], due_date=task["due_date"],
                                  task_id=existing["id"])
                        print(f"  ↻ 模糊匹配更新: {bank_name} 「{existing['title']}」→「{task['title']}」")
                    except Exception as e:
                        print(f"  Fuzzy update failed for {bank_name}: {e}")
                        skipped.append({"bank": bank_name, "reason": f"模糊匹配更新失败: {e}"})
                    continue
                else:
                    # 多个同银行任务（可能是不同卡/不同月份）：选金额最接近的更新
                    # 其余的如果标题看起来是旧格式，标记完成清理掉
                    import re as _re
                    def _extract_amount(title):
                        m = _re.search(r'[\d,]+\.?\d*', title.replace(',', ''))
                        return float(m.group()) if m else 0.0
                    target_amt = info["total_amount"]
                    best = min(fuzzy_matches, key=lambda t: abs(_extract_amount(t["title"]) - target_amt))
                    consumed_task_ids.add(best["id"])
                    renamed_old_titles.append(best["title"])
                    # 清理其他旧格式任务（标题含"银行信用卡还款"或"¥"的）
                    cleaned_duplicates = 0
                    for t in fuzzy_matches:
                        if t["id"] == best["id"]:
                            continue
                        if "银行信用卡还款" in t["title"] or "¥" in t["title"]:
                            try:
                                self.api.update_task(t["id"],
                                    project_id=t.get("projectId", project_id), status=2)
                                cleaned_duplicates += 1
                                log_event("complete_task", bank=bank_name, title=t["title"],
                                          reason="模糊匹配清理旧格式重复任务", task_id=t["id"])
                            except Exception:
                                pass
                    try:
                        self.api.update_task(
                            best["id"],
                            project_id=best.get("projectId", project_id),
                            title=task["title"],
                            content=task["content"],
                            due_date=task["due_date"],
                            priority=task["priority"],
                            due_hour=task.get("due_hour", 11),
                            reminders=task["reminders"],
                            is_all_day=False
                        )
                        updated.append({"bank": bank_name, "task_id": best["id"],
                                        "title": task["title"], "fuzzy": True})
                        _confirm(task["title"], info)
                        log_event("rename_task", bank=bank_name, old_title=best["title"],
                                  new_title=task["title"], due_date=task["due_date"],
                                  task_id=best["id"], cleaned_duplicates=cleaned_duplicates)
                        if cleaned_duplicates:
                            print(f"  ↻ 模糊匹配更新 + 清理{cleaned_duplicates}个旧任务: {bank_name}")
                    except Exception as e:
                        print(f"  Fuzzy update failed for {bank_name}: {e}")
                        skipped.append({"bank": bank_name, "reason": f"模糊匹配更新失败: {e}"})
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
                _confirm(task["title"], info)
                log_event("create_task", bank=bank_name, title=task["title"],
                          amount=info["total_amount"], due_date=task["due_date"],
                          task_id=result.get("id"))
            except Exception as e:
                created.append({"bank": bank_name, "error": str(e)})

        # 保存本次确认存在的任务（结构化）供下次同步对比；
        # renamed_old_titles 里是被系统重命名的旧标题，不在 confirmed 中，
        # 下次自然不会出现在 last_seen → 不会被误判为"用户手动完成"
        self._save_sync_state(created, skipped, confirmed)

        # 日志留存：本次同步摘要（推送到 GitHub，作为运行审计记录）
        log_event("sync_summary",
                  created=len([c for c in created if "error" not in c]),
                  updated=len(updated),
                  skipped=len(skipped),
                  skipped_completed=len(skipped_completed),
                  errors=len([c for c in created if "error" in c]),
                  legacy_cleaned=cleaned_legacy,
                  created_titles=[c["title"] for c in created if "error" not in c],
                  updated_titles=[u["title"] for u in updated])

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

    def _filter_completed_amounts(self, upcoming):
        """从聚合结果中剔除用户已完成的账单。

        匹配键：银行缩写 + 邮箱label + 子账户 + 金额 + 还款日。
        完成记录无还款日时（历史迁移数据），只对已过期的同额账单生效，
        避免误杀未来同金额的新账单（如车贷每月固定 2833.33）。
        """
        try:
            from datetime import timezone, timedelta as _td
            today = datetime.now(timezone(_td(hours=8))).date()
        except Exception:
            today = datetime.now().date()

        completed = self._load_completed_amounts()
        if not completed:
            return upcoming

        for key in list(upcoming.keys()):
            info = upcoming[key]
            abbr = self._bank_abbr(info["bank_name"])
            label = info.get("source_label") or ""
            sub_account = info.get("sub_account") or ""
            kept, removed = [], []
            for d in info["details"]:
                matched = False
                for c in completed:
                    if (c.get("bank") != abbr
                            or (c.get("label") or "") != label
                            or (c.get("sub_account") or "") != sub_account
                            or abs(float(c.get("amount", 0)) - d["amount"]) > 0.005):
                        continue
                    c_due = c.get("due_date")
                    if c_due:
                        if c_due == d.get("due_date"):
                            matched = True
                            break
                    else:
                        # 无还款日的历史记录：只剔除已过期的同额账单
                        try:
                            dd = datetime.strptime(str(d.get("due_date")), "%Y-%m-%d").date()
                            if dd < today:
                                matched = True
                                break
                        except Exception:
                            pass
                (removed if matched else kept).append(d)
            if removed:
                print(f"  ✓ 剔除已完成账单: {abbr}{sub_account}{' (' + label + ')' if label else ''} " +
                      "、".join(f"¥{d['amount']:.2f}({d.get('due_date')})" for d in removed))
            if kept:
                info["details"] = kept
                info["total_amount"] = sum(d["amount"] for d in kept)
                # 重算组还款日：取剩余账单中最接近今天的
                best = min(kept, key=lambda d: abs(d["days_until"]))
                info["due_date"] = best["due_date"]
                info["days_until"] = best["days_until"]
            else:
                del upcoming[key]
        return upcoming

    def _save_sync_state(self, created, skipped, confirmed_titles=None):
        """保存同步状态。confirmed_titles: {title: 结构化info}（本次确认存在于滴答清单的任务）"""
        state = {
            "last_sync": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "created_count": len(created),
            "skipped_count": len(skipped),
            "created_tasks": created,
            "last_seen_titles": confirmed_titles or {}
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

        返回 dict: {title: 结构化info or None}（旧格式 list 状态下 info 为 None）
        """
        state = self.load_sync_state()
        if not state:
            return {}
        last_seen = state.get("last_seen_titles", {})
        # 兼容旧格式（list[str]）
        if isinstance(last_seen, list):
            last_seen = {t: None for t in last_seen}
        if not last_seen:
            return {}
        disappeared = set(last_seen.keys()) - current_titles_set
        return {t: last_seen[t] for t in disappeared}

    def cleanup_old_tasks(self, project_name="信用卡还款"):
        """保留所有任务，不再自动删除逾期任务。

        逾期账单会一直保留在滴答清单里，直到用户手动勾选完成。
        用户完成后由 completed_titles.json 机制防止重建。
        此方法保留为兼容入口（daily_run.py 会调用），但不再做任何删除。
        """
        project_id = self.api.find_or_create_project(project_name)
        tasks = self.api.get_project_tasks(project_id)
        return {"deleted": 0, "remaining": len(tasks)}

    @staticmethod
    def _is_legacy_format_title(title):
        """判断任务标题是否为旧格式。

        旧格式特征（满足任一即视为旧格式）：
        1. 标题含"银行信用卡还款"（如 "💳 招商银行信用卡还款 ¥2,833.33"）
        2. 标题含"¥"且金额带千分位逗号（如 "💳 招行 ¥2,833.33"）

        新格式标准："💳 银行缩写 金额 元"（如 "💳 招行 2833.33 元"）
        """
        if not title:
            return False
        # 旧格式特征1：完整银行名 + "信用卡还款"
        if "银行信用卡还款" in title:
            return True
        # 旧格式特征2：含 ¥ 且金额带千分位逗号
        if "¥" in title and "," in title:
            return True
        return False

    def _cleanup_legacy_format_tasks(self, existing_tasks, project_id):
        """主动清理旧格式任务。

        策略：扫描 existing_tasks，对每个旧格式任务：
        - 若存在同银行的新格式任务（标题含银行缩写且不含旧格式特征）→ 删除旧格式任务
        - 若不存在新格式对应任务 → 跳过（避免丢失账单，打印警告）

        返回清理的任务数量。
        """
        legacy_tasks = [t for t in existing_tasks if self._is_legacy_format_title(t.get("title", ""))]
        if not legacy_tasks:
            return 0

        new_format_tasks = [t for t in existing_tasks if not self._is_legacy_format_title(t.get("title", ""))]
        # 按银行缩写索引新格式任务
        new_format_by_abbr = {}
        for t in new_format_tasks:
            ttitle = t.get("title", "")
            for full, abbr in self.BANK_ABBR.items():
                if full in ttitle or abbr in ttitle:
                    new_format_by_abbr.setdefault(abbr, []).append(t)
                    break

        cleaned = 0
        for legacy in legacy_tasks:
            legacy_title = legacy.get("title", "")
            # 找出旧格式任务对应的银行缩写
            legacy_abbr = None
            for full, abbr in self.BANK_ABBR.items():
                if full in legacy_title or abbr in legacy_title:
                    legacy_abbr = abbr
                    break

            if legacy_abbr is None:
                print(f"  ⚠ 旧格式任务无法识别银行，跳过: 「{legacy_title}」")
                continue

            # 检查是否存在同银行的新格式任务
            if legacy_abbr in new_format_by_abbr and new_format_by_abbr[legacy_abbr]:
                new_match = new_format_by_abbr[legacy_abbr][0]
                try:
                    self.api.delete_task(
                        legacy["id"],
                        project_id=legacy.get("projectId", project_id)
                    )
                    cleaned += 1
                    log_event("delete_task", bank=legacy_abbr, title=legacy_title,
                              reason="旧格式任务清理", task_id=legacy["id"],
                              kept=new_match.get("title", ""))
                    print(f"  🗑 清理旧格式任务: 「{legacy_title}」→ 保留 「{new_match.get('title', '')}」")
                except Exception as e:
                    print(f"  ✗ 清理失败: 「{legacy_title}」: {e}")
            else:
                # 无新格式对应：可能是这个银行本月有账单但 sync 还没创建新格式
                # 不删除，让正常 sync 流程通过 fuzzy 匹配把它转成新格式
                print(f"  ℹ 旧格式任务暂无新格式对应（等待 sync 转换）: 「{legacy_title}」")

        return cleaned


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
