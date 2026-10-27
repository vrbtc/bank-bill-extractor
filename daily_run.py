#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import sys
import os
import traceback
from datetime import datetime, timezone, timedelta
from pathlib import Path

# 北京时区
_BJ_TZ = timezone(timedelta(hours=8))

SCRIPT_DIR = Path(__file__).parent
LOG_FILE = SCRIPT_DIR / "daily_run.log"


def log(msg):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {msg}"
    print(line)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def rotate_log(max_lines=500):
    if not LOG_FILE.exists():
        return
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()
    if len(lines) > max_lines:
        with open(LOG_FILE, "w", encoding="utf-8") as f:
            f.writelines(lines[-max_lines:])


def _log_quality_alerts(alerts):
    """把提取质量告警逐条写进日志（P0-1：失败不再静默）。"""
    for f in alerts.get('extraction_failures', []):
        label = f" ({f['label']})" if f.get('label') else ''
        log(f"ERROR: 待人工提取 - {f['bank']}{label} 「{f['subject']}」 "
            f"邮件 {f['date']} 还款日 {f['due_dates']} - {f['reason']}")
    for s in alerts.get('suspicious', []):
        label = f" ({s['label']})" if s.get('label') else ''
        log(f"WARN: 疑似误提取 - {s['bank']}{label} 金额 {s['amounts']} - {s['reason']}")
    for n in alerts.get('needs_review', []):
        label = f" ({n['label']})" if n.get('label') else ''
        log(f"WARN: 还款日缺失待确认 - {n['bank']}{label} 金额 {n['amounts']} - {n['reason']}")
    for e in alerts.get('email_failures', []):
        log(f"ERROR: 邮箱拉取失败 - {e['email']} ({e.get('label', '')}) - {e['error']}")
    for u in alerts.get('unrecognized_subjects', []):
        log(f"WARN: 非已知账单主题（未入链）- {u.get('subject', '')} ({u.get('date', '')})")
    for a in alerts.get('attachment_bills', []):
        label = f" ({a['label']})" if a.get('label') else ''
        log(f"INFO: 附件型历史账单回执（已抑制告警，不推飞书）- {a['bank']}{label} "
            f"「{a['subject']}」 邮件 {a['date']} - {a['reason']}")
        try:
            from run_logger import log_event
            log_event("attachment_bill_suppressed", bank=a['bank'],
                      label=a.get('label', ''), subject=a['subject'],
                      date=a.get('date', ''), reason=a['reason'],
                      attachments=a.get('attachments', []))
        except Exception:
            pass


def _push_quality_alerts(alerts):
    """cloud 角色：经飞书推送「待人工提取」告警卡片。失败不影响主流程。"""
    if not (alerts.get('extraction_failures') or alerts.get('suspicious')
            or alerts.get('needs_review') or alerts.get('email_failures')):
        return
    try:
        from feishu_notify import FeishuNotifier
        notifier = FeishuNotifier()
        result = notifier.send_extraction_alerts(
            failures=alerts.get('extraction_failures'),
            suspicious=alerts.get('suspicious'),
            needs_review=alerts.get('needs_review'),
            email_errors=alerts.get('email_failures'),
        )
        if isinstance(result, dict) and result.get('skipped'):
            log(f"  告警卡片未推送（{result.get('reason', 'skipped')}）")
        else:
            log("  OK: 提取告警卡片已推送飞书")
    except Exception as e:
        log(f"WARN: 提取告警卡片推送失败 - {e}")


def run():
    log("=" * 60)
    log("每日账单自动查询 + 滴答清单同步 开始")

    sys.path.insert(0, str(SCRIPT_DIR))

    # 运行角色（P0-7 云端优先）：local 只提取+刷缓存，不写滴答不推飞书
    from config import get_run_role
    role = get_run_role()
    log(f"运行角色: {role}")

    # 供结束时写 run_summary 日志（留存到 GitHub）
    bills_count = 0
    upcoming_total = 0.0
    sync_created = None
    sync_updated = None
    alerts = {}

    # Step 1: 刷新账单
    log("Step 1: 从邮箱获取最新账单...")
    try:
        from this_month_bills import (
            BillExtractor, get_upcoming_bills, get_overdue_bills,
            collect_quality_alerts,
        )

        extractor = BillExtractor()
        bills = extractor.fetch_and_extract(limit=100)

        if bills is None:
            log("ERROR: 无法获取账单数据")
            return False

        upcoming = get_upcoming_bills(bills, days=None)
        total_amount = sum(info["total_amount"] for _, info in upcoming.items())

        data_to_save = {
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "total_bills": len(bills),
            "upcoming_total": total_amount,
            "bills": bills,
        }

        # 提取质量告警（P0-1/P0-2/P0-3/P0-4）：失败/可疑/待确认/邮箱故障
        alerts = collect_quality_alerts(
            bills,
            email_failures=extractor.email_failures,
            unrecognized=extractor.unrecognized_subjects,
        )
        data_to_save["extraction_alerts"] = alerts
        _log_quality_alerts(alerts)

        # 超过宽限期未确认账单（P0-6）：报表可见，需人工核实是否已还
        overdue = get_overdue_bills(bills)
        overdue_rows = [(k, i) for k, i in overdue.items()
                        if i["total_amount"] > 0 and i.get("earliest_due_date")]
        if overdue_rows:
            overdue_rows.sort(key=lambda x: x[1]["earliest_due_date"]["days_until"])
            log(f"WARN: {len(overdue_rows)} 组账单超过 3 天宽限期未确认"
                f"（合计 ¥{sum(i['total_amount'] for _, i in overdue_rows):,.2f}，需人工核实是否已还）：")
            for _, info in overdue_rows:
                label = f" ({info['source_label']})" if info['source_label'] else ''
                log(f"  OVERDUE: {info['bank_name']}{label} "
                    f"¥{info['total_amount']:,.2f} 还款日 {info['earliest_due_date']['date']}"
                    f"（已超期 {-info['earliest_due_date']['days_until']} 天）")

        data_file = SCRIPT_DIR / "this_month_bills.json"
        with open(data_file, "w", encoding="utf-8") as f:
            json.dump(data_to_save, f, ensure_ascii=False, indent=2)

        log(f"OK: 获取 {len(bills)} 封账单，待还总额 ¥{total_amount:,.2f}")
        bills_count = len(bills)
        upcoming_total = total_amount
    except Exception as e:
        log(f"ERROR: 刷新账单失败 - {e}")
        traceback.print_exc()
        return False

    # Step 2: 检查紧急账单（只读缓存，两个角色都执行）
    log("Step 2: 检查紧急账单...")
    try:
        from bill_skill import BillSkill

        skill = BillSkill(
            config_path=str(SCRIPT_DIR / "config.json"),
            data_path=str(SCRIPT_DIR / "this_month_bills.json"),
        )
        urgent = skill.check_urgent(days=3)
        if urgent:
            for bill in urgent:
                log(f"  URGENT: {bill['bank']} ¥{bill['amount']:,.2f} ({bill['days']}天后到期)")
        else:
            log("  OK: 无紧急账单")
    except Exception as e:
        log(f"WARN: 紧急检查失败 - {e}")

    if role != 'cloud':
        # P0-7：local 角色不写滴答、不推飞书（云端优先，避免双写重建已还任务）
        log("Step 3/4: local 角色跳过滴答同步与飞书推送（云端优先，由 deploy.yml 负责）")
        log("  提取告警已写入日志，待云端运行推送飞书卡片")
        _finish(bills_count, upcoming_total, sync_created, sync_updated, alerts)
        return True

    # Step 3: 同步到滴答清单
    log("Step 3: 同步到滴答清单...")
    try:
        from ticktick_sync import TickTickSync

        sync = TickTickSync()

        # 先清理过期任务
        cleanup = sync.cleanup_old_tasks()
        log(f"  清理过期任务: 删除 {cleanup['deleted']} 个")

        # 同步新账单
        result = sync.sync_bills(data_to_save)
        if result["success"]:
            sync_created = result.get("total_created", 0)
            sync_updated = result.get("total_updated", 0)
            log(f"  OK: 创建 {result['total_created']} 个, 跳过 {result['total_skipped']} 个, 更新 {result.get('total_updated', 0)} 个")
            for c in result.get("created", []):
                if "error" not in c:
                    log(f"    + {c['title']}")
                else:
                    log(f"    ! {c['bank']}: {c['error']}")
        else:
            log(f"  WARN: 同步失败 - {result.get('message', '未知错误')}")
    except Exception as e:
        log(f"WARN: 滴答清单同步失败 - {e}")
        traceback.print_exc()

    # Step 4: 推送代办到飞书群（不限于账单）
    # 按北京时间小时区分：上午(<14)推未来3天，下午(>=14)推今日+逾期
    log("Step 4: 推送代办到飞书群...")
    try:
        from feishu_notify import FeishuNotifier

        notifier = FeishuNotifier()
        hour_bj = datetime.now(_BJ_TZ).hour
        if hour_bj < 14:
            days = 4
            log(f"  模式：上午（北京 {hour_bj} 时）→ 未来 4 天待办")
        else:
            days = 1
            log(f"  模式：下午（北京 {hour_bj} 时）→ 今日 + 逾期紧急提醒")
        result = notifier.send_today_tasks(days=days)
        log(f"  OK: 飞书推送成功 - {result.get('StatusMessage', 'done')}")
    except Exception as e:
        log(f"WARN: 飞书推送失败 - {e}")
        traceback.print_exc()

    # Step 5: 提取质量告警卡片（P0-1：待人工提取/疑似误提取/还款日缺失/邮箱故障）
    log("Step 5: 推送提取质量告警...")
    _push_quality_alerts(alerts)

    log("每日账单自动查询 + 滴答清单同步 完成")
    log("=" * 60)

    _finish(bills_count, upcoming_total, sync_created, sync_updated, alerts)
    return True


def _finish(bills_count, upcoming_total, sync_created, sync_updated, alerts):
    """运行摘要留存到 run_log.jsonl（由 auto-sync 自动推送 GitHub）"""
    try:
        from run_logger import log_event
        log_event("run_summary", runner="daily_run",
                  bills=bills_count, upcoming_total=upcoming_total,
                  sync_created=sync_created, sync_updated=sync_updated,
                  extract_failures=len(alerts.get("extraction_failures", [])),
                  suspicious=len(alerts.get("suspicious", [])),
                  needs_review=len(alerts.get("needs_review", [])),
                  email_failures=len(alerts.get("email_failures", [])))
    except Exception:
        pass


if __name__ == "__main__":
    rotate_log()
    success = run()
    sys.exit(0 if success else 1)
