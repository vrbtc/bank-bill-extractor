#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
WXpusher 微信推送模块
将滴答清单待办事项（银行还款账单等）推送到微信（WXpusher 通道）。

与 feishu_notify.py 平行设计：
- 同一数据源（ticktick_api.get_upcoming_tasks，拉取滴答清单全部项目待办）
- 同一分组逻辑（逾期 / 今日 / 明日 / 后天...）
- 同一时段守卫与上午/下午模式（由调用方 generate_dashboard.push_to_wxpusher 负责）

使用方法：
    from wxpusher_notify import WXPusherNotifier

    notifier = WXPusherNotifier()
    notifier.send_text("测试消息")                  # 纯文本
    notifier.send_today_tasks(days=4)              # 未来 4 天待办汇总

配置解析优先级（与 feishu_notify 一致）：
    1. 构造参数 app_token / uids
    2. 环境变量 WXPUSHER_APP_TOKEN / WXPUSHER_UIDS（多个 UID 用逗号分隔）
    3. config.json 的 wxpusher_app_token / wxpusher_uids 字段

config.json 示例：
    "wxpusher_app_token": "AT_xxxxxxxx",
    "wxpusher_uids": ["UID_安卓", "UID_苹果"],
    "wxpusher_enabled": false    # generate_dashboard 接入总开关，默认关闭

API 信息：
    POST https://wxpusher.zjiecode.com/api/send/message
    contentType: 1=文本, 2=HTML, 3=Markdown
    成功返回 code == 1000；data 数组中每个 UID 的 code == 0 表示该设备送达
"""

import json
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests

# 逾期推送分级：与飞书同一规则（过期 > 7 天的旧任务折叠为汇总行，不逐条提醒）
from feishu_notify import OVERDUE_NOTIFY_MAX_DAYS, split_overdue

API_URL = "https://wxpusher.zjiecode.com/api/send/message"

# 北京时区（UTC+8）
_BJ_TZ = timezone(timedelta(hours=8))


class WXPusherNotifier:
    def __init__(self, app_token=None, uids=None):
        self.app_token = app_token or self._resolve_app_token()
        if not self.app_token:
            raise ValueError(
                "WXpusher AppToken not found. "
                "Set environment variable WXPUSHER_APP_TOKEN or add "
                "'wxpusher_app_token' to config.json."
            )
        self.uids = self._resolve_uids(uids)
        if not self.uids:
            raise ValueError(
                "WXpusher UIDs not found. "
                "Set environment variable WXPUSHER_UIDS (comma separated) or add "
                "'wxpusher_uids' to config.json."
            )

    # ---------- 配置解析 ----------

    @staticmethod
    def _load_config():
        config_path = Path(__file__).parent / 'config.json'
        if config_path.exists():
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def _resolve_app_token(self):
        token = os.environ.get('WXPUSHER_APP_TOKEN', '').strip()
        if token:
            return token
        return self._load_config().get('wxpusher_app_token', '').strip()

    def _resolve_uids(self, uids):
        if uids:
            return [u.strip() for u in uids if u and u.strip()]
        env_uids = os.environ.get('WXPUSHER_UIDS', '').strip()
        if env_uids:
            return [u.strip() for u in env_uids.split(',') if u.strip()]
        cfg_uids = self._load_config().get('wxpusher_uids', [])
        if isinstance(cfg_uids, str):
            cfg_uids = [u.strip() for u in cfg_uids.split(',') if u.strip()]
        return [u.strip() for u in cfg_uids if u and str(u).strip()]

    # ---------- 核心发送 ----------

    def send_message(self, content, summary="", content_type=1, uids=None):
        """发送消息到 WXpusher（推送到微信）

        Args:
            content: 消息内容
            summary: 摘要标题（显示在微信通知栏）
            content_type: 1=文本, 2=HTML, 3=Markdown
            uids: 接收设备 UID 列表，默认发往配置的全部设备（安卓+苹果）

        Returns:
            dict: {"success": bool, "code": int, "msg": str, "records": [...]}
        """
        target_uids = [u.strip() for u in (uids or self.uids) if u and u.strip()]
        if not target_uids:
            raise ValueError("No target UIDs specified")

        payload = {
            "appToken": self.app_token,
            "content": content,
            "summary": summary,
            "contentType": content_type,
            "uids": target_uids,
        }
        resp = requests.post(
            API_URL,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=10,
        )
        resp.raise_for_status()
        result = resp.json()

        code = result.get("code")
        records = result.get("data") or []
        # WXpusher 成功码统一为 1000（顶层与每条设备记录相同）
        failed = [r for r in records if r.get("code") != 1000]
        success = (code == 1000) and not failed
        if not success:
            print(f"WXpusher 返回异常: {result}")
        return {
            "success": success,
            "code": code,
            "msg": result.get("msg", ""),
            "records": records,
            "failed": failed,
        }

    def send_text(self, content, summary="RBANK 提醒"):
        """发送纯文本消息（contentType=1）"""
        return self.send_message(content, summary=summary, content_type=1)

    def send_markdown(self, content, summary="RBANK 提醒"):
        """发送 Markdown 消息（contentType=3）"""
        return self.send_message(content, summary=summary, content_type=3)

    # ---------- 业务推送 ----------

    def send_today_tasks(self, days=1, dry_run=False):
        """推送滴答清单待办汇总到微信

        与 feishu_notify.FeishuNotifier.send_today_tasks 同一数据源与分组逻辑，
        格式改为微信友好的纯文本。

        Args:
            days: 未来天数（含今天）。days=1 仅今天+逾期（下午紧急提醒）；
                  days=4 = 今天+明天+后天+大后天（上午概览）
            dry_run: True 时只返回构建的 payload 不实际发送

        Returns:
            dict: send_message 的结果；dry_run 时为 {"success": True, "dry_run": True, "payload": {...}}
        """
        from ticktick_api import TickTickAPI

        now_bj = datetime.now(_BJ_TZ)
        today_str = now_bj.strftime("%Y-%m-%d")

        api = TickTickAPI()
        tasks = api.get_upcoming_tasks(days=days, include_overdue=True)

        if days <= 1:
            title_label = "今日待办提醒"
        else:
            title_label = f"未来 {days} 天待办提醒"

        # 分组：逾期 / 今天(offset=0) / 明天(1) / 后天(2) ...
        overdue = [t for t in tasks if t["is_overdue"]]
        by_offset = {}
        for t in tasks:
            if t["is_overdue"]:
                continue
            by_offset.setdefault(t["days_offset"], []).append(t)

        if not tasks:
            # 无未完成待办：不推送（2026-10-24 用户要求：当天没有未完成的待办就不要推送）
            summary = f"{title_label}·无待办"
            if dry_run:
                return {"success": True, "dry_run": True, "skipped": True,
                        "reason": "no_tasks",
                        "payload": {"content": f"📅 {today_str} {title_label}\n\n暂无待办事项",
                                    "summary": summary}}
            return {"skipped": True, "reason": "no_tasks",
                    "StatusMessage": "No tasks, skip push"}

        offset_label = {0: "今日", 1: "明日", 2: "后天", 3: "大后天"}
        lines = [f"📅 {title_label}（{today_str} 北京时间）", ""]

        if overdue:
            recent, older = split_overdue(overdue, today_str)
            lines.append(f"🔴 逾期未完成（{len(recent)} 项）")
            for t in recent:
                p_mark = {"5": "🔥", "3": "⚠️", "1": "📝"}.get(str(t["priority"]), "")
                lines.append(f"• {p_mark} {t['title']}（{t['project_name']}，应于 {t['due_date_bj']}）")
            if older:
                lines.append(
                    f"• 📦 另有 {len(older)} 项过期超过 {OVERDUE_NOTIFY_MAX_DAYS} 天的旧任务，已折叠不再逐条提醒"
                )
            lines.append("")

        for offset in sorted(by_offset.keys()):
            day_tasks = by_offset[offset]
            label = offset_label.get(offset, f"{offset} 天后")
            lines.append(f"📋 {label}到期（{len(day_tasks)} 项）")
            for t in day_tasks:
                p_mark = {"5": "🔥", "3": "⚠️", "1": "📝"}.get(str(t["priority"]), "")
                lines.append(f"• {p_mark} {t['title']}（{t['project_name']}）")
            lines.append("")

        today_count = len(by_offset.get(0, []))
        upcoming_count = sum(len(v) for k, v in by_offset.items() if k > 0)
        overdue_label = f"逾期 {len(overdue)}"
        if overdue:
            _, older_cnt = split_overdue(overdue, today_str)
            if older_cnt:
                overdue_label += f"（{len(older_cnt)} 项超 {OVERDUE_NOTIFY_MAX_DAYS} 天已折叠）"
        lines.append(f"共 {len(tasks)} 项待办（{overdue_label}，今日 {today_count}，"
                     f"未来 {upcoming_count}）")

        text = "\n".join(lines)
        summary = f"{title_label}·共 {len(tasks)} 项"

        if dry_run:
            return {"success": True, "dry_run": True,
                    "payload": {"content": text, "summary": summary,
                                "contentType": 1, "uids": self.uids}}
        return self.send_text(text, summary=summary)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="WXpusher 微信推送（RBANK）")
    parser.add_argument("--test", action="store_true", help="发送测试消息到全部设备")
    parser.add_argument("--days", type=int, default=1, help="推送未来 N 天待办（含今天，默认 1）")
    parser.add_argument("--dry-run", action="store_true", help="只构建 payload，不实际发送")
    args = parser.parse_args()

    notifier = WXPusherNotifier()

    if args.test:
        print("发送测试消息到微信（WXpusher）...")
        result = notifier.send_text(
            "✅ WXpusher 通道测试成功！RBANK 银行账单提醒已就绪。",
            summary="RBANK 通道测试")
        print(f"结果: {result}")
        print("✅ 测试完成" if result.get("success") else "❌ 测试失败")
    else:
        print(f"推送未来 {args.days} 天待办{'（dry-run）' if args.dry_run else ''}...")
        result = notifier.send_today_tasks(days=args.days, dry_run=args.dry_run)
        print(f"结果: {result}")
        print("✅ 完成" if result.get("success") else "❌ 失败")
