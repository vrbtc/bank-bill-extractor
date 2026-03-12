#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
详细搜索兴业银行的金额和还款日
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


def search_cib_detail():
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
                    print(f"检查：{subject}")
                    print("="*80)
                    
                    # 获取所有内容
                    text_body = ""
                    
                    if msg.is_multipart():
                        for part in msg.walk():
                            if part.get_content_type() == 'text/plain':
                                try:
                                    charset = part.get_content_charset() or 'utf-8'
                                    text_body = part.get_payload(decode=True).decode(charset, errors='ignore')
                                except:
                                    pass
                    else:
                        try:
                            charset = msg.get_content_charset() or 'utf-8'
                            text_body = msg.get_payload(decode=True).decode(charset, errors='ignore')
                        except:
                            pass
                    
                    full_text = f"{subject}\n{text_body}"
                    
                    # 搜索所有可能的金额格式
                    print("\n【搜索所有金额格式】")
                    print("-"*80)
                    
                    patterns = [
                        (r'[0-9,]+\.[0-9]{2}', '数字金额'),
                        (r'应还款.*?[0-9,]+', '应还款'),
                        (r'账单.*?[0-9,]+', '账单'),
                        (r'最低.*?[0-9,]+', '最低'),
                        (r'消费.*?[0-9,]+', '消费'),
                    ]
                    
                    for pattern, desc in patterns:
                        matches = re.findall(pattern, full_text, re.IGNORECASE)
                        if matches:
                            print(f"{desc}: {matches[:10]}")
                    
                    # 搜索特定关键词
                    print("\n【搜索关键词上下文】")
                    print("-"*80)
                    
                    keywords = ['到期', '还款', '账单', '金额', '应还', '最低']
                    for keyword in keywords:
                        pos = full_text.find(keyword)
                        if pos != -1:
                            start = max(0, pos - 100)
                            end = min(len(full_text), pos + 300)
                            print(f"\n'{keyword}'的上下文：")
                            print(full_text[start:end])
                            print()
                    
                    # 保存完整文本
                    with open('cib_full_text.txt', 'w', encoding='utf-8') as f:
                        f.write(full_text)
                    print(f"\n完整文本已保存至：cib_full_text.txt ({len(full_text)} 字符)")
                    
                    return
    
    mail.logout()


if __name__ == "__main__":
    search_cib_detail()
