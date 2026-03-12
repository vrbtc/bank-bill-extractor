#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
保存建设银行和交通银行的 HTML 内容
"""

import imaplib
import email


EMAIL_ADDRESS = "rrking@aliyun.com"
PASSWORD = "Aa2599589"
IMAP_SERVER = "imap.aliyun.com"
IMAP_PORT = 993


def save_bank_html():
    print("连接邮箱...")
    mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
    mail.login(EMAIL_ADDRESS, PASSWORD)
    print("登录成功！")
    
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
                subject = str(msg.get('Subject', ''))
                
                if '建设银行' in subject:
                    print(f"\n找到建设银行：{subject}")
                    
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
                    
                    with open('ccb_email.html', 'w', encoding='utf-8') as f:
                        f.write(html_body)
                    print(f"HTML 已保存：ccb_email.html ({len(html_body)} 字符)")
                
                if '交通银行' in subject:
                    print(f"\n找到交通银行：{subject}")
                    
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
                    
                    with open('bankcomm_email.html', 'w', encoding='utf-8') as f:
                        f.write(html_body)
                    print(f"HTML 已保存：bankcomm_email.html ({len(html_body)} 字符)")
    
    mail.logout()


if __name__ == "__main__":
    save_bank_html()
