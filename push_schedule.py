#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
推送时段调度模块（2026-10-24 新增）

把「什么时候推送」从「云端什么时候运行」中解耦：
GitHub Actions cron 延迟不稳定（实测 3-5.5 小时），无法精确命中时刻。
因此按北京时间定义推送档位（slot），每次云端运行只判断自己落在哪个档位窗口，
同一档位同一渠道每天只推一次（跨运行去重），无待办时由各渠道 notifier 自行跳过。

档位表（北京时间，[start, end) 左闭右开）：
    morning    06:00-14:00  未来 4 天待办      （承接原有上午档：hour<14 推 days=4）
    afternoon  14:00-15:30  今日 + 逾期        （承接原有下午档）
    t1700      15:30-19:00  今日 + 逾期        （2026-10-24 新增：下午 17 点档）
    evening    19:00-21:30  今日 + 逾期        （承接原有晚间档）
    t2200      21:30-23:00  今日 + 逾期        （2026-10-24 新增：晚上 22 点档）

WXpusher 仅在 t1700 / t2200 两个档位推送（见 WXPUSHER_SLOTS）。

去重机制：推送成功后向 run_log.jsonl 写一条 event="push" 记录
（channel + slot + 日期）；already_pushed_today 扫描该日志判定。
云端每次运行后 deploy.yml 的「Commit run log」步骤会把 run_log.jsonl
commit 回 main，去重状态跨运行生效。
"""

import json
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path

_BJ_TZ = timezone(timedelta(hours=8))
SCRIPT_DIR = Path(__file__).parent

# 档位定义：start/end 为北京时间 HH:MM；days = 推送范围（未来 N 天，含今天+逾期）
PUSH_SLOTS = [
    {"id": "morning",   "start": "06:00", "end": "14:00", "days": 4, "label": "未来4天待办"},
    {"id": "afternoon", "start": "14:00", "end": "15:30", "days": 1, "label": "今日+逾期"},
    {"id": "t1700",     "start": "15:30", "end": "19:00", "days": 1, "label": "今日+逾期"},
    {"id": "evening",   "start": "19:00", "end": "21:30", "days": 1, "label": "今日+逾期"},
    {"id": "t2200",     "start": "21:30", "end": "23:00", "days": 1, "label": "今日+逾期"},
]

# WXpusher 允许推送的档位（用户要求：仅下午 17:00 与晚上 22:00）
WXPUSHER_SLOTS = ("t1700", "t2200")

# 本地兜底宽限期（分钟）：截止时间过后这么久之内仍可兜底。
# 覆盖看门狗周期（30 分钟）+ 任务服务抖动/睡眠唤醒延迟；
# 超过宽限期的旧档位不再补推——其内容（今日+逾期）与更新档位重复，补推只是噪音。
FALLBACK_GRACE_MIN = 90

# 本地兜底截止时间（北京时间 HH:MM）：
# 云端运行落在档位窗口内即推送；到截止时间该档位今天仍未推送
# （GitHub 延迟/跳过/堵塞），由本地看门狗 local_fallback.py 接管推送。
# 截止时间留足云端延迟余量（实测延迟 3-5.5 小时），同时不晚于人类合理接收时间。
SLOT_FALLBACK_DEADLINE = {
    "morning":   "09:00",   # 窗口 06:00-14:00，云端预期 ~07:05
    "afternoon": "16:30",   # 窗口 14:00-15:30，云端预期 ~14:55
    "t1700":     "18:30",   # 窗口 15:30-19:00，云端预期 ~15:00-17:30
    "evening":   "22:00",   # 窗口 19:00-21:30，云端预期 ~21:20
    "t2200":     "22:45",   # 窗口 21:30-23:00，云端预期 ~21:00-23:00
}


def _to_minutes(hhmm):
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def current_slot(now_bj=None):
    """返回当前北京时间落在的档位 dict；不在任何档位返回 None。

    Args:
        now_bj: 可选的 datetime（用于测试传固定时间）
    """
    now_bj = now_bj or datetime.now(_BJ_TZ)
    minutes = now_bj.hour * 60 + now_bj.minute
    for slot in PUSH_SLOTS:
        if _to_minutes(slot["start"]) <= minutes < _to_minutes(slot["end"]):
            return slot
    return None


def due_unpaid_slots(channel, now_bj=None, today_str=None, log_path=None,
                     allowed_slots=None, grace_min=None):
    """返回宽限期内已过兜底截止时间、且今天该渠道未推送过的档位列表（本地兜底用）。

    宽限期逻辑：只有 [截止时间, 截止时间 + grace_min) 内的档位才补推，
    避免把整晚漏推的旧档位一次性全部补推（消息轰炸）。

    Args:
        channel: 'feishu' 或 'wxpusher'
        now_bj: 可选的 datetime（测试传固定时间）
        today_str: 可选，默认今天（北京时间日期）
        log_path: 可选，测试用临时日志路径
        allowed_slots: 可选，限定档位 id 集合（如 WXPUSHER_SLOTS）
        grace_min: 可选，宽限期分钟数，默认 FALLBACK_GRACE_MIN

    Returns:
        list[dict]: 按 PUSH_SLOTS 顺序（=截止时间先后）排列的到期未推档位
    """
    grace_min = FALLBACK_GRACE_MIN if grace_min is None else grace_min
    now_bj = now_bj or datetime.now(_BJ_TZ)
    minutes = now_bj.hour * 60 + now_bj.minute
    due = []
    for slot in PUSH_SLOTS:
        deadline = SLOT_FALLBACK_DEADLINE.get(slot["id"])
        if not deadline:
            continue
        if allowed_slots is not None and slot["id"] not in allowed_slots:
            continue
        deadline_min = _to_minutes(deadline)
        if deadline_min <= minutes < deadline_min + grace_min:
            if not already_pushed_today(channel, slot["id"],
                                        today_str=today_str, log_path=log_path):
                due.append(slot)
    return due


def _log_path(log_path=None):
    return Path(log_path) if log_path else (SCRIPT_DIR / "run_log.jsonl")


def already_pushed_today(channel, slot_id, today_str=None, log_path=None):
    """同一 channel 同一 slot 今天是否已推送过（跨运行去重）。

    Args:
        channel: 'feishu' 或 'wxpusher'
        slot_id: 档位 id（morning/afternoon/t1700/evening/t2200）
        today_str: 可选，默认取今天（北京时间日期）
        log_path: 可选，测试用临时日志路径
    """
    today_str = today_str or datetime.now(_BJ_TZ).strftime("%Y-%m-%d")
    path = _log_path(log_path)
    if not path.exists():
        return False
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                if '"push"' not in line:
                    continue
                try:
                    rec = json.loads(line)
                except Exception:
                    continue
                if (rec.get("event") == "push"
                        and rec.get("channel") == channel
                        and rec.get("slot") == slot_id
                        and str(rec.get("ts", ""))[:10] == today_str):
                    return True
    except Exception:
        return False
    return False


def mark_pushed_today(channel, slot_id, log_path=None):
    """记录一次成功推送（供 already_pushed_today 去重）。"""
    rec = {
        "ts": datetime.now(_BJ_TZ).strftime("%Y-%m-%d %H:%M:%S"),
        "event": "push",
        "source": "github_actions" if os.environ.get("GITHUB_ACTIONS") == "true" else "local",
        "channel": channel,
        "slot": slot_id,
    }
    try:
        with open(_log_path(log_path), "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        return True
    except Exception:
        return False
