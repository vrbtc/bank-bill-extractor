#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
查找招商银行本期应还金额和还款日
"""

from bs4 import BeautifulSoup
import re

# 读取 HTML 文件
with open('cmb_html_part_1.html', 'r', encoding='utf-8') as f:
    html_content = f.read()

soup = BeautifulSoup(html_content, 'html.parser')
text = soup.get_text()

print("="*80)
print('【搜索"本期应还"相关】')
print("="*80)

patterns = [
    r'本期应还.{0,100}',
    r'本期账单.{0,100}',
    r'应还款.{0,100}',
    r'最低应还.{0,100}',
]

for pattern in patterns:
    matches = re.findall(pattern, text, re.IGNORECASE)
    for match in matches[:3]:
        clean = ' '.join(match.split())
        print(f"找到：{clean}")

print("\n" + "="*80)
print("【搜索所有 4 月日期】")
print("="*80)

april_dates = re.findall(r'2026[/年-]0?4[/月-]\d{1,2}[日号]?', text)
for date in set(april_dates):
    print(f"  {date}")

print("\n" + "="*80)
print('【搜索"04/06"或"0406"相关上下文】')
print("="*80)

pos = text.find('04/06')
if pos != -1:
    context = text[max(0, pos-100):pos+100]
    clean = ' '.join(context.split())
    print(f"04/06 上下文：{clean}")

# 也搜索 0406
pos2 = text.find('0406')
if pos2 != -1:
    context = text[max(0, pos2-100):pos2+100]
    clean = ' '.join(context.split())
    print(f"0406 上下文：{clean}")

print("\n" + "="*80)
print("【总结提取】")
print("="*80)

# 提取账单周期
bill_period = re.search(r'2026/02/19-2026/03/18', text)
if bill_period:
    print(f"账单周期：{bill_period.group()}")

# 提取到期日期（积分到期）
due_date = re.search(r'到期日期：2026/03/31', text)
if due_date:
    print(f"积分到期日：{due_date.group()}")

# 推测还款日（从 0306 银联转账还款推断）
print("从交易记录'0306 银联转账还款'推测，还款日可能是 4 月 6 日")
