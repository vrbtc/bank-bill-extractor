#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
重新检查建设银行和民生银行的正确金额和还款日
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


def check_banks():
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
                
                if '建设银行' in subject or '民生' in subject:
                    print("="*80)
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
                    
                    print("\n【搜索所有金额相关信息】")
                    print("-"*80)
                    
                    # 搜索所有包含金额的行
                    amount_keywords = [
                        '本期账单金额',
                        '本期应还款',
                        '最低还款额',
                        '账单金额',
                        '应还金额',
                        'New Balance',
                        'Total Balance',
                        'Balance',
                    ]
                    
                    for keyword in amount_keywords:
                        # 查找 keyword 后面跟着的金额
                        pattern = f'{keyword}[^￥$¥0-9]*[￥$¥]?\s*([0-9,]+\.?[0-9]*)'
                        matches = re.findall(pattern, full_text, re.IGNORECASE)
                        if matches:
                            print(f"✓ {keyword}: {matches}")
                    
                    # 查找所有人民币金额
                    all_amounts = re.findall(r'￥([0-9,]+\.?[0-9]*)', full_text)
                    if all_amounts:
                        print(f"\n所有￥金额：{all_amounts[:15]}")
                    
                    print("\n【搜索还款日信息】")
                    print("-"*80)
                    
                    due_keywords = [
                        '到期还款日',
                        '还款日',
                        '最后还款日',
                        'Payment Due Date',
                    ]
                    
                    for keyword in due_keywords:
                        pattern = f'{keyword}[^0-9]*([0-9]{{4}}[-/.][0-9]{{1,2}}[-/.][0-9]{{1,2}})'
                        matches = re.findall(pattern, full_text)
                        if matches:
                            print(f"✓ {keyword}: {matches}")
                    
                    print("\n【HTML 关键片段】")
                    print("-"*80)
                    
                    # 查找包含"本期账单金额"或"本期应还款"的片段
                    for keyword in ['本期账单金额', '本期应还款', '最低还款额', 'New Balance']:
                        pos = full_text.find(keyword)
                        if pos != -1:
                            start = max(0, pos - 200)
                            end = min(len(full_text), pos + 600)
                            print(f"\n包含'{keyword}'的片段：")
                            print(full_text[start:end])
                            print()
                    
                    print("\n" + "="*80)
                    print()
    
    mail.logout()


if __name__ == "__main__":
    check_banks()
