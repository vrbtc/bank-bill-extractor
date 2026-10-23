#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""失败邮件样本转储工具（只读 IMAP）。

按「银行 + 邮箱 label + 邮件日期」把失败账单邮件的原文 HTML 导出到
samples/ 目录，供提取规则修复做离线分析（P0-1 的前置输入）。

安全性：
- 只读：仅 IMAP SELECT/SEARCH/FETCH，不写邮箱、不删邮件；
- 样本只存邮件内容（HTML + 元信息），不存任何凭据；
- samples/ 已在 .gitignore 中排除，不会提交含金额的邮件原文。

用法：
    python scripts/dump_failed_samples.py            # 导出全部目标样本
    python scripts/dump_failed_samples.py --list     # 只列出匹配到的邮件，不落盘
"""

import argparse
import email
import json
import sys
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_DIR))

from config import get_all_emails  # noqa: E402
from email_client import EmailClient  # noqa: E402
from email_decoder import EmailDecoder  # noqa: E402

SAMPLES_DIR = PROJECT_DIR / "samples"
FETCH_LIMIT = 200  # 覆盖回翻到 7 月的邮件（QQ 邮箱总量较小，200 足够）

# 目标样本清单：(文件名, label, 主题关键字, 邮件日期串用于精确匹配)
# 日期串与审计 raw JSON 中 extract_failures 的 Date 头一致
TARGETS = [
    ("changan_yy_20261021.html", "YY", "长安银行信用卡电子账单", "Wed, 21 Oct 2026 09:38:43"),
    ("changan_yy_20260821.html", "YY", "长安银行信用卡电子账单", "Fri, 21 Aug 2026 09:33:03"),
    # 7/22 同日两封：08:44:24 这封提取失败（另一封 08:44:23 成功），按时间区分
    ("changan_yy_20260722_fail.html", "YY", "长安银行信用卡电子账单", "Wed, 22 Jul 2026 08:44:24"),
    ("ccb_yy_20260919.html", "YY", "中国建设银行信用卡电子账单", "Sat, 19 Sep 2026 20:24:31"),
    ("ccb_yy_20260819.html", "YY", "中国建设银行信用卡电子账单", "Wed, 19 Aug 2026 19:51:20"),
    # 兴业YY 10/12：坐实 ¥1.00 误提取（模式3 无界跨全文）
    ("cib_yy_20261012.html", "YY", "兴业银行信用卡2026年10月电子账单", "Mon, 12 Oct 2026 15:38:29"),
]


def _extract_html_body(msg, decoder):
    """取第一个 text/html part 的内容（与 this_month_bills 逻辑一致）。"""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == 'text/html':
                return decoder.decode_html_content(part)
    else:
        try:
            if msg.get_content_type() == 'text/html':
                return decoder.decode_html_content(msg)
        except Exception:
            pass
    return ""


def dump(list_only=False):
    SAMPLES_DIR.mkdir(exist_ok=True)
    decoder = EmailDecoder()
    emails_config = get_all_emails()
    if not emails_config:
        print("未配置任何邮箱（config.json / 环境变量）")
        return 1

    # label -> 邮箱配置
    by_label = {em.get('label', ''): em for em in emails_config}
    manifest = []
    remaining = list(TARGETS)

    for label in sorted({t[1] for t in TARGETS}):
        em_cfg = by_label.get(label)
        if not em_cfg:
            print(f"⚠️ 未找到 label={label!r} 的邮箱配置，跳过")
            continue
        print(f"\n--- 连接邮箱 {em_cfg['address']} (label={label}) ---")
        client = EmailClient(
            em_cfg['imap_server'], em_cfg['imap_port'],
            em_cfg['address'], em_cfg['password'],
        )
        client.connect()
        try:
            emails = client.fetch_emails(limit=FETCH_LIMIT)
            print(f"拉取 {len(emails)} 封邮件，开始匹配目标样本...")
            for msg in emails:
                subject = decoder.decode_mime_words(msg.get('Subject', ''))
                date = decoder.decode_mime_words(msg.get('Date', ''))
                for target in list(remaining):
                    fname, t_label, t_subject_kw, t_date_prefix = target
                    if t_label != label:
                        continue
                    if t_subject_kw not in subject:
                        continue
                    if not date.startswith(t_date_prefix):
                        continue
                    html_body = _extract_html_body(msg, decoder)
                    print(f"  ✓ 命中: {fname} | {subject} | {date} | HTML {len(html_body)} 字节")
                    if not list_only:
                        out = SAMPLES_DIR / fname
                        with open(out, "w", encoding="utf-8") as f:
                            f.write(html_body or "")
                        manifest.append({
                            "file": fname,
                            "subject": subject,
                            "date": date,
                            "from": decoder.decode_mime_words(msg.get('From', '')),
                            "label": label,
                            "html_bytes": len(html_body or ""),
                            "dumped_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        })
                    remaining.remove(target)
        finally:
            client.disconnect()

    if not list_only:
        with open(SAMPLES_DIR / "manifest.json", "w", encoding="utf-8") as f:
            json.dump({
                "dumped_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "note": "只读导出的失败邮件样本；仅含邮件内容，不含凭据；samples/ 已 gitignore",
                "samples": manifest,
            }, f, ensure_ascii=False, indent=2)

    if remaining:
        print("\n⚠️ 以下目标未匹配到（可能已不在邮箱窗口中）：")
        for fname, label, kw, dp in remaining:
            print(f"  - {fname} ({label}, {kw}, {dp})")
        return 2
    print(f"\n完成：{len(manifest)}/{len(TARGETS)} 个样本已存入 {SAMPLES_DIR}")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="只读导出失败账单邮件样本")
    parser.add_argument("--list", action="store_true", help="只列出匹配结果，不写文件")
    args = parser.parse_args()
    sys.exit(dump(list_only=args.list))
