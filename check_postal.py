#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
检查邮政储蓄银行的邮件
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


def check_postal_bank():
    print("连接邮箱...")
    mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
    mail.login(EMAIL_ADDRESS, PASSWORD)
    print("登录成功！\n")
    
    mail.select('INBOX')
    status, messages = mail.search(None, 'ALL')
    
    email_ids = messages[0].split()
    
    target_keywords = ['邮政', '邮储']
    
    for idx, email_id in enumerate(reversed(email_ids), 1):
        status, msg_data = mail.fetch(email_id, '(RFC822)')
        
        if status != 'OK':
            continue
        
        for response_part in msg_data:
            if isinstance(response_part, tuple):
                msg = email.message_from_bytes(response_part[1])
                subject = decode_mime_words(msg.get('Subject', ''))
                
                for keyword in target_keywords:
                    if keyword in subject:
                        print(f"[{idx}] 找到邮政银行邮件：")
                        print(f"    主题：{subject}")
                        print(f"    日期：{decode_mime_words(msg.get('Date', ''))}")
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
                        
                        print("\n【搜索金额和还款日】")
                        print("-"*80)
                        
                        # 搜索所有金额
                        all_amounts = re.findall(r'￥([0-9,]+\.?[0-9]*)', full_text)
                        if all_amounts:
                            print(f"所有￥金额：{all_amounts}")
                        
                        # 搜索 303.69
                        if '303.69' in full_text or '303' in full_text:
                            pos = full_text.find('303')
                            start = max(0, pos - 300)
                            end = min(len(full_text), pos + 300)
                            print(f"\n包含'303'的片段：")
                            print(full_text[start:end])
                        
                        # 搜索还款日
                        due_patterns = [
                            r'到期还款日.*?([0-9]{4}[-/.][0-9]{1,2}[-/.][0-9]{1,2})',
                            r'还款日.*?([0-9]{4}[-/.][0-9]{1,2}[-/.][0-9]{1,2})',
                        ]
                        
                        for pattern in due_patterns:
                            matches = re.findall(pattern, full_text)
                            if matches:
                                print(f"\n✓ 还款日：{matches}")
                        
                        print("\n" + "="*80)
                        return
    
    print("未找到邮政银行邮件")
    mail.logout()


if __name__ == "__main__":
    check_postal_bank()
