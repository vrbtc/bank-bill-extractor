#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
重新提取所有银行账单，包括交通银行
"""

import imaplib
import email
from email.header import decode_header
import re
import json
from datetime import datetime
import html2text
from bs4 import BeautifulSoup


EMAIL_ADDRESS = "rrking@aliyun.com"
PASSWORD = "Aa2599589"
IMAP_SERVER = "imap.aliyun.com"
IMAP_PORT = 993


class BillExtractor:
    def __init__(self):
        self.html_converter = html2text.HTML2Text()
        self.html_converter.ignore_links = False
        self.html_converter.ignore_images = True
        
    def decode_mime_words(self, s):
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
    
    def clean_html(self, html_content):
        if not html_content:
            return ""
        soup = BeautifulSoup(html_content, 'html.parser')
        for tag in soup(['script', 'style', 'head', 'meta', 'link']):
            tag.decompose()
        return str(soup.body) if soup.body else str(soup)
    
    def html_to_markdown(self, html_content):
        cleaned_html = self.clean_html(html_content)
        markdown = self.html_converter.handle(cleaned_html)
        return markdown
    
    def extract_bills(self, text, subject, date):
        bills_found = []
        
        full_text = f"{subject}\n{text}"
        
        bill_keywords = ['账单', 'bill', 'statement', '还款', 'payment', '信用卡', 'credit card', '银行', 'bank']
        is_bill_email = any(keyword in full_text.lower() for keyword in bill_keywords)
        
        if not is_bill_email:
            return bills_found
        
        bill_info = {
            'subject': subject,
            'date': date,
            'amounts': [],
            'due_dates': [],
            'bank_name': None
        }
        
        banks = [
            '交通银行', '招商银行', '中国银行', '建设银行', '工商银行', '农业银行',
            '兴业银行', '中信银行', '光大银行', '民生银行', '浦发银行',
            '平安银行', '广发银行', '华夏银行', '上海银行', '北京银行'
        ]
        
        for bank in banks:
            if bank in full_text:
                bill_info['bank_name'] = bank
                print(f"  识别到银行：{bank}")
                break
        
        if not bill_info['bank_name']:
            if 'BOCHK' in full_text or '中银' in full_text or '香港' in full_text:
                bill_info['bank_name'] = '中银香港'
        
        amount_patterns = [
            r'[￥$¥HKD]\s*([\d,]+\.?\d*)',
            r'([\d,]+\.?\d*)\s*元',
            r'([\d,]+\.?\d*)\s*USD',
            r'([\d,]+\.?\d*)\s*CNY',
            r'([\d,]+\.?\d*)\s*HKD',
            r'本期账单 [:：]?\s*[￥$¥]?\s*([\d,]+\.?\d*)',
            r'应还金额 [:：]?\s*[￥$¥]?\s*([\d,]+\.?\d*)',
            r'账单金额 [:：]?\s*[￥$¥]?\s*([\d,]+\.?\d*)',
            r'人民币账单 [:：]?\s*[￥$¥]?\s*([\d,]+\.?\d*)',
        ]
        
        for pattern in amount_patterns:
            matches = re.findall(pattern, full_text, re.IGNORECASE)
            for match in matches:
                amount_str = match.replace(',', '')
                try:
                    amount = float(amount_str)
                    if 0 < amount < 1000000:
                        if 'HKD' in full_text or '港币' in full_text:
                            currency = 'HKD'
                        elif 'USD' in full_text or '$' in full_text:
                            currency = 'USD'
                        else:
                            currency = 'CNY'
                        
                        bill_info['amounts'].append({
                            'value': amount,
                            'currency': currency
                        })
                except:
                    continue
        
        date_patterns = [
            (r'(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})', '%Y-%m-%d'),
            (r'(\d{4}) 年 (\d{1,2}) 月 (\d{1,2}) 日', '%Y-%m-%d'),
            (r'(\d{1,2}) 月 (\d{1,2}) 日', '%m-%d'),
            (r'还款日 [:：]?\s*(\d{4}[-/.]\d{1,2}[-/.]\d{1,2})', '%Y-%m-%d'),
            (r'到期日 [:：]?\s*(\d{4}[-/.]\d{1,2}[-/.]\d{1,2})', '%Y-%m-%d'),
            (r'最后还款日 [:：]?\s*(\d{4}[-/.]\d{1,2}[-/.]\d{1,2})', '%Y-%m-%d'),
            (r'请于 (\d{4}[-/.]\d{1,2}[-/.]\d{1,2}) 前', '%Y-%m-%d'),
        ]
        
        for pattern, date_format in date_patterns:
            matches = re.findall(pattern, full_text)
            for match in matches:
                try:
                    if isinstance(match, tuple):
                        if len(match) == 3:
                            date_str = f"{match[0]}-{match[1].zfill(2)}-{match[2].zfill(2)}"
                        else:
                            date_str = match[0]
                    else:
                        date_str = match
                    
                    if len(date_str) <= 5:
                        current_year = datetime.now().year
                        date_str = f"{current_year}-{date_str}"
                    
                    if date_str not in bill_info['due_dates']:
                        bill_info['due_dates'].append(date_str)
                except:
                    continue
        
        if bill_info['amounts'] or bill_info['due_dates']:
            bills_found.append(bill_info)
            print(f"  金额数量：{len(bill_info['amounts'])}")
            print(f"  还款日期数量：{len(bill_info['due_dates'])}")
            if bill_info['amounts']:
                print(f"  金额：{bill_info['amounts'][:3]}")
            if bill_info['due_dates']:
                print(f"  还款日：{bill_info['due_dates'][:3]}")
        
        return bills_found
    
    def fetch_and_extract(self, limit=50):
        print("连接邮箱...")
        mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
        mail.login(EMAIL_ADDRESS, PASSWORD)
        print("登录成功！")
        
        mail.select('INBOX')
        status, messages = mail.search(None, 'ALL')
        
        if status != 'OK':
            print("搜索失败")
            return []
        
        email_ids = messages[0].split()
        print(f"共找到 {len(email_ids)} 封邮件\n")
        
        emails_to_process = email_ids[-limit:] if len(email_ids) > limit else email_ids
        
        all_bills = []
        
        for idx, email_id in enumerate(reversed(emails_to_process), 1):
            status, msg_data = mail.fetch(email_id, '(RFC822)')
            
            if status != 'OK':
                continue
            
            for response_part in msg_data:
                if isinstance(response_part, tuple):
                    msg = email.message_from_bytes(response_part[1])
                    subject = self.decode_mime_words(msg.get('Subject', ''))
                    date = self.decode_mime_words(msg.get('Date', ''))
                    
                    body = ""
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
                                    html_content = part.get_payload(decode=True).decode(charset, errors='ignore')
                                    body = self.html_to_markdown(html_content)
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
                                html_content = msg.get_payload(decode=True).decode(charset, errors='ignore')
                                body = self.html_to_markdown(html_content)
                        except:
                            pass
                    
                    if any(kw in subject.lower() for kw in ['账单', 'bill', 'statement', '还款', '信用卡']):
                        print(f"\n[{idx}] 处理：{subject}")
                        bills = self.extract_bills(body, subject, date)
                        all_bills.extend(bills)
        
        mail.logout()
        return all_bills


def main():
    extractor = BillExtractor()
    bills = extractor.fetch_and_extract(limit=50)
    
    print("\n" + "="*80)
    print("提取结果汇总")
    print("="*80)
    print(f"共找到 {len(bills)} 封账单邮件\n")
    
    for idx, bill in enumerate(bills, 1):
        print(f"{idx}. {bill['subject']}")
        print(f"   银行：{bill['bank_name']}")
        print(f"   金额：{len(bill['amounts'])} 笔")
        print(f"   还款日：{len(bill['due_dates'])} 个")
        if bill['amounts']:
            print(f"   金额明细：{bill['amounts'][:3]}")
        if bill['due_dates']:
            print(f"   还款日前 3: {bill['due_dates'][:3]}")
        print()
    
    with open('bill_report_v2.json', 'w', encoding='utf-8') as f:
        json.dump({
            'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'total_bills': len(bills),
            'bills': bills
        }, f, ensure_ascii=False, indent=2)
    
    print(f"详细报告已保存至：bill_report_v2.json")


if __name__ == "__main__":
    main()
