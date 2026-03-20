#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
分析招商银行 HTML 找到还款日
"""

from bs4 import BeautifulSoup
import re

# 读取 HTML 文件
with open('cmb_html_part_1.html', 'r', encoding='utf-8') as f:
    html_content = f.read()

soup = BeautifulSoup(html_content, 'html.parser')

# 提取所有文本
text = soup.get_text()

print("="*80)
print('【搜索所有包含"日"的文本（可能是日期）】')
print("="*80)

# 搜索包含"日"的文本片段
patterns_with_date = re.findall(r'.{0,50}\d{4}[-/年]\d{1,2}[-/月]\d{1,2}[日号]?.{0,50}', text)
for match in patterns_with_date[:20]:
    clean_match = ' '.join(match.split())
    print(clean_match[:200])

print("\n" + "="*80)
print("【搜索账单相关信息】")
print("="*80)

# 搜索包含"账单"的文本
bill_patterns = [
    r'账单日.{0,30}',
    r'账单周期.{0,50}',
    r'账单月份.{0,30}',
    r'本期账单.{0,100}',
]

for pattern in bill_patterns:
    matches = re.findall(pattern, text, re.IGNORECASE)
    for match in matches[:5]:
        clean_match = ' '.join(match.split())
        print(f"找到：{clean_match}")

print("\n" + "="*80)
print("【搜索 7601.17 附近的文本】")
print("="*80)

pos = text.find('7601.17')
if pos != -1:
    context = text[max(0, pos-300):pos+300]
    clean_context = ' '.join(context.split())
    print(f"上下文：{clean_context}")

print("\n" + "="*80)
print("【查找所有表格并提取文本】")
print("="*80)

tables = soup.find_all('table')
print(f"找到 {len(tables)} 个表格\n")

for i, table in enumerate(tables):
    table_text = table.get_text()
    if '7601.17' in table_text or '到期' in table_text or '还款' in table_text:
        print(f"表格 {i+1}:")
        clean_text = ' '.join(table_text.split())
        print(f"  内容：{clean_text[:500]}")
        print()
