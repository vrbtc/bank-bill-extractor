#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
确认 7601.17 是什么金额
"""

from bs4 import BeautifulSoup
import re

# 读取 HTML 文件
with open('cmb_html_part_1.html', 'r', encoding='utf-8') as f:
    html_content = f.read()

soup = BeautifulSoup(html_content, 'html.parser')
text = soup.get_text()

print("="*80)
print("【搜索 7601.17 前后 500 字符】")
print("="*80)

pos = text.find('7601.17')
if pos != -1:
    context = text[max(0, pos-500):pos+500]
    # 格式化输出
    lines = context.split('\n')
    for line in lines:
        clean_line = ' '.join(line.split())
        if clean_line:
            # 高亮 7601.17
            if '7601.17' in clean_line:
                print(f">>> {clean_line}")
            else:
                print(f"    {clean_line}")

print("\n" + "="*80)
print("【搜索所有 7000-8000 之间的金额】")
print("="*80)

# 查找所有金额
all_amounts = re.findall(r'¥\s*([0-9,]+\.[0-9]{2})', text)
for amt_str in all_amounts:
    try:
        amount = float(amt_str.replace(',', ''))
        if 7000 < amount < 8000:
            print(f"  ¥{amt_str}")
    except:
        pass

print("\n" + "="*80)
print('【查找"预借现金"或"现金分期"相关（可能是 7601.17 的来源）】')
print("="*80)

patterns = [
    r'预借现金.{0,200}',
    r'现金分期.{0,200}',
    r'分期本金.{0,200}',
]

for pattern in patterns:
    matches = re.findall(pattern, text, re.IGNORECASE)
    for match in matches[:2]:
        clean = ' '.join(match.split())
        print(f"找到：{clean}")
