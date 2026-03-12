#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
检查所有银行邮件的存在情况
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


def check_all_banks():
    print("连接邮箱...")
    mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
    mail.login(EMAIL_ADDRESS, PASSWORD)
    print("登录成功！\n")
    
    mail.select('INBOX')
    status, messages = mail.search(None, 'ALL')
    
    email_ids = messages[0].split()
    print(f"共找到 {len(email_ids)} 封邮件\n")
    
    all_banks = {
        '交通银行': [],
        '招商银行': [],
        '中国银行': [],
        '建设银行': [],
        '工商银行': [],
        '农业银行': [],
        '兴业银行': [],
        '中信银行': [],
        '光大银行': [],
        '民生银行': [],
        '民生信用卡': [],
        '浦发银行': [],
        '平安银行': [],
        '广发银行': [],
        '华夏银行': [],
        '邮储银行': [],
        '邮政储蓄': [],
        '中银香港': [],
        'BOCHK': []
    }
    
    for idx, email_id in enumerate(reversed(email_ids), 1):
        status, msg_data = mail.fetch(email_id, '(RFC822)')
        
        if status != 'OK':
            continue
        
        for response_part in msg_data:
            if isinstance(response_part, tuple):
                msg = email.message_from_bytes(response_part[1])
                subject = decode_mime_words(msg.get('Subject', ''))
                date = decode_mime_words(msg.get('Date', ''))
                
                for bank in all_banks.keys():
                    if bank in subject:
                        all_banks[bank].append({
                            'idx': idx,
                            'subject': subject,
                            'date': date
                        })
    
    print("="*80)
    print("银行邮件统计")
    print("="*80)
    
    for bank, emails in all_banks.items():
        if emails:
            print(f"\n✓ {bank}: {len(emails)} 封")
            for e in emails:
                print(f"  [{e['idx']}] {e['subject']} ({e['date']})")
        else:
            print(f"✗ {bank}: 0 封")
    
    print("\n" + "="*80)
    
    mail.logout()


if __name__ == "__main__":
    check_all_banks()
