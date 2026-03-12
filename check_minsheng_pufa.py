#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
检查民生、浦发、邮储银行邮件
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


def check_specific_banks():
    print("连接邮箱...")
    mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
    mail.login(EMAIL_ADDRESS, PASSWORD)
    print("登录成功！\n")
    
    mail.select('INBOX')
    status, messages = mail.search(None, 'ALL')
    
    email_ids = messages[0].split()
    print(f"共找到 {len(email_ids)} 封邮件\n")
    
    target_banks = ['民生', '浦发', '邮储', '邮政']
    
    for idx, email_id in enumerate(reversed(email_ids), 1):
        status, msg_data = mail.fetch(email_id, '(RFC822)')
        
        if status != 'OK':
            continue
        
        for response_part in msg_data:
            if isinstance(response_part, tuple):
                msg = email.message_from_bytes(response_part[1])
                subject = decode_mime_words(msg.get('Subject', ''))
                date = decode_mime_words(msg.get('Date', ''))
                
                for bank in target_banks:
                    if bank in subject:
                        print(f"[{idx}] 找到 {bank} 银行邮件：")
                        print(f"    主题：{subject}")
                        print(f"    日期：{date}")
                        
                        body = ""
                        html_body = ""
                        
                        if msg.is_multipart():
                            for part in msg.walk():
                                content_type = part.get_content_type()
                                content_disposition = str(part.get('Content-Disposition', ''))
                                
                                if 'attachment' in content_disposition:
                                    continue
                                
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
                                        if charset.lower() in ['gbk', 'gb2312', 'gb18030']:
                                            html_body = part.get_payload(decode=True).decode('gbk', errors='ignore')
                                        else:
                                            html_body = part.get_payload(decode=True).decode(charset, errors='ignore')
                                    except:
                                        pass
                                    break
                        else:
                            try:
                                charset = msg.get_content_charset() or 'utf-8'
                                if charset.lower() in ['gbk', 'gb2312', 'gb18030']:
                                    html_body = msg.get_payload(decode=True).decode('gbk', errors='ignore')
                                else:
                                    html_body = msg.get_payload(decode=True).decode(charset, errors='ignore')
                            except:
                                pass
                        
                        full_text = f"{subject}\n{body}\n{html_body}"
                        
                        print(f"    内容长度：HTML={len(html_body)}, 文本={len(body)}")
                        
                        if '账单' in full_text or '还款' in full_text or '信用卡' in full_text:
                            print(f"    ✓ 包含账单/还款/信用卡关键词")
                            
                            import re
                            amount_match = re.search(r'本期应还款.*?￥([0-9,]+\.?[0-9]*)', full_text)
                            if amount_match:
                                print(f"    ✓ 本期应还款：￥{amount_match.group(1)}")
                            
                            due_match = re.search(r'到期还款日.*?([0-9]{4}[-/.][0-9]{1,2}[-/.][0-9]{1,2})', full_text)
                            if due_match:
                                print(f"    ✓ 还款日：{due_match.group(1)}")
                        else:
                            print(f"    ✗ 不包含账单关键词")
                        
                        print()
    
    mail.logout()


if __name__ == "__main__":
    check_specific_banks()
