#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
查找招商银行所有账单的 3 个金额
"""

import imaplib
import email
from email.header import decode_header
from bs4 import BeautifulSoup
import re

EMAIL_ADDRESS = "rrking@aliyun.com"
PASSWORD = "Aa2599589"
IMAP_SERVER = "imap.aliyun.com"
IMAP_PORT = 993

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

def get_html_content(msg):
    html_body = ""
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            cdispo = str(part.get("Content-Disposition"))
            if ctype == "text/html" and "attachment" not in cdispo:
                try:
                    charset = part.get_content_charset() or 'utf-8'
                    if charset.lower() in ['gbk', 'gb2312', 'gb18030']:
                        html_body = part.get_payload(decode=True).decode('gbk', errors='ignore')
                    else:
                        html_body = part.get_payload(decode=True).decode(charset, errors='ignore')
                    break
                except:
                    try:
                        html_body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                        break
                    except:
                        pass
    else:
        try:
            charset = msg.get_content_charset() or 'utf-8'
            html_body = msg.get_payload(decode=True).decode(charset, errors='ignore')
        except:
            try:
                html_body = msg.get_payload(decode=True).decode('utf-8', errors='ignore')
            except:
                pass
    return html_body

# 连接邮箱
mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
mail.login(EMAIL_ADDRESS, PASSWORD)
mail.select("INBOX")

status, messages = mail.search(None, "ALL")
email_ids = messages[0].split()

print("搜索所有招商银行邮件中的 3 个目标金额...\n")

target_amounts = {
    '3173.72': False,
    '1244.68': False,
    '2787.26': False
}

# 查找所有招商银行邮件
for i, email_id in enumerate(reversed(email_ids[-30:]), 1):
    status, msg_data = mail.fetch(email_id, "(RFC822)")
    for response_part in msg_data:
        if isinstance(response_part, tuple):
            msg = email.message_from_bytes(response_part[1])
            subject = decode_mime_words(msg.get("Subject", ""))
            
            if "招商银行" in subject:
                html_content = get_html_content(msg)
                soup = BeautifulSoup(html_content, 'html.parser')
                text = soup.get_text()
                
                # 检查是否包含目标金额
                for target in target_amounts.keys():
                    if target in text or target.replace('.', ',') in text:
                        print(f"✓ 邮件 {i}: {subject}")
                        print(f"  找到金额：{target}")
                        
                        # 提取账单周期和还款日
                        bill_period = re.search(r'(\d{4}/\d{2}/\d{2}-\d{4}/\d{2}/\d{2})', text)
                        if bill_period:
                            print(f"  账单周期：{bill_period.group()}")
                        
                        due_date = re.search(r'2026/04/06|2026/03/\d{2}', text)
                        if due_date:
                            print(f"  还款日：{due_date.group()}")
                        
                        target_amounts[target] = True
                        print()

print("\n总结：")
for target, found in target_amounts.items():
    status = "✓ 找到" if found else "✗ 未找到"
    print(f"  {target}: {status}")

mail.close()
mail.logout()
