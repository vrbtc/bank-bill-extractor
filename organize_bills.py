#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
账单整理工具
按银行、待还款金额、还款日期重新整理账单数据
"""

import json
from datetime import datetime
from collections import defaultdict


def load_bill_data():
    """加载账单数据"""
    with open('bill_report.json', 'r', encoding='utf-8') as f:
        return json.load(f)


def parse_date(date_str):
    """解析日期字符串"""
    if not date_str:
        return None
    
    date_formats = [
        '%Y-%m-%d',
        '%Y/%m/%d',
        '%Y-%m-%d %H:%M:%S',
    ]
    
    for fmt in date_formats:
        try:
            return datetime.strptime(date_str, fmt)
        except:
            continue
    
    return None


def organize_by_bank(bills):
    """按银行整理账单"""
    bank_data = defaultdict(lambda: {
        'total_amount': 0,
        'amounts': [],
        'due_dates': set(),
        'bill_count': 0,
        'emails': []
    })
    
    for bill in bills:
        bank_name = bill.get('bank_name') or '其他'
        bank_info = bank_data[bank_name]
        
        bank_info['bill_count'] += 1
        bank_info['emails'].append(bill['subject'])
        
        for amount_info in bill.get('amounts', []):
            amount = amount_info['value']
            currency = amount_info.get('currency', 'CNY')
            bank_info['amounts'].append({
                'value': amount,
                'currency': currency,
                'email': bill['subject']
            })
            bank_info['total_amount'] += amount
        
        for due_date in bill.get('due_dates', []):
            bank_info['due_dates'].add(due_date)
    
    return bank_data


def organize_by_date(bills):
    """按还款日期整理账单"""
    date_data = defaultdict(lambda: {
        'total_amount': 0,
        'banks': set(),
        'details': []
    })
    
    for bill in bills:
        bank_name = bill.get('bank_name') or '其他'
        
        for due_date in bill.get('due_dates', []):
            parsed_date = parse_date(due_date)
            if parsed_date:
                date_key = parsed_date.strftime('%Y-%m-%d')
                date_info = date_data[date_key]
                date_info['banks'].add(bank_name)
                
                for amount_info in bill.get('amounts', []):
                    date_info['details'].append({
                        'bank': bank_name,
                        'amount': amount_info['value'],
                        'currency': amount_info.get('currency', 'CNY'),
                        'email': bill['subject']
                    })
                    date_info['total_amount'] += amount_info['value']
    
    return date_data


def generate_report(data, report_type='bank'):
    """生成整理后的报告"""
    print("\n" + "="*100)
    
    if report_type == 'bank':
        print("按银行整理的待还款账单")
        print("="*100)
        
        sorted_banks = sorted(data.items(), key=lambda x: x[1]['total_amount'], reverse=True)
        
        for bank_name, info in sorted_banks:
            print(f"\n【{bank_name}】")
            print(f"  账单数量：{info['bill_count']} 封")
            print(f"  待还款总额：¥{info['total_amount']:,.2f} CNY")
            
            if info['amounts']:
                print(f"  金额明细:")
                for idx, amt in enumerate(info['amounts'][:10], 1):
                    print(f"    {idx}. ¥{amt['value']:,.2f} {amt['currency']} (来自：{amt['email'][:50]}...)")
                if len(info['amounts']) > 10:
                    print(f"    ... 还有 {len(info['amounts']) - 10} 笔")
            
            if info['due_dates']:
                sorted_dates = sorted(info['due_dates'])
                print(f"  还款日期范围：{sorted_dates[0]} 至 {sorted_dates[-1]}")
                print(f"  所有还款日：{', '.join(sorted_dates[:5])}")
                if len(sorted_dates) > 5:
                    print(f"    ... 共 {len(sorted_dates)} 个日期")
    
    elif report_type == 'date':
        print("按还款日期整理的待还款账单")
        print("="*100)
        
        sorted_dates = sorted(data.items(), key=lambda x: parse_date(x[0]) or datetime.max)
        today = datetime.now()
        
        upcoming_count = 0
        for date_str, info in sorted_dates:
            parsed_date = parse_date(date_str)
            if not parsed_date:
                continue
            
            days_until = (parsed_date - today).days
            
            if days_until >= 0:
                upcoming_count += 1
            
            if days_until < 0:
                date_label = f"{date_str} (已逾期 {abs(days_until)} 天)"
            elif days_until == 0:
                date_label = f"{date_str} (今天！)"
            elif days_until <= 3:
                date_label = f"{date_str} (还剩 {days_until} 天) ⚠️"
            elif days_until <= 7:
                date_label = f"{date_str} (还剩 {days_until} 天)"
            else:
                date_label = date_str
            
            print(f"\n【{date_label}】")
            print(f"  涉及银行：{', '.join(info['banks'])}")
            print(f"  待还总额：¥{info['total_amount']:,.2f}")
            
            if info['details']:
                print(f"  明细:")
                for idx, detail in enumerate(info['details'][:5], 1):
                    print(f"    {idx}. {detail['bank']}: ¥{detail['amount']:,.2f} {detail['currency']}")
                if len(info['details']) > 5:
                    print(f"    ... 还有 {len(info['details']) - 5} 笔")
    
    print("\n" + "="*100)


def generate_summary_table(bank_data):
    """生成汇总表格"""
    print("\n" + "─"*100)
    print("银行待还款金额汇总表")
    print("─"*100)
    print(f"{'银行名称':<15} {'账单数量':<10} {'待还款总额 (CNY)':<20} {'还款日期数':<15}")
    print("─"*100)
    
    total_all = 0
    for bank_name, info in sorted(bank_data.items(), key=lambda x: x[1]['total_amount'], reverse=True):
        print(f"{bank_name:<15} {info['bill_count']:<10} ¥{info['total_amount']:>18,.2f}  {len(info['due_dates']):<15}")
        total_all += info['total_amount']
    
    print("─"*100)
    print(f"{'总计':<15} {sum(info['bill_count'] for info in bank_data.values()):<10} ¥{total_all:>18,.2f}")
    print("─"*100)


def main():
    print("="*100)
    print("账单整理报告")
    print("="*100)
    
    data = load_bill_data()
    bills = data['bills']
    
    print(f"\n共加载 {len(bills)} 封账单邮件")
    print(f"数据生成时间：{data['generated_at']}")
    
    bank_data = organize_by_bank(bills)
    date_data = organize_by_date(bills)
    
    generate_summary_table(bank_data)
    generate_report(bank_data, report_type='bank')
    generate_report(date_data, report_type='date')
    
    save_organized_data(bank_data, date_data)


def save_organized_data(bank_data, date_data):
    """保存整理后的数据"""
    organized_data = {
        'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'by_bank': {},
        'by_date': {}
    }
    
    for bank_name, info in bank_data.items():
        organized_data['by_bank'][bank_name] = {
            'total_amount': info['total_amount'],
            'bill_count': info['bill_count'],
            'amounts': info['amounts'],
            'due_dates': sorted(list(info['due_dates'])),
            'emails': info['emails']
        }
    
    for date_str, info in date_data.items():
        organized_data['by_date'][date_str] = {
            'total_amount': info['total_amount'],
            'banks': list(info['banks']),
            'details': info['details']
        }
    
    with open('organized_bills.json', 'w', encoding='utf-8') as f:
        json.dump(organized_data, f, ensure_ascii=False, indent=2)
    
    print(f"\n整理后的数据已保存至：organized_bills.json")


if __name__ == "__main__":
    main()
