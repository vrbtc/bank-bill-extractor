#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
银行账单查询技能 (Bank Bill Query Skill)
- 供 OpenClaw 和其他智能体调用
- 查询银行信用卡待还款账单
- 本地运行，数据安全
"""

import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Union

try:
    from this_month_bills import BillExtractor, get_upcoming_bills, generate_report
except ImportError:
    print("⚠️ 警告：无法导入 this_month_bills 模块")
    print("   请确保 this_month_bills.py 在同一目录或 Python 路径中")


class BillSkill:
    """
    银行账单查询技能
    
    功能：
    - 从邮箱提取银行账单
    - 查询待还款金额和日期
    - 检测紧急账单
    - 生成格式化报告
    
    使用示例：
        skill = BillSkill()
        
        # 查询所有未来账单
        result = skill.query()
        
        # 查询未来 15 天的账单
        result = skill.query(days=15)
        
        # 检查紧急账单（3天内）
        urgent = skill.check_urgent(days=3)
        
        # 生成报告
        report = skill.report(days=15)
    """
    
    def __init__(self, config_path: str = 'config.json', data_path: str = 'this_month_bills.json'):
        """
        初始化技能实例
        
        Args:
            config_path: 配置文件路径（默认当前目录）
            data_path: 数据文件路径（默认 this_month_bills.json）
        """
        self.config_path = Path(config_path)
        self.data_path = Path(data_path)
        self.config = None
        self._data_cache = None
        self._cache_time = None
        
        # 加载配置
        self._load_config()
    
    def _load_config(self):
        """加载配置文件"""
        if not self.config_path.exists():
            raise FileNotFoundError(
                f"配置文件不存在：{self.config_path}\n"
                f"请创建 config.json 并填入邮箱信息"
            )
        
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
            
            # 验证必要字段
            required_fields = ['email', 'password', 'imap_server']
            for field in required_fields:
                if field not in self.config:
                    raise ValueError(f"配置文件缺少必要字段：{field}")
            
            return True
        
        except json.JSONDecodeError as e:
            raise ValueError(f"配置文件格式错误：{e}")
    
    def _load_data(self) -> dict:
        """加载数据文件"""
        if not self.data_path.exists():
            return {'success': False, 'error': '数据文件不存在，请先运行 refresh()'}
        
        try:
            with open(self.data_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            self._data_cache = data
            self._cache_time = datetime.now()
            
            return {
                'success': True,
                'data': data,
                'loaded_at': self._cache_time.strftime('%Y-%m-%d %H:%M:%S')
            }
        
        except json.JSONDecodeError as e:
            return {'success': False, 'error': f'JSON 解析错误：{e}'}
        except Exception as e:
            return {'success': False, 'error': f'读取失败：{e}'}
    
    def _is_cache_valid(self, max_age_hours: int = 24) -> bool:
        """检查缓存是否有效"""
        if self._cache_time is None or self._data_cache is None:
            return False
        
        age = (datetime.now() - self._cache_time).total_seconds() / 3600
        return age < max_age_hours
    
    def refresh(self, force: bool = False) -> dict:
        """
        从邮箱刷新账单数据
        
        Args:
            force: 是否强制刷新（忽略缓存）
        
        Returns:
            dict: 包含 success, message, bills_count 的字典
        """
        try:
            # 导入并使用 BillExtractor
            from this_month_bills import BillExtractor
            
            extractor = BillExtractor()
            bills = extractor.fetch_and_extract(limit=50)
            
            if bills is None:
                return {
                    'success': False,
                    'message': '无法获取账单数据',
                    'bills_count': 0
                }
            
            # 更新缓存
            result = self._load_data()
            
            if result['success']:
                return {
                    'success': True,
                    'message': f'成功刷新数据',
                    'bills_count': len(bills),
                    'timestamp': result['loaded_at']
                }
            else:
                return {
                    'success': True,
                    'message': f'已获取 {len(bills)} 封账单，但缓存更新失败',
                    'bills_count': len(bills),
                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
        
        except Exception as e:
            return {
                'success': False,
                'message': f'刷新失败：{str(e)}',
                'bills_count': 0
            }
    
    def query(self, days: int = None, bank_name: str = None) -> dict:
        """
        查询账单信息
        
        Args:
            days: 未来多少天内的账单（None=所有未来账单）
            bank_name: 指定银行名称（None=所有银行）
        
        Returns:
            dict: 结构化的账单数据
        """
        # 加载数据
        result = self._load_data()
        
        if not result['success']:
            return {
                'success': False,
                'error': result['error'],
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
        
        data = result['data']
        bills = data.get('bills', [])
        
        # 使用 get_upcoming_bills 函数过滤
        try:
            upcoming = get_upcoming_bills(bills, days=days)
        except:
            # 如果函数不可用，手动过滤
            upcoming = self._manual_filter(bills, days)
        
        # 过滤指定银行
        if bank_name:
            filtered = {}
            for bname, info in upcoming.items():
                if bank_name in bname:
                    filtered[bname] = info
            upcoming = filtered
        
        # 构建返回结果
        total_amount = sum(info['total_amount'] for _, info in upcoming.items())
        
        banks_list = []
        for bname, info in sorted(upcoming.items(), key=lambda x: x[1].get('earliest_due_date') and x[1]['earliest_due_date'].get('days_until', 999) or 999):
            if info['total_amount'] > 0 and info.get('earliest_due_date'):
                banks_list.append({
                    'name': bname,
                    'amount': info['total_amount'],
                    'due_date': info['earliest_due_date']['date'],
                    'days_until': info['earliest_due_date']['days_until'],
                    'bills_count': len(info.get('bills', []))
                })
        
        return {
            'success': True,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'total_amount': total_amount,
            'bank_count': len(banks_list),
            'banks': banks_list,
            'raw_data': upcoming
        }
    
    def _manual_filter(self, bills: List[dict], days: int = None) -> dict:
        """手动过滤账单（备用方法）"""
        today = datetime.now()
        bank_bills = {}
        
        for bill in bills:
            bank_name = bill.get('bank_name')
            if not bank_name:
                continue
            
            if bank_name not in bank_bills:
                bank_bills[bank_name] = {
                    'total_amount': 0,
                    'amounts': [],
                    'earliest_due_date': None
                }
            
            info = bank_bills[bank_name]
            
            # 找到最近的未来还款日
            best_due_date = None
            best_days = None
            
            for due_date_str in bill.get('due_dates', []):
                due_date_str = due_date_str.replace('/', '-')
                
                try:
                    due_date = datetime.strptime(due_date_str, '%Y-%m-%d')
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
                for amount_info in bill.get('amounts', []):
                    info['amounts'].append({
                        'value': amount_info['value'],
                        'due_date': best_due_date,
                        'days_until': best_days
                    })
                    info['total_amount'] += amount_info['value']
                
                if info['earliest_due_date'] is None or best_days < info['earliest_due_date']['days_until']:
                    info['earliest_due_date'] = {
                        'date': best_due_date,
                        'days_until': best_days
                    }
        
        return bank_bills
    
    def check_urgent(self, days: int = 3) -> List[dict]:
        """
        检查紧急账单
        
        Args:
            days: 紧急阈值天数（默认 3 天）
        
        Returns:
            list: 紧急账单列表
        """
        result = self.query(days=days)
        
        if not result['success']:
            return []
        
        urgent = []
        for bank in result['banks']:
            if bank['days_until'] <= days and bank['amount'] > 0:
                urgent.append({
                    'bank': bank['name'],
                    'amount': bank['amount'],
                    'due_date': bank['due_date'],
                    'days': bank['days_until']
                })
        
        # 按剩余天数排序
        urgent.sort(key=lambda x: x['days'])
        
        return urgent
    
    def report(self, days: int = 15, format_type: str = 'text') -> str:
        """
        生成格式化报告
        
        Args:
            days: 查询范围（天）
            format_type: 输出格式 ('text'/'json'/'table')
        
        Returns:
            str: 格式化的报告字符串
        """
        result = self.query(days=days)
        
        if not result['success']:
            return f"❌ 错误：{result['error']}"
        
        if format_type == 'json':
            return json.dumps(result, ensure_ascii=False, indent=2)
        
        elif format_type == 'table':
            return self._format_table(result, days)
        
        else:  # text
            return self._format_text(result, days)
    
    def _format_text(self, result: dict, days: int) -> str:
        """格式化为文本报告"""
        now = datetime.now().strftime('%Y年%m月%d日')
        
        lines = [
            f"📊 银行账单报告 - {now}",
            "",
            "=" * 60,
            "",
            f"📋 未来 {days} 天待还款账单",
            "",
            "  银行          金额          还款日      状态",
            "  " + "-" * 50,
        ]
        
        for bank in result['banks']:
            if bank['days_until'] <= 3:
                status = f"🔴 {bank['days_until']}天后"
            elif bank['days_until'] <= 7:
                status = f"🟡 {bank['days_until']}天后"
            else:
                status = f"🟢 {bank['days_until']}天后"
            
            lines.append(
                f"  {bank['name']:8s} ¥{bank['amount']:>12,.2f} "
                f"{bank['due_date']}  {status}"
            )
        
        lines.extend([
            "",
            "  " + "-" * 50,
            f"  💰 合计：¥{result['total_amount']:>12,.2f}",
            "",
        ])
        
        # 紧急提醒
        urgent = self.check_urgent(days=min(3, days))
        if urgent:
            lines.extend([
                "⚠️ 紧急提醒（3天内到期）：",
                ""
            ])
            for bill in urgent:
                lines.append(f"  • {bill['bank']}: ¥{bill['amount']:,.2f} ({bill['days']}天后到期)")
            
            total_urgent = sum(b['amount'] for b in urgent)
            lines.append(f"\n  总计：¥{total_urgent:,.2f}")
        
        lines.extend([
            "",
            "=" * 60,
        ])
        
        return "\n".join(lines)
    
    def _format_table(self, result: dict, days: int) -> str:
        """格式化为表格"""
        lines = [
            f"╔{'═'*65}╗",
            f"║{'银行名称':^10s}║{'本期应还':^15s}║{'最晚还款日':^15s}║{'剩余天数':^10s}║",
            f"╠{'─'*65}╣",
        ]
        
        for bank in result['banks']:
            emoji = "🔴" if bank['days_until'] <= 3 else "🟡" if bank['days_until'] <= 7 else "🟢"
            lines.append(
                f"║{emoji}{bank['name']:^9s}║¥{bank['amount']:>13,.2f}║"
                f"{bank['due_date']:^15s}║{bank['days_until']:>8d} 天 ║"
            )
        
        lines.extend([
            f"╠{'─'*65}╣",
            f"║{'总计':^10s}║¥{result['total_amount']:>13,.2f}║{'':^15s}║{'':^10s}║",
            f"╚{'═'*65}╝",
        ])
        
        return "\n".join(lines)
    
    def export(self, filepath: str = None, format_type: str = 'json') -> str:
        """
        导出数据到文件
        
        Args:
            filepath: 文件路径（None=自动生成）
            format_type: 导出格式 ('json'/'txt'/'csv')
        
        Returns:
            str: 导出的文件路径
        """
        result = self.query()
        
        if not result['success']:
            raise RuntimeError(f"导出失败：{result['error']}")
        
        # 生成文件名
        if filepath is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            if format_type == 'json':
                filepath = f'bills_export_{timestamp}.json'
            elif format_type == 'csv':
                filepath = f'bills_export_{timestamp}.csv'
            else:
                filepath = f'bills_export_{timestamp}.txt'
        
        # 根据格式写入
        if format_type == 'json':
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
        
        elif format_type == 'csv':
            import csv
            with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                writer.writerow(['银行名称', '金额', '还款日', '剩余天数'])
                for bank in result['banks']:
                    writer.writerow([
                        bank['name'],
                        bank['amount'],
                        bank['due_date'],
                        bank['days_until']
                    ])
        
        else:  # txt
            content = self.report(format_type='text')
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
        
        return os.path.abspath(filepath)
    
    def get_status(self) -> dict:
        """
        获取系统状态
        
        Returns:
            dict: 系统状态信息
        """
        status = {
            'config_exists': self.config_path.exists(),
            'data_exists': self.data_path.exists(),
            'last_update': None,
            'bills_count': 0,
            'cache_age_hours': None,
            'skill_version': '1.0.0'
        }
        
        if status['data_exists']:
            result = self._load_data()
            if result['success']:
                data = result['data']
                status['last_update'] = data.get('generated_at')
                status['bills_count'] = data.get('total_bills', 0)
                
                if self._cache_time:
                    age = (datetime.now() - self._cache_time).total_seconds() / 3600
                    status['cache_age_hours'] = round(age, 1)
        
        return status


def load_config(config_path: str = 'config.json') -> dict:
    """
    加载配置文件
    
    Args:
        config_path: 配置文件路径
    
    Returns:
        dict: 配置字典
    """
    path = Path(config_path)
    
    if not path.exists():
        raise FileNotFoundError(f"配置文件不存在：{path}")
    
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def validate_config(config: dict) -> tuple:
    """
    验证配置文件是否有效
    
    Args:
        config: 配置字典
    
    Returns:
        tuple: (is_valid, error_message)
    """
    required_fields = ['email', 'password', 'imap_server']
    
    for field in required_fields:
        if field not in config:
            return (False, f"缺少必要字段：{field}")
        
        if not config[field]:
            return (False, f"字段 '{field}' 不能为空")
    
    # 可选字段
    if 'imap_port' not in config:
        config['imap_port'] = 993
    
    return (True, None)


def format_currency(amount: float, currency: str = 'CNY') -> str:
    """
    格式化金额显示
    
    Args:
        amount: 金额数值
        currency: 货币代码
    
    Returns:
        str: 格式化后的金额字符串
    """
    symbols = {
        'CNY': '¥',
        'USD': '$',
        'EUR': '€',
        'GBP': '£'
    }
    
    symbol = symbols.get(currency, currency)
    
    return f"{symbol}{amount:,.2f}"


# 命令行接口
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='银行账单查询工具')
    subparsers = parser.add_subparsers(dest='command', help='可用命令')
    
    # query 命令
    query_parser = subparsers.add_parser('query', help='查询账单')
    query_parser.add_argument('--days', type=int, default=None, help='未来多少天（默认全部）')
    query_parser.add_argument('--bank', type=str, default=None, help='指定银行名称')
    query_parser.add_argument('--format', choices=['text', 'json', 'table'], default='text', help='输出格式')
    
    # urgent 命令
    urgent_parser = subparsers.add_parser('urgent', help='检查紧急账单')
    urgent_parser.add_argument('--days', type=int, default=3, help='紧急阈值天数')
    
    # refresh 命令
    refresh_parser = subparsers.add_parser('refresh', help='刷新数据')
    refresh_parser.add_argument('--force', action='store_true', help='强制刷新')
    
    # export 命令
    export_parser = subparsers.add_parser('export', help='导出数据')
    export_parser.add_argument('--format', choices=['json', 'txt', 'csv'], default='json', help='导出格式')
    export_parser.add_argument('--output', type=str, default=None, help='输出文件路径')
    
    # status 命令
    status_parser = subparsers.add_parser('status', help='查看系统状态')
    
    # report 命令
    report_parser = subparsers.add_parser('report', help='生成账单报告')
    report_parser.add_argument('--days', type=int, default=15, help='报告天数范围（默认15天）')
    report_parser.add_argument('--format', choices=['text', 'json'], default='text', help='输出格式')
    
    args = parser.parse_args()
    
    if args.command is None:
        parser.print_help()
        sys.exit(1)
    
    try:
        skill = BillSkill()
        
        if args.command == 'query':
            result = skill.query(days=args.days, bank_name=args.bank)
            
            if args.format == 'json':
                print(json.dumps(result, ensure_ascii=False, indent=2))
            else:
                print(skill.report(days=args.days or 15, format_type=args.format))
        
        elif args.command == 'urgent':
            urgent = skill.check_urgent(days=args.days)
            
            if urgent:
                print(f"⚠️ 发现 {len(urgent)} 笔紧急账单（{args.days}天内到期）：\n")
                
                for bill in urgent:
                    emoji = "🔴" if bill['days'] <= 1 else "🟡" if bill['days'] <= 3 else "🟢"
                    print(f"  {emoji} {bill['bank']}: ¥{bill['amount']:,.2f} ({bill['days']}天后到期)")
                
                total = sum(b['amount'] for b in urgent)
                print(f"\n总计：¥{total:,.2f}")
            else:
                print("✅ 无紧急账单")
        
        elif args.command == 'refresh':
            result = skill.refresh(force=args.force)
            
            if result['success']:
                print(f"✅ {result['message']}")
                print(f"   共获取 {result['bills_count']} 封账单邮件")
                if result.get('timestamp'):
                    print(f"   时间：{result['timestamp']}")
            else:
                print(f"❌ {result['message']}")
        
        elif args.command == 'export':
            try:
                filepath = skill.export(filepath=args.output, format_type=args.format)
                print(f"✅ 数据已导出到：{filepath}")
            except Exception as e:
                print(f"❌ 导出失败：{e}")
        
        elif args.command == 'status':
            status = skill.get_status()
            
            print("📊 系统状态")
            print("="*40)
            print(f"  配置文件：{'✓ 存在' if status['config_exists'] else '✗ 不存在'}")
            print(f"  数据文件：{'✓ 存在' if status['data_exists'] else '✗ 不存在'}")
            
            if status['last_update']:
                print(f"  最后更新：{status['last_update']}")
            
            if status['bills_count']:
                print(f"  账单数量：{status['bills_count']} 封")
            
            if status['cache_age_hours'] is not None:
                age = status['cache_age_hours']
                if age < 24:
                    print(f"  缓存年龄：{age:.1f} 小时 ✓")
                else:
                    print(f"  缓存年龄：{age:.1f} 小时 ⚠️ （建议刷新）")
            
            print(f"  技能版本：v{status['skill_version']}")
        
        elif args.command == 'report':
            report_text = skill.report(days=args.days, format_type=args.format)
            
            if args.format == 'json':
                print(report_text)
            else:
                print(report_text)
    
    except FileNotFoundError as e:
        print(f"❌ 错误：{e}")
        print("\n请先创建 config.json 文件：")
        print("""
{
  "email": "your_email@example.com",
  "password": "your_password",
  "imap_server": "imap.example.com",
  "imap_port": 993
}
""")
    
    except Exception as e:
        print(f"❌ 发生错误：{e}")
        import traceback
        traceback.print_exc()
