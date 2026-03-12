#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
详细检查兴业银行的 HTML 结构
"""

import imaplib
import email
from email.header import decode_header


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


def check_cib_html():
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
                
                if '兴业' in subject:
                    print(f"找到：{subject}")
                    print("="*80)
                    
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
                    
                    print(f"HTML 长度：{len(html_body)} 字符")
                    
                    # 保存 HTML
                    with open('cib_email.html', 'w', encoding='utf-8') as f:
                        f.write(html_body)
                    print(f"HTML 已保存至：cib_email.html\n")
                    
                    # 显示前 3000 字符
                    print("HTML 前 3000 字符：")
                    print("-"*80)
                    print(html_body[:3000])
                    print("-"*80)
                    
                    return
    
    mail.logout()


if __name__ == "__main__":
    check_cib_html()
