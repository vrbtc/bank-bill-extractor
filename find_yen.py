#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
查找 &yen; 符号的位置
"""

with open('gf_email_2.html', 'rb') as f:
    raw_content = f.read()

# 直接在二进制内容中查找 'yen' 或 '213.97'
text = raw_content.decode('latin-1')

print("查找 'yen' 的位置...")
positions = []
idx = 0
while True:
    idx = text.find('yen', idx)
    if idx == -1:
        break
    positions.append(idx)
    idx += 3

print(f"找到 'yen' 在位置：{positions}")

# 打印每个 yen 周围的内容
for pos in positions:
    start = max(0, pos - 50)
    end = min(len(text), pos + 100)
    snippet = text[start:end]
    print(f"\n位置 {pos} 周围：\n{snippet}\n")

# 查找 '213.97'
print("\n" + "="*80)
print("查找 '213.97'")
idx_213 = text.find('213.97')
if idx_213 != -1:
    start = max(0, idx_213 - 100)
    end = min(len(text), idx_213 + 100)
    snippet = text[start:end]
    print(f"\n位置 {idx_213} 周围：\n{snippet}\n")
