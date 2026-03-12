#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
银行账单持久化存储和新邮件检测系统
功能：
1. 保存所有账单数据到 JSON 文件
2. 检测新邮件并更新
3. 提供历史数据查询
"""

import json
import os
from datetime import datetime
from pathlib import Path


class BillStorage:
    """账单数据存储管理类"""
    
    def __init__(self, storage_file='bill_data_history.json'):
        self.storage_file = storage_file
        self.data = self.load_data()
    
    def load_data(self):
        """加载历史数据"""
        if os.path.exists(self.storage_file):
            try:
                with open(self.storage_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                pass
        
        # 初始化数据结构
        return {
            'last_check_time': None,
            'last_email_count': 0,
            'last_email_ids': [],
            'total_checks': 0,
            'bills_history': [],
            'upcoming_bills': []
        }
    
    def save_data(self):
        """保存数据到文件"""
        self.data['last_check_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self.data['total_checks'] += 1
        
        with open(self.storage_file, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)
        
        print(f"✓ 数据已保存至：{self.storage_file}")
    
    def check_new_emails(self, current_email_ids):
        """检查是否有新邮件"""
        last_email_ids = self.data.get('last_email_ids', [])
        
        # 第一次运行
        if not last_email_ids:
            self.data['last_email_ids'] = current_email_ids
            self.data['last_email_count'] = len(current_email_ids)
            return True, "首次运行，初始化完成"
        
        # 检查是否有新邮件
        new_emails = [eid for eid in current_email_ids if eid not in last_email_ids]
        
        if new_emails:
            self.data['last_email_ids'] = current_email_ids
            self.data['last_email_count'] = len(current_email_ids)
            return True, f"发现 {len(new_emails)} 封新邮件"
        else:
            return False, "没有新邮件"
    
    def update_bills(self, bills, upcoming_bills):
        """更新账单数据"""
        # 保存本次提取的所有账单
        bill_record = {
            'check_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'total_bills': len(bills),
            'bills': bills
        }
        self.data['bills_history'].append(bill_record)
        
        # 保留最近 100 次记录
        if len(self.data['bills_history']) > 100:
            self.data['bills_history'] = self.data['bills_history'][-100:]
        
        # 保存当前待还款账单
        self.data['upcoming_bills'] = upcoming_bills
        
        print(f"✓ 已更新账单数据：{len(bills)} 封账单，{len(upcoming_bills)} 个待还款")
    
    def get_latest_bills(self):
        """获取最新的账单数据"""
        if self.data['bills_history']:
            return self.data['bills_history'][-1]
        return None
    
    def get_upcoming_bills(self):
        """获取待还款账单"""
        return self.data.get('upcoming_bills', [])
    
    def get_statistics(self):
        """获取统计信息"""
        return {
            'last_check_time': self.data.get('last_check_time', '从未检查'),
            'total_checks': self.data.get('total_checks', 0),
            'last_email_count': self.data.get('last_email_count', 0),
            'total_bills_records': len(self.data.get('bills_history', []))
        }


def generate_text_report(storage, output_file='bill_summary.txt'):
    """生成文本格式的汇总报告"""
    upcoming = storage.get_upcoming_bills()
    stats = storage.get_statistics()
    latest = storage.get_latest_bills()
    
    lines = []
    lines.append("="*80)
    lines.append("银行账单汇总报告")
    lines.append("="*80)
    lines.append(f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"上次检查：{stats['last_check_time']}")
    lines.append(f"总检查次数：{stats['total_checks']}")
    lines.append("")
    
    if latest:
        lines.append(f"最新提取：{latest['check_time']}")
        lines.append(f"账单总数：{latest['total_bills']}")
        lines.append("")
    
    lines.append("-"*80)
    lines.append("未来 15 天内待还款账单")
    lines.append("-"*80)
    
    if upcoming:
        total = 0
        for bank, info in upcoming.items():
            if info['total_amount'] > 0 and info.get('earliest_due_date'):
                due_date = info['earliest_due_date']['date']
                days_left = info['earliest_due_date']['days_until']
                amount = info['total_amount']
                total += amount
                
                if days_left <= 3:
                    alert = "⚠️⚠️⚠️ 紧急"
                elif days_left <= 7:
                    alert = "⚠️ 注意"
                else:
                    alert = ""
                
                lines.append(f"{bank}: ¥{amount:,.2f} | 还款日：{due_date} | 剩余：{days_left}天 {alert}")
        
        lines.append("-"*80)
        lines.append(f"总计：¥{total:,.2f}")
    else:
        lines.append("未来 15 天内没有待还款账单")
    
    lines.append("")
    lines.append("="*80)
    lines.append("详细数据请查看：bill_data_history.json")
    lines.append("="*80)
    
    text = "\n".join(lines)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(text)
    
    print(f"✓ 文本报告已保存至：{output_file}")
    return text


if __name__ == "__main__":
    # 测试
    storage = BillStorage()
    stats = storage.get_statistics()
    print(f"统计信息：{stats}")
