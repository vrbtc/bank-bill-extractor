#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
CI 运行脚本 - 供 GitHub Actions 调用
功能：提取账单 → 生成 JSON → 输出到 docs/bills.json 供 GitHub Pages 展示
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

# 确保能导入项目模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from this_month_bills import BillExtractor, get_upcoming_bills


def main():
    print("=" * 60)
    print("CI 账单提取脚本")
    print(f"运行时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # 检查环境变量
    email_addr = os.environ.get('EMAIL_ADDRESS')
    email_pwd = os.environ.get('EMAIL_PASSWORD')

    if not email_addr or not email_pwd:
        print("ERROR: 缺少邮箱环境变量 EMAIL_ADDRESS / EMAIL_PASSWORD")
        sys.exit(1)

    print(f"邮箱账号：{email_addr}")

    # 提取账单
    print("\n步骤 1: 提取账单...")
    extractor = BillExtractor()
    bills = extractor.fetch_and_extract(limit=50)
    print(f"共提取 {len(bills)} 封账单邮件")

    # 获取待还款账单
    print("\n步骤 2: 筛选待还款账单...")
    upcoming_all = get_upcoming_bills(bills, days=None)
    upcoming_15 = get_upcoming_bills(bills, days=15)

    # 构建输出数据
    banks_list = []
    total_amount = 0

    for bname, info in sorted(
        upcoming_all.items(),
        key=lambda x: x[1].get('earliest_due_date', {}).get('days_until', 999) if x[1].get('earliest_due_date') else 999
    ):
        if info['total_amount'] > 0 and info.get('earliest_due_date'):
            entry = {
                'name': bname,
                'amount': info['total_amount'],
                'due_date': info['earliest_due_date']['date'],
                'days_until': info['earliest_due_date']['days_until'],
            }
            banks_list.append(entry)
            total_amount += info['total_amount']

    # 紧急账单（3天内）
    urgent_list = [b for b in banks_list if b['days_until'] <= 3]

    output = {
        'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'total_bills': len(bills),
        'total_amount': round(total_amount, 2),
        'bank_count': len(banks_list),
        'urgent_count': len(urgent_list),
        'banks': banks_list,
        'urgent': urgent_list,
    }

    # 输出到 docs/bills.json（GitHub Pages 读取）
    docs_dir = Path('docs')
    docs_dir.mkdir(exist_ok=True)

    output_file = docs_dir / 'bills.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n✓ 数据已保存至：{output_file}")
    print(f"  待还款银行：{len(banks_list)} 个")
    print(f"  待还款总额：¥{total_amount:,.2f}")
    print(f"  紧急账单（3天内）：{len(urgent_list)} 个")

    # 同时保存一份完整的原始数据
    raw_file = docs_dir / 'bills_raw.json'
    with open(raw_file, 'w', encoding='utf-8') as f:
        json.dump({
            'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'bills': bills,
        }, f, ensure_ascii=False, indent=2)

    print(f"✓ 原始数据已保存至：{raw_file}")

    print("\nCI 脚本执行完成！")


if __name__ == "__main__":
    main()
