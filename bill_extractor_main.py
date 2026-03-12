#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
银行账单自动提取主程序（集成持久化存储）
功能：
1. 从邮箱提取账单
2. 检测新邮件
3. 保存数据到 JSON
4. 生成文本报告
5. 提供 API 接口供 OpenClaw 调用
"""

import sys
import json
import os
import imaplib
import traceback
from datetime import datetime
from bill_storage import BillStorage, generate_text_report
from this_month_bills import BillExtractor, get_upcoming_bills, EMAIL_ADDRESS, PASSWORD, IMAP_SERVER, IMAP_PORT


class BillExtractorWithStorage:
    """带存储功能的账单提取器"""
    
    def __init__(self):
        self.storage = BillStorage()
        self.extractor = BillExtractor()
        self.error_log = []
    
    def run(self, email_limit=50):
        """执行完整的提取和存储流程"""
        print("="*80)
        print("银行账单自动提取系统")
        print("="*80)
        print(f"开始时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        
        try:
            # 1. 连接邮箱并获取邮件 ID
            print("步骤 1: 连接邮箱...")
            mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
            mail.login(EMAIL_ADDRESS, PASSWORD)
            print("登录成功！")
            
            mail.select('INBOX')
            status, messages = mail.search(None, 'ALL')
            
            if status != 'OK':
                raise Exception("搜索邮件失败")
            
            email_ids = messages[0].split()
            # 将 bytes 转换为字符串
            email_ids = [eid.decode('utf-8') if isinstance(eid, bytes) else eid for eid in email_ids]
            print(f"共找到 {len(email_ids)} 封邮件\n")
            
            # 2. 检查是否有新邮件
            print("步骤 2: 检查新邮件...")
            has_new, message = self.storage.check_new_emails(email_ids)
            print(f"检查结果：{message}")
            
            if not has_new and self.storage.data['last_email_count'] > 0:
                print("\n✓ 没有新邮件，使用已有数据")
                mail.logout()
                self.storage.save_data()
                generate_text_report(self.storage)
                return {
                    'success': True,
                    'message': '没有新邮件',
                    'has_new_emails': False
                }
            
            # 3. 提取账单
            print("\n步骤 3: 提取账单...")
            extractor = BillExtractor()
            bills = extractor.fetch_and_extract(limit=email_limit)
            print(f"提取到 {len(bills)} 封账单邮件\n")
            
            # 4. 获取待还款账单
            print("步骤 4: 筛选待还款账单...")
            upcoming_bills = get_upcoming_bills(bills, days=15)
            
            # 转换为字典格式以便存储
            upcoming_dict = {}
            for bank_name, info in upcoming_bills.items():
                upcoming_dict[bank_name] = {
                    'total_amount': info['total_amount'],
                    'amounts': info['amounts'],
                    'earliest_due_date': info['earliest_due_date']
                }
            
            # 5. 保存数据
            print("\n步骤 5: 保存数据...")
            self.storage.update_bills(bills, upcoming_dict)
            self.storage.save_data()
            
            # 6. 生成报告
            print("\n步骤 6: 生成报告...")
            text_report = generate_text_report(self.storage)
            
            print("\n" + text_report)
            
            # 7. 返回结果
            mail.logout()
            
            result = {
                'success': True,
                'message': '提取成功',
                'has_new_emails': has_new,
                'total_bills': len(bills),
                'upcoming_banks': list(upcoming_dict.keys()),
                'total_amount': sum(info['total_amount'] for info in upcoming_dict.values()),
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            return result
            
        except Exception as e:
            error_msg = f"{type(e).__name__}: {str(e)}"
            stack_trace = traceback.format_exc()
            
            print(f"\n❌ 错误：{error_msg}")
            print(stack_trace)
            
            # 记录错误
            self.error_log.append({
                'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'error': error_msg,
                'traceback': stack_trace
            })
            
            # 保存错误日志
            self.save_error_log()
            
            return {
                'success': False,
                'error': error_msg,
                'traceback': stack_trace
            }
    
    def save_error_log(self, log_file='error_log.json'):
        """保存错误日志"""
        errors = []
        if os.path.exists(log_file):
            try:
                with open(log_file, 'r', encoding='utf-8') as f:
                    errors = json.load(f)
            except:
                pass
        
        errors.extend(self.error_log[-10:])  # 只保留最近 10 个错误
        
        with open(log_file, 'w', encoding='utf-8') as f:
            json.dump(errors, f, ensure_ascii=False, indent=2)
        
        print(f"✓ 错误日志已保存至：{log_file}")
    
    def get_status(self):
        """获取系统状态"""
        stats = self.storage.get_statistics()
        upcoming = self.storage.get_upcoming_bills()
        
        total_amount = sum(
            info['total_amount'] for info in upcoming.values()
            if info['total_amount'] > 0
        )
        
        return {
            'status': 'ready',
            'last_check': stats['last_check_time'],
            'total_checks': stats['total_checks'],
            'upcoming_banks': len([b for b, i in upcoming.items() if i['total_amount'] > 0]),
            'total_amount': total_amount,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }


if __name__ == "__main__":
    extractor = BillExtractorWithStorage()
    result = extractor.run()
    
    print("\n" + "="*80)
    print("执行结果:")
    print(json.dumps(result, ensure_ascii=False, indent=2))
