#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
检查招商银行分期账单
"""

import imaplib
import email
from email.header import decode_header
import re
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

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

print("检查招商银行分期账单：\n")

# 查找所有招商银行邮件
for i, email_id in enumerate(reversed(email_ids[-30:]), 1):
    status, msg_data = mail.fetch(email_id, "(RFC822)")
    for response_part in msg_data:
        if isinstance(response_part, tuple):
            msg = email.message_from_bytes(response_part[1])
            subject = decode_mime_words(msg.get("Subject", ""))
            email_date = msg.get("Date", "")
            
            if "招商" in subject:
                # 解析邮件日期
                try:
                    parsed_date = email.utils.parsedate(email_date)
                    if parsed_date:
                        mail_date = datetime(*parsed_date[:6])
                        days_ago = (datetime.now() - mail_date).days
                    else:
                        days_ago = 999
                except:
                    days_ago = 999
                
                # 只处理最近 15 天的邮件
                if days_ago <= 15:
                    print(f"{i}. {subject}")
                    print(f"   日期：{email_date[:16]} ({days_ago}天前)")
                    
                    # 获取 HTML 并提取金额
                    html_content = get_html_content(msg)
                    soup = BeautifulSoup(html_content, 'html.parser')
                    full_text = f"{subject}\n{html_content}"
                    full_text = full_text.replace('&yen;', '￥').replace('&nbsp;', ' ')
                    
                    # 清理 HTML
                    clean_text = soup.get_text()
                    clean_text = re.sub(r'\s+', ' ', clean_text)
                    
                    # 查找账单周期
                    bill_period_match = re.search(r'(\d{4}/\d{2}/\d{2}-\d{4}/\d{2}/\d{2})', clean_text)
                    
                    if bill_period_match:
                        bill_period = bill_period_match.group(1)
                        pos = clean_text.find(bill_period)
                        
                        if pos != -1:
                            snippet = clean_text[pos:]
                            
                            # 查找所有￥金额
                            amounts = re.findall(r'￥\s*([0-9,]+\.[0-9]+)', snippet)
                            
                            if amounts:
                                print(f"   找到的金额：{amounts[:5]}")
                                
                                # 确定目标金额
                                if 'e 招贷' not in subject and '分期' not in subject:
                                    if len(amounts) >= 2:
                                        target_amt = amounts[1]
                                    else:
                                        target_amt = amounts[0] if amounts else None
                                else:
                                    target_amt = amounts[0] if amounts else None
                                
                                if target_amt:
                                    # 清理日期连接
                                    amt_str = target_amt.replace(',', '')
                                    if '.' in amt_str:
                                        integer_part, decimal_part = amt_str.split('.', 1)
                                        if len(decimal_part) > 2:
                                            amt_str = f"{integer_part}.{decimal_part[:2]}"
                                    
                                    try:
                                        amount = float(amt_str)
                                        print(f"   ✓ 提取金额：¥{amount:,.2f}")
                                    except:
                                        print(f"   ✗ 金额转换失败：{target_amt}")
                    
                    print()
                else:
                    print(f"{i}. {subject} - 跳过（{days_ago}天前，超过 15 天）")
                    print()

mail.close()
mail.logout()
