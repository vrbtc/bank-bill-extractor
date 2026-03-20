#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
详细调试招商银行提取
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

# 查找最新的招商银行信用卡电子账单
for email_id in reversed(email_ids[-20:]):
    status, msg_data = mail.fetch(email_id, "(RFC822)")
    for response_part in msg_data:
        if isinstance(response_part, tuple):
            msg = email.message_from_bytes(response_part[1])
            subject = decode_mime_words(msg.get("Subject", ""))
            
            if "招商银行信用卡电子账单" in subject and "分期" not in subject and "e 招贷" not in subject:
                html_content = get_html_content(msg)
                full_text = f"{subject}\n{html_content}"
                full_text = full_text.replace('&yen;', '￥').replace('&nbsp;', ' ')
                
                print(f"\n{'='*80}")
                print(f"调试邮件：{subject}")
                print(f"{'='*80}")
                
                # 查找账单周期
                bill_period_match = re.search(r'(\d{4}/\d{2}/\d{2}-\d{4}/\d{2}/\d{2})', full_text)
                
                if bill_period_match:
                    bill_period = bill_period_match.group(1)
                    print(f"\n账单周期：{bill_period}")
                    
                    # 方法 1：直接在 HTML 中查找金额
                    print("\n【方法 1: 直接在 HTML 中查找】")
                    html_amounts = re.findall(r'¥\s*([0-9,]+\.[0-9]+)', full_text)
                    print(f"找到的金额：{html_amounts[:10]}")
                    
                    # 方法 2：先清理 HTML
                    print("\n【方法 2: 清理 HTML 后查找】")
                    soup = BeautifulSoup(full_text, 'html.parser')
                    clean_text = soup.get_text()
                    clean_text = re.sub(r'\s+', ' ', clean_text)
                    
                    pos = clean_text.find(bill_period)
                    if pos != -1:
                        snippet = clean_text[pos:pos+500]
                        print(f"清理后片段：{snippet}")
                        
                        clean_amounts = re.findall(r'¥\s*([0-9,]+\.[0-9]+)', snippet)
                        print(f"清理后找到的金额：{clean_amounts[:10]}")
                    
                    # 方法 3：不清理，直接找
                    print("\n【方法 3: 不清理，直接找】")
                    pos_orig = full_text.find(bill_period)
                    if pos_orig != -1:
                        snippet_orig = full_text[pos_orig:pos_orig+500]
                        orig_amounts = re.findall(r'￥\s*([0-9,]+\.[0-9]+)', snippet_orig)
                        print(f"原始找到的金额：{orig_amounts[:10]}")
                
                break

mail.close()
mail.logout()
