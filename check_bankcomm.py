#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
专门检查交通银行邮件的详细内容
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


def check_bankcomm_email():
    print("连接邮箱...")
    mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
    mail.login(EMAIL_ADDRESS, PASSWORD)
    print("登录成功！")
    
    mail.select('INBOX')
    status, messages = mail.search(None, 'ALL')
    
    if status != 'OK':
        print("搜索失败")
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
                
                if '交通' in subject or 'bankcomm' in subject.lower():
                    print("\n" + "="*80)
                    print(f"找到交通银行邮件！")
                    print(f"主题：{subject}")
                    print(f"日期：{decode_mime_words(msg.get('Date', ''))}")
                    print("="*80)
                    
                    print(f"\n邮件部分列表:")
                    for i, part in enumerate(msg.walk()):
                        print(f"  部分 {i}: {part.get_content_type()}")
                        print(f"    Content-Disposition: {part.get('Content-Disposition')}")
                        print(f"    Content-ID: {part.get('Content-ID')}")
                        print(f"    Filename: {part.get_filename()}")
                    
                    body = ""
                    html_body = ""
                    
                    if msg.is_multipart():
                        for part in msg.walk():
                            content_type = part.get_content_type()
                            content_disposition = str(part.get('Content-Disposition', ''))
                            
                            if 'attachment' in content_disposition:
                                print(f"\n附件：{part.get_filename()}")
                                continue
                            
                            if content_type == 'text/plain':
                                try:
                                    charset = part.get_content_charset() or 'utf-8'
                                    body = part.get_payload(decode=True).decode(charset, errors='ignore')
                                    print(f"\n【纯文本内容】({len(body)} 字符):")
                                    print("-"*80)
                                    print(body[:2000])
                                except Exception as e:
                                    print(f"解析文本失败：{e}")
                            
                            elif content_type == 'text/html':
                                try:
                                    charset = part.get_content_charset() or 'utf-8'
                                    html_body = part.get_payload(decode=True).decode(charset, errors='ignore')
                                    print(f"\n【HTML 内容】({len(html_body)} 字符):")
                                    print("-"*80)
                                    print(html_body[:3000])
                                except Exception as e:
                                    print(f"解析 HTML 失败：{e}")
                    
                    if not body and not html_body:
                        print("\n未找到文本或 HTML 内容，可能是图片邮件")
                    
                    return
    
    print("未找到交通银行邮件")
    mail.logout()


if __name__ == "__main__":
    check_bankcomm_email()
