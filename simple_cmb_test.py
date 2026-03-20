#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
简单直接提取招商银行账单
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
                
                # 替换所有空白字符为单个空格
                text = re.sub(r'\s+', ' ', text)
                
                print("="*80)
                print("招商银行账单提取测试")
                print("="*80)
                
                # 方法 1：查找账单周期后的第一个¥金额（信用额度），第二个¥金额（本期应还）
                bill_period_match = re.search(r'(\d{4}/\d{2}/\d{2}-\d{4}/\d{2}/\d{2})', text)
                if bill_period_match:
                    bill_period = bill_period_match.group(1)
                    print(f"\n账单周期：{bill_period}")
                    
                    # 找到账单周期的位置
                    pos = text.find(bill_period)
                    if pos != -1:
                        # 从账单周期后面开始查找
                        snippet = text[pos:]
                        
                        # 查找所有¥金额
                        amounts = re.findall(r'¥\s*([0-9,]+\.[0-9]+)', snippet)
                        print(f"找到的金额序列：{amounts[:10]}")
                        
                        if len(amounts) >= 2:
                            print(f"\n✓ 信用额度：¥{amounts[0]}")
                            print(f"✓ 本期应还：¥{amounts[1]}")
                            print(f"  最低还款：¥{amounts[2] if len(amounts) > 2 else 'N/A'}")
                        
                        # 查找还款日（在账单周期后面但不是账单周期的一部分）
                        # 查找格式为 2026/04/06 的日期
                        dates = re.findall(r'(\d{4}/\d{2}/\d{2})', snippet)
                        bill_dates = [bill_period[:10], bill_period[11:]]
                        due_dates = [d for d in dates if d not in bill_dates]
                        
                        if due_dates:
                            print(f"✓ 还款日：{due_dates[0]}")
                
                break

mail.close()
mail.logout()
