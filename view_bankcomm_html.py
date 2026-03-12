#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
查看交通银行邮件的完整 HTML 内容
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


def view_html():
    print("连接邮箱...")
    mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
    mail.login(EMAIL_ADDRESS, PASSWORD)
    print("登录成功！")
    
    mail.select('INBOX')
    status, messages = mail.search(None, 'ALL')
    
    if status != 'OK':
        return
    
    email_ids = messages[0].split()
    
    for email_id in reversed(email_ids):
        status, msg_data = mail.fetch(email_id, '(RFC822)')
        
        if status != 'OK':
            continue
        
        for response_part in msg_data:
            if isinstance(response_part, tuple):
                msg = email.message_from_bytes(response_part[1])
                subject = decode_mime_words(msg.get('Subject', ''))
                
                if '交通' in subject:
                    print(f"\n交通银行邮件：{subject}")
                    print("="*80)
                    
                    for part in msg.walk():
                        if part.get_content_type() == 'text/html':
                            try:
                                charset = part.get_content_charset() or 'utf-8'
                                html_content = part.get_payload(decode=True).decode(charset, errors='ignore')
                                
                                print(f"HTML 长度：{len(html_content)} 字符")
                                print("\nHTML 内容预览:")
                                print("="*80)
                                print(html_content[:5000])
                                print("\n" + "="*80)
                                
                                with open('bankcomm_email.html', 'w', encoding='utf-8') as f:
                                    f.write(html_content)
                                print("\n完整 HTML 已保存至：bankcomm_email.html")
                                
                                return
                            except Exception as e:
                                print(f"错误：{e}")
    
    mail.logout()


if __name__ == "__main__":
    view_html()
