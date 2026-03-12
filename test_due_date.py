#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试交通银行还款日提取
"""

import re
from datetime import datetime

html_content = """
到期还款日<br><span style="font-size: 13px; line-height: 15px;">Payment Due Date</span></td>
<td colspan="2" style="padding: 6px 0;"><span style="font-weight: 900;">2026-03-15</span>
"""

full_text = f"交通银行白金信用卡 2026 年 02 月电子账单\n{html_content}"
full_text = full_text.replace('&yen;', '￥').replace('&nbsp;', ' ').replace('&amp;', '&')

due_patterns = [
    r'到期还款日.*?([0-9]{4}[-/.年][0-9]{1,2}[-/.月][0-9]{1,2}[-/.日]*)',
    r'Payment Due Date.*?([0-9]{4}[-/.][0-9]{1,2}[-/.][0-9]{1,2})',
    r'还款日.*?([0-9]{4}[-/.][0-9]{1,2}[-/.][0-9]{1,2})',
]

print("测试还款日提取：")
print("="*80)

for pattern in due_patterns:
    matches = re.findall(pattern, full_text)
    print(f"模式：{pattern}")
    print(f"匹配结果：{matches}")
    
    for match in matches:
        date_str = match.replace('年', '-').replace('月', '-').replace('日', '')
        if len(date_str) <= 5:
            current_year = datetime.now().year
            date_str = f"{current_year}-{date_str}"
        
        date_str = date_str.replace('/', '-')
        
        try:
            parsed = datetime.strptime(date_str, '%Y-%m-%d')
            print(f"  解析成功：{date_str} -> {parsed}")
        except Exception as e:
            print(f"  解析失败：{date_str} -> {e}")
    
    print()
