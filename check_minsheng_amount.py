#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
重新检查民生银行账单的正确金额
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


def check_minsheng():
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
                
                if '民生' in subject and '信用卡' in subject:
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
                    
                    # 查找所有包含"9901"或"9,901"的位置
                    print("\n搜索 9901 相关的金额：")
                    print("-"*80)
                    
                    pos = full_text.find('9,901')
                    if pos != -1:
                        start = max(0, pos - 500)
                        end = min(len(full_text), pos + 500)
                        print(f"\n包含'9,901'的片段：")
                        print(full_text[start:end])
                        print()
                    
                    # 查找所有人民币金额
                    all_amounts = re.findall(r'￥([0-9,]+\.?[0-9]*)', full_text)
                    if all_amounts:
                        print(f"\n所有￥金额：{all_amounts}")
                    
                    # 查找表格中的金额
                    table_amounts = re.findall(r'<td[^>]*>[^<]*([0-9,]+\.[0-9]+)[^<]*</td>', full_text)
                    if table_amounts:
                        print(f"\n表格中的金额：{table_amounts[:20]}")
                    
                    print("\n" + "="*80)
                    return
    
    print("未找到民生银行邮件")
    mail.logout()


if __name__ == "__main__":
    check_minsheng()
