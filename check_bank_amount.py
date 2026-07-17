#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
检查交通银行账单提取
"""

import imaplib
import email
from email.header import decode_header
import re
from bs4 import BeautifulSoup
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

# 查找交通银行邮件
print("查找交通银行最新账单...\n")

for email_id in reversed(email_ids[-30:]):
    status, msg_data = mail.fetch(email_id, "(RFC822)")
    for response_part in msg_data:
        if isinstance(response_part, tuple):
            msg = email.message_from_bytes(response_part[1])
            subject = decode_mime_words(msg.get("Subject", ""))
            
            if "交通银行" in subject and "白金信用卡" in subject:
                print(f"邮件主题：{subject}")
                print(f"邮件日期：{msg.get('Date', '')}")
                print("="*80)
                
                html_content = get_html_content(msg)
                soup = BeautifulSoup(html_content, 'html.parser')
                full_text = f"{subject}\n{html_content}"
                full_text = full_text.replace('&yen;', '￥').replace('&nbsp;', ' ')
                
                # 清理 HTML
                clean_text = soup.get_text()
                clean_text = re.sub(r'\s+', ' ', clean_text)
                
                # 搜索关键词
                keywords = ['本期应还款', '本期账单', '应还金额', 'New Balance', '27075.99']
                
                print("\n【搜索关键词】")
                for keyword in keywords:
                    if keyword in clean_text:
                        pos = clean_text.find(keyword)
                        context = clean_text[max(0, pos-50):pos+100]
                        print(f"✓ 找到 '{keyword}': {context}")
                
                # 查找所有金额
                print("\n【查找所有金额】")
                amounts = re.findall(r'￥\s*([0-9,]+\.[0-9]+)', clean_text)
                print(f"找到的金额：{amounts[:20]}")
                
                # 查找表格
                print("\n【查找表格内容】")
                tables = soup.find_all('table')
                for i, table in enumerate(tables[:3]):
                    table_text = table.get_text()
                    if '27075' in table_text or '本期' in table_text:
                        print(f"\n表格 {i+1}:")
                        print(table_text[:500])
                
                break

mail.close()
mail.logout()
