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
        """广发银行不替换 &yen;"""
        return full_text.replace('&amp;', '&')
    
    def extract_amount(self, full_text, bill_info):
        """提取广发银行金额"""
        amount_match = re.search(r'&yen;[^>]*>[^>]*>([\d,]+\.?\d*)', full_text)
        if amount_match:
            try:
                amount = float(amount_match.group(1).replace(',', ''))
                if 0 < amount < 1000000:
                    bill_info['amounts'] = [{'value': amount, 'currency': 'CNY'}]
            except:
                pass
        
        if not bill_info['amounts']:
            amount_matches = re.findall(r'>([\d,]+\.\d{2})<', full_text)
            for amt_str in amount_matches:
                try:
                    amount = float(amt_str.replace(',', ''))
                    if 1000 < amount < 100000:
                        bill_info['amounts'] = [{'value': amount, 'currency': 'CNY'}]
                        break
                except:
                    continue
    
    def extract_due_date(self, full_text, bill_info):
        """提取广发银行还款日"""
        due_patterns = [r'([0-9]{4}/[0-9]{2}/[0-9]{2})']
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
        """注册默认的银行提取器"""
        extractors = [
            GuangfaBankExtractor(),
            CMBBankExtractor(),
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
