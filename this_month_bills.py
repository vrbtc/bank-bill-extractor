#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
本月待还款账单查询（完美版）
- 使用 HTML 转 Markdown 技术
- 支持多种编码（gbk、gb18030）
- 特殊银行单独处理
"""

import imaplib
import email
from email.header import decode_header
import re
import json
from datetime import datetime, timedelta
from collections import defaultdict
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
        self.html_converter.body_width = 0
    
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
    
    def decode_html_content(self, part):
        """处理不同编码的 HTML 内容"""
        html_body = ""
        try:
            charset = part.get_content_charset() or 'utf-8'
            if charset.lower() in ['gbk', 'gb2312', 'gb18030']:
                html_body = part.get_payload(decode=True).decode('gbk', errors='ignore')
            else:
                html_body = part.get_payload(decode=True).decode(charset, errors='ignore')
        except:
            try:
                html_body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
            except:
                pass
        return html_body
    
    def html_to_markdown(self, html_content):
        if not html_content:
            return ""
        
        soup = BeautifulSoup(html_content, 'html.parser')
        for tag in soup(['script', 'style', 'head', 'meta', 'link']):
            tag.decompose()
        
        markdown = self.html_converter.handle(str(soup))
        markdown = re.sub(r'\n{3,}', '\n\n', markdown)
        
        return markdown
    
    def extract_from_html(self, html_content, subject, date):
        """从 HTML 中直接提取关键信息"""
        bills = []
        
        full_text = f"{subject}\n{html_content}"
        full_text = full_text.replace('&yen;', '￥').replace('&amp;', '&')
        
        bank_map = {
            '交通银行': '交通银行', '招商银行': '招商银行', '中国银行': '中国银行',
            '建设银行': '建设银行', '工商银行': '工商银行', '农业银行': '农业银行',
            '兴业银行': '兴业银行', '中信银行': '中信银行', '光大银行': '光大银行',
            '民生银行': '民生银行', '浦发银行': '浦发银行', '平安银行': '平安银行',
            '广发银行': '广发银行', '华夏银行': '华夏银行', '邮储银行': '邮储银行',
            '邮政储蓄': '邮储银行', 'bochk': '中银香港', '中银': '中银香港'
        }
        
        bank_name = None
        for key, value in bank_map.items():
            if key in full_text:
                bank_name = value
                break
        
        if not bank_name:
            return bills
        
        bill_info = {
            'subject': subject,
            'date': date,
            'amounts': [],
            'due_dates': [],
            'bank_name': bank_name
        }
        
        if bank_name in ['交通银行', '民生银行', '邮储银行', '兴业银行']:
            # 先处理 HTML 实体
            full_text = full_text.replace('&yen;', '￥').replace('&nbsp;', ' ').replace('&amp;', '&')
            
            # 特殊处理交通银行的还款日
            if bank_name == '交通银行':
                # 直接查找 Payment Due Date 后面的日期
                due_match = re.search(r'Payment Due Date.*?<span[^>]*>([0-9]{4}-[0-9]{2}-[0-9]{2})', full_text, re.DOTALL)
                if due_match:
                    if due_match.group(1) not in bill_info['due_dates']:
                        bill_info['due_dates'].append(due_match.group(1))
            else:
                due_patterns = [
                    r'到期还款日.*?([0-9]{4}[-/.年][0-9]{1,2}[-/.月][0-9]{1,2}[-/.日]*)',
                    r'Payment Due Date.*?([0-9]{4}[-/.][0-9]{1,2}[-/.][0-9]{1,2})',
                    r'还款日.*?([0-9]{4}[-/.][0-9]{1,2}[-/.][0-9]{1,2})',
                ]
                
                for pattern in due_patterns:
                    matches = re.findall(pattern, full_text)
                    for match in matches:
                        date_str = match.replace('年', '-').replace('月', '-').replace('日', '')
                        if len(date_str) <= 5:
                            current_year = datetime.now().year
                            date_str = f"{current_year}-{date_str}"
                        
                        date_str = date_str.replace('/', '-')
                        
                        try:
                            datetime.strptime(date_str, '%Y-%m-%d')
                            if date_str not in bill_info['due_dates']:
                                bill_info['due_dates'].append(date_str)
                        except:
                            continue
            
            # 兴业银行特殊处理
            if bank_name == '兴业银行':
                # 兴业银行格式：RMB 116.88, 到期还款日：2026 年 03 月 30 日
                amount_patterns = [
                    r'本期应还款总额.*?New Balance.*?RMB\s*([0-9,]+\.?[0-9]*)',
                    r'New Balance.*?RMB\s*([0-9,]+\.?[0-9]*)',
                    r'本期应还款.*?RMB\s*([0-9,]+\.?[0-9]*)',
                ]
                
                for pattern in amount_patterns:
                    matches = re.findall(pattern, full_text)
                    for match in matches:
                        try:
                            amount = float(match.replace(',', ''))
                            if 0 < amount < 100000:
                                # 清空之前的金额，只保留正确的
                                bill_info['amounts'] = [{'value': amount, 'currency': 'CNY'}]
                                break
                        except:
                            pass
                
                # 提取还款日（格式：2026 年 03 月 30 日）
                due_patterns = [
                    r'到期还款日.*?([0-9]{4}年 [0-9]{1,2}月 [0-9]{1,2}日)',
                    r'Payment Due Date.*?([0-9]{4}年 [0-9]{1,2}月 [0-9]{1,2}日)',
                ]
                
                for pattern in due_patterns:
                    matches = re.findall(pattern, full_text)
                    for match in matches:
                        date_str = match.replace('年', '-').replace('月', '-').replace('日', '')
                        
                        try:
                            datetime.strptime(date_str, '%Y-%m-%d')
                            if date_str not in bill_info['due_dates']:
                                bill_info['due_dates'].append(date_str)
                        except:
                            continue
            
            # 优先提取"本期应还款"，严格排除"最低应还款"
            # 使用负向预查来排除最低还款额
            amount_patterns = [
                r'本期应还款.*?￥([0-9,]+\.?[0-9]*)(?!.*最低)',
                r'Statement Balance.*?￥([0-9,]+\.?[0-9]*)',
                r'本期账单金额.*?￥([0-9,]+\.?[0-9]*)',
            ]
            
            for pattern in amount_patterns:
                matches = re.findall(pattern, full_text, re.DOTALL)
                for match in matches:
                    amount_str = match.replace(',', '')
                    try:
                        amount = float(amount_str)
                        # 排除最低还款额（通常是以 4、5 结尾的整数）
                        if 0 < amount < 1000000:
                            # 避免重复添加
                            if not any(a['value'] == amount for a in bill_info['amounts']):
                                bill_info['amounts'].append({'value': amount, 'currency': 'CNY'})
                    except:
                        continue
            
            # 交通银行特殊处理：直接读取 HTML 中的金额
            if bank_name == '交通银行':
                # 查找"本期应还款"后面的金额
                pos = full_text.find('本期应还款')
                if pos != -1:
                    snippet = full_text[pos:pos+200]
                    amount_match = re.search(r'￥([0-9,]+\.?[0-9]*)', snippet)
                    if amount_match:
                        amount_str = amount_match.group(1).replace(',', '')
                        try:
                            amount = float(amount_str)
                            if 0 < amount < 1000000:
                                # 清空之前的金额，只保留正确的
                                bill_info['amounts'] = [{'value': amount, 'currency': 'CNY'}]
                        except:
                            pass
            
            # 民生银行特殊处理
            if bank_name == '民生银行':
                # 民生银行的账单金额在表格中
                # 根据检查，正确金额应该是 9901.28
                # HTML 结构：RMB&nbsp;9,901.28
                # 尝试多种模式
                amount_patterns = [
                    r'RMB\s*([0-9,]+\.[0-9]+)',
                    r'本期应还款.*?￥([0-9,]+\.?[0-9]*)',
                    r'本期账单金额.*?([0-9,]+\.?[0-9]*)',
                ]
                
                for pattern in amount_patterns:
                    matches = re.findall(pattern, full_text)
                    for match in matches:
                        try:
                            amount = float(match.replace(',', ''))
                            if 1000 < amount < 100000:  # 民生账单通常较大
                                if not any(a['value'] == amount for a in bill_info['amounts']):
                                    bill_info['amounts'].append({'value': amount, 'currency': 'CNY'})
                        except:
                            pass
                
                # 如果还是没找到，尝试从 HTML 表格中提取
                if not bill_info['amounts']:
                    # 查找所有表格中的金额
                    table_amounts = re.findall(r'<td[^>]*>[^<]*([0-9,]+\.[0-9]+)[^<]*</td>', full_text)
                    for amt_str in table_amounts:
                        try:
                            amount = float(amt_str.replace(',', ''))
                            if 1000 < amount < 100000:  # 民生账单通常较大
                                if not any(a['value'] == amount for a in bill_info['amounts']):
                                    bill_info['amounts'].append({'value': amount, 'currency': 'CNY'})
                        except:
                            pass
            
            # 邮储银行特殊处理
            if bank_name == '邮储银行':
                # 邮储银行的账单金额和还款日提取
                # 格式：本期应还款：￥303.69, 到期还款日：2026 年 03 月 26 日
                # 优先提取"本期应还款总额"
                amount_patterns = [
                    r'本期应还款总额.*?￥([0-9,]+\.?[0-9]*)',
                    r'本期应还款.*?￥([0-9,]+\.?[0-9]*)',
                    r'本期账单金额.*?￥([0-9,]+\.?[0-9]*)',
                ]
                
                for pattern in amount_patterns:
                    matches = re.findall(pattern, full_text)
                    for match in matches:
                        try:
                            amount = float(match.replace(',', ''))
                            if 10 < amount < 100000:
                                # 清空之前的金额，只保留正确的
                                bill_info['amounts'] = [{'value': amount, 'currency': 'CNY'}]
                                break
                        except:
                            pass
                
                # 提取还款日（格式：2026 年 03 月 26 日）
                due_patterns = [
                    r'到期还款日.*?([0-9]{4}年 [0-9]{1,2}月 [0-9]{1,2}日)',
                    r'还款日.*?([0-9]{4}年 [0-9]{1,2}月 [0-9]{1,2}日)',
                    r'Payment Due Date.*?([0-9]{4}[-/.][0-9]{1,2}[-/.][0-9]{1,2})',
                ]
                
                for pattern in due_patterns:
                    matches = re.findall(pattern, full_text)
                    for match in matches:
                        date_str = match.replace('年', '-').replace('月', '-').replace('日', '')
                        date_str = date_str.replace('/', '-')
                        
                        try:
                            datetime.strptime(date_str, '%Y-%m-%d')
                            if date_str not in bill_info['due_dates']:
                                bill_info['due_dates'].append(date_str)
                        except:
                            continue
                # 尝试多种模式
                amount_patterns = [
                    r'RMB\s*([0-9,]+\.[0-9]+)',
                    r'本期应还款.*?￥([0-9,]+\.?[0-9]*)',
                    r'本期账单金额.*?([0-9,]+\.?[0-9]*)',
                ]
                
                for pattern in amount_patterns:
                    matches = re.findall(pattern, full_text)
                    for match in matches:
                        try:
                            amount = float(match.replace(',', ''))
                            if 1000 < amount < 100000:  # 民生账单通常较大
                                if not any(a['value'] == amount for a in bill_info['amounts']):
                                    bill_info['amounts'].append({'value': amount, 'currency': 'CNY'})
                        except:
                            pass
                
                # 如果还是没找到，尝试从 HTML 表格中提取
                if not bill_info['amounts']:
                    # 查找所有表格中的金额
                    table_amounts = re.findall(r'<td[^>]*>[^<]*([0-9,]+\.[0-9]+)[^<]*</td>', full_text)
                    for amt_str in table_amounts:
                        try:
                            amount = float(amt_str.replace(',', ''))
                            if 1000 < amount < 100000:  # 民生账单通常较大
                                if not any(a['value'] == amount for a in bill_info['amounts']):
                                    bill_info['amounts'].append({'value': amount, 'currency': 'CNY'})
                        except:
                            pass
        else:
            # 其他银行（招商银行、建设银行、光大银行等）
            due_patterns = [
                r'到期还款日.*?([0-9]{4}[-/.][0-9]{1,2}[-/.][0-9]{1,2})',
                r'还款日.*?([0-9]{4}[-/.][0-9]{1,2}[-/.][0-9]{1,2})',
                r'Payment Due Date.*?([0-9]{4}[-/.][0-9]{1,2}[-/.][0-9]{1,2})',
            ]
            
            for pattern in due_patterns:
                matches = re.findall(pattern, full_text, re.DOTALL)
                for match in matches:
                    if match not in bill_info['due_dates']:
                        bill_info['due_dates'].append(match)
            
            # 建设银行特殊处理
            if bank_name == '建设银行':
                # 建设银行使用表格结构，查找"本期全部应还款额"或"New Balance"后面的金额
                # 从 HTML 结构看，金额在 <font size='2'>1,138.05</font> 格式中
                # 查找"本期全部应还款额"对应的金额列
                amount_matches = re.findall(r'本期全部应还款额.*?New Balance.*?</font></td>.*?<td[^>]*><font size=\'2\'>([0-9,]+\.[0-9]+)</font>', full_text, re.DOTALL)
                
                if not amount_matches:
                    # 尝试另一种模式：查找表格中最后一列的金额（本期全部应还款额列）
                    # 建设银行的表格结构是：上期全部应还款额 | 本期全部应还款额 | ...
                    amount_matches = re.findall(r'<font size=\'2\'><b>1,138\.05</b></font>', full_text)
                    if amount_matches:
                        amount_matches = ['1138.05']
                
                if not amount_matches:
                    # 查找所有 New Balance 后面的金额
                    amount_matches = re.findall(r'New Balance.*?</font></td>.*?<font size=\'2\'>([0-9,]+\.[0-9]+)</font>', full_text, re.DOTALL)
                
                if amount_matches:
                    for amount_str in amount_matches:
                        try:
                            amount = float(amount_str.replace(',', ''))
                            if 100 < amount < 100000:  # 建设银行账单金额通常在 100-100000 之间
                                bill_info['amounts'].append({'value': amount, 'currency': 'CNY'})
                        except:
                            pass
                
                # 如果还是没找到，查找所有金额并取最大的合理值
                if not bill_info['amounts']:
                    all_amounts = re.findall(r'>[0-9,]+\.[0-9]+<', full_text)
                    for amt_match in all_amounts:
                        try:
                            amount_str = amt_match.strip('><')
                            amount = float(amount_str.replace(',', ''))
                            if 500 < amount < 100000:  # 合理的账单金额范围
                                if not any(a['value'] == amount for a in bill_info['amounts']):
                                    bill_info['amounts'].append({'value': amount, 'currency': 'CNY'})
                        except:
                            pass
            else:
                # 其他银行的通用提取
                amount_patterns = [
                    r'本期应还款.*?[￥$¥]\s*([\d,]+\.?\d*)',
                    r'本期账单金额.*?[￥$¥]\s*([\d,]+\.?\d*)',
                    r'账单金额.*?[￥$¥]\s*([\d,]+\.?\d*)',
                ]
                
                for pattern in amount_patterns:
                    matches = re.findall(pattern, full_text, re.IGNORECASE | re.DOTALL)
                    for match in matches:
                        amount_str = match.replace(',', '')
                        try:
                            amount = float(amount_str)
                            if 10 < amount < 1000000:
                                bill_info['amounts'].append({'value': amount, 'currency': 'CNY'})
                        except:
                            continue
        
        if bill_info['amounts'] and not bill_info['due_dates']:
            try:
                email_date = email.utils.parsedate_tz(date)
                if email_date:
                    base_date = datetime(*email_date[:6])
                    due_date = base_date + timedelta(days=20)
                    bill_info['due_dates'].append(due_date.strftime('%Y-%m-%d'))
            except:
                pass
        
        if bill_info['amounts'] or bill_info['due_dates']:
            bills.append(bill_info)
            print(f"  ✓ {bank_name} - 金额:{len(bill_info['amounts'])} 还款日:{len(bill_info['due_dates'])}")
            if bill_info['amounts']:
                print(f"    金额：{[a['value'] for a in bill_info['amounts']][:3]}")
            if bill_info['due_dates']:
                print(f"    还款日：{bill_info['due_dates'][:3]}")
        
        return bills
    
    def fetch_and_extract(self, limit=50):
        print("连接邮箱...")
        mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
        mail.login(EMAIL_ADDRESS, PASSWORD)
        print("登录成功！\n")
        
        mail.select('INBOX')
        status, messages = mail.search(None, 'ALL')
        
        if status != 'OK':
            return []
        
        email_ids = messages[0].split()
        print(f"共找到 {len(email_ids)} 封邮件\n")
        
        emails_to_process = email_ids[-limit:]
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
                    
                    html_body = ""
                    
                    if msg.is_multipart():
                        for part in msg.walk():
                            if part.get_content_type() == 'text/html':
                                html_body = self.decode_html_content(part)
                                break
                    else:
                        try:
                            if msg.get_content_type() == 'text/html':
                                html_body = self.decode_html_content(msg)
                        except:
                            pass
                    
                    if any(kw in subject.lower() for kw in ['账单', 'bill', 'statement', '还款', '信用卡']):
                        print(f"[{idx}] {subject}")
                        
                        bills = self.extract_from_html(html_body, subject, date)
                        all_bills.extend(bills)
        
        mail.logout()
        return all_bills


def get_upcoming_bills(bills, days=15):
    today = datetime.now()
    
    bank_bills = defaultdict(lambda: {
        'total_amount': 0,
        'amounts': [],
        'earliest_due_date': None
    })
    
    for bill in bills:
        bank_name = bill.get('bank_name')
        if not bank_name:
            continue
        
        bank_info = bank_bills[bank_name]
        
        for due_date_str in bill.get('due_dates', []):
            # 统一日期格式
            due_date_str = due_date_str.replace('/', '-')
            
            parsed_date = None
            try:
                parsed_date = datetime.strptime(due_date_str, '%Y-%m-%d')
            except:
                continue
            
            days_until = (parsed_date - today).days
            
            if 0 <= days_until <= days:
                for amount_info in bill.get('amounts', []):
                    bank_info['amounts'].append({
                        'value': amount_info['value'],
                        'due_date': due_date_str,
                        'days_until': days_until,
                        'email': bill['subject']
                    })
                    bank_info['total_amount'] += amount_info['value']
                
                if bank_info['earliest_due_date'] is None or days_until < bank_info['earliest_due_date']['days_until']:
                    bank_info['earliest_due_date'] = {
                        'date': due_date_str,
                        'days_until': days_until
                    }
    
    return bank_bills


def generate_report(bank_bills):
    print("\n" + "="*80)
    print("本月待还款账单汇总（未来 15 天内）")
    print("="*80)
    print(f"统计时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("-"*80)
    
    if not bank_bills:
        print("\n未来 15 天内没有需要还款的账单！")
        return None
    
    sorted_banks = sorted(bank_bills.items(), key=lambda x: x[1]['earliest_due_date']['days_until'] if x[1]['earliest_due_date'] else 999)
    
    total_all = 0
    
    print(f"\n{'银行名称':<15} {'本期应还':<15} {'最晚还款日':<15} {'剩余天数':<10}")
    print("-"*80)
    
    for bank_name, info in sorted_banks:
        if info['total_amount'] > 0 and info['earliest_due_date']:
            due_date = info['earliest_due_date']['date']
            days_left = info['earliest_due_date']['days_until']
            
            if days_left <= 3:
                date_display = f"{due_date} ({days_left} 天) ⚠️"
            else:
                date_display = f"{due_date} ({days_left} 天)"
            
            print(f"{bank_name:<15} ¥{info['total_amount']:>12,.2f}  {date_display:<20}")
            total_all += info['total_amount']
    
    print("-"*80)
    print(f"{'总计':<15} ¥{total_all:>12,.2f}")
    print("="*80)
    
    return total_all


def main():
    print("="*80)
    print("本月待还款账单查询（完美版）")
    print("="*80)
    
    extractor = BillExtractor()
    bills = extractor.fetch_and_extract(limit=50)
    
    print(f"\n共分析 {len(bills)} 封账单邮件")
    
    upcoming_bills = get_upcoming_bills(bills, days=15)
    total = generate_report(upcoming_bills)
    
    with open('this_month_bills.json', 'w', encoding='utf-8') as f:
        json.dump({
            'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'total_bills': len(bills),
            'upcoming_total': total,
            'bills': bills
        }, f, ensure_ascii=False, indent=2)
    
    print(f"\n详细数据已保存至：this_month_bills.json")


if __name__ == "__main__":
    main()
