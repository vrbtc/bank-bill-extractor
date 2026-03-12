#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试交通银行账单提取
"""

import re

html_content = """
<td align="center" style="padding: 16px 0 0; font-size: 26px; color: #666;">本期应还款</td>
<td width="38%" style="padding: 16px 8px 0 0; font-size: 32px; font-weight: 900;">￥4169.77</td>
"""

full_text = f"交通银行白金信用卡 2026 年 02 月电子账单\n{html_content}"
full_text = full_text.replace('&yen;', '￥').replace('&amp;', '&')

print("搜索文本:")
print(full_text)
print("\n" + "="*80)

due_match = re.search(r'到期还款日 [^0-9]*([0-9]{4}-[0-9]{2}-[0-9]{2})', full_text)
print(f"还款日匹配结果：{due_match}")

amount_match = re.search(r'本期应还款.*?￥([0-9,]+\.?[0-9]*)', full_text, re.DOTALL)
print(f"金额匹配结果：{amount_match}")

if amount_match:
    print(f"匹配到的金额：{amount_match.group(1)}")
    amount_str = amount_match.group(1).replace(',', '')
    try:
        amount = float(amount_str)
        print(f"转换后的金额：{amount}")
    except:
        print("转换失败")
