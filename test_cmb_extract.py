#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试招商银行账单提取
"""

import imaplib
import email
from email.header import decode_header
import re
import html2text
from bs4 import BeautifulSoup

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

def get_html_content(msg):
    """获取邮件的 HTML 内容"""
    html_body = ""
    
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            cdispo = str(part.get("Content-Disposition"))
            
            if ctype == "text/html" and "attachment" not in cdispo:
                try:
                    charset = part.get_content_charset() or 'utf-8'
                    if charset.lower() in ['gbk', 'gb2312', 'gb18030']:
                        html_body = part.get_payload(decode=True).decode('gbk', errors='ignore')
                    else:
                        html_body = part.get_payload(decode=True).decode(charset, errors='ignore')
                    break
                except:
                    try:
                        html_body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                        break
                    except:
                        pass
    else:
        try:
            charset = msg.get_content_charset() or 'utf-8'
            html_body = msg.get_payload(decode=True).decode(charset, errors='ignore')
        except:
            try:
                html_body = msg.get_payload(decode=True).decode('utf-8', errors='ignore')
            except:
                pass
    
    return html_body

# 连接邮箱
print("连接邮箱...")
mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
mail.login(EMAIL_ADDRESS, PASSWORD)
mail.select("INBOX")

# 搜索所有邮件
status, messages = mail.search(None, "ALL")
email_ids = messages[0].split()

print(f"共找到 {len(email_ids)} 封邮件")

# 查找招商银行的邮件
cmb_emails = []
for email_id in email_ids[-35:]:  # 最近 35 封
    status, msg_data = mail.fetch(email_id, "(RFC822)")
    for response_part in msg_data:
        if isinstance(response_part, tuple):
            msg = email.message_from_bytes(response_part[1])
            subject = decode_mime_words(msg.get("Subject", ""))
            
            if "招商银行" in subject or "CMB" in subject:
                html_content = get_html_content(msg)
                cmb_emails.append({
                    'id': email_id,
                    'subject': subject,
                    'date': msg.get("Date", ""),
                    'html': html_content
                })

print(f"\n找到 {len(cmb_emails)} 封招商银行邮件")

# 测试提取逻辑
for i, cmb_email in enumerate(cmb_emails[:3], 1):
    print(f"\n{'='*80}")
    print(f"测试邮件 {i}: {cmb_email['subject']}")
    print(f"{'='*80}")
    
    html_content = cmb_email['html']
    subject = cmb_email['subject']
    full_text = f"{subject}\n{html_content}"
    full_text = full_text.replace('&yen;', '￥').replace('&amp;', '&')
    
    # 识别银行
    bank_map = {
        '交通银行': '交通银行', '招商银行': '招商银行', '中国银行': '中国银行',
        '建设银行': '建设银行', '工商银行': '工商银行', '农业银行': '农业银行',
        '兴业银行': '兴业银行', '中信银行': '中信银行', '光大银行': '光大银行',
        '民生银行': '民生银行', '浦发银行': '浦发银行', '平安银行': '平安银行',
        '广发银行': '广发银行', '华夏银行': '华夏银行', '邮储银行': '邮储银行',
        '邮政储蓄': '邮储银行', 'bochk': '中银香港', '中银': '中银香港',
        'CMB': '招商银行'
    }
    
    bank_name = None
    for key, value in bank_map.items():
        if key in full_text:
            bank_name = value
            break
    
    print(f"识别银行：{bank_name}")
    
    if bank_name == '招商银行':
        # 招商银行特殊处理
        print("\n【执行招商银行特殊处理逻辑】")
        
        # 查找最大的合理金额作为本期应还款
        all_amounts = re.findall(r'([0-9,]+\.[0-9]{2})', full_text)
        print(f"找到所有金额：{all_amounts[:10]}...")  # 只显示前 10 个
        
        # 过滤出合理的账单金额（1000-100000）
        valid_amounts = []
        for amt_str in all_amounts:
            try:
                amount = float(amt_str.replace(',', ''))
                if 1000 < amount < 100000:
                    valid_amounts.append(amount)
            except:
                pass
        
        print(f"有效金额（1000-100000）：{valid_amounts}")
        
        # 取最大的金额作为本期应还款
        if valid_amounts:
            max_amount = max(valid_amounts)
            print(f"✓ 提取金额：¥{max_amount}")
        else:
            print("✗ 未找到有效金额")
        
        # 提取还款日（格式：到期日期：2026/03/31）
        due_match = re.search(r'到期日期：([0-9]{4}/[0-9]{2}/[0-9]{2})', full_text)
        if due_match:
            date_str = due_match.group(1).replace('/', '-')
            print(f"✓ 提取还款日：{date_str}")
        else:
            print("✗ 未找到还款日（到期日期：YYYY/MM/DD）")
            
            # 尝试其他还款日模式
            other_patterns = [
                r'到期还款日.*?([0-9]{4}[-/][0-9]{2}[-/][0-9]{2})',
                r'还款日.*?([0-9]{4}[-/][0-9]{2}[-/][0-9]{2})',
            ]
            for pattern in other_patterns:
                match = re.search(pattern, full_text)
                if match:
                    print(f"  通过其他模式找到：{match.group(1)}")

mail.close()
mail.logout()
