#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
阿里云邮箱账单提取器
功能：登录阿里云邮箱，提取所有账单邮件，分析金额、还款日等信息
"""

import imaplib
import email
from email.header import decode_header
import re
import json
from datetime import datetime
import html2text
from bs4 import BeautifulSoup


class AliyunEmailBillExtractor:
    """阿里云邮箱账单提取器"""
    
    def __init__(self, email_address, password):
        self.email_address = email_address
        self.password = password
        self.imap_server = "imap.aliyun.com"
        self.imap_port = 993
        self.mail = None
        self.bills = []
        
        self.html_converter = html2text.HTML2Text()
        self.html_converter.ignore_links = False
        self.html_converter.ignore_images = True
        self.html_converter.ignore_emphasis = False
        
    def connect(self):
        """连接到阿里云邮箱 IMAP 服务器"""
        print(f"正在连接到 {self.imap_server}...")
        try:
            self.mail = imaplib.IMAP4_SSL(self.imap_server, self.imap_port)
            self.mail.login(self.email_address, self.password)
            print("登录成功！")
            return True
        except Exception as e:
            print(f"登录失败：{str(e)}")
            return False
    
    def disconnect(self):
        """断开连接"""
        if self.mail:
            self.mail.logout()
            print("已断开连接")
    
    def decode_mime_words(self, s):
        """解码 MIME 编码的字符串"""
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
        """清理 HTML 内容，删除无用标签"""
        if not html_content:
            return ""
        
        soup = BeautifulSoup(html_content, 'html.parser')
        
        for tag in soup(['script', 'style', 'head', 'meta', 'link']):
            tag.decompose()
        
        return str(soup.body) if soup.body else str(soup)
    
    def html_to_markdown(self, html_content):
        """将 HTML 转换为 Markdown"""
        cleaned_html = self.clean_html(html_content)
        markdown = self.html_converter.handle(cleaned_html)
        return markdown
    
    def extract_bills_from_text(self, text, email_subject, email_date):
        """从文本中提取账单信息"""
        bills_found = []
        
        text_lower = text.lower()
        
        bill_keywords = [
            '账单', 'bill', 'statement', '还款', 'payment', 
            '信用卡', 'credit card', '银行', 'bank',
            '应还', '本期账单', '最低还款', '账单金额'
        ]
        
        is_bill_email = any(keyword in text_lower for keyword in bill_keywords)
        
        if not is_bill_email:
            return bills_found
        
        bill_info = {
            'subject': email_subject,
            'date': email_date,
            'amounts': [],
            'due_dates': [],
            'bank_name': None,
            'bill_type': None
        }
        
        banks = [
            '招商银行', '中国银行', '建设银行', '工商银行', '农业银行',
            '交通银行', '中信银行', '光大银行', '民生银行', '浦发银行',
            '平安银行', '广发银行', '华夏银行', '兴业银行', '上海银行',
            '北京银行', '南京银行', '宁波银行', '杭州银行'
        ]
        
        for bank in banks:
            if bank in text:
                bill_info['bank_name'] = bank
                break
        
        amount_patterns = [
            r'[￥$¥]\s*([\d,]+\.?\d*)',
            r'([\d,]+\.?\d*)\s*元',
            r'([\d,]+\.?\d*)\s*USD',
            r'([\d,]+\.?\d*)\s*CNY',
            r'金额 [:：]?\s*[￥$¥]?\s*([\d,]+\.?\d*)',
            r'总额 [:：]?\s*[￥$¥]?\s*([\d,]+\.?\d*)',
            r'应还 [:：]?\s*[￥$¥]?\s*([\d,]+\.?\d*)',
            r'本期账单 [:：]?\s*[￥$¥]?\s*([\d,]+\.?\d*)',
        ]
        
        for pattern in amount_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                amount_str = match.replace(',', '')
                try:
                    amount = float(amount_str)
                    if amount > 0:
                        bill_info['amounts'].append({
                            'value': amount,
                            'currency': 'CNY' if '￥' in text or '元' in text or 'CNY' in text else 'USD'
                        })
                except:
                    continue
        
        date_patterns = [
            (r'(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})', '%Y-%m-%d'),
            (r'(\d{4})年 (\d{1,2}) 月 (\d{1,2}) 日', '%Y-%m-%d'),
            (r'(\d{1,2}) 月 (\d{1,2}) 日', '%m-%d'),
            (r'还款日 [:：]?\s*(\d{4}[-/.]\d{1,2}[-/.]\d{1,2})', '%Y-%m-%d'),
            (r'到期日 [:：]?\s*(\d{4}[-/.]\d{1,2}[-/.]\d{1,2})', '%Y-%m-%d'),
            (r'最后还款日 [:：]?\s*(\d{4}[-/.]\d{1,2}[-/.]\d{1,2})', '%Y-%m-%d'),
        ]
        
        for pattern, date_format in date_patterns:
            matches = re.findall(pattern, text)
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
                    
                    bill_info['due_dates'].append(date_str)
                except:
                    continue
        
        if bill_info['amounts'] or bill_info['due_dates']:
            bills_found.append(bill_info)
        
        return bills_found
    
    def fetch_emails(self, folder='INBOX', limit=100):
        """获取邮件"""
        print(f"正在获取邮件...")
        try:
            self.mail.select(folder)
            
            status, messages = self.mail.search(None, 'ALL')
            if status != 'OK':
                print("搜索邮件失败")
                return []
            
            email_ids = messages[0].split()
            total_emails = len(email_ids)
            print(f"找到 {total_emails} 封邮件")
            
            emails_to_process = email_ids[-limit:] if len(email_ids) > limit else email_ids
            
            all_bills = []
            processed = 0
            
            for email_id in reversed(emails_to_process):
                processed += 1
                if processed % 10 == 0:
                    print(f"已处理 {processed}/{len(emails_to_process)} 封邮件...")
                
                status, msg_data = self.mail.fetch(email_id, '(RFC822)')
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
                        
                        full_text = f"{subject}\n{body}"
                        bills = self.extract_bills_from_text(full_text, subject, date)
                        all_bills.extend(bills)
            
            return all_bills
            
        except Exception as e:
            print(f"获取邮件失败：{str(e)}")
            return []
    
    def generate_report(self, bills):
        """生成汇总报告"""
        print("\n" + "="*80)
        print("账单汇总报告")
        print("="*80)
        
        if not bills:
            print("未找到账单邮件")
            return
        
        print(f"\n共找到 {len(bills)} 封账单邮件\n")
        
        total_amount = 0
        bank_summary = {}
        
        for idx, bill in enumerate(bills, 1):
            print(f"{'-'*80}")
            print(f"账单 #{idx}")
            print(f"{'-'*80}")
            print(f"邮件主题：{bill['subject']}")
            print(f"邮件日期：{bill['date']}")
            
            if bill['bank_name']:
                print(f"银行名称：{bill['bank_name']}")
                bank_name = bill['bank_name']
                bank_summary[bank_name] = bank_summary.get(bank_name, 0) + len(bill['amounts'])
            
            if bill['amounts']:
                amounts_str = ', '.join([f"{amt['value']:.2f} {amt['currency']}" for amt in bill['amounts']])
                print(f"金额：{amounts_str}")
                
                for amt in bill['amounts']:
                    total_amount += amt['value']
            
            if bill['due_dates']:
                due_dates_str = ', '.join(bill['due_dates'])
                print(f"还款日：{due_dates_str}")
            
            print()
        
        print("="*80)
        print("汇总统计")
        print("="*80)
        print(f"总账单数量：{len(bills)}")
        print(f"总金额：{total_amount:.2f} CNY")
        
        if bank_summary:
            print("\n按银行统计:")
            for bank, count in bank_summary.items():
                print(f"  - {bank}: {count} 笔账单")
        
        print("="*80)
        
        report_data = {
            'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'total_bills': len(bills),
            'total_amount': total_amount,
            'bank_summary': bank_summary,
            'bills': bills
        }
        
        with open('bill_report.json', 'w', encoding='utf-8') as f:
            json.dump(report_data, f, ensure_ascii=False, indent=2)
        
        print(f"\n详细报告已保存至：bill_report.json")
        
        return report_data
    
    def run(self, email_limit=100):
        """执行完整流程"""
        print("="*80)
        print("阿里云邮箱账单提取器")
        print("="*80)
        
        if not self.connect():
            return None
        
        try:
            bills = self.fetch_emails(limit=email_limit)
            report = self.generate_report(bills)
            return report
        finally:
            self.disconnect()


def main():
    EMAIL_ADDRESS = "rrking@aliyun.com"
    PASSWORD = "Aa2599589"
    
    extractor = AliyunEmailBillExtractor(EMAIL_ADDRESS, PASSWORD)
    report = extractor.run(email_limit=200)
    
    if report:
        print("\n✓ 账单提取完成！")
    else:
        print("\n✗ 账单提取失败！")


if __name__ == "__main__":
    main()
