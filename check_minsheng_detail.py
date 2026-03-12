#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
详细检查民生银行邮件内容
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


def check_minsheng_detail():
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
                    print("="*80)
                    print(f"民生银行邮件：{subject}")
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
                    
                    print("\n搜索关键信息：")
                    print("-"*80)
                    
                    amount_patterns = [
                        r'本期应还款.*?￥([0-9,]+\.?[0-9]*)',
                        r'本期账单.*?￥([0-9,]+\.?[0-9]*)',
                        r'应还金额.*?￥([0-9,]+\.?[0-9]*)',
                        r'人民币.*?([0-9,]+\.?[0-9]*)',
                        r'账单金额.*?([0-9,]+\.?[0-9]*)',
                    ]
                    
                    for pattern in amount_patterns:
                        matches = re.findall(pattern, full_text, re.DOTALL)
                        if matches:
                            print(f"✓ 模式 '{pattern}' 匹配到：{matches}")
                    
                    due_patterns = [
                        r'到期还款日.*?([0-9]{4}[-/.][0-9]{1,2}[-/.][0-9]{1,2})',
                        r'还款日.*?([0-9]{4}[-/.][0-9]{1,2}[-/.][0-9]{1,2})',
                    ]
                    
                    for pattern in due_patterns:
                        matches = re.findall(pattern, full_text)
                        if matches:
                            print(f"✓ 模式 '{pattern}' 匹配到：{matches}")
                    
                    print("\nHTML 内容片段（包含'本期应还款'的位置）：")
                    print("-"*80)
                    
                    pos = full_text.find('本期应还款')
                    if pos != -1:
                        start = max(0, pos - 200)
                        end = min(len(full_text), pos + 500)
                        print(full_text[start:end])
                    else:
                        print("未找到'本期应还款'关键词")
                        print(f"\nHTML 前 2000 字符：")
                        print(full_text[:2000])
                    
                    return
    
    print("未找到民生银行邮件")
    mail.logout()


if __name__ == "__main__":
    check_minsheng_detail()
