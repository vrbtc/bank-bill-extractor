#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
分析招商银行 HTML 结构找到还款日
"""

from bs4 import BeautifulSoup
import re

# 读取 HTML 文件
with open('latest_cmb_email.html', 'r', encoding='utf-8') as f:
    html_content = f.read()

soup = BeautifulSoup(html_content, 'html.parser')

# 提取所有文本内容
full_text = soup.get_text()

print("="*80)
print("【搜索所有包含日期的行】")
print("="*80)

# 分割成行并搜索
lines = full_text.split('\n')
for i, line in enumerate(lines):
    # 查找包含 2026 或日期格式的行
    if re.search(r'2026|到期 | 还款 | 日期|due', line, re.IGNORECASE):
        # 清理空白字符
        line_clean = ' '.join(line.split())
        if len(line_clean) > 5 and len(line_clean) < 300:  # 过滤太短或太长的行
            print(f"第{i}行：{line_clean}")

print("\n" + "="*80)
print("【搜索金额 7601.17 附近的内容】")
print("="*80)

pos = full_text.find('7601.17')
if pos != -1:
    # 获取前后 500 个字符
    context_start = max(0, pos - 500)
    context_end = min(len(full_text), pos + 500)
    context = full_text[context_start:context_end]
    
    # 清理并打印
    context_clean = ' '.join(context.split())
    print(f"上下文：{context_clean}")
    
print("\n" + "="*80)
print("【搜索所有表格】")
print("="*80)

tables = soup.find_all('table')
print(f"找到 {len(tables)} 个表格")

for i, table in enumerate(tables[:5]):  # 只显示前 5 个表格
    text = table.get_text()
    text_clean = ' '.join(text.split())
    if len(text_clean) > 10 and len(text_clean) < 500:
        print(f"\n表格 {i+1}: {text_clean[:300]}")
