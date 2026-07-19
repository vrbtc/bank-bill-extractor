#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
本月待还款账单查询（重构版）
- 使用模块化架构
- 职责分离：邮箱连接、邮件解码、HTML 解析、账单提取
- 策略模式：支持不同银行的特殊提取逻辑
"""

import os
import email
import json
from datetime import datetime, timedelta
from collections import defaultdict

from email_client import EmailClient
from email_decoder import EmailDecoder
from bank_extractors import BankExtractorFactory


# 支持环境变量配置（CI 环境），回退到默认值（本地运行）
from config import EMAIL_ADDRESS, PASSWORD, IMAP_SERVER, IMAP_PORT


class BillExtractor:
    """账单提取器（协调器）"""
    
    BANK_MAP = {
        '交通银行': '交通银行', '招商银行': '招商银行', '中国银行': '中国银行',
        '建设银行': '建设银行', '工商银行': '工商银行', '农业银行': '农业银行',
        '兴业银行': '兴业银行', '中信银行': '中信银行', '光大银行': '光大银行',
        '民生银行': '民生银行', '浦发银行': '浦发银行', '平安银行': '平安银行',
        '广发银行': '广发银行', '华夏银行': '华夏银行', '邮储银行': '邮储银行',
        '邮政储蓄': '邮储银行', 'bochk': '中银香港', '中银': '中银香港',
        'CMB': '招商银行',
        # 工商银行英文/简称（Peony Card 对账单标题常用）
        'ICBC': '工商银行', 'Peony': '工商银行', '牡丹卡': '工商银行',
    }
    
    def __init__(self):
        self.email_decoder = EmailDecoder()
        self.bank_factory = BankExtractorFactory()
    
    def fetch_and_extract(self, limit=50):
        """获取并提取账单"""
        client = EmailClient(IMAP_SERVER, IMAP_PORT, EMAIL_ADDRESS, PASSWORD)
        client.connect()
        
        try:
            emails = client.fetch_emails(limit=limit)
            all_bills = []
            
            for idx, msg in enumerate(emails, 1):
                subject = self.email_decoder.decode_mime_words(msg.get('Subject', ''))
                date = self.email_decoder.decode_mime_words(msg.get('Date', ''))
                
                html_body = self._extract_html_body(msg)
                
                if self._is_bill_email(subject):
                    print(f"[{idx}] {subject}")
                    bills = self.extract_from_html(html_body, subject, date)
                    all_bills.extend(bills)
            
            return all_bills
        finally:
            client.disconnect()
    
    def _extract_html_body(self, msg):
        """提取邮件 HTML 内容"""
        html_body = ""
        
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == 'text/html':
                    html_body = self.email_decoder.decode_html_content(part)
                    break
        else:
            try:
                if msg.get_content_type() == 'text/html':
                    html_body = self.email_decoder.decode_html_content(msg)
            except:
                pass
        
        return html_body
    
    def _is_bill_email(self, subject):
        """判断是否为账单邮件"""
        keywords = ['账单', 'bill', 'statement', '还款', '信用卡']
        return any(kw in subject.lower() for kw in keywords)
    
    def _identify_bank(self, full_text):
        """识别银行"""
        for key, value in self.BANK_MAP.items():
            if key in full_text:
                return value
        return None
    
    def extract_from_html(self, html_content, subject, date):
        """从 HTML 中提取账单信息"""
        bills = []
        
        full_text = f"{subject}\n{html_content}"
        
        bank_name = self._identify_bank(full_text)
        if not bank_name:
            return bills
        
        extractor = self.bank_factory.create_extractor(bank_name)
        full_text = extractor.preprocess_text(full_text)
        
        bill_info = {
            'subject': subject,
            'date': date,
            'amounts': [],
            'due_dates': [],
            'bank_name': bank_name
        }
        
        extractor.extract_amount(full_text, bill_info)
        extractor.extract_due_date(full_text, bill_info)
        
        if bill_info['amounts'] and not bill_info['due_dates']:
            self._set_default_due_date(bill_info, date)
        
        if bill_info['amounts'] or bill_info['due_dates']:
            bills.append(bill_info)
            self._print_bill_info(bill_info)
        
        return bills
    
    def _set_default_due_date(self, bill_info, date):
        """设置默认还款日"""
        try:
            email_date = email.utils.parsedate_tz(date)
            if email_date:
                base_date = datetime(*email_date[:6])
                due_date = base_date + timedelta(days=20)
                bill_info['due_dates'].append(due_date.strftime('%Y-%m-%d'))
        except:
            pass
    
    def _print_bill_info(self, bill_info):
        """打印账单信息"""
        bank_name = bill_info['bank_name']
        print(f"  ✓ {bank_name} - 金额:{len(bill_info['amounts'])} 还款日:{len(bill_info['due_dates'])}")
        if bill_info['amounts']:
            print(f"    金额：{[a['value'] for a in bill_info['amounts']][:3]}")
        if bill_info['due_dates']:
            print(f"    还款日：{bill_info['due_dates'][:3]}")


def get_upcoming_bills(bills, days=None):
    """
    获取未来账单
    days: None 表示获取所有未来账单，数字表示未来多少天
    """
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
        
        best_due_date = None
        best_days_until = None
        
        for due_date_str in bill.get('due_dates', []):
            due_date_str = due_date_str.replace('/', '-')
            
            parsed_date = None
            try:
                parsed_date = datetime.strptime(due_date_str, '%Y-%m-%d')
            except:
                continue
            
            days_until = (parsed_date - today).days
            
            if days_until >= 0:
                if days is None or days_until <= days:
                    if best_days_until is None or days_until < best_days_until:
                        best_days_until = days_until
                        best_due_date = due_date_str
        
        if best_due_date and best_days_until is not None:
            for amount_info in bill.get('amounts', []):
                bank_info['amounts'].append({
                    'value': amount_info['value'],
                    'due_date': best_due_date,
                    'days_until': best_days_until,
                    'email': bill['subject']
                })
                bank_info['total_amount'] += amount_info['value']
            
            if bank_info['earliest_due_date'] is None or best_days_until < bank_info['earliest_due_date']['days_until']:
                bank_info['earliest_due_date'] = {
                    'date': best_due_date,
                    'days_until': best_days_until
                }
    
    return bank_bills


def generate_report(bank_bills, title="本月待还款账单汇总（未来 15 天内）"):
    print("\n" + "="*80)
    print(title)
    print("="*80)
    print(f"统计时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("-"*80)
    
    if not bank_bills:
        print("\n没有需要还款的账单！")
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
    print("本月待还款账单查询（重构版）")
    print("="*80)
    
    extractor = BillExtractor()
    bills = extractor.fetch_and_extract(limit=50)
    
    print(f"\n共分析 {len(bills)} 封账单邮件")
    
    upcoming_bills = get_upcoming_bills(bills, days=None)
    total = generate_report(upcoming_bills, title="未来待还款账单汇总（所有未来账单）")
    
    upcoming_15 = get_upcoming_bills(bills, days=15)
    total_15 = generate_report(upcoming_15, title="近期待还款账单（未来 15 天内）")
    
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
