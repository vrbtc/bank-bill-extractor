#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
查找招商银行金额（带千分位）
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

# 查找最新的招商银行信用卡电子账单
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
                
                # 提取账单周期
                bill_period = re.search(r'(\d{4}/\d{2}/\d{2})-(\d{4}/\d{2}/\d{2})', text)
                if bill_period:
                    print(f"\n账单周期：{bill_period.group()}")
                    
                    # 查找账单周期后面的金额（格式：账单周期 ¥额度¥本期应还¥最低还款 还款日...）
                    pos = text.find(bill_period.group())
                    if pos != -1:
                        snippet = text[pos:pos+500]
                        print(f"\n账单周期后 500 字符：")
                        print(snippet)
                        
                        # 提取金额序列
                        # 格式应该是：¥45,000.00¥1,244.68¥1,181.032026/04/06
                        amount_pattern = r'¥([0-9,]+\.[0-9]+)'
                        amounts = re.findall(amount_pattern, snippet)
                        print(f"\n找到的金额序列：{amounts}")
                        
                        if len(amounts) >= 2:
                            print(f"\n✓ 信用额度：{amounts[0]}")
                            print(f"✓ 本期应还：{amounts[1]}")
                            if len(amounts) >= 3:
                                print(f"  最低还款：{amounts[2]}")
                        
                        # 提取还款日
                        due_date_pattern = r'(2026/\d{2}/\d{2})'
                        dates = re.findall(due_date_pattern, snippet)
                        # 排除账单周期的日期
                        bill_dates = [bill_period.group(1), bill_period.group(2)]
                        due_dates = [d for d in dates if d not in bill_dates]
                        if due_dates:
                            print(f"\n✓ 还款日：{due_dates[0]}")
                
                break

mail.close()
mail.logout()
