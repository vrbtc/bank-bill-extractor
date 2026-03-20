#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
查找招商银行 3 个特定金额：3173.72, 1244.68, 2787.26
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

# 查找招商银行邮件
for email_id in reversed(email_ids[-20:]):
    status, msg_data = mail.fetch(email_id, "(RFC822)")
    for response_part in msg_data:
        if isinstance(response_part, tuple):
            msg = email.message_from_bytes(response_part[1])
            subject = decode_mime_words(msg.get("Subject", ""))
            
            if "招商银行信用卡电子账单" in subject and "分期" not in subject and "e 招贷" not in subject:
                html_content = get_html_content(msg)
                soup = BeautifulSoup(html_content, 'html.parser')
                text = soup.get_text()
                
                print(f"邮件主题：{subject}")
                print(f"邮件日期：{msg.get('Date', '')}")
                print("="*80)
                
                # 搜索 3 个特定金额
                target_amounts = ['3173.72', '3,173.72', '1244.68', '1,244.68', '2787.26', '2,787.26']
                
                for target in target_amounts:
                    pos = text.find(target)
                    if pos != -1:
                        context = text[max(0, pos-200):pos+200]
                        clean_context = ' '.join(context.split())
                        print(f"\n✓ 找到金额 {target}:")
                        print(f"  上下文：{clean_context}")
                
                # 搜索账单周期
                bill_period = re.search(r'2026/\d{2}/\d{2}-2026/\d{2}/\d{2}', text)
                if bill_period:
                    print(f"\n账单周期：{bill_period.group()}")
                    
                    # 查找账单周期附近的金额
                    pos = text.find(bill_period.group())
                    if pos != -1:
                        context = text[pos:pos+300]
                        clean_context = ' '.join(context.split())
                        print(f"账单周期附近：{clean_context}")
                
                # 搜索所有金额（带￥符号的）
                print("\n【所有带￥符号的金额】")
                amounts = re.findall(r'￥\s*([0-9,]+\.[0-9]{2})', text)
                for amt in set(amounts):
                    print(f"  ￥{amt}")
                
                break

mail.close()
mail.logout()
