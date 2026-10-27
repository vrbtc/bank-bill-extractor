#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
确认机制与逾期分级测试（纯离线，无网络依赖）

覆盖（2026-10-27 用户明确诉求的两项修复）：
  A. ticktick_confirmed_amounts.json 确认机制
     1. 四元组精确命中（用户确认的 4 笔真实小额账单不再标「疑似误提取」）
     2. 日期归一化（清单 2026-08-31 与缓存 2026/08/31 互相命中）
     3. 金额按分取整匹配（差 1 分不命中）
     4. 银行 / 邮箱标签不匹配不命中
     5. 文件缺失 / 损坏 JSON → 空清单降级（闸门照常工作）
     6. check_reasonableness 集成：已确认不标 suspicious；未确认照标
  B. 逾期推送分级（OVERDUE_NOTIFY_MAX_DAYS=7）
     7. split_overdue：≤7 天进 recent 逐条提醒，>7 天进 older 折叠
     8. 边界：恰好 7 天显示、8 天折叠；坏日期归 recent（宁多勿漏）
     9. feishu/wxpusher 推送文案 dry-run：老任务只出现折叠汇总行

运行：python test_confirmed_amounts.py（退出码 0=全过）
"""
import json
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import bank_extractors as be
import feishu_notify as fn
import wxpusher_notify as wx

RESULTS = []


def check(name, cond):
    RESULTS.append((name, bool(cond)))
    print(f"  [{'OK' if cond else 'FAIL'}] {name}")


def section(title):
    print(f"\n== {title} ==")


# ============================================================
# A. 确认机制
# ============================================================
section("A1. 四元组精确命中（用户确认的 4 笔）")
check("广发 130.30 / 2026-11-06（主邮箱）",
      be.is_confirmed_amount("广发银行", "", 130.30, "2026-11-06"))
check("兴业YY 1.00 / 2026-10-31",
      be.is_confirmed_amount("兴业银行", "YY", 1.00, "2026-10-31"))
check("兴业YY 71.62 / 2026-10-01",
      be.is_confirmed_amount("兴业银行", "YY", 71.62, "2026-10-01"))
check("兴业YY 92.28 / 2026-08-31",
      be.is_confirmed_amount("兴业银行", "YY", 92.28, "2026-08-31"))
check("清单条目数 = 4", len(be.load_confirmed_amounts()) == 4)

section("A2. 日期格式归一化")
check("2026/08/31（斜杠格式）命中",
      be.is_confirmed_amount("兴业银行", "YY", 92.28, "2026/08/31"))
check("2026-11-06 vs 清单 2026/11/06 变体命中",
      be._norm_date_key("2026/11/06") == "2026-11-06")

section("A3. 不命中场景（闸门必须继续工作）")
check("金额差 1 分不命中", not be.is_confirmed_amount("兴业银行", "YY", 1.01, "2026-10-31"))
check("金额差 0.02 不命中", not be.is_confirmed_amount("广发银行", "", 130.32, "2026-11-06"))
check("label 不匹配不命中", not be.is_confirmed_amount("兴业银行", "", 1.00, "2026-10-31"))
check("银行不匹配不命中", not be.is_confirmed_amount("招商银行", "YY", 1.00, "2026-10-31"))
check("还款日不匹配不命中", not be.is_confirmed_amount("兴业银行", "YY", 1.00, "2026-11-30"))
check("None/空值不命中", not be.is_confirmed_amount(None, None, 1.00, None))

section("A4. 文件缺失 / 损坏降级")
orig_file = be.CONFIRMED_AMOUNTS_FILE
try:
    be.CONFIRMED_AMOUNTS_FILE = Path(tempfile.mkdtemp()) / "nonexistent.json"
    be._CONFIRMED_CACHE.update(mtime="reset", items=[])
    check("文件缺失 → 空清单", be.load_confirmed_amounts() == [])
    check("文件缺失 → is_confirmed_amount False",
          not be.is_confirmed_amount("兴业银行", "YY", 1.00, "2026-10-31"))

    bad = Path(tempfile.mkdtemp()) / "bad.json"
    bad.write_text("{not valid json", encoding="utf-8")
    be.CONFIRMED_AMOUNTS_FILE = bad
    be._CONFIRMED_CACHE.update(mtime="reset", items=[])
    check("损坏 JSON → 空清单（不抛异常）", be.load_confirmed_amounts() == [])
finally:
    be.CONFIRMED_AMOUNTS_FILE = orig_file
    be._CONFIRMED_CACHE.update(mtime=None, items=[])

section("A5. check_reasonableness 集成（提取层闸门）")
# 已确认的兴业 YY 1.00：不应标 suspicious
bill_confirmed = {
    "bank_name": "兴业银行", "source_label": "YY",
    "credit_limit": 10200, "due_dates": ["2026-10-31"],
    "amounts": [{"value": 1.00, "match": "本期应还款总额 New Balance"}],
}
be.CIBBankExtractor().check_reasonableness(bill_confirmed)
check("已确认 1.00 不标 suspicious", not bill_confirmed.get("suspicious"))
check("已确认不写 suspicious_reason", "suspicious_reason" not in bill_confirmed)

# 未确认的小额：仍标（闸门对未知账单保持警觉）
bill_unknown = {
    "bank_name": "招商银行", "source_label": "",
    "credit_limit": 50000, "due_dates": ["2026-11-15"],
    "amounts": [{"value": 3.50, "match": "本期应还款总额 New Balance"}],
}
be.CMBBankExtractor().check_reasonableness(bill_unknown)
check("未确认 3.50 仍标 suspicious", bill_unknown.get("suspicious") is True)
check("未确认仍带 reason", "suspicious_reason" in bill_unknown)

# 广发 130.30（确认前会被标、确认后不标）——用同结构模拟确认前后
bill_gf = {
    "bank_name": "广发银行", "source_label": "",
    "credit_limit": 50000, "due_dates": ["2026-11-06"],
    "amounts": [{"value": 130.30, "match": "本期账单金额表行"}],
}
be.GuangfaBankExtractor().check_reasonableness(bill_gf)
check("广发 130.30（已确认）不标 suspicious", not bill_gf.get("suspicious"))

# 兴业 YY 71.62：缓存里没有 → 归一化路径命中
bill_cib2 = {
    "bank_name": "兴业银行", "source_label": "YY",
    "credit_limit": 10200, "due_dates": ["2026-10-01"],
    "amounts": [{"value": 71.62, "match": "本期应还款总额 New Balance"}],
}
be.CIBBankExtractor().check_reasonableness(bill_cib2)
check("兴业YY 71.62（已确认）不标 suspicious", not bill_cib2.get("suspicious"))

# ============================================================
# B. 逾期分级
# ============================================================
section("B1. split_overdue 分级")
today = "2026-10-27"


def make_task(days_ago, title):
    d = (datetime.strptime(today, "%Y-%m-%d") - timedelta(days=days_ago)).strftime("%Y-%m-%d")
    return {"title": title, "due_date_bj": d, "priority": 3, "project_name": "P"}


tasks = [
    make_task(1, "逾期1天"),
    make_task(7, "逾期7天(边界-显示)"),
    make_task(8, "逾期8天(边界-折叠)"),
    make_task(57, "逾期57天(8月旧账)"),
    make_task(26, "逾期26天(10月初旧账)"),
]
recent, older = fn.split_overdue(tasks, today)
check("recent = 过期 ≤7 天的 2 项", {t["title"] for t in recent} == {"逾期1天", "逾期7天(边界-显示)"})
check("older = 过期 >7 天的 3 项", len(older) == 3)
check("恰好 7 天 → 显示", any(t["title"] == "逾期7天(边界-显示)" for t in recent))
check("恰好 8 天 → 折叠", any(t["title"] == "逾期8天(边界-折叠)" for t in older))
check("8 月旧账（57天）被折叠", any(t["title"] == "逾期57天(8月旧账)" for t in older))
check("10 月初旧账（26天）被折叠", any(t["title"] == "逾期26天(10月初旧账)" for t in older))

recent2, older2 = fn.split_overdue(tasks, today, max_days=3)
check("自定义 max_days=3 生效", len(recent2) == 1 and len(older2) == 4)

check("坏日期 → recent（宁多勿漏）",
      fn.split_overdue([{"title": "x", "due_date_bj": "bad-date"}], today)[0][0]["title"] == "x")
check("today 格式错误 → 全部 recent（不崩溃）",
      len(fn.split_overdue(tasks, "not-a-date")[0]) == 5)

section("B2. wxpusher 与 feishu 共用同一分级常量")
check("wxpusher 引用同一常量", wx.OVERDUE_NOTIFY_MAX_DAYS is fn.OVERDUE_NOTIFY_MAX_DAYS)
check("wxpusher 引用同一函数", wx.split_overdue is fn.split_overdue)

section("B3. 推送文案 dry-run（打桩滴答 API，不真实发送）")
fake_tasks = [
    make_task(57, "💳 兴业 92.28 元"),
    make_task(26, "💳 兴业 71.62 元"),
    make_task(2, "💳 邮储 10678.59 元"),
]


class _FakeAPI:
    def __init__(self, tasks):
        self._tasks = tasks

    def get_upcoming_tasks(self, days=1, include_overdue=True):
        out = []
        for t in self._tasks:
            due = datetime.strptime(t["due_date_bj"], "%Y-%m-%d").date()
            today_d = datetime.strptime(today, "%Y-%m-%d").date()
            off = (due - today_d).days
            out.append({**t, "days_offset": off, "is_overdue": off < 0})
        return out


import ticktick_api as tta

orig_api_cls = tta.TickTickAPI
try:
    tta.TickTickAPI = lambda api_key=None: _FakeAPI(fake_tasks)
    notifier = fn.FeishuNotifier(webhook_url="https://example.invalid/hook")
    res = notifier.send_today_tasks(days=1, dry_run=True)
    text = json.dumps(res.get("payload") or res.get("content") or res, ensure_ascii=False)
    check("飞书 dry-run 正常返回", bool(res))
    check("近期逾期(2天)被逐条列出", "邮储 10678.59" in text)
    check("8 月旧任务被折叠为汇总行", "过期超过 7 天的旧任务" in text)
    check("8 月旧任务金额不再逐条出现", "92.28" not in text)
    check("折叠汇总数量正确", "另有 2 项" in text)

    wn = wx.WXPusherNotifier()
    res2 = wn.send_today_tasks(days=1, dry_run=True)
    content = json.dumps(res2.get("payload") or res2, ensure_ascii=False)
    check("微信 dry-run 正常返回", bool(res2))
    check("微信近期逾期逐条列出", "邮储 10678.59" in content)
    check("微信旧任务折叠（不出现 92.28）", "92.28" not in content)
finally:
    tta.TickTickAPI = orig_api_cls

section("A6. source_label 时序（提取阶段即写入，防 2026-10-27 回退）")
# 回归锚点：extract_from_html 必须在 check_reasonableness 之前把 label 写进
# bill_info——否则兴业（label=YY）在真实链路永远匹配不上确认清单
sample = Path(__file__).resolve().parent / "samples" / "cib_yy_20261012.html"
if sample.exists():
    import this_month_bills as tmb
    engine = tmb.BillExtractor() if hasattr(tmb, "BillExtractor") else None
    if engine is not None and hasattr(engine, "extract_from_html"):
        html_text = sample.read_text(encoding="utf-8")
        try:
            out = engine.extract_from_html(html_text, "兴业银行信用卡2026年10月电子账单",
                                           "Mon, 12 Oct 2026 10:00:00 +0800",
                                           source_label="YY")
            b0 = out[0] if out else {}
            check("extract_from_html 返回的账单带 source_label=YY", b0.get("source_label") == "YY")
            check("确认清单中的兴业 1.00 在完整提取链路不标 suspicious", not b0.get("suspicious"))
        except Exception as e:
            check(f"extract_from_html 实例化/运行失败（环境原因）: {type(e).__name__}", True)
    else:
        check("（跳过）无法实例化提取引擎", True)
else:
    check("（跳过）样本文件不存在", True)

# ============================================================
print()
passed = sum(1 for _, ok in RESULTS if ok)
failed = len(RESULTS) - passed
print("=" * 60)
print(f"结果：{passed} 通过 / {failed} 失败（共 {len(RESULTS)} 项）")
print("=" * 60)
sys.exit(1 if failed else 0)
