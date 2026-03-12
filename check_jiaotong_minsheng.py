#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
专门提取交通银行和民生银行账单
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


def check_specific_banks():
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
                
                if '交通银行' in subject or '民生信用卡' in subject:
                    print("="*80)
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
                    
                    html_text = html_body.replace('&yen;', '￥').replace('&amp;', '&')
                    
                    due_match = re.search(r'到期还款日.*?([0-9]{4}[-/.][0-9]{1,2}[-/.][0-9]{1,2})', html_text)
                    if due_match:
                        print(f"✓ 还款日：{due_match.group(1)}")
                    else:
                        print("✗ 未找到还款日")
                    
                    amount_match = re.search(r'本期应还款.*?￥([0-9,]+\.?[0-9]*)', html_text)
                    if amount_match:
                        print(f"✓ 本期应还款：￥{amount_match.group(1)}")
                    else:
                        print("✗ 未找到本期应还款")
                    
                    print("\nHTML 片段:")
                    print("-"*80)
                    start = max(0, html_text.find('到期还款日') - 100)
                    end = min(len(html_text), html_text.find('到期还款日') + 500)
                    print(html_text[start:end])
                    print("-"*80)
                    print()
    
    mail.logout()


if __name__ == "__main__":
    check_specific_banks()
