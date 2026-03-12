#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
检查所有邮件，查找交通银行相关邮件
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
    """解码 MIME 编码的字符串"""
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


def connect_and_check():
    """连接邮箱并检查所有邮件"""
    print("正在连接邮箱...")
    mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
    mail.login(EMAIL_ADDRESS, PASSWORD)
    print("登录成功！")
    
    mail.select('INBOX')
    status, messages = mail.search(None, 'ALL')
    
    if status != 'OK':
        print("搜索失败")
        return
    
    email_ids = messages[0].split()
    print(f"共找到 {len(email_ids)} 封邮件\n")
    
    bank_keywords = ['交通', '银行', '信用卡', '账单', '还款', 'Bill', 'Statement']
    
    print("查找包含银行/账单关键词的邮件：")
    print("="*80)
    
    for email_id in reversed(email_ids[-50:]):
        status, msg_data = mail.fetch(email_id, '(RFC822)')
        
        if status != 'OK':
            continue
        
        for response_part in msg_data:
            if isinstance(response_part, tuple):
                msg = email.message_from_bytes(response_part[1])
                subject = decode_mime_words(msg.get('Subject', ''))
                date = decode_mime_words(msg.get('Date', ''))
                
                body = ""
                if msg.is_multipart():
                    for part in msg.walk():
                        content_type = part.get_content_type()
                        if content_type == 'text/plain':
                            try:
                                charset = part.get_content_charset() or 'utf-8'
                                body = part.get_payload(decode=True).decode(charset, errors='ignore')
                            except:
                                pass
                            break
                        elif content_type == 'text/html':
                            try:
                                charset = part.get_content_charset() or 'utf-8'
                                body = part.get_payload(decode=True).decode(charset, errors='ignore')
                            except:
                                pass
                            break
                else:
                    try:
                        charset = msg.get_content_charset() or 'utf-8'
                        body = msg.get_payload(decode=True).decode(charset, errors='ignore')
                    except:
                        pass
                
                full_text = f"{subject}\n{body}"
                
                found_keywords = [kw for kw in bank_keywords if kw.lower() in full_text.lower()]
                
                if found_keywords:
                    print(f"\n日期：{date}")
                    print(f"主题：{subject}")
                    print(f"匹配关键词：{', '.join(found_keywords)}")
                    print("-"*80)


if __name__ == "__main__":
    connect_and_check()
