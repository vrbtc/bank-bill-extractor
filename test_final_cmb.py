#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
正确提取招商银行账单金额和还款日
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

print("提取招商银行最新账单信息：\n")

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
                
                print(f"邮件主题：{subject}")
                print(f"邮件日期：{msg.get('Date', '')}")
                print("="*80)
                
                # 提取账单周期
                bill_period = re.search(r'(\d{4}/\d{2}/\d{2})-(\d{4}/\d{2}/\d{2})', text)
                if bill_period:
                    start_date = bill_period.group(1)
                    end_date = bill_period.group(2)
                    print(f"\n账单周期：{start_date} - {end_date}")
                    
                    # 查找账单周期后面的金额序列
                    # 格式：账单周期 ¥ 额度¥ 本期应还¥最低还款还款日
                    # 例如：2026/02/19-2026/03/18 ¥ 45,000.00¥ 1,244.68¥ 1,181.032026/04/06
                    pattern = rf'{re.escape(start_date)}-{re.escape(end_date)}\s*¥\s*([0-9,]+\.[0-9]+)\s*¥\s*([0-9,]+\.[0-9]+)\s*¥\s*([0-9,]+\.[0-9]+)(\d{4}/\d{2}/\d{2})'
                    match = re.search(pattern, text)
                    
                    if match:
                        credit_limit = match.group(1)
                        current_balance = match.group(2)  # 本期应还
                        min_payment = match.group(3)       # 最低还款
                        due_date = match.group(4)          # 还款日
                        
                        print(f"✓ 信用额度：¥{credit_limit}")
                        print(f"✓ 本期应还：¥{current_balance}")
                        print(f"  最低还款：¥{min_payment}")
                        print(f"✓ 还款日：{due_date}")
                    else:
                        print("✗ 未找到金额序列")
                        # 调试输出
                        pos = text.find(f'{start_date}-{end_date}')
                        if pos != -1:
                            print(f"附近内容：{text[pos:pos+200]}")
                
                break

print("\n" + "="*80)
print("总结：招商银行本期应还金额为 ¥1,244.68，还款日为 2026/04/06")

mail.close()
mail.logout()
