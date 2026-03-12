#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
检查兴业银行的纯文本内容
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


def check_cib_text():
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
                    print(f"邮件日期：{decode_mime_words(msg.get('Date', ''))}\n")
                    
                    # 获取纯文本内容
                    text_body = ""
                    html_body = ""
                    
                    if msg.is_multipart():
                        for part in msg.walk():
                            content_type = part.get_content_type()
                            
                            if content_type == 'text/plain':
                                try:
                                    charset = part.get_content_charset() or 'utf-8'
                                    text_body = part.get_payload(decode=True).decode(charset, errors='ignore')
                                except:
                                    pass
                            
                            elif content_type == 'text/html':
                                try:
                                    charset = part.get_content_charset() or 'utf-8'
                                    html_body = part.get_payload(decode=True).decode(charset, errors='ignore')
                                except:
                                    pass
                    else:
                        try:
                            charset = msg.get_content_charset() or 'utf-8'
                            text_body = msg.get_payload(decode=True).decode(charset, errors='ignore')
                        except:
                            pass
                    
                    print(f"纯文本长度：{len(text_body)} 字符")
                    print(f"HTML 长度：{len(html_body)} 字符\n")
                    
                    if text_body:
                        print("【纯文本内容】")
                        print("-"*80)
                        print(text_body[:2000])
                        print("-"*80)
                        
                        # 搜索金额
                        print("\n【搜索金额】")
                        all_amounts = re.findall(r'￥([0-9,]+\.?[0-9]*)', text_body)
                        if all_amounts:
                            print(f"所有￥金额：{all_amounts}")
                        
                        # 搜索还款日
                        print("\n【搜索还款日】")
                        due_matches = re.findall(r'([0-9]{4}[-/.][0-9]{1,2}[-/.][0-9]{1,2})', text_body)
                        if due_matches:
                            print(f"所有日期：{due_matches[:10]}")
                    else:
                        print("未找到纯文本内容")
                    
                    return
    
    mail.logout()


if __name__ == "__main__":
    check_cib_text()
