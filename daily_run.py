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


def run():
    log("=" * 60)
    log("每日账单自动查询 + 滴答清单同步 开始")

    sys.path.insert(0, str(SCRIPT_DIR))

    # Step 1: 刷新账单
    log("Step 1: 从邮箱获取最新账单...")
    try:
        from this_month_bills import BillExtractor, get_upcoming_bills

        extractor = BillExtractor()
        bills = extractor.fetch_and_extract(limit=50)

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

        data_file = SCRIPT_DIR / "this_month_bills.json"
        with open(data_file, "w", encoding="utf-8") as f:
            json.dump(data_to_save, f, ensure_ascii=False, indent=2)

        log(f"OK: 获取 {len(bills)} 封账单，待还总额 ¥{total_amount:,.2f}")
    except Exception as e:
        log(f"ERROR: 刷新账单失败 - {e}")
        traceback.print_exc()
        return False

    # Step 2: 检查紧急账单
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
            log(f"  OK: 创建 {result['total_created']} 个, 跳过 {result['total_skipped']} 个")
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

    log("每日账单自动查询 + 滴答清单同步 完成")
    log("=" * 60)
    return True


if __name__ == "__main__":
    rotate_log()
    success = run()
    sys.exit(0 if success else 1)
