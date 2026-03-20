#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
详细检查招商银行分期账单
"""

import imaplib
import email
from email.header import decode_header
import re
from bs4 import BeautifulSoup

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

# 查找分期账单
for email_id in reversed(email_ids[-30:]):
    status, msg_data = mail.fetch(email_id, "(RFC822)")
    for response_part in msg_data:
        if isinstance(response_part, tuple):
            msg = email.message_from_bytes(response_part[1])
            subject = decode_mime_words(msg.get("Subject", ""))
            
            if "招商" in subject and "分期" in subject:
                print(f"邮件主题：{subject}")
                print(f"日期：{msg.get('Date', '')}")
                print("="*80)
                
                html_content = get_html_content(msg)
                soup = BeautifulSoup(html_content, 'html.parser')
                full_text = f"{subject}\n{html_content}"
                full_text = full_text.replace('&yen;', '￥').replace('&nbsp;', ' ')
                
                # 清理 HTML
                clean_text = soup.get_text()
                clean_text = re.sub(r'\s+', ' ', clean_text)
                
                # 查找 2787.26
                target = "2787.26"
                if target in clean_text or target.replace('.', ',') in clean_text:
                    print(f"\n✓ 找到 {target}")
                    pos = clean_text.find(target.replace('.', ',') if target.replace('.', ',') in clean_text else target)
                    context = clean_text[max(0, pos-200):pos+200]
                    print(f"上下文：{context}")
                else:
                    print(f"\n✗ 未找到 {target}")
                
                # 查找账单周期
                bill_period_match = re.search(r'(\d{4}/\d{2}/\d{2}-\d{4}/\d{2}/\d{2})', clean_text)
                
                if bill_period_match:
                    bill_period = bill_period_match.group(1)
                    print(f"\n账单周期：{bill_period}")
                    pos = clean_text.find(bill_period)
                    
                    if pos != -1:
                        snippet = clean_text[pos:pos+500]
                        print(f"\n账单周期后 500 字符：\n{snippet}")
                        
                        # 查找所有￥金额
                        amounts = re.findall(r'￥\s*([0-9,]+\.[0-9]+)', snippet)
                        print(f"\n找到的金额：{amounts[:10]}")
                
                break

mail.close()
mail.logout()
