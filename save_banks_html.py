#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
保存建设银行和民生银行的完整 HTML
"""

import imaplib
import email


# 凭据统一从 config.json 导入（2026-10-23 安全整改：移除硬编码；config.json 已 gitignore）
from config import get_all_emails as _get_all_emails
_email_cfg = (_get_all_emails() or [{}])[0]
EMAIL_ADDRESS = _email_cfg.get('address', '')
PASSWORD = _email_cfg.get('password', '')
IMAP_SERVER = _email_cfg.get('imap_server', 'imap.aliyun.com')
IMAP_PORT = int(_email_cfg.get('imap_port') or 993)


def save_html():
    print("连接邮箱...")
    mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
    mail.login(EMAIL_ADDRESS, PASSWORD)
    print("登录成功！")
    
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
                subject = str(msg.get('Subject', ''))
                
                if '建设银行' in subject:
                    print(f"\n找到建设银行：{subject}")
                    
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
                    
                    with open('ccb_email_full.html', 'w', encoding='utf-8') as f:
                        f.write(html_body)
                    print(f"已保存：ccb_email_full.html ({len(html_body)} 字符)")
                
                if '民生' in subject and '信用卡' in subject:
                    print(f"\n找到民生银行：{subject}")
                    
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
                    
                    with open('minsheng_email_full.html', 'w', encoding='utf-8') as f:
                        f.write(html_body)
                    print(f"已保存：minsheng_email_full.html ({len(html_body)} 字符)")
    
    mail.logout()


if __name__ == "__main__":
    save_html()
