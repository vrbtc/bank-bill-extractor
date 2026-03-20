#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
保存招商银行 HTML 并查找还款日
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


def save_cmb_html():
    print("连接邮箱...")
    mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
    mail.login(EMAIL_ADDRESS, PASSWORD)
    print("登录成功！\n")
    
    mail.select('INBOX')
    status, messages = mail.search(None, 'ALL')
    
    email_ids = messages[0].split()
    
    for email_id in reversed(email_ids):
        status, msg_data = mail.fetch(email_id, '(RFC822)')
        
        if status != 'OK':
            continue
        
        for response_part in msg_data:
            if isinstance(response_part, tuple):
                msg = email.message_from_bytes(response_part[1])
                subject = decode_mime_words(msg.get('Subject', ''))
                
                if '招商' in subject and '信用卡' in subject:
                    print(f"找到：{subject}")
                    
                    html_body = ""
                    if msg.is_multipart():
                        for part in msg.walk():
                            if part.get_content_type() == 'text/html':
                                try:
                                    charset = part.get_content_charset() or 'utf-8'
                                    html_body = part.get_payload(decode=True).decode(charset, errors='ignore')
                                except:
                                    pass
                                break
                    
                    # 保存 HTML
                    with open('cmb_email.html', 'w', encoding='utf-8') as f:
                        f.write(html_body)
                    print(f"HTML 已保存至：cmb_email.html ({len(html_body)} 字符)\n")
                    
                    # 搜索还款日
                    print("【搜索还款日相关信息】")
                    print("-"*80)
                    
                    full_text = f"{subject}\n{html_body}"
                    
                    # 搜索所有日期格式
                    date_patterns = [
                        r'([0-9]{4}[-/.年][0-9]{1,2}[-/.月][0-9]{1,2}[-/.日]*)',
                        r'(\d{2}/\d{2}/\d{4})',
                    ]
                    
                    for pattern in date_patterns:
                        matches = re.findall(pattern, full_text)
                        if matches:
                            print(f"\n模式 '{pattern}': {matches[:20]}")
                    
                    # 搜索包含"还款"的日期
                    keywords = ['到期日', '还款日', '最后还款', 'Payment Due']
                    for keyword in keywords:
                        pos = full_text.find(keyword)
                        if pos != -1:
                            start = max(0, pos - 100)
                            end = min(len(full_text), pos + 300)
                            print(f"\n包含'{keyword}'的片段：")
                            print(full_text[start:end])
                    
                    return
    
    mail.logout()


if __name__ == "__main__":
    save_cmb_html()
