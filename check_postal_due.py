#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
详细检查邮政储蓄银行的还款日
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


def check_postal_due_date():
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
                
                if '邮储' in subject or '邮政' in subject:
                    print(f"检查：{subject}")
                    print("="*80)
                    
                    html_body = ""
                    if msg.is_multipart():
                        for part in msg.walk():
                            if part.get_content_type() == 'text/html':
                                try:
                                    charset = part.get_content_charset() or 'utf-8'
                                    if charset.lower() in ['gbk', 'gb2312', 'gb18030']:
                                        html_body = part.get_payload(decode=True).decode('gbk', errors='ignore')
                                    else:
                                        html_body = part.get_payload(decode=True).decode(charset, errors='ignore')
                                except:
                                    pass
                                break
                    
                    full_text = f"{subject}\n{html_body}"
                    
                    # 搜索所有日期
                    print("\n【搜索所有日期】")
                    print("-"*80)
                    
                    date_patterns = [
                        r'([0-9]{4}[-/.年][0-9]{1,2}[-/.月][0-9]{1,2}[-/.日]*)',
                    ]
                    
                    for pattern in date_patterns:
                        matches = re.findall(pattern, full_text)
                        if matches:
                            print(f"日期：{matches[:10]}")
                    
                    # 搜索包含"还款日"的行
                    print("\n【搜索还款日相关信息】")
                    print("-"*80)
                    
                    keywords = ['到期还款日', '还款日', '最后还款日', 'Payment Due Date']
                    
                    for keyword in keywords:
                        pos = full_text.find(keyword)
                        if pos != -1:
                            start = max(0, pos - 100)
                            end = min(len(full_text), pos + 300)
                            print(f"\n包含'{keyword}'的片段：")
                            print(full_text[start:end])
                            print()
                    
                    # 保存到文件
                    with open('postal_email.html', 'w', encoding='utf-8') as f:
                        f.write(html_body)
                    print(f"\nHTML 已保存至：postal_email.html")
                    
                    return
    
    mail.logout()


if __name__ == "__main__":
    check_postal_due_date()
