#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
分析广发银行HTML账单
"""

from bs4 import BeautifulSoup

# 尝试多种编码方式读取文件
html_content = None
for encoding in ['gb18030', 'gbk', 'utf-8']:
    try:
        with open('gf_email_1.html', 'r', encoding=encoding, errors='ignore') as f:
            html_content = f.read()
        print(f"成功使用 {encoding} 编码读取文件")
        break
    except Exception as e:
        print(f"{encoding} 编码失败：{e}")
        continue

if not html_content:
    print("无法读取文件！")
    exit(1)

soup = BeautifulSoup(html_content, 'html.parser')

print("="*80)
print("查找关键信息...")
print("="*80)

# 查找所有文本
all_text = soup.get_text(separator='\n', strip=True)
lines = [line.strip() for line in all_text.split('\n') if line.strip()]

print("\n前100行内容：")
for i, line in enumerate(lines[:100]):
    print(f"[{i+1}] {line}")

print("\n" + "="*80)
print("查找金额相关内容：")
print("="*80)
for line in lines:
    if any(keyword in line for keyword in ['本期', '应还', '账单', '金额', 'USD', 'CNY', '￥', '$']):
        print(line)

print("\n" + "="*80)
print("查找日期相关内容：")
print("="*80)
for line in lines:
    if any(keyword in line for keyword in ['还款日', '到期日', '还款', '日']):
        print(line)
