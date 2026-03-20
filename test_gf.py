#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试广发银行解析 - 直接搜索HTML
"""

import re
from datetime import datetime


def test_extract_gf(raw_html, subject, date):
    """测试广发银行提取函数"""
    bills = []
    
    # 先用 gb18030 解码
    try:
        full_text = raw_html.decode('gb18030', errors='ignore')
    except:
        full_text = raw_html.decode('utf-8', errors='ignore')
    
    bill_info = {
        'subject': subject,
        'date': date,
        'amounts': [],
        'due_dates': [],
        'bank_name': '广发银行'
    }
    
    print("  开始查找金额...")
    
    # 方法1: 查找 &yen; 后面跟数字的模式
    amount_patterns = [
        r'&yen;[^>]*>[^>]*>([\d,]+\.?\d*)',
        r'&yen;\s*([\d,]+\.?\d*)',
        r'[￥$¥]\s*([\d,]+\.?\d*)',
    ]
    
    for pattern in amount_patterns:
        matches = re.findall(pattern, full_text)
        if matches:
            print(f"  模式 {pattern} 找到: {matches}")
            for amt_str in matches:
                try:
                    amount = float(amt_str.replace(',', ''))
                    if 0 < amount < 1000000:
                        if not any(a['value'] == amount for a in bill_info['amounts']):
                            bill_info['amounts'].append({'value': amount, 'currency': 'CNY'})
                            print(f"  添加金额：{amount}")
                except Exception as e:
                    print(f"  转换金额失败：{e}")
                    continue
    
    # 方法2: 查找表格中的数字，没有 &yen; 符号的，像 4,551.47
    if not bill_info['amounts']:
        print("\n  尝试查找表格中的数字...")
        table_amount_patterns = [
            r'>([\d,]+\.\d{2})<',
        ]
        for pattern in table_amount_patterns:
            matches = re.findall(pattern, full_text)
            if matches:
                print(f"  模式 {pattern} 找到: {matches[:10]}")
                for amt_str in matches:
                    try:
                        amount = float(amt_str.replace(',', ''))
                        if 100 < amount < 100000:  # 合理的账单金额范围
                            if not any(a['value'] == amount for a in bill_info['amounts']):
                                bill_info['amounts'].append({'value': amount, 'currency': 'CNY'})
                                print(f"  添加金额：{amount}")
                    except Exception as e:
                        print(f"  转换金额失败：{e}")
                        continue
    
    # 方法2: 查找日期格式 20XX/XX/XX
    print("\n  开始查找还款日...")
    due_patterns = [
        r'(\d{4}/\d{2}/\d{2})',
    ]
    
    for pattern in due_patterns:
        matches = re.findall(pattern, full_text)
        if matches:
            print(f"  模式 {pattern} 找到: {matches}")
            for match in matches:
                date_str = match.replace('/', '-')
                try:
                    datetime.strptime(date_str, '%Y-%m-%d')
                    if date_str not in bill_info['due_dates']:
                        bill_info['due_dates'].append(date_str)
                        print(f"  添加还款日：{date_str}")
                except Exception as e:
                    print(f"  转换日期失败：{e}")
                    continue
    
    if bill_info['amounts'] or bill_info['due_dates']:
        bills.append(bill_info)
    
    return bills


# 测试 gf_email_2.html (还款提醒) - 这个应该有清晰的格式
print("="*80)
print("测试 gf_email_2.html (还款提醒)")
print("="*80)
with open('gf_email_2.html', 'rb') as f:
    raw_content2 = f.read()

bills2 = test_extract_gf(raw_content2, "【广发卡 03月还款提醒】", "Tue, 03 Mar 2026 08:29:52 +0800")
print(f"\n最终结果：{bills2}")

# 测试 gf_email_1.html (正式电子账单)
print("\n" + "="*80)
print("测试 gf_email_1.html (正式电子账单)")
print("="*80)
with open('gf_email_1.html', 'rb') as f:
    raw_content = f.read()

bills1 = test_extract_gf(raw_content, "广发信用卡 2026年03月电子账单", "Wed, 18 Mar 2026 10:37:24 +0800")
print(f"\n最终结果：{bills1}")
