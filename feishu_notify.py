#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
飞书群机器人推送模块
将当天到期的滴答清单待办事项（银行还款账单）推送到飞书群。

使用方法：
    from feishu_notify import FeishuNotifier

    notifier = FeishuNotifier(webhook_url="https://open.feishu.cn/open-apis/bot/v2/hook/xxx")
    notifier.send_bills_summary(bills_data)

环境变量：
    FEISHU_WEBHOOK_URL — 飞书自定义机器人 webhook 地址（也可通过参数传入）
"""

import json
import os
from datetime import datetime
from pathlib import Path

import requests


class FeishuNotifier:
    def __init__(self, webhook_url=None):
        self.webhook_url = webhook_url or os.environ.get("FEISHU_WEBHOOK_URL", "").strip()
        if not self.webhook_url:
            # 尝试从 config.json 读取
            config_path = Path(__file__).parent / 'config.json'
            if config_path.exists():
                try:
                    with open(config_path, 'r', encoding='utf-8') as f:
                        config = json.load(f)
                        self.webhook_url = config.get('feishu_webhook_url', '').strip()
                except Exception:
                    pass
        if not self.webhook_url:
            raise ValueError(
                "Feishu webhook URL not found. "
                "Set environment variable FEISHU_WEBHOOK_URL or add 'feishu_webhook_url' to config.json."
            )

    def _send(self, payload):
        """发送消息到飞书 webhook"""
        resp = requests.post(
            self.webhook_url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=10,
        )
        resp.raise_for_status()
        result = resp.json()
        if result.get("code", 0) != 0:
            raise RuntimeError(f"飞书返回错误: {result}")
        return result

    def send_text(self, text):
        """发送纯文本消息"""
        return self._send({
            "msg_type": "text",
            "content": {"text": text},
        })

    def send_bills_summary(self, bills_data):
        """推送银行账单待办汇总到飞书群

        Args:
            bills_data: dict，包含 "bills" 列表（来自 this_month_bills 的输出）
                        或包含 "all_bills" 列表（来自 generate_dashboard 的 data）

        Returns:
            dict: 飞书返回结果
        """
        today = datetime.now()
        today_str = today.strftime("%Y-%m-%d")

        # 兼容两种数据格式
        # 格式1: generate_dashboard 的 data（含 all_bills）
        # 格式2: this_month_bills 的输出（含 bills 原始数据）
        all_bills = bills_data.get("all_bills")
        if all_bills is None:
            all_bills = self._build_from_raw_bills(bills_data.get("bills", []))

        if not all_bills:
            return self.send_text(f"📅 {today_str} 银行账单提醒\n\n今日暂无待还款账单。")

        # 按紧急程度排序
        all_bills_sorted = sorted(all_bills, key=lambda x: x.get("days_until", 999))

        # 统计
        total_amount = sum(b.get("amount", 0) for b in all_bills_sorted)
        urgent_bills = [b for b in all_bills_sorted if b.get("days_until", 999) <= 3]
        today_bills = [b for b in all_bills_sorted if b.get("days_until", 999) == 0]

        # 构建富文本卡片消息
        elements = []

        # 标题
        elements.append({
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": f"**📅 银行账单还款提醒**\n{today_str}"
            }
        })

        # 分割线
        elements.append({"tag": "hr"})

        # 今日到期（如果有）
        if today_bills:
            lines = ["**🔴 今日到期（请立即还款）**"]
            for b in today_bills:
                lines.append(f"• {b['bank']}：¥{b['amount']:,.2f}（今天到期）")
            elements.append({
                "tag": "div",
                "text": {"tag": "lark_md", "content": "\n".join(lines)}
            })

        # 近期紧急（3天内，排除今天到期的）
        near_bills = [b for b in urgent_bills if b.get("days_until", 999) > 0]
        if near_bills:
            lines = ["**🟠 近期到期（3天内）**"]
            for b in near_bills:
                days_text = "明天到期" if b.get("days_until") == 1 else f"{b.get('days_until')}天后到期"
                lines.append(f"• {b['bank']}：¥{b['amount']:,.2f}（{days_text}，{b.get('due_date', '?')}）")
            elements.append({
                "tag": "div",
                "text": {"tag": "lark_md", "content": "\n".join(lines)}
            })

        # 全部待还款
        non_urgent = [b for b in all_bills_sorted if b.get("days_until", 999) > 3]
        if non_urgent:
            lines = [f"**📋 全部待还款（{len(all_bills_sorted)}家银行）**"]
            for b in non_urgent:
                lines.append(f"• {b['bank']}：¥{b['amount']:,.2f}（{b.get('days_until', '?')}天后，{b.get('due_date', '?')}）")
            elements.append({
                "tag": "div",
                "text": {"tag": "lark_md", "content": "\n".join(lines)}
            })

        # 汇总
        elements.append({"tag": "hr"})
        elements.append({
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": f"**💰 待还款总额：¥{total_amount:,.2f}**\n更新时间：{bills_data.get('generated_at', today_str)}"
            }
        })

        # 构建卡片
        payload = {
            "msg_type": "interactive",
            "card": {
                "header": {
                    "title": {
                        "tag": "plain_text",
                        "content": "🏦 银行账单还款提醒"
                    },
                    "template": "red" if today_bills else ("orange" if near_bills else "blue")
                },
                "elements": elements
            }
        }

        return self._send(payload)

    def _build_from_raw_bills(self, raw_bills):
        """从原始 bills 数据构建 all_bills 格式（兼容 this_month_bills 输出）"""
        from this_month_bills import get_upcoming_bills

        if not raw_bills:
            return []

        all_upcoming = get_upcoming_bills(raw_bills, days=None)
        result = []
        for bank_name, info in sorted(all_upcoming.items(),
                                       key=lambda x: x[1].get('earliest_due_date', {}).get('days_until', 999)
                                                       if x[1].get('earliest_due_date') else 999):
            if info['total_amount'] > 0 and info.get('earliest_due_date'):
                result.append({
                    'bank': bank_name,
                    'amount': info['total_amount'],
                    'due_date': info['earliest_due_date']['date'],
                    'days_until': info['earliest_due_date']['days_until'],
                })
        return result

    def send_today_tasks(self, api_key=None, days=1, dry_run=False):
        """推送代办事项汇总到飞书群（不限于账单）

        从滴答清单拉取所有项目中未来 `days` 天（含今天）到期 + 已逾期未完成的任务，
        按相对天数分组后推送一条卡片消息。

        Args:
            api_key: 滴答清单 API key（不传则从环境变量/config 读取）
            days: 未来天数（含今天）。days=1 仅今天+逾期（用于下午紧急提醒）；
                  days=3 = 今天+明天+后天+逾期（用于早上的未来3天概览）
            dry_run: True 时只返回构建的 payload 不实际发送（用于本地验证）

        Returns:
            dry_run=True 时返回 payload dict；否则返回飞书响应。
        """
        from ticktick_api import TickTickAPI
        from datetime import datetime, timezone, timedelta

        bj_tz = timezone(timedelta(hours=8))
        now_bj = datetime.now(bj_tz)
        today_str = now_bj.strftime("%Y-%m-%d")

        api = TickTickAPI(api_key=api_key)
        tasks = api.get_upcoming_tasks(days=days, include_overdue=True)

        # 标题与文案
        if days <= 1:
            title_label = "今日待办提醒"
            empty_text = f"📅 {today_str} 今日待办\n\n今日暂无待办事项，享受一天吧 ✨"
        else:
            end_date = (now_bj + timedelta(days=days - 1)).strftime("%Y-%m-%d")
            title_label = f"未来 {days} 天待办提醒"
            empty_text = f"📅 {today_str} ~ {end_date}\n\n未来 {days} 天暂无待办事项 ✨"

        if not tasks:
            # 无待办事项时不推送（避免无意义打扰）
            # 仅在日志中记录，不调用 _send()
            print(f"  ℹ️ 无待办事项，跳过推送（days={days}）")
            if dry_run:
                return {"skipped": True, "reason": "no_tasks", "msg_type": "text", "content": {"text": empty_text}}
            return {"skipped": True, "reason": "no_tasks", "StatusMessage": "No tasks, skip push"}

        # 分组：逾期 / 今天(offset=0) / 明天(1) / 后天(2) ...
        overdue = [t for t in tasks if t["is_overdue"]]
        by_offset = {}
        for t in tasks:
            if t["is_overdue"]:
                continue
            by_offset.setdefault(t["days_offset"], []).append(t)

        offset_label = {0: "今日", 1: "明日", 2: "后天", 3: "大后天"}
        date_by_offset = {off: (now_bj + timedelta(days=off)).strftime("%m-%d") for off in by_offset}

        elements = [{
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": f"**📅 {title_label}**\n{today_str}（北京时间）"
            }
        }, {"tag": "hr"}]

        # 逾期未完成
        if overdue:
            lines = [f"**🔴 逾期未完成（{len(overdue)} 项）**"]
            for t in overdue:
                p_mark = {"5": "🔥", "3": "⚠️", "1": "📝"}.get(str(t["priority"]), "")
                lines.append(f"• {p_mark} {t['title']}（{t['project_name']}，应于 {t['due_date_bj']}）")
            elements.append({"tag": "div", "text": {"tag": "lark_md", "content": "\n".join(lines)}})

        # 按天分组（今天、明天、后天...）
        for offset in sorted(by_offset.keys()):
            day_tasks = by_offset[offset]
            label = offset_label.get(offset, f"{offset}天后")
            date_str = date_by_offset[offset]
            lines = [f"**📋 {label}到期（{len(day_tasks)} 项 · {date_str}）**"]
            for t in day_tasks:
                p_mark = {"5": "🔥", "3": "⚠️", "1": "📝"}.get(str(t["priority"]), "")
                lines.append(f"• {p_mark} {t['title']}（{t['project_name']}）")
            elements.append({"tag": "div", "text": {"tag": "lark_md", "content": "\n".join(lines)}})

        # 汇总
        today_count = len(by_offset.get(0, []))
        upcoming_count = sum(len(v) for k, v in by_offset.items() if k > 0)
        elements.append({"tag": "hr"})
        elements.append({
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": f"**共 {len(tasks)} 项待办**（逾期 {len(overdue)}，今日 {today_count}，未来 {upcoming_count}）\n更新时间：{today_str}"
            }
        })

        payload = {
            "msg_type": "interactive",
            "card": {
                "header": {
                    "title": {"tag": "plain_text", "content": f"📅 {title_label}"},
                    "template": "red" if overdue else ("orange" if by_offset else "blue")
                },
                "elements": elements
            }
        }

        if dry_run:
            return payload
        return self._send(payload)


if __name__ == "__main__":
    import sys

    notifier = FeishuNotifier()

    # 测试消息
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        print("发送测试消息到飞书...")
        result = notifier.send_text("✅ 飞书机器人连接测试成功！银行账单提醒已就绪。")
        print(f"结果: {result}")
        print("✅ 测试完成")

    # 从数据文件推送
    elif len(sys.argv) > 1 and sys.argv[1] == "--push":
        data_file = None
        # 优先用 gh-pages/data.json（dashboard 格式）
        for candidate in ["gh-pages/data.json", "docs/bills.json", "this_month_bills.json"]:
            p = Path(candidate)
            if p.exists():
                data_file = p
                break

        if not data_file:
            print("❌ 未找到账单数据文件，请先运行 generate_dashboard.py")
            sys.exit(1)

        print(f"读取数据: {data_file}")
        with open(data_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        result = notifier.send_bills_summary(data)
        print(f"✅ 推送完成: {result}")

    else:
        print("用法:")
        print("  python feishu_notify.py --test    # 发送测试消息")
        print("  python feishu_notify.py --push    # 推送账单汇总")
