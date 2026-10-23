#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
列出所有邮件主题
"""

import imaplib
import email
from email.header import decode_header


# 凭据统一从 config.json 导入（2026-10-23 安全整改：移除硬编码；config.json 已 gitignore）
from config import get_all_emails as _get_all_emails
_email_cfg = (_get_all_emails() or [{}])[0]
EMAIL_ADDRESS = _email_cfg.get('address', '')
PASSWORD = _email_cfg.get('password', '')
IMAP_SERVER = _email_cfg.get('imap_server', 'imap.aliyun.com')
IMAP_PORT = int(_email_cfg.get('imap_port') or 993)


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


def list_subjects():
    print("连接邮箱...")
    mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
    mail.login(EMAIL_ADDRESS, PASSWORD)
    print("登录成功！")
    
    mail.select('INBOX')
    status, messages = mail.search(None, 'ALL')
    
    email_ids = messages[0].split()
    print(f"共找到 {len(email_ids)} 封邮件\n")
    
    count = 0
    for email_id in reversed(email_ids):
        status, msg_data = mail.fetch(email_id, '(RFC822)')
        
        if status != 'OK':
            continue
        
        for response_part in msg_data:
            if isinstance(response_part, tuple):
                msg = email.message_from_bytes(response_part[1])
                subject = decode_mime_words(msg.get('Subject', ''))
                date = decode_mime_words(msg.get('Date', ''))
                print(f"[{count+1}] {date[:30]} - {subject}")
                
                # 检查是否可能是广发银行邮件
                if '广' in subject or 'GF' in subject.upper() or 'CGB' in subject.upper():
                    print(f"  >>> 可能是广发银行邮件！")
                
                count += 1
                if count >= 100:
                    break
        if count >= 100:
            break
    
    mail.logout()
    print(f"\n已列出最近 {count} 封邮件")


if __name__ == "__main__":
    list_subjects()
