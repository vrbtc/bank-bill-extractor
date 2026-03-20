#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
查找招商银行最新账单的还款日
"""

import imaplib
import email
from email.header import decode_header
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

# 查找最新的招商银行信用卡电子账单（非分期、非 e 招贷）
for email_id in reversed(email_ids[-20:]):
    status, msg_data = mail.fetch(email_id, "(RFC822)")
    for response_part in msg_data:
        if isinstance(response_part, tuple):
            msg = email.message_from_bytes(response_part[1])
            subject = decode_mime_words(msg.get("Subject", ""))
            
            # 只找普通的电子账单，不要分期或 e 招贷
            if "招商银行信用卡电子账单" in subject and "分期" not in subject and "e 招贷" not in subject:
                html_content = get_html_content(msg)
                full_text = html_content
                
                print(f"邮件主题：{subject}")
                print(f"邮件日期：{msg.get('Date', '')}")
                print("="*80)
                
                # 搜索所有包含"到期"的文字
                due_patterns = [
                    r'到期日期 [：:]\s*([0-9]{4}[-/年][0-9]{1,2}[-/月][0-9]{1,2}[日]?)',
                    r'到期还款日 [：:]\s*([0-9]{4}[-/年][0-9]{1,2}[-/月][0-9]{1,2}[日]?)',
                    r'还款日 [：:]\s*([0-9]{4}[-/年][0-9]{1,2}[-/月][0-9]{1,2}[日]?)',
                    r'最后还款日 [：:]\s*([0-9]{4}[-/年][0-9]{1,2}[-/月][0-9]{1,2}[日]?)',
                    r'Payment Due.*?[：:]\s*([0-9]{4}[-/年][0-9]{1,2}[-/月][0-9]{1,2}[日]?)',
                ]
                
                print("\n【搜索还款日】")
                for pattern in due_patterns:
                    matches = re.findall(pattern, full_text, re.IGNORECASE)
                    if matches:
                        print(f"模式 '{pattern}': {matches}")
                
                # 搜索所有日期格式的文本
                print("\n【搜索所有日期相关文本】")
                date_contexts = re.findall(r'.{0,30}([0-9]{4}[-/年][0-9]{1,2}[-/月][0-9]{1,2}[日]?).{0,30}', full_text)
                for ctx in date_contexts[:10]:  # 只显示前 10 个
                    if '到期' in ctx or '还款' in ctx or 'due' in ctx.lower():
                        print(f"  找到：{ctx}")
                
                # 显示金额附近的文本
                print("\n【搜索 7601.17 附近的文本】")
                pos = full_text.find('7601.17')
                if pos != -1:
                    context = full_text[max(0, pos-200):min(len(full_text), pos+200)]
                    context = context.replace('\n', ' ').replace('\r', ' ')
                    print(f"上下文：{context}")
                
                print("\n" + "="*80)
                break

mail.close()
mail.logout()
