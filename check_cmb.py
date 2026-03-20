#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
检查招商银行邮件内容
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


def check_cmb():
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
                
                if '招商' in subject and '信用卡' in subject:
                    print("="*80)
                    print(f"检查：{subject}")
                    print("="*80)
                    print(f"邮件日期：{decode_mime_words(msg.get('Date', ''))}\n")
                    
                    # 获取内容
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
                            content = msg.get_payload(decode=True).decode(charset, errors='ignore')
                            if msg.get_content_type() == 'text/html':
                                html_body = content
                            else:
                                text_body = content
                        except:
                            pass
                    
                    full_text = f"{subject}\n{text_body}\n{html_body}"
                    
                    print(f"纯文本长度：{len(text_body)}")
                    print(f"HTML 长度：{len(html_body)}")
                    
                    # 搜索所有数字金额（不带￥符号）
                    print("\n【搜索所有数字金额】")
                    print("-"*80)
                    
                    all_numbers = re.findall(r'([0-9,]+\.[0-9]{2})', full_text)
                    if all_numbers:
                        print(f"所有数字金额：{all_numbers[:30]}")
                    
                    # 查找表格中的金额
                    table_amounts = re.findall(r'<td[^>]*>[^<]*([0-9,]+\.[0-9]+)[^<]*</td>', html_body)
                    if table_amounts:
                        print(f"\n表格中的金额：{table_amounts[:20]}")
                    
                    # 搜索关键词
                    keywords = ['本期应还款', '账单金额', '最低还款额', '应还款额', '人民币', '本期全部应还款']
                    for keyword in keywords:
                        pos = full_text.find(keyword)
                        if pos != -1:
                            start = max(0, pos - 100)
                            end = min(len(full_text), pos + 300)
                            print(f"\n包含'{keyword}'的片段：")
                            print(full_text[start:end])
                    
                    # 搜索还款日
                    print("\n【搜索还款日】")
                    print("-"*80)
                    
                    due_patterns = [
                        r'到期还款日.*?([0-9]{4}[-/.年][0-9]{1,2}[-/.月][0-9]{1,2}[-/.日]*)',
                        r'还款日.*?([0-9]{4}[-/.][0-9]{1,2}[-/.][0-9]{1,2})',
                    ]
                    
                    for pattern in due_patterns:
                        matches = re.findall(pattern, full_text)
                        if matches:
                            print(f"还款日：{matches}")
                    
                    print("\n" + "="*80)
                    return
    
    print("未找到招商银行邮件")
    mail.logout()


if __name__ == "__main__":
    check_cmb()
