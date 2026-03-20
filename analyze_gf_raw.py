#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
直接分析广发银行HTML账单原始内容
"""

import re

# 以二进制读取文件
with open('gf_email_1.html', 'rb') as f:
    raw_content = f.read()

print("="*80)
print("分析原始HTML...")
print("="*80)

# 尝试用gbk解码，忽略错误
html_content = raw_content.decode('gbk', errors='replace')

# 查找金额
print("\n查找所有数字模式...")
amount_patterns = [
    r'(\d{1,3}(?:,\d{3})*\.\d{2})',  # 带逗号的小数
    r'(\d+\.\d{2})',  # 简单小数
]

for pattern in amount_patterns:
    matches = re.findall(pattern, html_content)
    if matches:
        print(f"\n模式 {pattern} 找到的匹配：")
        for m in matches[:20]:
            print(f"  {m}")

# 查找日期
print("\n" + "="*80)
print("查找日期模式...")
print("="*80)

date_patterns = [
    r'(\d{4}/\d{2}/\d{2})',
    r'(\d{4}-\d{2}-\d{2})',
]

for pattern in date_patterns:
    matches = re.findall(pattern, html_content)
    if matches:
        print(f"\n模式 {pattern} 找到的匹配：")
        for m in matches[:20]:
            print(f"  {m}")

# 保存解码后的内容用于查看
with open('gf_email_decoded.html', 'w', encoding='utf-8') as f:
    f.write(html_content)
print("\n解码后的HTML已保存到：gf_email_decoded.html")

# 现在让我们也分析一下还款提醒邮件
print("\n" + "="*80)
print("分析还款提醒邮件 gf_email_2.html...")
print("="*80)

with open('gf_email_2.html', 'rb') as f:
    raw_content2 = f.read()

html_content2 = raw_content2.decode('gbk', errors='replace')

for pattern in amount_patterns:
    matches = re.findall(pattern, html_content2)
    if matches:
        print(f"\n模式 {pattern} 找到的匹配：")
        for m in matches[:20]:
            print(f"  {m}")

for pattern in date_patterns:
    matches = re.findall(pattern, html_content2)
    if matches:
        print(f"\n模式 {pattern} 找到的匹配：")
        for m in matches[:20]:
            print(f"  {m}")

with open('gf_email_2_decoded.html', 'w', encoding='utf-8') as f:
    f.write(html_content2)
print("\n还款提醒解码后的HTML已保存到：gf_email_2_decoded.html")
