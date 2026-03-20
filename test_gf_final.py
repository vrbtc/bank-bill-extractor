#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
最终测试广发银行提取 - 确保能正确获取 4,551.47
"""

import re
from datetime import datetime


def extract_gf_bill(html_content, subject, date):
    """专门提取广发银行账单"""
    bills = []
    
    full_text = html_content
    
    bill_info = {
        'subject': subject,
        'date': date,
        'amounts': [],
        'due_dates': [],
        'bank_name': '广发银行'
    }
    
    print(f"处理邮件: {subject}")
    print("  开始提取金额...")
    
    # 模式1: 查找 &yen; 后面跟数字的模式（还款提醒）
    amount_match = re.search(r'&yen;[^>]*>[^>]*>([\d,]+\.?\d*)', full_text)
    if amount_match:
        try:
            amount = float(amount_match.group(1).replace(',', ''))
            if 0 < amount < 1000000:
                bill_info['amounts'] = [{'value': amount, 'currency': 'CNY'}]
                print(f"  ✓ 找到金额（还款提醒模式）：{amount}")
        except Exception as e:
            print(f"  ✗ 失败：{e}")
    
    # 如果没找到，尝试正式电子账单模式：查找表格中的数字
    if not bill_info['amounts']:
        print("  尝试正式电子账单模式...")
        amount_matches = re.findall(r'>([\d,]+\.\d{2})<', full_text)
        print(f"  找到数字: {amount_matches[:10]}")
        
        for amt_str in amount_matches:
            try:
                amount = float(amt_str.replace(',', ''))
                print(f"  检查: {amount}")
                if 1000 < amount < 100000:  # 合理的账单金额范围
                    bill_info['amounts'] = [{'value': amount, 'currency': 'CNY'}]
                    print(f"  ✓ 找到金额（正式电子账单模式）：{amount}")
                    break  # 只取第一个合理的金额
            except Exception as e:
                print(f"  ✗ 转换失败：{e}")
                continue
    
    # 查找最后还款日
    print("\n  开始提取还款日...")
    due_patterns = [r'([0-9]{4}/[0-9]{2}/[0-9]{2})']
    for pattern in due_patterns:
        matches = re.findall(pattern, full_text)
        for match in matches:
            date_str = match.replace('/', '-')
            try:
                datetime.strptime(date_str, '%Y-%m-%d')
                if date_str not in bill_info['due_dates']:
                    bill_info['due_dates'].append(date_str)
                    print(f"  ✓ 找到还款日：{date_str}")
            except:
                continue
    
    if bill_info['amounts'] or bill_info['due_dates']:
        bills.append(bill_info)
    
    print(f"\n最终结果: {bills}")
    return bills


# 测试正式电子账单 gf_email_1.html
print("="*80)
print("测试 1: gf_email_1.html (正式电子账单 - 目标：4,551.47)")
print("="*80)
with open('gf_email_1.html', 'rb') as f:
    raw_content = f.read()

html_content_1 = raw_content.decode('gb18030', errors='ignore')
bills1 = extract_gf_bill(html_content_1, "广发信用卡 2026年03月电子账单", "Wed, 18 Mar 2026 10:37:24 +0800")

# 测试还款提醒 gf_email_2.html
print("\n" + "="*80)
print("测试 2: gf_email_2.html (还款提醒)")
print("="*80)
with open('gf_email_2.html', 'rb') as f:
    raw_content2 = f.read()

html_content_2 = raw_content2.decode('gb18030', errors='ignore')
bills2 = extract_gf_bill(html_content_2, "【广发卡 03月还款提醒】", "Tue, 03 Mar 2026 08:29:52 +0800")
