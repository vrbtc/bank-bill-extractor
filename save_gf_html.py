#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
保存广发银行的完整 HTML 和文本
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


def save_html():
    print("连接邮箱...")
    mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
    mail.login(EMAIL_ADDRESS, PASSWORD)
    print("登录成功！")
    
    mail.select('INBOX')
    status, messages = mail.search(None, 'ALL')
    
    email_ids = messages[0].split()
    
    gf_count = 0
    
    for email_id in reversed(email_ids):
        status, msg_data = mail.fetch(email_id, '(RFC822)')
        
        if status != 'OK':
            continue
        
        for response_part in msg_data:
            if isinstance(response_part, tuple):
                msg = email.message_from_bytes(response_part[1])
                subject = decode_mime_words(msg.get('Subject', ''))
                
                if '广发' in subject:
                    gf_count += 1
                    print(f"\n找到广发银行 #{gf_count}：{subject}")
                    
                    html_body = ""
                    text_body = ""
                    
                    if msg.is_multipart():
                        for part in msg.walk():
                            content_type = part.get_content_type()
                            print(f"  发现内容类型：{content_type}")
                            
                            if content_type == 'text/html':
                                try:
                                    charset = part.get_content_charset() or 'utf-8'
                                    if charset.lower() in ['gbk', 'gb2312', 'gb18030']:
                                        html_body = part.get_payload(decode=True).decode('gbk', errors='ignore')
                                    else:
                                        html_body = part.get_payload(decode=True).decode(charset, errors='ignore')
                                except Exception as e:
                                    print(f"  HTML解码失败：{e}")
                                    try:
                                        html_body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                                    except:
                                        pass
                            
                            elif content_type == 'text/plain':
                                try:
                                    charset = part.get_content_charset() or 'utf-8'
                                    if charset.lower() in ['gbk', 'gb2312', 'gb18030']:
                                        text_body = part.get_payload(decode=True).decode('gbk', errors='ignore')
                                    else:
                                        text_body = part.get_payload(decode=True).decode(charset, errors='ignore')
                                except Exception as e:
                                    print(f"  文本解码失败：{e}")
                                    try:
                                        text_body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                                    except:
                                        pass
                    else:
                        content_type = msg.get_content_type()
                        print(f"  单部分邮件，内容类型：{content_type}")
                        try:
                            charset = msg.get_content_charset() or 'utf-8'
                            if charset.lower() in ['gbk', 'gb2312', 'gb18030']:
                                body = msg.get_payload(decode=True).decode('gbk', errors='ignore')
                            else:
                                body = msg.get_payload(decode=True).decode(charset, errors='ignore')
                            if content_type == 'text/html':
                                html_body = body
                            else:
                                text_body = body
                        except Exception as e:
                            print(f"  解码失败：{e}")
                    
                    # 保存HTML
                    if html_body:
                        html_filename = f'gf_email_{gf_count}.html'
                        with open(html_filename, 'w', encoding='utf-8') as f:
                            f.write(html_body)
                        print(f"  已保存HTML：{html_filename} ({len(html_body)} 字符)")
                    
                    # 保存文本
                    if text_body:
                        text_filename = f'gf_email_{gf_count}.txt'
                        with open(text_filename, 'w', encoding='utf-8') as f:
                            f.write(text_body)
                        print(f"  已保存文本：{text_filename} ({len(text_body)} 字符)")
                    
                    if not html_body and not text_body:
                        print("  警告：未找到任何内容！")
    
    mail.logout()
    print(f"\n共保存 {gf_count} 封广发银行邮件")


if __name__ == "__main__":
    save_html()
