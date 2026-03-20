#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
调试招商银行邮件结构
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

# 连接邮箱
mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
mail.login(EMAIL_ADDRESS, PASSWORD)
mail.select("INBOX")

status, messages = mail.search(None, "ALL")
email_ids = messages[0].split()

# 查找最新的招商银行信用卡电子账单
for email_id in reversed(email_ids[-20:]):
    status, msg_data = mail.fetch(email_id, "(RFC822)")
    for response_part in msg_data:
        if isinstance(response_part, tuple):
            msg = email.message_from_bytes(response_part[1])
            subject = decode_mime_words(msg.get("Subject", ""))
            
            if "招商银行信用卡电子账单" in subject and "分期" not in subject and "e 招贷" not in subject:
                print(f"邮件主题：{subject}")
                print(f"邮件日期：{msg.get('Date', '')}")
                print(f"Content-Type: {msg.get_content_type()}")
                print(f"Is multipart: {msg.is_multipart()}")
                print("="*80)
                
                if msg.is_multipart():
                    print("\n【邮件部分结构】")
                    for i, part in enumerate(msg.walk()):
                        ctype = part.get_content_type()
                        cdispo = str(part.get("Content-Disposition"))
                        charset = part.get_content_charset()
                        print(f"  部分 {i}: 类型={ctype}, 编码={charset}, 处置={cdispo}")
                        
                        # 尝试获取每个 HTML 部分的内容
                        if ctype == "text/html":
                            try:
                                payload = part.get_payload(decode=True)
                                if payload:
                                    if charset and charset.lower() in ['gbk', 'gb2312', 'gb18030']:
                                        html_text = payload.decode('gbk', errors='ignore')
                                    else:
                                        html_text = payload.decode(charset or 'utf-8', errors='ignore')
                                    
                                    print(f"    HTML 长度：{len(html_text)}")
                                    # 检查是否包含 7601.17
                                    if '7601.17' in html_text:
                                        print(f"    ✓ 找到 7601.17!")
                                        # 保存这个 HTML
                                        with open(f'cmb_html_part_{i}.html', 'w', encoding='utf-8') as f:
                                            f.write(html_text)
                                        print(f"    已保存到：cmb_html_part_{i}.html")
                                        
                                        # 搜索还款日
                                        import re
                                        due_match = re.search(r'到期日期 [：:]\s*([0-9]{4}/[0-9]{2}/[0-9]{2})', html_text)
                                        if due_match:
                                            print(f"    ✓ 找到还款日：{due_match.group(1)}")
                                    else:
                                        print(f"    ✗ 未找到 7601.17")
                            except Exception as e:
                                print(f"    错误：{e}")
                
                break

mail.close()
mail.logout()
