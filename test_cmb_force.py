#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试招商银行账单提取（强制重新提取）
"""

from this_month_bills import BillExtractor, EMAIL_ADDRESS, PASSWORD, IMAP_SERVER, IMAP_PORT
import imaplib
import email

# 创建提取器
extractor = BillExtractor()

# 连接邮箱
print("连接邮箱...")
mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
mail.login(EMAIL_ADDRESS, PASSWORD)
mail.select("INBOX")

# 搜索所有邮件
status, messages = mail.search(None, "ALL")
email_ids = messages[0].split()

print(f"共找到 {len(email_ids)} 封邮件\n")

# 测试招商银行邮件提取
cmb_count = 0
for email_id in email_ids[-35:]:  # 最近 35 封
    status, msg_data = mail.fetch(email_id, "(RFC822)")
    for response_part in msg_data:
        if isinstance(response_part, tuple):
            msg = email.message_from_bytes(response_part[1])
            subject = extractor.decode_mime_words(msg.get("Subject", ""))
            
            if "招商银行" in subject:
                cmb_count += 1
                print(f"\n{'='*80}")
                print(f"招商银行邮件 {cmb_count}: {subject}")
                print(f"{'='*80}")
                
                # 获取 HTML 内容
                html_content = extractor.decode_html_content(msg)
                
                # 提取账单
                bills = extractor.extract_from_html(html_content, subject, msg.get("Date", ""))
                
                if bills:
                    for bill in bills:
                        print(f"  银行：{bill['bank']}")
                        print(f"  金额：{[a['value'] for a in bill['amounts']]}")
                        print(f"  还款日：{bill['due_dates']}")
                else:
                    print("  ✗ 未提取到账单信息")

print(f"\n\n总共处理了 {cmb_count} 封招商银行邮件")

mail.close()
mail.logout()
