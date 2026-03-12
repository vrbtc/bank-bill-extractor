#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
检查所有银行相关的邮件
"""

import imaplib
import email
from email.header import decode_header
import html2text
from bs4 import BeautifulSoup
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


def html_to_text(html_content):
    """将 HTML 转换为纯文本"""
    if not html_content:
        return ""
    
    soup = BeautifulSoup(html_content, 'html.parser')
    
    for tag in soup(['script', 'style', 'head', 'meta', 'link']):
        tag.decompose()
    
    text = soup.get_text(separator='\n')
    
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return '\n'.join(lines)


def check_all_banks():
    print("连接邮箱...")
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
    
    bank_keywords = [
        '交通银行', '招商银行', '中国银行', '建设银行', '工商银行', '农业银行',
        '兴业银行', '中信银行', '光大银行', '民生银行', '浦发银行',
        '平安银行', '广发银行', '华夏银行', '邮储银行', '邮政储蓄',
        '上海银行', '北京银行', '信用卡', '账单'
    ]
    
    found_emails = []
    
    for idx, email_id in enumerate(reversed(email_ids), 1):
        status, msg_data = mail.fetch(email_id, '(RFC822)')
        
        if status != 'OK':
            continue
        
        for response_part in msg_data:
            if isinstance(response_part, tuple):
                msg = email.message_from_bytes(response_part[1])
                subject = decode_mime_words(msg.get('Subject', ''))
                date = decode_mime_words(msg.get('Date', ''))
                
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
                                html_body = part.get_payload(decode=True).decode(charset, errors='ignore')
                            except:
                                pass
                            break
                else:
                    try:
                        content_type = msg.get_content_type()
                        charset = msg.get_content_charset() or 'utf-8'
                        
                        if content_type == 'text/plain':
                            body = msg.get_payload(decode=True).decode(charset, errors='ignore')
                        elif content_type == 'text/html':
                            html_body = msg.get_payload(decode=True).decode(charset, errors='ignore')
                    except:
                        pass
                
                full_text = f"{subject}\n{body}\n{html_body}"
                
                matched_banks = [bank for bank in bank_keywords if bank in full_text]
                
                if matched_banks:
                    found_emails.append({
                        'idx': idx,
                        'subject': subject,
                        'date': date,
                        'banks': matched_banks,
                        'has_html': bool(html_body),
                        'html_length': len(html_body) if html_body else 0
                    })
    
    print("="*80)
    print(f"找到 {len(found_emails)} 封银行相关邮件：")
    print("="*80)
    
    for email_info in found_emails:
        print(f"\n{email_info['idx']}. {email_info['subject']}")
        print(f"   日期：{email_info['date']}")
        print(f"   匹配银行：{', '.join(email_info['banks'])}")
        print(f"   HTML 长度：{email_info['html_length']} 字符")
    
    mail.logout()
    
    return found_emails


if __name__ == "__main__":
    check_all_banks()
