#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
银行账单提取器模块
包含银行提取器基类和具体银行实现
"""

import re
from abc import ABC, abstractmethod
from datetime import datetime
from bs4 import BeautifulSoup


class BaseBankExtractor(ABC):
    """银行提取器基类"""
    
    @abstractmethod
    def extract_amount(self, full_text, bill_info):
        """
        提取金额
        
        Args:
            full_text: 邮件全文
            bill_info: 账单信息字典
        """
        pass
    
    @abstractmethod
    def extract_due_date(self, full_text, bill_info):
        """
        提取还款日
        
        Args:
            full_text: 邮件全文
            bill_info: 账单信息字典
        """
        pass
    
    @abstractmethod
    def get_supported_banks(self):
        """
        获取支持的银行列表
        
        Returns:
            银行名称列表
        """
        pass
    
    def preprocess_text(self, full_text):
        """
        预处理文本（子类可重写）
        
        Args:
            full_text: 邮件全文
            
        Returns:
            预处理后的文本
        """
        return full_text.replace('&amp;', '&').replace('&yen;', '￥').replace('&nbsp;', ' ')


class GuangfaBankExtractor(BaseBankExtractor):
    """广发银行提取器"""
    
    def get_supported_banks(self):
        return ['广发银行']
    
    def preprocess_text(self, full_text):
        return full_text.replace('&amp;', '&')
    
    def extract_amount(self, full_text, bill_info):
        soup = BeautifulSoup(full_text, 'html.parser')
        clean_text = soup.get_text()
        clean_text = ' '.join(clean_text.split())
        
        amount_match = re.search(r'卡号末四位\s+本期账单金额\s+最低还款额\s+最后还款日\s+入账货币\s+存款\s+卡片消费额度\s+\d+\s+([\d,]+\.\d+)', clean_text)
        if amount_match:
            try:
                amount = float(amount_match.group(1).replace(',', ''))
                if 0 < amount < 1000000:
                    bill_info['amounts'] = [{'value': amount, 'currency': 'CNY'}]
                    return
            except:
                pass
        
        amount_match = re.search(r'本期账单金额\s+最低还款额.*?\d{4}\s+([\d,]+\.\d{2})', clean_text)
        if amount_match:
            try:
                amount = float(amount_match.group(1).replace(',', ''))
                if 0 < amount < 1000000:
                    bill_info['amounts'] = [{'value': amount, 'currency': 'CNY'}]
                    return
            except:
                pass
        
        amount_match = re.search(r'&yen;[^>]*>[^>]*>([\d,]+\.?\d*)', full_text)
        if amount_match:
            try:
                amount = float(amount_match.group(1).replace(',', ''))
                if 0 < amount < 1000000:
                    bill_info['amounts'] = [{'value': amount, 'currency': 'CNY'}]
                    return
            except:
                pass
    
    def extract_due_date(self, full_text, bill_info):
        soup = BeautifulSoup(full_text, 'html.parser')
        clean_text = soup.get_text()
        clean_text = ' '.join(clean_text.split())
        
        due_match = re.search(r'最后还款日\s+入账货币\s+存款\s+卡片消费额度\s+\d+\s+[\d,]+\.\d+\s+[\d,]+\.\d+\s+(\d{4}/\d{2}/\d{2})', clean_text)
        if due_match:
            date_str = due_match.group(1).replace('/', '-')
            try:
                datetime.strptime(date_str, '%Y-%m-%d')
                if date_str not in bill_info['due_dates']:
                    bill_info['due_dates'].append(date_str)
                return
            except:
                pass
        
        due_match = re.search(r'最后还款日.*?(\d{4}/\d{2}/\d{2})', clean_text)
        if due_match:
            date_str = due_match.group(1).replace('/', '-')
            try:
                datetime.strptime(date_str, '%Y-%m-%d')
                if date_str not in bill_info['due_dates']:
                    bill_info['due_dates'].append(date_str)
                return
            except:
                pass
        
        due_patterns = [r'最后还款日.*?(\d{4}/\d{2}/\d{2})']
        for pattern in due_patterns:
            matches = re.findall(pattern, full_text)
            for match in matches:
                date_str = match.replace('/', '-')
                try:
                    datetime.strptime(date_str, '%Y-%m-%d')
                    if date_str not in bill_info['due_dates']:
                        bill_info['due_dates'].append(date_str)
                except:
                    continue


class CMBBankExtractor(BaseBankExtractor):
    """招商银行提取器"""
    
    def get_supported_banks(self):
        return ['招商银行']
    
    def extract_amount(self, full_text, bill_info):
        """提取招商银行金额"""
        bill_period_match = re.search(r'(\d{4}/\d{2}/\d{2}-\d{4}/\d{2}/\d{2})', full_text)
        
        if bill_period_match:
            bill_period = bill_period_match.group(1)
            
            soup = BeautifulSoup(full_text, 'html.parser')
            clean_text = soup.get_text()
            clean_text = re.sub(r'\s+', ' ', clean_text)
            
            pos = clean_text.find(bill_period)
            
            if pos != -1:
                snippet = clean_text[pos:]
                amounts = re.findall(r'￥\s*([0-9,]+\.[0-9]+)', snippet)
                
                target_amount_idx = 0
                subject = bill_info.get('subject', '')
                if 'e 招贷' not in subject and '分期' not in subject:
                    if len(amounts) >= 2:
                        target_amount_idx = 1
                elif '分期' in subject:
                    for idx, amt in enumerate(amounts):
                        try:
                            test_amt = float(amt.replace(',', ''))
                            if test_amt > 0:
                                target_amount_idx = idx
                                break
                        except:
                            pass
                
                if len(amounts) > target_amount_idx:
                    amt_str = amounts[target_amount_idx].replace(',', '')
                    if '.' in amt_str:
                        integer_part, decimal_part = amt_str.split('.', 1)
                        if len(decimal_part) > 2:
                            amt_str = f"{integer_part}.{decimal_part[:2]}"
                    
                    try:
                        amount = float(amt_str)
                        if 100 < amount < 100000:
                            bill_info['amounts'] = [{'value': amount, 'currency': 'CNY'}]
                    except:
                        pass
    
    def extract_due_date(self, full_text, bill_info):
        """提取招商银行还款日"""
        bill_period_match = re.search(r'(\d{4}/\d{2}/\d{2}-\d{4}/\d{2}/\d{2})', full_text)
        
        if bill_period_match:
            bill_period = bill_period_match.group(1)
            
            soup = BeautifulSoup(full_text, 'html.parser')
            clean_text = soup.get_text()
            clean_text = re.sub(r'\s+', ' ', clean_text)
            
            pos = clean_text.find(bill_period)
            
            if pos != -1:
                snippet = clean_text[pos:]
                dates = re.findall(r'(\d{4}/\d{2}/\d{2})', snippet)
                bill_dates = [bill_period[:10], bill_period[11:]]
                due_dates = [d for d in dates if d not in bill_dates]
                
                if due_dates:
                    date_str = due_dates[0].replace('/', '-')
                    if date_str not in bill_info['due_dates']:
                        bill_info['due_dates'].append(date_str)


class CCBBankExtractor(BaseBankExtractor):
    """建设银行提取器"""
    
    def get_supported_banks(self):
        return ['建设银行']
    
    def extract_amount(self, full_text, bill_info):
        """提取建设银行金额 - 精确匹配本期全部应还款额"""
        
        # 模式1：精确匹配"应还款信息"表格中的New Balance（最准确）
        amount_match = re.search(
            r'应还款信息.*?Payment Information.*?'
            r'New Balance.*?</b></font>\s*</td>\s*<td[^>]*>.*?</td>\s*'
            r'<td bgcolor="#EAEAEA"><font size=\'3\'[^>]*><b>([0-9,]+\.[0-9]+)</b></font>',
            full_text,
            re.DOTALL | re.IGNORECASE
        )
        
        if amount_match:
            try:
                amount = float(amount_match.group(1).replace(',', ''))
                if 100 < amount < 100000:
                    bill_info['amounts'] = [{'value': amount, 'currency': 'CNY'}]
                    return
            except:
                pass
        
        # 模式2：查找带<b>标签的New Balance金额（备选）
        amount_matches = re.findall(
            r'New Balance.*?<b>([0-9,]+\.[0-9]+)</b>',
            full_text,
            re.DOTALL | re.IGNORECASE
        )
        
        for amount_str in amount_matches:
            try:
                amount = float(amount_str.replace(',', ''))
                if 100 < amount < 100000:
                    bill_info['amounts'] = [{'value': amount, 'currency': 'CNY'}]
                    return
            except:
                continue
        
        # 模式3：查找"本期全部应还款额"后面紧跟的<b>金额</b>（最后备选）
        amount_match = re.search(
            r'本期全部应还款额.*?<b>([0-9,]+\.[0-9]+)</b>',
            full_text,
            re.DOTALL
        )
        
        if amount_match:
            try:
                amount = float(amount_match.group(1).replace(',', ''))
                if 100 < amount < 100000:
                    bill_info['amounts'] = [{'value': amount, 'currency': 'CNY'}]
            except:
                pass
    
    def extract_due_date(self, full_text, bill_info):
        """提取建设银行还款日"""
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


class CommBankExtractor(BaseBankExtractor):
    """交通银行提取器"""
    
    def get_supported_banks(self):
        return ['交通银行']
    
    def extract_amount(self, full_text, bill_info):
        """提取交通银行金额"""
        # 特殊处理：直接读取 HTML 中的金额
        pos = full_text.find('本期应还款')
        if pos != -1:
            snippet = full_text[pos:pos+200]
            amount_match = re.search(r'￥([0-9,]+\.?[0-9]*)', snippet)
            if amount_match:
                amount_str = amount_match.group(1).replace(',', '')
                try:
                    amount = float(amount_str)
                    if 0 < amount < 1000000:
                        bill_info['amounts'] = [{'value': amount, 'currency': 'CNY'}]
                except:
                    pass
        
        # 如果没找到，尝试通用模式
        if not bill_info['amounts']:
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
                        if 0 < amount < 1000000:
                            if not any(a['value'] == amount for a in bill_info['amounts']):
                                bill_info['amounts'].append({'value': amount, 'currency': 'CNY'})
                    except:
                        continue
    
    def extract_due_date(self, full_text, bill_info):
        """提取交通银行还款日"""
        # 特殊处理交通银行的还款日格式
        due_match = re.search(
            r'Payment Due Date.*?<span[^>]*>([0-9]{4}-[0-9]{2}-[0-9]{2})',
            full_text,
            re.DOTALL
        )
        if due_match:
            if due_match.group(1) not in bill_info['due_dates']:
                bill_info['due_dates'].append(due_match.group(1))
        
        # 如果没找到，使用通用模式
        if not bill_info['due_dates']:
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


class SPDBankExtractor(BaseBankExtractor):
    """浦发银行提取器"""
    
    def get_supported_banks(self):
        return ['浦发银行']
    
    def extract_amount(self, full_text, bill_info):
        """提取浦发银行金额"""
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
                        if not any(a['value'] == amount for a in bill_info['amounts']):
                            bill_info['amounts'].append({'value': amount, 'currency': 'CNY'})
                except:
                    continue
    
    def extract_due_date(self, full_text, bill_info):
        """提取浦发银行还款日"""
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


class PSBCBankExtractor(BaseBankExtractor):
    """邮储银行提取器"""
    
    def get_supported_banks(self):
        return ['邮储银行']
    
    def extract_amount(self, full_text, bill_info):
        """提取邮储银行金额"""
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
                        bill_info['amounts'] = [{'value': amount, 'currency': 'CNY'}]
                        break
                except:
                    pass
    
    def extract_due_date(self, full_text, bill_info):
        """提取邮储银行还款日"""
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


class CMBCBankExtractor(BaseBankExtractor):
    """民生银行提取器"""
    
    def get_supported_banks(self):
        return ['民生银行']
    
    def extract_amount(self, full_text, bill_info):
        """提取民生银行金额 - 精确匹配RMB格式"""
        
        # 模式1：精确匹配 RMB 金额格式（最准确）
        amount_match = re.search(r'RMB\s*([0-9,]+\.[0-9]{2})', full_text)
        
        if amount_match:
            try:
                amount = float(amount_match.group(1).replace(',', ''))
                if 10 < amount < 100000:
                    bill_info['amounts'] = [{'value': amount, 'currency': 'CNY'}]
                    return
            except:
                pass
        
        # 模式2：查找"本期应还款"相关金额（备选）
        amount_patterns = [
            r'本期应还款.*?￥([0-9,]+\.?[0-9]*)',
            r'本期账单金额.*?([0-9,]+\.?[0-9]*)',
        ]
        
        for pattern in amount_patterns:
            matches = re.findall(pattern, full_text)
            if matches:
                try:
                    amount = float(matches[0].replace(',', ''))
                    if 10 < amount < 100000:
                        bill_info['amounts'] = [{'value': amount, 'currency': 'CNY'}]
                        return
                except:
                    continue
    
    def extract_due_date(self, full_text, bill_info):
        """提取民生银行还款日"""
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


class CIBBankExtractor(BaseBankExtractor):
    """兴业银行提取器"""

    def get_supported_banks(self):
        return ['兴业银行']

    def extract_amount(self, full_text, bill_info):
        soup = BeautifulSoup(full_text, 'html.parser')
        clean_text = soup.get_text()
        clean_text = ' '.join(clean_text.split())

        amount_match = re.search(r'本期应还款总额\s*New Balance\s*RMB\s*([\d,]+\.\d+)', clean_text)
        if amount_match:
            try:
                amount = float(amount_match.group(1).replace(',', ''))
                if 0 < amount < 1000000:
                    bill_info['amounts'] = [{'value': amount, 'currency': 'CNY'}]
                    return
            except:
                pass

        amount_match = re.search(r'本期账单金额\s*New Activity\s*([\d,]+\.\d+)', clean_text)
        if amount_match:
            try:
                amount = float(amount_match.group(1).replace(',', ''))
                if 0 < amount < 1000000:
                    bill_info['amounts'] = [{'value': amount, 'currency': 'CNY'}]
                    return
            except:
                pass

        amount_match = re.search(r'New Balance.*?RMB\s*([\d,]+\.\d+)', clean_text)
        if amount_match:
            try:
                amount = float(amount_match.group(1).replace(',', ''))
                if 0 < amount < 1000000:
                    bill_info['amounts'] = [{'value': amount, 'currency': 'CNY'}]
            except:
                pass

    def extract_due_date(self, full_text, bill_info):
        soup = BeautifulSoup(full_text, 'html.parser')
        clean_text = soup.get_text()
        clean_text = ' '.join(clean_text.split())

        due_match = re.search(r'到期还款日\s*Payment Due Date\s*(\d{4})年(\d{1,2})月(\d{1,2})日', clean_text)
        if due_match:
            date_str = f"{due_match.group(1)}-{due_match.group(2).zfill(2)}-{due_match.group(3).zfill(2)}"
            if date_str not in bill_info['due_dates']:
                bill_info['due_dates'].append(date_str)
            return

        due_match = re.search(r'Payment Due Date\s*(\d{4})年(\d{1,2})月(\d{1,2})日', clean_text)
        if due_match:
            date_str = f"{due_match.group(1)}-{due_match.group(2).zfill(2)}-{due_match.group(3).zfill(2)}"
            if date_str not in bill_info['due_dates']:
                bill_info['due_dates'].append(date_str)
            return

        due_patterns = [
            r'到期还款日.*?(\d{4})年(\d{1,2})月(\d{1,2})日',
            r'Payment Due Date.*?(\d{4})年(\d{1,2})月(\d{1,2})日',
        ]
        for pattern in due_patterns:
            matches = re.findall(pattern, clean_text)
            for match in matches:
                date_str = f"{match[0]}-{match[1].zfill(2)}-{match[2].zfill(2)}"
                try:
                    datetime.strptime(date_str, '%Y-%m-%d')
                    if date_str not in bill_info['due_dates']:
                        bill_info['due_dates'].append(date_str)
                except:
                    continue


class PingAnBankExtractor(BaseBankExtractor):
    """平安银行提取器"""
    
    def get_supported_banks(self):
        return ['平安银行']
    
    def extract_amount(self, full_text, bill_info):
        soup = BeautifulSoup(full_text, 'html.parser')
        clean_text = soup.get_text()
        clean_text = ' '.join(clean_text.split())
        
        amount_match = re.search(r'本期应还金额\s+[￥¥]\s*([\d,]+\.\d+)', clean_text)
        if amount_match:
            try:
                amount = float(amount_match.group(1).replace(',', ''))
                if 0 < amount < 1000000:
                    bill_info['amounts'] = [{'value': amount, 'currency': 'CNY'}]
                    return
            except:
                pass
        
        amount_match = re.search(r'本期应还金额.*?[￥¥]\s*([\d,]+\.\d+)', clean_text)
        if amount_match:
            try:
                amount = float(amount_match.group(1).replace(',', ''))
                if 0 < amount < 1000000:
                    bill_info['amounts'] = [{'value': amount, 'currency': 'CNY'}]
                    return
            except:
                pass
        
        amount_match = re.search(r'&yen;\s*([\d,]+\.\d+)', full_text)
        if amount_match:
            try:
                amount = float(amount_match.group(1).replace(',', ''))
                if 0 < amount < 1000000:
                    bill_info['amounts'] = [{'value': amount, 'currency': 'CNY'}]
            except:
                pass
    
    def extract_due_date(self, full_text, bill_info):
        soup = BeautifulSoup(full_text, 'html.parser')
        clean_text = soup.get_text()
        clean_text = ' '.join(clean_text.split())
        
        due_match = re.search(r'本期还款日\s+(\d{4}-\d{2}-\d{2})', clean_text)
        if due_match:
            date_str = due_match.group(1)
            if date_str not in bill_info['due_dates']:
                bill_info['due_dates'].append(date_str)
            return
        
        due_patterns = [
            r'还款日.*?(\d{4}[-/.]\d{1,2}[-/.]\d{1,2})',
            r'Payment Due Date.*?(\d{4}[-/.]\d{1,2}[-/.]\d{1,2})',
        ]
        for pattern in due_patterns:
            matches = re.findall(pattern, clean_text)
            for match in matches:
                date_str = match.replace('/', '-').replace('.', '-')
                try:
                    datetime.strptime(date_str, '%Y-%m-%d')
                    if date_str not in bill_info['due_dates']:
                        bill_info['due_dates'].append(date_str)
                except:
                    continue


class CEBBankExtractor(BaseBankExtractor):
    """光大银行提取器"""
    
    def get_supported_banks(self):
        return ['光大银行']
    
    def extract_amount(self, full_text, bill_info):
        soup = BeautifulSoup(full_text, 'html.parser')
        clean_text = soup.get_text()
        clean_text = ' '.join(clean_text.split())
        
        amount_match = re.search(r'人民币本期账单金额\s*RMB Statement Balance\s*人民币本期最低还款额.*?￥[\d,]+\.\d+\s*￥([\d,]+\.\d+)', clean_text)
        if amount_match:
            try:
                amount = float(amount_match.group(1).replace(',', ''))
                if 0 < amount < 1000000:
                    bill_info['amounts'] = [{'value': amount, 'currency': 'CNY'}]
                    return
            except:
                pass
        
        amount_match = re.search(r'人民币本期账单金额.*?￥[\d,]+\.\d+\s*￥([\d,]+\.\d+)', clean_text)
        if amount_match:
            try:
                amount = float(amount_match.group(1).replace(',', ''))
                if 0 < amount < 1000000:
                    bill_info['amounts'] = [{'value': amount, 'currency': 'CNY'}]
                    return
            except:
                pass
        
        amount_match = re.search(r'本期账单金额\s*Statement Balance\s*本期最低还款额.*?[\d,]+\.\d+\s*([\d,]+\.\d+)', clean_text)
        if amount_match:
            try:
                amount = float(amount_match.group(1).replace(',', ''))
                if 0 < amount < 1000000:
                    bill_info['amounts'] = [{'value': amount, 'currency': 'CNY'}]
                    return
            except:
                pass
        
        amount_match = re.search(r'本期欠款\s*Closing Balance[：:]\s*([\d,]+\.\d+)', clean_text)
        if amount_match:
            try:
                amount = float(amount_match.group(1).replace(',', ''))
                if 0 < amount < 1000000:
                    bill_info['amounts'] = [{'value': amount, 'currency': 'CNY'}]
            except:
                pass
    
    def extract_due_date(self, full_text, bill_info):
        soup = BeautifulSoup(full_text, 'html.parser')
        clean_text = soup.get_text()
        clean_text = ' '.join(clean_text.split())
        
        due_match = re.search(r'到期还款日\s*Payment Due Date\s*信用额度.*?(\d{4}/\d{2}/\d{2})\s+(\d{4}/\d{2}/\d{2})', clean_text)
        if due_match:
            date_str = due_match.group(2).replace('/', '-')
            try:
                datetime.strptime(date_str, '%Y-%m-%d')
                if date_str not in bill_info['due_dates']:
                    bill_info['due_dates'].append(date_str)
                return
            except:
                pass
        
        due_match = re.search(r'Payment Due Date.*?(\d{4}/\d{2}/\d{2})\s+(\d{4}/\d{2}/\d{2})', clean_text)
        if due_match:
            date_str = due_match.group(2).replace('/', '-')
            try:
                datetime.strptime(date_str, '%Y-%m-%d')
                if date_str not in bill_info['due_dates']:
                    bill_info['due_dates'].append(date_str)
                return
            except:
                pass
        
        due_patterns = [
            r'到期还款日.*?(\d{4}[-/.]\d{1,2}[-/.]\d{1,2})',
            r'Payment Due Date.*?(\d{4}[-/.]\d{1,2}[-/.]\d{1,2})',
        ]
        for pattern in due_patterns:
            matches = re.findall(pattern, clean_text)
            for match in matches:
                date_str = match.replace('/', '-').replace('.', '-')
                try:
                    datetime.strptime(date_str, '%Y-%m-%d')
                    if date_str not in bill_info['due_dates']:
                        bill_info['due_dates'].append(date_str)
                except:
                    continue


class ICBCBankExtractor(BaseBankExtractor):
    """工商银行（牡丹卡/ICBC Peony Card）提取器"""

    def get_supported_banks(self):
        return ['工商银行']

    def _clean_text(self, full_text):
        soup = BeautifulSoup(full_text, 'html.parser')
        clean_text = soup.get_text(separator=' ')
        clean_text = clean_text.replace('\xa0', ' ').replace('&nbsp;', ' ')
        clean_text = clean_text.replace('&yen;', '￥').replace('¥', '￥')
        return ' '.join(clean_text.split())

    def _parse_amount(self, amount_str):
        try:
            amount = float(amount_str.replace(',', '').replace(' ', ''))
            if 0 < amount < 1000000:
                return amount
        except Exception:
            pass
        return None

    def extract_amount(self, full_text, bill_info):
        """提取工商银行本期应还金额（兼容 RMB / ￥ / 纯数字格式）"""
        clean_text = self._clean_text(full_text)

        # 优先匹配「本期应还金额 / New Balance」——工行对账单核心字段
        amount_patterns = [
            # 本期应还金额 New Balance RMB 1,234.56
            r'本期应还金额\s*New Balance\s*(?:RMB|￥)?\s*([0-9,]+\.[0-9]{2})',
            # 本期应还金额：RMB 1,234.56 / ￥1,234.56
            r'本期应还金额[：:\s]*(?:RMB|￥)\s*([0-9,]+\.[0-9]{2})',
            # 本期应还款额 RMB 1,234.56
            r'本期应还款额[：:\s]*(?:RMB|￥)?\s*([0-9,]+\.[0-9]{2})',
            # New Balance: RMB 1,234.56
            r'New Balance[：:\s]*(?:RMB|￥)\s*([0-9,]+\.[0-9]{2})',
            # 人民币账户 ... 本期应还 ... 1,234.56（避免误抓最低还款额）
            r'人民币(?:账户)?[^0-9]{0,40}本期应还(?:金额|款项|款额)?[^0-9￥RMB]{0,20}(?:RMB|￥)?\s*([0-9,]+\.[0-9]{2})',
            # 账单应还金额 / 应还总额
            r'(?:账单应还金额|应还总额|应还款总额)[：:\s]*(?:RMB|￥)?\s*([0-9,]+\.[0-9]{2})',
            # HTML 残留：New Balance 后的数字
            r'New Balance[^0-9]{0,80}([0-9,]+\.[0-9]{2})',
            # 宽松：本期应还金额 后第一个金额
            r'本期应还金额[^0-9]{0,40}([0-9,]+\.[0-9]{2})',
        ]

        for pattern in amount_patterns:
            match = re.search(pattern, clean_text, re.IGNORECASE)
            if not match:
                match = re.search(pattern, full_text, re.IGNORECASE | re.DOTALL)
            if match:
                amount = self._parse_amount(match.group(1))
                if amount is not None:
                    bill_info['amounts'] = [{'value': amount, 'currency': 'CNY'}]
                    return

        # 表格类文本：标签序列后跟数值列
        # e.g. 本期应还金额 最低还款额 ... 1234.56 123.45
        table_match = re.search(
            r'本期应还金额\s*(?:New Balance\s*)?最低还款额.*?(?:RMB\s*)?([0-9,]+\.[0-9]{2})\s+(?:RMB\s*)?[0-9,]+\.[0-9]{2}',
            clean_text,
            re.IGNORECASE
        )
        if table_match:
            amount = self._parse_amount(table_match.group(1))
            if amount is not None:
                bill_info['amounts'] = [{'value': amount, 'currency': 'CNY'}]
                return

    def extract_due_date(self, full_text, bill_info):
        """提取工商银行到期还款日（避免误抓账单日 Statement Date）"""
        clean_text = self._clean_text(full_text)

        due_patterns = [
            # 到期还款日 Payment Due Date 2026/07/22
            r'到期还款日\s*Payment Due Date\s*(\d{4})[./-](\d{1,2})[./-](\d{1,2})',
            # Payment Due Date: 2026-07-22
            r'Payment Due Date[：:\s]*(\d{4})[./-](\d{1,2})[./-](\d{1,2})',
            # 到期还款日：2026年07月22日
            r'到期还款日[：:\s]*(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日?',
            # 到期还款日 2026/07/22
            r'到期还款日[：:\s]*(\d{4})[./-](\d{1,2})[./-](\d{1,2})',
            # 最后还款日
            r'最后还款日[：:\s]*(\d{4})[./-](\d{1,2})[./-](\d{1,2})',
            r'最后还款日[：:\s]*(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日?',
        ]

        for pattern in due_patterns:
            match = re.search(pattern, clean_text, re.IGNORECASE)
            if not match:
                match = re.search(pattern, full_text, re.IGNORECASE | re.DOTALL)
            if match:
                y, m, d = match.group(1), match.group(2).zfill(2), match.group(3).zfill(2)
                date_str = f"{y}-{m}-{d}"
                try:
                    datetime.strptime(date_str, '%Y-%m-%d')
                    if date_str not in bill_info['due_dates']:
                        bill_info['due_dates'].append(date_str)
                    return
                except Exception:
                    continue


class OtherBankExtractor(BaseBankExtractor):
    """其他银行提取器（通用实现）"""
    
    def __init__(self, bank_name):
        """
        初始化通用银行提取器
        
        Args:
            bank_name: 银行名称
        """
        self.bank_name = bank_name
    
    def get_supported_banks(self):
        return [self.bank_name]
    
    def extract_amount(self, full_text, bill_info):
        """提取金额（通用实现）"""
        amount_patterns = [
            r'本期应还款.*?￥([0-9,]+\.?[0-9]*)(?!.*最低)',
            r'Statement Balance.*?￥([0-9,]+\.?[0-9]*)',
            r'本期账单金额.*?￥([0-9,]+\.?[0-9]*)',
            # 兼容 RMB 前缀（部分银行含工行历史兜底）
            r'本期应还金额.*?RMB\s*([0-9,]+\.[0-9]{2})',
            r'New Balance.*?RMB\s*([0-9,]+\.[0-9]{2})',
        ]
        
        for pattern in amount_patterns:
            matches = re.findall(pattern, full_text, re.DOTALL | re.IGNORECASE)
            for match in matches:
                amount_str = match.replace(',', '')
                try:
                    amount = float(amount_str)
                    if 0 < amount < 1000000:
                        if not any(a['value'] == amount for a in bill_info['amounts']):
                            bill_info['amounts'].append({'value': amount, 'currency': 'CNY'})
                except:
                    continue
    
    def extract_due_date(self, full_text, bill_info):
        """提取还款日（通用实现）"""
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


class BankExtractorFactory:
    """银行提取器工厂"""
    
    def __init__(self):
        self.extractors = {}
        self._register_default_extractors()
    
    def _register_default_extractors(self):
        extractors = [
            GuangfaBankExtractor(),
            CMBBankExtractor(),
            CCBBankExtractor(),
            CommBankExtractor(),
            SPDBankExtractor(),
            PSBCBankExtractor(),
            CMBCBankExtractor(),
            CIBBankExtractor(),
            PingAnBankExtractor(),
            CEBBankExtractor(),
            ICBCBankExtractor(),
        ]
        
        for extractor in extractors:
            for bank in extractor.get_supported_banks():
                self.extractors[bank] = extractor
    
    def register_extractor(self, extractor):
        """
        注册新的银行提取器
        
        Args:
            extractor: 银行提取器实例
        """
        for bank in extractor.get_supported_banks():
            self.extractors[bank] = extractor
    
    def create_extractor(self, bank_name):
        """
        创建银行提取器
        
        Args:
            bank_name: 银行名称
            
        Returns:
            银行提取器实例
        """
        if bank_name in self.extractors:
            return self.extractors[bank_name]
        else:
            return OtherBankExtractor(bank_name)
