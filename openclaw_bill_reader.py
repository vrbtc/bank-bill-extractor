#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
OpenClaw 银行账单查询模块
读取本地账单数据，提供简单接口
"""

import json
from datetime import datetime
from pathlib import Path

# 配置文件路径
BILL_FILE = Path(r'k:\Trae CN\R BANK\this_month_bills.json')

def load_bills():
    """
    加载账单数据
    
    Returns:
        dict: 账单数据，如果加载失败返回 None
    """
    if not BILL_FILE.exists():
        return {
            'success': False,
            'error': '账单文件不存在，请先运行 this_month_bills.py 生成数据'
        }
    
    try:
        with open(BILL_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        return {
            'success': True,
            'data': data,
            'file_path': str(BILL_FILE),
            'loaded_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
    except json.JSONDecodeError as e:
        return {
            'success': False,
            'error': f'JSON 解析错误：{str(e)}'
        }
    except Exception as e:
        return {
            'success': False,
            'error': f'读取失败：{str(e)}'
        }

def get_upcoming_bills(days=None):
    """
    获取未来待还款账单
    
    Args:
        days: 未来多少天，None 表示所有未来账单
    
    Returns:
        dict: 处理后的账单数据
    """
    result = load_bills()
    
    if not result['success']:
        return result
    
    data = result['data']
    bills = data.get('bills', [])
    
    today = datetime.now()
    bank_summary = {}
    
    for bill in bills:
        bank_name = bill.get('bank_name')
        if not bank_name:
            continue
        
        # 找到最近的未来还款日
        best_due_date = None
        best_days = None
        
        for due_date_str in bill.get('due_dates', []):
            try:
                due_date = datetime.strptime(due_date_str.replace('/', '-'), '%Y-%m-%d')
                days_until = (due_date - today).days
                
                if days_until >= 0:
                    if days is None or days_until <= days:
                        if best_days is None or days_until < best_days:
                            best_days = days_until
                            best_due_date = due_date_str
            except:
                continue
        
        # 添加到汇总
        if best_due_date and best_days is not None:
            if bank_name not in bank_summary:
                bank_summary[bank_name] = {
                    'total_amount': 0,
                    'earliest_due_date': best_due_date,
                    'days_until': best_days,
                    'bills': []
                }
            
            # 累加金额
            for amount_info in bill.get('amounts', []):
                bank_summary[bank_name]['total_amount'] += amount_info['value']
                bank_summary[bank_name]['bills'].append({
                    'subject': bill['subject'],
                    'amount': amount_info['value'],
                    'due_date': best_due_date
                })
    
    # 转换为列表并排序
    sorted_banks = sorted(
        bank_summary.items(),
        key=lambda x: x[1]['days_until']
    )
    
    total_amount = sum(info['total_amount'] for _, info in sorted_banks)
    
    return {
        'success': True,
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'total_amount': total_amount,
        'bank_count': len(sorted_banks),
        'banks': sorted_banks
    }

def print_report(days=None):
    """
    打印账单报告
    
    Args:
        days: 未来多少天，None 表示所有
    """
    result = get_upcoming_bills(days)
    
    if not result['success']:
        print(f"❌ {result['error']}")
        return
    
    print("="*80)
    if days:
        print(f"未来{days}天待还款账单")
    else:
        print("所有未来待还款账单")
    print("="*80)
    print(f"查询时间：{result['timestamp']}")
    print(f"待还款总额：¥{result['total_amount']:,.2f}")
    print(f"银行数量：{result['bank_count']}")
    print("-"*80)
    
    if not result['banks']:
        print("没有待还款账单")
        return
    
    for bank_name, info in result['banks']:
        days_text = f"{info['days_until']} 天后"
        if info['days_until'] <= 3:
            days_text += " ⚠️"
        
        print(f"{bank_name}: ¥{info['total_amount']:>12,.2f}  ({info['earliest_due_date']}, {days_text})")
    
    print("="*80)

def check_urgent_bills():
    """
    检查紧急账单（3 天内）
    
    Returns:
        list: 紧急账单列表
    """
    result = get_upcoming_bills(days=3)
    
    if not result['success']:
        return []
    
    urgent = []
    for bank_name, info in result['banks']:
        if info['total_amount'] > 0 and info['days_until'] <= 3:
            urgent.append({
                'bank': bank_name,
                'amount': info['total_amount'],
                'due_date': info['earliest_due_date'],
                'days': info['days_until']
            })
    
    return urgent

def send_notification():
    """
    发送通知（示例）
    """
    urgent = check_urgent_bills()
    
    if urgent:
        message = "⚠️ 紧急还款提醒\n\n"
        for bill in urgent:
            message += f"{bill['bank']}: ¥{bill['amount']:,.2f} ({bill['days']}天后)\n"
        
        message += f"\n总计：¥{sum(b['amount'] for b in urgent):,.2f}"
        
        # TODO: 在这里添加通知逻辑
        # 例如：微信、钉钉、邮件等
        print(message)
        return message
    else:
        print("✓ 无紧急账单")
        return None

if __name__ == "__main__":
    # 测试
    print_report(days=15)
    print()
    print_report(days=None)
    print()
    send_notification()
