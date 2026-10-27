#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
推送档位机制测试（2026-10-24 新增）

覆盖：
  1. 档位边界判定（北京时间各时刻 → 档位）
  2. 同日去重（同渠道同档位每天只推一次；跨天/换档位/换渠道不受限）
  3. 无待办跳过（打桩滴答 API 返回空 → 不发送）
  4. 全路径 dry-run（打桩档位，验证 generate_dashboard 两个推送函数的分支；
     不真实发送任何消息）
  5. WXpusher 渠道档位限制（仅 t1700/t2200）
  6. 本地兜底截止时间与到期未推判定（due_unpaid_slots）
  7. 指定档位直推（slot_id 参数，本地兜底路径）
  8. 看门狗在无 .git 目录拒绝运行（沙箱天然无 .git）

运行：
  "C:/Users/Administrator/.workbuddy/binaries/python/envs/default/Scripts/python.exe" test_push_schedule.py
"""

import json
import os
import sys
import tempfile
from contextlib import redirect_stdout
from datetime import datetime, timezone, timedelta
from io import StringIO
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))

BJ = timezone(timedelta(hours=8))


def _t(h, m=0):
    """固定时刻、日期取今天（北京时间）。

    日期必须与 mark_pushed_today() 写入的真实今天一致，
    否则同日去重查询会因日期不耦合而误失败（与运行日期无关）。
    """
    _today = datetime.now(BJ)
    return datetime(_today.year, _today.month, _today.day, h, m, tzinfo=BJ)


passed = failed = 0


def check(name, cond, detail=""):
    global passed, failed
    if cond:
        passed += 1
        print(f"  [OK] {name}")
    else:
        failed += 1
        print(f"  [FAIL] {name} {detail}")


from push_schedule import current_slot, already_pushed_today, mark_pushed_today, PUSH_SLOTS, WXPUSHER_SLOTS

print("== 1. 档位边界判定 ==")
cases = [
    ("02:30 不在档位", _t(2, 30), None),
    ("05:59 不在档位", _t(5, 59), None),
    ("06:00 → morning", _t(6, 0), "morning"),
    ("07:05 → morning", _t(7, 5), "morning"),
    ("13:59 → morning", _t(13, 59), "morning"),
    ("14:00 → afternoon", _t(14, 0), "afternoon"),
    ("14:55 → afternoon", _t(14, 55), "afternoon"),
    ("15:29 → afternoon", _t(15, 29), "afternoon"),
    ("15:30 → t1700", _t(15, 30), "t1700"),
    ("17:00 → t1700", _t(17, 0), "t1700"),
    ("18:59 → t1700", _t(18, 59), "t1700"),
    ("19:00 → evening", _t(19, 0), "evening"),
    ("21:20 → evening", _t(21, 20), "evening"),
    ("21:29 → evening", _t(21, 29), "evening"),
    ("21:30 → t2200", _t(21, 30), "t2200"),
    ("22:00 → t2200", _t(22, 0), "t2200"),
    ("22:59 → t2200", _t(22, 59), "t2200"),
    ("23:00 不在档位", _t(23, 0), None),
]
for name, now, expect in cases:
    slot = current_slot(now)
    got = slot["id"] if slot else None
    check(name, got == expect, f"期望 {expect} 实得 {got}")

print("== 2. 同日去重（临时日志，不碰真实 run_log.jsonl） ==")
tmp = Path(tempfile.mkdtemp()) / "run_log.jsonl"
# 动态取今天：mark_pushed_today() 写的是真实今天，查询基准必须与之耦合，
# 不能用硬编码历史日期（2026-10-24 当天跑能过是因为写入日=查询日）。
today = datetime.now(BJ).strftime("%Y-%m-%d")
check("初始未推送", already_pushed_today("feishu", "t1700", today_str=today, log_path=tmp) is False)
mark_pushed_today("feishu", "t1700", log_path=tmp)
check("标记后同档位已推送", already_pushed_today("feishu", "t1700", today_str=today, log_path=tmp) is True)
check("同渠道不同档位未推送", already_pushed_today("feishu", "t2200", today_str=today, log_path=tmp) is False)
check("同档位不同渠道未推送", already_pushed_today("wxpusher", "t1700", today_str=today, log_path=tmp) is False)
mark_pushed_today("wxpusher", "t2200", log_path=tmp)
check("wxpusher t2200 已推送", already_pushed_today("wxpusher", "t2200", today_str=today, log_path=tmp) is True)
# 非当天/跨天用相对日期（T-1 / T+1），与运行日期无关
check("非当天日期未推送",
      already_pushed_today("feishu", "t1700",
                           today_str=(datetime.now(BJ) - timedelta(days=1)).strftime("%Y-%m-%d"),
                           log_path=tmp) is False)
check("跨天可再推",
      already_pushed_today("feishu", "t1700",
                           today_str=(datetime.now(BJ) + timedelta(days=1)).strftime("%Y-%m-%d"),
                           log_path=tmp) is False)

print("== 3. 渠道档位限制 ==")
check("WXPUSHER_SLOTS 仅含 17/22 点档", set(WXPUSHER_SLOTS) == {"t1700", "t2200"})

print("== 4. 无待办跳过（打桩滴答 API 返回空，不发送） ==")
import ticktick_api
from wxpusher_notify import WXPusherNotifier

orig_get = ticktick_api.TickTickAPI.get_upcoming_tasks
ticktick_api.TickTickAPI.get_upcoming_tasks = lambda self, days=1, include_overdue=False: []
r = WXPusherNotifier().send_today_tasks(days=1, dry_run=False)
check("WXpusher 无待办→跳过不发送",
      r.get("skipped") is True and r.get("reason") == "no_tasks", f"实得 {r}")
r = WXPusherNotifier().send_today_tasks(days=1, dry_run=True)
check("WXpusher 无待办 dry-run 也标记 skipped", r.get("skipped") is True)
ticktick_api.TickTickAPI.get_upcoming_tasks = orig_get

print("== 5. 全路径 dry-run（打桩档位；不真实发送） ==")
import generate_dashboard as gd
import push_schedule as ps

cfg = json.loads((SCRIPT_DIR / "config.json").read_text(encoding="utf-8"))
os.environ["FEISHU_WEBHOOK_URL"] = cfg.get("feishu_webhook_url", "")
os.environ["TICKTICK_API_KEY"] = cfg.get("ticktick_api_key", "")

fake_slot = lambda sid: next(s for s in PUSH_SLOTS if s["id"] == sid)
orig_current = ps.current_slot
orig_already = ps.already_pushed_today


def run_push(fn, window_slot=None, already=False, **kwargs):
    """打桩档位窗口+去重状态，运行推送函数（dry-run），返回 (stdout, 是否抛异常)。

    window_slot: 打桩 current_slot() 的返回值（None = 不在任何窗口）；
                 slot_id  kwarg 走函数自身的指定档位参数，与本参数无关。
    """
    ps.current_slot = (lambda: fake_slot(window_slot)) if window_slot else (lambda: None)
    ps.already_pushed_today = lambda c, s, **kw: already
    buf = StringIO()
    err = None
    try:
        with redirect_stdout(buf):
            fn(**kwargs)
    except Exception as e:
        err = e
    finally:
        ps.current_slot = orig_current
        ps.already_pushed_today = orig_already
    return buf.getvalue(), err


# 5.1 飞书 t1700 档 dry-run：应进入发送分支（拉真实滴答数据构建 payload）
out, err = run_push(gd.push_to_feishu, "t1700", dry_run=True)
check("飞书 t1700 档 dry-run 无异常", err is None, f"异常: {err}")
check("飞书 t1700 档识别档位", "档位：t1700" in out, out[-300:])
check("飞书 t1700 档有推送结果", "Push result" in out or "无待办" in out, out[-300:])

# 5.2 飞书 morning 档 dry-run
out, err = run_push(gd.push_to_feishu, "morning", dry_run=True)
check("飞书 morning 档 dry-run 无异常", err is None, f"异常: {err}")
check("飞书 morning 档识别档位", "档位：morning" in out)

# 5.3 飞书 t2200 档 dry-run
out, err = run_push(gd.push_to_feishu, "t2200", dry_run=True)
check("飞书 t2200 档 dry-run 无异常", err is None, f"异常: {err}")
check("飞书 t2200 档识别档位", "档位：t2200" in out)

# 5.4 飞书不在档位（02:30）→ 跳过
out, err = run_push(gd.push_to_feishu, None, dry_run=True)
check("飞书无档位→跳过", "不在任何推送档位" in out and err is None)

# 5.5 飞书同档位已推送 → 跳过（防重复）
out, err = run_push(gd.push_to_feishu, "t1700", already=True, dry_run=True)
check("飞书同档位已推送→跳过", "已推送过" in out and err is None)

# 5.6 WXpusher t1700 档 dry-run（force 无视开关）→ 应发送分支
out, err = run_push(gd.push_to_wxpusher, "t1700", dry_run=True, force=True)
check("WXpusher t1700 档 dry-run 无异常", err is None, f"异常: {err}")
check("WXpusher t1700 档识别档位", "档位：t1700" in out, out[-300:])
check("WXpusher t1700 档有结果或跳过无待办", "WXpusher result" in out or "无待办" in out, out[-300:])

# 5.7 WXpusher t2200 档 dry-run
out, err = run_push(gd.push_to_wxpusher, "t2200", dry_run=True, force=True)
check("WXpusher t2200 档 dry-run 无异常", err is None, f"异常: {err}")
check("WXpusher t2200 档识别档位", "档位：t2200" in out)

# 5.8 WXpusher morning 档 → 跳过（仅 17/22 点档）
out, err = run_push(gd.push_to_wxpusher, "morning", dry_run=True, force=True)
check("WXpusher morning 档→跳过", "仅 17:00/22:00 档" in out and err is None)

# 5.9 WXpusher afternoon 档 → 跳过
out, err = run_push(gd.push_to_wxpusher, "afternoon", dry_run=True, force=True)
check("WXpusher afternoon 档→跳过", "仅 17:00/22:00 档" in out and err is None)

# 5.10 WXpusher evening 档 → 跳过
out, err = run_push(gd.push_to_wxpusher, "evening", dry_run=True, force=True)
check("WXpusher evening 档→跳过", "仅 17:00/22:00 档" in out and err is None)

# 5.11 WXpusher 同档位已推送 → 跳过
out, err = run_push(gd.push_to_wxpusher, "t2200", already=True, dry_run=True, force=True)
check("WXpusher 同档位已推送→跳过", "已推送过" in out and err is None)

# 5.12 WXpusher 无档位 → 跳过
out, err = run_push(gd.push_to_wxpusher, None, dry_run=True, force=True)
check("WXpusher 无档位→跳过", "不在推送档位" in out and err is None)

# 5.13 WXpusher 开关关闭 → 跳过（不打桩档位，走真实 config）
out, err = run_push(gd.push_to_wxpusher, "t1700", dry_run=True, force=False)
check("WXpusher 开关关闭→跳过", "wxpusher_enabled not set" in out and err is None)

print("== 6. 本地兜底：宽限期 + 截止时间 + 到期未推判定 ==")
from push_schedule import due_unpaid_slots, SLOT_FALLBACK_DEADLINE, FALLBACK_GRACE_MIN

tmp2 = Path(tempfile.mkdtemp()) / "run_log.jsonl"
# T 与 mark_pushed_today() 写入的真实今天耦合（动态取今天，与运行日期无关）
T = datetime.now(BJ).strftime("%Y-%m-%d")


def slot_ids(lst):
    return [s["id"] for s in lst]


def feishu_due(hh, mm=0):
    return slot_ids(due_unpaid_slots("feishu", now_bj=_t(hh, mm), today_str=T, log_path=tmp2))


check("宽限期默认 90 分钟", FALLBACK_GRACE_MIN == 90)
# 截止时间未到 → 不兜底
check("08:00 无档位到期（截止未到）", feishu_due(8, 0) == [])
check("16:00 无档位到期（截止未到）", feishu_due(16, 0) == [])
# 截止刚到 → 兜底
check("09:00 morning 到期", feishu_due(9, 0) == ["morning"])
check("16:30 afternoon 到期", feishu_due(16, 30) == ["afternoon"])
check("18:30 t1700 到期（afternoon 已过宽限期不补）", feishu_due(18, 30) == ["t1700"])
# 宽限期内仍可补
check("10:29 morning 仍在宽限期", feishu_due(10, 29) == ["morning"])
check("17:59 afternoon 仍在宽限期", feishu_due(17, 59) == ["afternoon"])
# 宽限期已过 → 不再补（防消息轰炸）
check("10:30 morning 宽限期已过不补", feishu_due(10, 30) == [])
check("18:00 afternoon 宽限期已过不补", feishu_due(18, 0) == [])
# 晚间两档位接近：22:50 时 evening 与 t2200 都在宽限期内
check("22:50 evening+t2200 均在宽限期", feishu_due(22, 50) == ["evening", "t2200"])
check("23:30 仅 t2200 仍在宽限期", feishu_due(23, 30) == ["t2200"])
# 已推送的档位不兜底
mark_pushed_today("feishu", "morning", log_path=tmp2)
check("morning 已推后到期不补", feishu_due(9, 0) == [])
mark_pushed_today("feishu", "evening", log_path=tmp2)
check("evening 已推后 22:50 仅剩 t2200", feishu_due(22, 50) == ["t2200"])
# WXpusher 仅两个档位参与兜底
tmp3 = Path(tempfile.mkdtemp()) / "run_log.jsonl"


def wx_due(hh, mm=0):
    return slot_ids(due_unpaid_slots("wxpusher", now_bj=_t(hh, mm), today_str=T,
                                     log_path=tmp3, allowed_slots=WXPUSHER_SLOTS))


check("WXpusher 09:00 无档位到期", wx_due(9, 0) == [])
check("WXpusher 18:30 仅 t1700 到期", wx_due(18, 30) == ["t1700"])
check("WXpusher 23:30 仅 t2200 到期", wx_due(23, 30) == ["t2200"])

print("== 6b. 看门狗每次只补最晚的一个档位 ==")
import local_fallback as lf

check("空列表 → None", lf.latest_slot([]) is None)
_due = due_unpaid_slots("feishu", now_bj=_t(22, 50), today_str=T, log_path=tmp3)
check("22:50 双档位到期 → 取最晚 t2200", lf.latest_slot(_due)["id"] == "t2200")
_due2 = due_unpaid_slots("feishu", now_bj=_t(18, 30), today_str=T, log_path=tmp3)
check("18:30 单档位到期 → t1700", lf.latest_slot(_due2)["id"] == "t1700")

print("== 7. 指定档位直推（本地兜底路径，dry-run） ==")
out, err = run_push(gd.push_to_feishu, None, dry_run=True, slot_id="t1700")
check("飞书 slot_id=t1700 直推无异常", err is None, f"异常: {err}")
check("飞书 slot_id 识别档位", "档位：t1700" in out)
out, err = run_push(gd.push_to_wxpusher, None, dry_run=True, force=True, slot_id="t2200")
check("WXpusher slot_id=t2200 直推无异常", err is None, f"异常: {err}")
check("WXpusher slot_id 识别档位", "档位：t2200" in out)
out, err = run_push(gd.push_to_wxpusher, None, dry_run=True, force=True, slot_id="morning")
check("WXpusher slot_id=morning 被拒（非允许档位）", "仅 17:00/22:00 档" in out and err is None)

print("== 8. 看门狗在无 .git 目录拒绝运行（沙箱天然无 .git） ==")
import subprocess as _sp

r = _sp.run([sys.executable, "local_fallback.py", "--dry-run"],
            cwd=str(SCRIPT_DIR), capture_output=True, text=True, timeout=120)
combined = (r.stdout or "") + (r.stderr or "")
check("看门狗无 .git → 拒绝兜底", "无 .git" in combined and r.returncode == 0, combined[-200:])
r2 = _sp.run([sys.executable, "local_fallback.py", "--status"],
             cwd=str(SCRIPT_DIR), capture_output=True, text=True, timeout=120)
check("看门狗 --status 正常输出", r2.returncode == 0 and "档位" in (r2.stdout or ""),
      (r2.stdout or "")[-200:])
# 清理看门狗测试日志
_lf = SCRIPT_DIR / "local_fallback.log"
if _lf.exists():
    _lf.unlink()

print()
print(f"===== 结果: {passed} 通过 / {failed} 失败 =====")
sys.exit(1 if failed else 0)
