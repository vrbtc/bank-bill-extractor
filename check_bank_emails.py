#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
检查交通银行邮件数量
"""

import imaplib
import email
from email.header import decode_header
from config import EMAIL_ADDRESS, PASSWORD, IMAP_SERVER, IMAP_PORT


def decode_mime_words(s):
    if not s:
        return ""
    decoded = ""
    for part, encoding in decode_header(s):
        if isinstance(part, bytes):
            try:
                decoded += part.decode(encoding if encoding else 'utf-8', errors='ignore')
            except:
                decoded += part.decode('utf-8', errors='ignore')
        else:
            decoded += part
    return decoded

# 连接邮箱
mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
mail.login(EMAIL_ADDRESS, PASSWORD)
mail.select("INBOX")

status, messages = mail.search(None, "ALL")
email_ids = messages[0].split()

print("查找所有交通银行邮件：\n")

count = 0
for i, email_id in enumerate(reversed(email_ids[-30:]), 1):
    status, msg_data = mail.fetch(email_id, "(RFC822)")
    for response_part in msg_data:
        if isinstance(response_part, tuple):
            msg = email.message_from_bytes(response_part[1])
            subject = decode_mime_words(msg.get("Subject", ""))
            
            if "交通银行" in subject:
                count += 1
                print(f"{count}. {subject}")
                print(f"   日期：{msg.get('Date', '')}")
                print()

print(f"\n总共找到 {count} 封交通银行邮件")

mail.close()
mail.logout()
