#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
查找数字周围的上下文
"""

with open('gf_email_1.html', 'rb') as f:
    raw_content = f.read()

html_content = raw_content.decode('gbk', errors='replace')

# 查找主表格区域 - 找到4,551.47的位置，再往前找更多
idx = html_content.find('4,551.47')
if idx != -1:
    start = max(0, idx - 1500)
    end = min(len(html_content), idx + 300)
    context = html_content[start:end]
    print("="*80)
    print("主表格区域（更大范围）：")
    print("="*80)
    print(context)
    print("\n")

# 也让我们查看一下还款提醒邮件
print("\n" + "="*80)
print("还款提醒邮件 gf_email_2.html（更大范围）：")
print("="*80)

with open('gf_email_2.html', 'rb') as f:
    raw_content2 = f.read()

html_content2 = raw_content2.decode('gbk', errors='replace')

# 查找213.97，再往前找更多
idx2 = html_content2.find('213.97')
if idx2 != -1:
    start2 = max(0, idx2 - 1500)
    end2 = min(len(html_content2), idx2 + 500)
    context2 = html_content2[start2:end2]
    print(context2)
