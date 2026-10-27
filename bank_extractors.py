#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
银行账单提取器模块
包含银行提取器基类和具体银行实现
"""

import json
import re
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from email.utils import parsedate_tz
from pathlib import Path

from bs4 import BeautifulSoup

# 用户已确认的真实小额账单清单（P0-2 静默白名单，2026-10-27 新增）。
# 四元组：银行 + 邮箱标签 + 金额 + 还款日。命中清单的账单不再标「疑似误提取」。
# 文件由用户人工维护（初始 4 笔经用户 2026-10-27 逐笔确认写入）；
# 缺失/损坏时静默降级为空清单，闸门照常工作。
CONFIRMED_AMOUNTS_FILE = Path(__file__).resolve().parent / "ticktick_confirmed_amounts.json"
_CONFIRMED_CACHE = {"mtime": None, "items": []}


def _norm_date_key(value):
    """日期键归一化：统一 / 为 -，去空白（清单与缓存格式可能不同）。"""
    return str(value or "").replace("/", "-").strip()


def load_confirmed_amounts(force=False):
    """读取已确认小额账单清单，带 mtime 缓存；返回 list[dict]。"""
    try:
        mtime = CONFIRMED_AMOUNTS_FILE.stat().st_mtime
    except OSError:
        _CONFIRMED_CACHE.update(mtime=None, items=[])
        return []
    if not force and _CONFIRMED_CACHE["mtime"] == mtime:
        return _CONFIRMED_CACHE["items"]
    items = []
    try:
        data = json.loads(CONFIRMED_AMOUNTS_FILE.read_text(encoding="utf-8"))
        for row in data.get("confirmed", []):
            try:
                items.append({
                    "bank": str(row.get("bank", "")).strip(),
                    "label": str(row.get("label") or "").strip(),
                    "amount": round(float(row.get("amount", 0)), 2),
                    "due_date": _norm_date_key(row.get("due_date")),
                })
            except Exception:
                continue
    except Exception:
        items = []
    _CONFIRMED_CACHE.update(mtime=mtime, items=items)
    return items


def is_confirmed_amount(bank, label, amount, due_date):
    """四元组精确匹配（金额按分取整、日期归一化 / 与 -）。"""
    try:
        amt = round(float(amount), 2)
    except Exception:
        return False
    key = {
        "bank": str(bank or "").strip(),
        "label": str(label or "").strip(),
        "amount": amt,
        "due_date": _norm_date_key(due_date),
    }
    return key in load_confirmed_amounts()


class BaseBankExtractor(ABC):
    """银行提取器基类"""

    # 合理性闸门阈值：额度已知且 0 < 金额 < 额度×该比例 → 标 suspicious（P0-2）
    SUSPICIOUS_RATIO = 0.01
    # 还款日合理性窗口（相对邮件日期）：滤除上周期残值/远期噪声
    DUE_WINDOW_PAST_DAYS = 40
    DUE_WINDOW_FUTURE_DAYS = 60
    
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

    def _clean_for_limit(self, full_text):
        soup = BeautifulSoup(full_text, 'html.parser')
        text = soup.get_text(separator=' ')
        text = text.replace('\xa0', ' ').replace('&nbsp;', ' ')
        text = text.replace('&yen;', '￥').replace('¥', '￥')
        return ' '.join(text.split())

    @staticmethod
    def _norm_date_str(date_str):
        """归一化日期字符串为 ISO `YYYY-MM-DD`。

        兼容 `2026/10/22`、`2026.10.22`、`2026年10月22日` 等写法；
        无法解析时返回 None。所有 extractor 追加还款日前统一走此归一化
        （修复浦发 `2026/10/22` 斜杠脏数据，P0 数据卫生）。
        """
        if not date_str:
            return None
        s = str(date_str).strip()
        s = s.replace('年', '-').replace('月', '-').replace('日', '')
        s = s.replace('/', '-').replace('.', '-')
        s = re.sub(r'\s+', '', s)
        parts = s.split('-')
        if len(parts) != 3:
            return None
        try:
            y, m, d = int(parts[0]), int(parts[1]), int(parts[2])
            datetime(y, m, d)
            return f"{y:04d}-{m:02d}-{d:02d}"
        except Exception:
            return None

    def _append_due_date(self, bill_info, date_str):
        """归一化后追加还款日（去重 + 格式校验），返回归一化值或 None。"""
        norm = self._norm_date_str(date_str)
        if not norm:
            return None
        if norm not in bill_info['due_dates']:
            bill_info['due_dates'].append(norm)
        return norm

    @staticmethod
    def _email_date(bill_info):
        """从 bill_info['date']（邮件 Date 头）解析日期，失败返回 None。"""
        raw = bill_info.get('date') or ''
        try:
            t = parsedate_tz(raw)
            if t:
                return datetime(*t[:3]).date()
        except Exception:
            pass
        return None

    def _search_anchored_due_date(self, patterns, full_text, clean_text):
        """锚定还款日模式的两段式匹配（基类公共逻辑）。

        1. 先在扁平化文本上匹配（锚点间只剩空格，`.{0,80}?` 紧界限足够）；
        2. 未命中再回退原始 HTML（锚点间夹标签，放宽到 `.{0,300}?`）。
        返回归一化日期或 None。间隔一律有界，避免无界 `.*?` 跨全文误取。
        """
        for regex in patterns:
            m = re.search(regex, clean_text, re.IGNORECASE)
            if m:
                return self._norm_date_str(m.group(1))
        for regex in patterns:
            wide = regex.replace('.{0,80}?', '.{0,300}?')
            m = re.search(wide, full_text, re.DOTALL | re.IGNORECASE)
            if m:
                return self._norm_date_str(m.group(1))
        return None

    def check_reasonableness(self, bill_info):
        """提取层合理性闸门（P0-2，先只告警不拦截）。

        额度已知且 0 < 金额 < 额度×1% → 标 `suspicious: true` 并记录原因
        （典型场景：把交易明细里的手续费/利息当成本期应还）。
        0.00（本期无需还款）与未知额度的情况不标记。

        原因文案分层（2026-10-25 告警复盘）：金额条目带 `match` 字段
        （提取自摘要区锚点/表行，如「本期应还款总额 New Balance」）时，
        值为银行公告的真实应还款额、大概率是真实小额账单，文案给
        「请人工核对」；无 `match`（兜底模式抓到的）才说「疑似误提取」，
        提醒优先人工复核。历史误提取（明细区 ¥1.00 手续费）均来自
        兜底路径，锚点路径至今零误判。
        """
        limit = bill_info.get('credit_limit')
        if not limit:
            return
        try:
            limit = float(limit)
        except Exception:
            return
        if limit <= 0:
            return
        for amount_info in bill_info.get('amounts', []):
            value = amount_info.get('value', 0) or 0
            if 0 < value < limit * self.SUSPICIOUS_RATIO:
                if is_confirmed_amount(bill_info.get('bank_name', ''),
                                       bill_info.get('source_label', ''),
                                       value,
                                       (bill_info.get('due_dates') or [''])[0]):
                    # 用户已逐笔确认为真实账单（ticktick_confirmed_amounts.json），
                    # 不再标「疑似误提取」——2026-10-27 用户明确要求：
                    # 提取正确且经确认的账单不得反复告警
                    continue
                bill_info['suspicious'] = True
                match_src = amount_info.get('match')
                if match_src:
                    bill_info['suspicious_reason'] = (
                        f"金额 ¥{value:,.2f} 低于信用额度 ¥{limit:,.0f} 的 1%，"
                        f"提取自摘要区「{match_src}」，请人工核对是否真实小额账单"
                    )
                else:
                    bill_info['suspicious_reason'] = (
                        f"金额 ¥{value:,.2f} 低于信用额度 ¥{limit:,.0f} 的 1%，"
                        f"疑似误提取，请人工核对"
                    )
                return

    @staticmethod
    def _parse_money_token(token):
        """解析金额字符串；过滤电话号等伪额度。"""
        if token is None:
            return None
        s = str(token).replace(',', '').replace(' ', '').replace('￥', '').replace('¥', '')
        try:
            val = float(s)
        except Exception:
            return None
        # 信用额度合理区间：通常 1000 ~ 500 万
        if 1000 <= val <= 5_000_000:
            return val
        return None

    def extract_credit_limit(self, full_text, bill_info):
        """
        提取信用/消费额度（通用实现，子类可覆盖）。
        写入 bill_info['credit_limit']（float）。
        """
        if bill_info.get('credit_limit'):
            return
        clean = self._clean_for_limit(full_text)
        patterns = [
            # 广发：个人消费额度:50,000.00（优先，勿把卡号末四位当额度）
            r'个人消费额度\s*[：:]\s*([0-9,]+(?:\.[0-9]+)?)',
            # 工商：应还款额 最低还款额 信用额度 ... 80,000.00/RMB（第三列）
            r'应还款额\s*最低还款额\s*信用额度.*?/RMB\s*[0-9,]+\.[0-9]{2}\s*/RMB\s*([0-9,]+\.[0-9]{2})\s*/RMB',
            r'人民币(?:\(本位币\))?\s*[0-9,]+\.[0-9]{2}\s*/\s*RMB\s*[0-9,]+\.[0-9]{2}\s*/\s*RMB\s*([0-9,]+\.[0-9]{2})\s*/\s*RMB',
            r'授信额度\s*Credit Limit\s*(?:CNY|￥|¥)?\s*([0-9,]+(?:\.[0-9]+)?)',
            r'信用额度\s*Credit Limit\s*[￥¥]?\s*([0-9,]+(?:\.[0-9]+)?)',
            r'信用额度\s*[：:￥¥]?\s*([0-9,]+(?:\.[0-9]+)?)',
            # 卡片消费额度后若为 4 位整数多半是卡号列，要求带小数
            r'卡片消费额度\s*[：:￥¥]?\s*([0-9,]+\.[0-9]{2})',
            r'固定额度\s*[：:￥¥]?\s*([0-9,]+(?:\.[0-9]+)?)',
            r'信用额度\s*([0-9,]+\.[0-9]{2})',  # 邮储：信用额度 50000.00
            r'Credit Limit\s*(?:CNY|￥|¥)?\s*([0-9,]+(?:\.[0-9]+)?)',
            r'个人总授信额度[^\d]{0,40}[￥¥]?\s*([0-9,]+(?:\.[0-9]+)?)',
        ]
        # 尝试提取卡号末四位，避免误判为额度
        last4s = set(re.findall(r'(?:卡号)?末四位\s*(\d{4})', clean))
        last4s.update(re.findall(r'尾号\s*[为是]?\s*(\d{4})', clean))
        for pat in patterns:
            m = re.search(pat, clean, re.IGNORECASE)
            if not m:
                continue
            raw = m.group(1).replace(',', '').replace(' ', '')
            # 纯 4 位整数且等于末四位 → 跳过
            if re.fullmatch(r'\d{4}', raw) and raw in last4s:
                continue
            if re.fullmatch(r'\d{4}', raw) and float(raw) < 10000:
                # 广发表头「卡片消费额度 8948」是卡号，不是额度
                continue
            val = self._parse_money_token(m.group(1))
            if val is not None:
                bill_info['credit_limit'] = val
                # 同时记下末四位供展示
                if last4s and not bill_info.get('last4'):
                    bill_info['last4'] = next(iter(last4s))
                return
        if last4s and not bill_info.get('last4'):
            bill_info['last4'] = next(iter(last4s))

    def extract_statement_date(self, full_text, bill_info):
        """
        提取账单日/出账日（通用实现）。
        写入 bill_info['statement_dates'] 列表（YYYY-MM-DD）。
        """
        if 'statement_dates' not in bill_info:
            bill_info['statement_dates'] = []
        clean = self._clean_for_limit(full_text)

        def _norm(date_str):
            s = date_str.replace('年', '-').replace('月', '-').replace('日', '')
            s = s.replace('/', '-').replace('.', '-')
            parts = [p for p in s.split('-') if p]
            if len(parts) != 3:
                return None
            try:
                y, m, d = int(parts[0]), int(parts[1]), int(parts[2])
                dt = datetime(y, m, d)
                return dt.strftime('%Y-%m-%d')
            except Exception:
                return None

        patterns = [
            # 邮储：账单周期为【2026/02/07-2026/03/06】→ 取周期末日作为账单日
            r'账单周期为【\d{4}[-/.]\d{1,2}[-/.]\d{1,2}-(\d{4}[-/.]\d{1,2}[-/.]\d{1,2})】',
            r'账单日\s*Statement Date[^0-9]{0,20}(\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日)',
            r'账单日\s*Statement Date[^0-9]{0,20}(\d{4}[-/.]\d{1,2}[-/.]\d{1,2})',
            r'账单日[：:\s]*(\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日)',
            r'账单日[：:\s]*(\d{4}[-/.]\d{1,2}[-/.]\d{1,2})',
            r'账单日\s*(\d{1,2})\s*本期',  # 邮储：账单日 06 本期
            r'出账日[：:\s]*(\d{4}[-/.]\d{1,2}[-/.]\d{1,2})',
            r'Statement Date[：:\s]*(\d{4}[-/.]\d{1,2}[-/.]\d{1,2})',
            r'账单周期\s*Statement Cycle\s*(\d{4}[-/.]\d{1,2}[-/.]\d{1,2})',
            r'Statement Cycle\s*(\d{4}[-/.]\d{1,2}[-/.]\d{1,2})',
            r'结账日[：:\s]*(\d{4}[-/.]\d{1,2}[-/.]\d{1,2})',
        ]
        for pat in patterns:
            for m in re.finditer(pat, clean, re.IGNORECASE):
                g = m.group(1).strip()
                # 仅日数字（邮储账单日06）
                if re.fullmatch(r'\d{1,2}', g):
                    # 结合邮件 Date 或 due_dates 推断年月，先存 day_only
                    day = int(g)
                    if 1 <= day <= 31:
                        bill_info['statement_day'] = day
                    continue
                norm = _norm(g)
                if norm and norm not in bill_info['statement_dates']:
                    bill_info['statement_dates'].append(norm)


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
                    bill_info['amounts'] = [{
                        'value': amount, 'currency': 'CNY',
                        'match': '本期账单金额表行',
                    }]
                    return
            except:
                pass
        
        amount_match = re.search(r'本期账单金额\s+最低还款额.*?\d{4}\s+([\d,]+\.\d{2})', clean_text)
        if amount_match:
            try:
                amount = float(amount_match.group(1).replace(',', ''))
                if 0 < amount < 1000000:
                    bill_info['amounts'] = [{
                        'value': amount, 'currency': 'CNY',
                        'match': '本期账单金额表行',
                    }]
                    return
            except:
                pass
        
        amount_match = re.search(r'&yen;[^>]*>[^>]*>([\d,]+\.?\d*)', full_text)
        if amount_match:
            try:
                amount = float(amount_match.group(1).replace(',', ''))
                if 0 < amount < 1000000:
                    bill_info['amounts'] = [{
                        'value': amount, 'currency': 'CNY',
                        'match': '￥金额标签（兜底匹配）',
                    }]
                    return
            except:
                pass
    
    def extract_due_date(self, full_text, bill_info):
        soup = BeautifulSoup(full_text, 'html.parser')
        clean_text = soup.get_text()
        clean_text = ' '.join(clean_text.split())
        
        due_match = re.search(r'最后还款日\s+入账货币\s+存款\s+卡片消费额度\s+\d+\s+[\d,]+\.\d+\s+[\d,]+\.\d+\s+(\d{4}/\d{2}/\d{2})', clean_text)
        if due_match:
            if self._append_due_date(bill_info, due_match.group(1)):
                return
        
        due_match = re.search(r'最后还款日.*?(\d{4}/\d{2}/\d{2})', clean_text)
        if due_match:
            if self._append_due_date(bill_info, due_match.group(1)):
                return
        
        due_patterns = [r'最后还款日.*?(\d{4}/\d{2}/\d{2})']
        for pattern in due_patterns:
            matches = re.findall(pattern, full_text)
            for match in matches:
                self._append_due_date(bill_info, match)

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
                    self._append_due_date(bill_info, due_dates[0])


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

        # 模式4：文本兜底（P0-1：YY/QQ 邮箱版式与阿里云不同，上述 HTML 正则
        # 全落空；对齐 ICBC 的 soup.get_text() 兜底策略）。
        # 锚定摘要表「争议款/笔数 Dispute Amt/Nbr」后的人民币行首值
        # = 本期全部应还款额；"-" 表示本期应还为 0（上期已全额还清，
        # 2026-10 样本实证：非提取失败，确实无需还款）。
        if bill_info['amounts']:
            return
        soup = BeautifulSoup(full_text, 'html.parser')
        clean_text = ' '.join(soup.get_text().split())
        amount_match = re.search(
            r'争议款/笔数\s*Dispute Amt/Nbr\s*人民币（CNY）\s*(-|[0-9,]+\.[0-9]{2})',
            clean_text,
            re.IGNORECASE
        )
        if amount_match:
            token = amount_match.group(1)
            try:
                amount = 0.0 if token == '-' else float(token.replace(',', ''))
                bill_info['amounts'] = [{'value': amount, 'currency': 'CNY'}]
            except:
                pass
    
    def extract_due_date(self, full_text, bill_info):
        """提取建设银行还款日

        优先锚定「本期到期还款日 Payment Due Date」（当前周期还款日）；
        回退通用模式时用邮件日 ±窗口滤除上周期残值（如明细表里的
        2026-08-29），并取窗口内最晚日期（当前周期还款日最晚出现）。
        """
        # 1) 锚定模式：当前周期还款日（阿里云与 YY 模板均适用）。
        # 先扁平化文本、再原始 HTML（基类 _search_anchored_due_date 处理）。
        clean_text = ' '.join(BeautifulSoup(full_text, 'html.parser').get_text().split())
        anchored_patterns = [
            r'本期到期还款日.{0,80}?Payment Due Date.{0,80}?(\d{4}[-/.]\d{1,2}[-/.]\d{1,2})',
            r'本期到期还款日.{0,80}?(\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日)',
            r'Payment Due Date.{0,80}?(\d{4}[-/.]\d{1,2}[-/.]\d{1,2})',
            r'Payment Due Date.{0,80}?(\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日)',
        ]
        anchored = self._search_anchored_due_date(anchored_patterns, full_text, clean_text)
        if anchored and self._append_due_date(bill_info, anchored):
            return

        # 2) 回退：通用模式 + 邮件日窗口滤残值
        due_patterns = [
            r'到期还款日.*?([0-9]{4}[-/.][0-9]{1,2}[-/.][0-9]{1,2})',
            r'还款日.*?([0-9]{4}[-/.][0-9]{1,2}[-/.][0-9]{1,2})',
            r'Payment Due Date.*?([0-9]{4}[-/.][0-9]{1,2}[-/.][0-9]{1,2})',
        ]
        candidates = []
        for pattern in due_patterns:
            for match in re.findall(pattern, full_text, re.DOTALL):
                norm = self._norm_date_str(match)
                if norm and norm not in candidates:
                    candidates.append(norm)
        if not candidates:
            return
        # 窗口滤除：只接受 [邮件日-40天, 邮件日+60天]（P0 数据卫生）
        email_date = self._email_date(bill_info)
        if email_date:
            lo = email_date - timedelta(days=self.DUE_WINDOW_PAST_DAYS)
            hi = email_date + timedelta(days=self.DUE_WINDOW_FUTURE_DAYS)
            windowed = []
            for c in candidates:
                try:
                    d = datetime.strptime(c, '%Y-%m-%d').date()
                except Exception:
                    continue
                if lo <= d <= hi:
                    windowed.append(c)
            candidates = windowed
        if candidates:
            # 当前周期还款日为窗口内最晚日期
            self._append_due_date(bill_info, max(candidates))


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
            self._append_due_date(bill_info, due_match.group(1))
        
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
                    
                    self._append_due_date(bill_info, date_str)


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
        """提取浦发银行还款日（归一化为 ISO，修复 2026/10/22 斜杠脏数据）"""
        due_patterns = [
            r'到期还款日.*?([0-9]{4}[-/.][0-9]{1,2}[-/.][0-9]{1,2})',
            r'还款日.*?([0-9]{4}[-/.][0-9]{1,2}[-/.][0-9]{1,2})',
            r'Payment Due Date.*?([0-9]{4}[-/.][0-9]{1,2}[-/.][0-9]{1,2})',
        ]
        
        for pattern in due_patterns:
            matches = re.findall(pattern, full_text, re.DOTALL)
            for match in matches:
                self._append_due_date(bill_info, match)


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
        """提取邮储银行还款日

        兼容两种版式：`2026年11月05日`（无空格，2026-10 实证）与
        `2026年 11月 05日`（带空格，旧模板）；斜杠日期走 Payment Due Date
        锚点。先在扁平化文本上锚定（间隔有界），再回退原始 HTML。
        """
        soup = BeautifulSoup(full_text, 'html.parser')
        clean_text = ' '.join(soup.get_text().split())

        # 主模式：到期还款日 + 中文日期（无空格/带空格均可）
        zh_date = r'(\d{4}年\s*\d{1,2}月\s*\d{1,2}日)'
        for regex in (
            r'到期还款日.{0,30}?' + zh_date,
            r'还款日.{0,30}?' + zh_date,
        ):
            m = re.search(regex, clean_text)
            if m and self._append_due_date(bill_info, m.group(1)):
                return
            m = re.search(regex.replace('.{0,30}?', '.{0,300}?'), full_text, re.DOTALL)
            if m and self._append_due_date(bill_info, m.group(1)):
                return

        # 备选：Payment Due Date + 斜杠/点分日期（旧版式）
        for regex in (
            r'Payment Due Date.{0,300}?(\d{4}[-/.]\d{1,2}[-/.]\d{1,2})',
            r'到期还款日.{0,300}?(\d{4}[-/.]\d{1,2}[-/.]\d{1,2})',
        ):
            m = re.search(regex, clean_text)
            if not m:
                m = re.search(regex, full_text, re.DOTALL)
            if m and self._append_due_date(bill_info, m.group(1)):
                return

        # 最后回退：通用还款日 + 窗口滤残值，取窗口内最晚日期
        candidates = []
        for regex in (
            r'还款日.{0,300}?(\d{4}[-/.][0-9]{1,2}[-/.][0-9]{1,2})',
            r'Payment Due Date.{0,300}?(\d{4}[-/.][0-9]{1,2}[-/.][0-9]{1,2})',
        ):
            for m in re.finditer(regex, full_text, re.DOTALL):
                norm = self._norm_date_str(m.group(1))
                if norm and norm not in candidates:
                    candidates.append(norm)
        if not candidates:
            return
        email_date = self._email_date(bill_info)
        if email_date:
            lo = email_date - timedelta(days=self.DUE_WINDOW_PAST_DAYS)
            hi = email_date + timedelta(days=self.DUE_WINDOW_FUTURE_DAYS)
            windowed = []
            for c in candidates:
                try:
                    d = datetime.strptime(c, '%Y-%m-%d').date()
                except Exception:
                    continue
                if lo <= d <= hi:
                    windowed.append(c)
            candidates = windowed
        if candidates:
            self._append_due_date(bill_info, max(candidates))


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
                
                self._append_due_date(bill_info, date_str)


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
                    bill_info['amounts'] = [{
                        'value': amount, 'currency': 'CNY',
                        'match': '本期应还款总额 New Balance',
                    }]
                    return
            except:
                pass

        amount_match = re.search(r'本期账单金额\s*New Activity\s*([\d,]+\.\d+)', clean_text)
        if amount_match:
            try:
                amount = float(amount_match.group(1).replace(',', ''))
                if 0 < amount < 1000000:
                    bill_info['amounts'] = [{
                        'value': amount, 'currency': 'CNY',
                        'match': '本期账单金额 New Activity',
                    }]
                    return
            except:
                pass

        # 模式3：New Balance 后 200 字符内的 RMB 金额。
        # P0-2：原为无界 `.*?` 跨整个扁平化文本，会把交易明细/费用区里的
        # 第一笔 RMB 金额（如 ¥1.00 手续费/利息）当成本期应还；
        # 加边界约束后只在摘要区附近取值。
        amount_match = re.search(r'New Balance.{0,200}?RMB\s*([\d,]+\.\d+)', clean_text)
        if amount_match:
            try:
                amount = float(amount_match.group(1).replace(',', ''))
                if 0 < amount < 1000000:
                    bill_info['amounts'] = [{
                        'value': amount, 'currency': 'CNY',
                        'match': 'New Balance 附近 RMB（兜底匹配）',
                    }]
            except:
                pass

    def extract_due_date(self, full_text, bill_info):
        soup = BeautifulSoup(full_text, 'html.parser')
        clean_text = soup.get_text()
        clean_text = ' '.join(clean_text.split())

        due_match = re.search(r'到期还款日\s*Payment Due Date\s*(\d{4})年(\d{1,2})月(\d{1,2})日', clean_text)
        if due_match:
            date_str = f"{due_match.group(1)}-{due_match.group(2).zfill(2)}-{due_match.group(3).zfill(2)}"
            if self._append_due_date(bill_info, date_str):
                return

        due_match = re.search(r'Payment Due Date\s*(\d{4})年(\d{1,2})月(\d{1,2})日', clean_text)
        if due_match:
            date_str = f"{due_match.group(1)}-{due_match.group(2).zfill(2)}-{due_match.group(3).zfill(2)}"
            if self._append_due_date(bill_info, date_str):
                return

        due_patterns = [
            r'到期还款日.*?(\d{4})年(\d{1,2})月(\d{1,2})日',
            r'Payment Due Date.*?(\d{4})年(\d{1,2})月(\d{1,2})日',
        ]
        for pattern in due_patterns:
            matches = re.findall(pattern, clean_text)
            for match in matches:
                date_str = f"{match[0]}-{match[1].zfill(2)}-{match[2].zfill(2)}"
                self._append_due_date(bill_info, date_str)


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
            if self._append_due_date(bill_info, due_match.group(1)):
                return
        
        due_patterns = [
            r'还款日.*?(\d{4}[-/.]\d{1,2}[-/.]\d{1,2})',
            r'Payment Due Date.*?(\d{4}[-/.]\d{1,2}[-/.]\d{1,2})',
        ]
        for pattern in due_patterns:
            matches = re.findall(pattern, clean_text)
            for match in matches:
                date_str = match.replace('/', '-').replace('.', '-')
                self._append_due_date(bill_info, date_str)


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
            if self._append_due_date(bill_info, due_match.group(2)):
                return
        
        due_match = re.search(r'Payment Due Date.*?(\d{4}/\d{2}/\d{2})\s+(\d{4}/\d{2}/\d{2})', clean_text)
        if due_match:
            if self._append_due_date(bill_info, due_match.group(2)):
                return
        
        due_patterns = [
            r'到期还款日.*?(\d{4}[-/.]\d{1,2}[-/.]\d{1,2})',
            r'Payment Due Date.*?(\d{4}[-/.]\d{1,2}[-/.]\d{1,2})',
        ]
        for pattern in due_patterns:
            matches = re.findall(pattern, clean_text)
            for match in matches:
                date_str = match.replace('/', '-').replace('.', '-')
                self._append_due_date(bill_info, date_str)


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
        """提取工商银行本期应还金额。

        真实牡丹卡邮件格式（2026 实测）：
          应还款额 最低还款额 信用额度
          人民币(本位币) 22,212.13/RMB 2,221.21/RMB 80,000.00/RMB
          合计 人民币(本位币) 22,212.13/RMB 2,221.21/RMB
        金额在 /RMB 之前，且不能误抓最低还款额 2,221.21。
        """
        clean_text = self._clean_text(full_text)

        amount_patterns = [
            # ★ 真实邮件：合计行应还款额（优先，避免卡号明细重复）
            r'合计\s*人民币(?:\(本位币\))?[^0-9\-]{0,30}([0-9,]+\.[0-9]{2})\s*/\s*RMB',
            # ★ 真实邮件：应还款额列 + 最低还款额列（取第一列）
            r'应还款额\s*最低还款额.*?人民币(?:\(本位币\))?[^0-9\-]{0,30}([0-9,]+\.[0-9]{2})\s*/\s*RMB\s*[0-9,]+\.[0-9]{2}\s*/\s*RMB',
            # HTML 单元格：>22,212.13/RMB< 出现在应还款额列
            r'应还款额[^0-9]{0,400}?([0-9,]+\.[0-9]{2})\s*/\s*RMB',
            # 牡丹贷记卡行：卡描述后第一个金额即应还
            r'牡丹贷记卡\)[^0-9]{0,40}人民币(?:\(本位币\))?[^0-9\-]{0,20}([0-9,]+\.[0-9]{2})\s*/\s*RMB',
            # 通用：金额/RMB 紧跟最低还款额
            r'([0-9,]+\.[0-9]{2})\s*/\s*RMB\s*[0-9,]+\.[0-9]{2}\s*/\s*RMB\s*[0-9,]+\.[0-9]{2}\s*/\s*RMB',
            # 旧模板：本期应还金额 New Balance RMB 1,234.56
            r'本期应还金额\s*New Balance\s*(?:RMB|￥)?\s*([0-9,]+\.[0-9]{2})',
            r'本期应还金额[：:\s]*(?:RMB|￥)\s*([0-9,]+\.[0-9]{2})',
            r'本期应还(?:金额|款额|款项)[：:\s]*(?:RMB|￥)?\s*([0-9,]+\.[0-9]{2})',
            r'New Balance[：:\s]*(?:RMB|￥)\s*([0-9,]+\.[0-9]{2})',
            r'(?:账单应还金额|应还总额|应还款总额)[：:\s]*(?:RMB|￥)?\s*([0-9,]+\.[0-9]{2})',
            r'New Balance[^0-9]{0,80}([0-9,]+\.[0-9]{2})',
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
        table_match = re.search(
            r'(?:本期应还金额|应还款额)\s*(?:New Balance\s*)?最低还款额.*?(?:RMB\s*)?([0-9,]+\.[0-9]{2})\s*(?:/\s*RMB)?\s+(?:RMB\s*)?[0-9,]+\.[0-9]{2}',
            clean_text,
            re.IGNORECASE
        )
        if table_match:
            amount = self._parse_amount(table_match.group(1))
            if amount is not None:
                bill_info['amounts'] = [{'value': amount, 'currency': 'CNY'}]
                return

    def extract_due_date(self, full_text, bill_info):
        """提取工商银行到期还款日（避免误抓账单日 / 交易日）"""
        clean_text = self._clean_text(full_text)

        due_patterns = [
            # ★ 真实邮件：贷记卡到期还款日 …… 2026年7月19日
            r'贷记卡到期还款日[^0-9]{0,80}(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日?',
            # 到期还款日 Payment Due Date 2026/07/22
            r'到期还款日\s*Payment Due Date\s*(\d{4})[./-](\d{1,2})[./-](\d{1,2})',
            # Payment Due Date: 2026-07-22
            r'Payment Due Date[：:\s]*(\d{4})[./-](\d{1,2})[./-](\d{1,2})',
            # 到期还款日：2026年07月22日（含「贷记卡到期还款日」子串）
            r'到期还款日[：:\s]*(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日?',
            # 到期还款日 后最多 80 字符内出现中文日期（HTML 表格拉开距离）
            r'到期还款日[^0-9]{0,80}(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日?',
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
                if self._append_due_date(bill_info, date_str):
                    return


class ChangAnBankExtractor(BaseBankExtractor):
    """长安银行提取器

    长安银行账单 HTML 特点（2026-10 样本实证）：
    - 摘要区：本期应还款金额(元) Current Balance 0.00
    - 到期还款日 Payment Due Date 2026/07/15
    - Current Balance 为 0.00 是合法结果：表示上期已全额还清、本期无需还款
      （明细表里的 Opening/Payment 列如 9,104.00 是上期流水，不是本期应还）。
      旧实现用 `0 < amount` 把 0.00 当提取失败，实际是误判。
    - Current Balance 为负数时，按邮件自身说明（账户有存款、不需另行还款）记 0.00。
    """

    def get_supported_banks(self):
        return ['长安银行']

    def preprocess_text(self, full_text):
        return full_text.replace('&amp;', '&').replace('&nbsp;', ' ')

    def extract_amount(self, full_text, bill_info):
        """提取金额：摘要区「本期应还款金额(元) Current Balance X」。

        取摘要区第一个值（当前余额）；0.00 = 本期无需还款（下游聚合与
        滴答同步会过滤总额为 0 的账单，不会生成还款任务）。
        """
        soup = BeautifulSoup(full_text, 'html.parser')
        clean_text = ' '.join(soup.get_text().split())

        # 主模式：摘要区 本期应还款金额(元) Current Balance X
        m = re.search(
            r'本期应还款金额\s*\(元\)?\s*Current Balance\s*(-?[0-9,]+\.[0-9]{2})',
            clean_text,
            re.IGNORECASE
        )
        if m:
            amount = float(m.group(1).replace(',', ''))
            if amount < 0:
                amount = 0.0  # 存款余额：邮件明示不需另行还款
            bill_info['amounts'] = [{'value': amount, 'currency': 'CNY'}]
            return

        # 备选1：不带英文列名的版式，取本期应还款金额后第一个金额
        m = re.search(r'本期应还款金额.*?([0-9,]+\.[0-9]{2})', clean_text, re.DOTALL)
        if m:
            amount = float(m.group(1).replace(',', ''))
            if 0 <= amount < 1000000:
                bill_info['amounts'] = [{'value': amount, 'currency': 'CNY'}]
                return

        # 备选2：明细表头「本期应还金额」
        m = re.search(r'本期应还金额.*?([0-9,]+\.[0-9]{2})', clean_text, re.DOTALL)
        if m:
            amount = float(m.group(1).replace(',', ''))
            if 0 <= amount < 1000000:
                bill_info['amounts'] = [{'value': amount, 'currency': 'CNY'}]

    def extract_due_date(self, full_text, bill_info):
        """提取还款日：到期还款日 Payment Due Date 2026/07/15（归一化为 ISO）"""
        soup = BeautifulSoup(full_text, 'html.parser')
        clean_text = ' '.join(soup.get_text().split())

        # 锚定模式：摘要区「到期还款日 Payment Due Date」
        # 先扁平化文本、再原始 HTML（基类 _search_anchored_due_date 处理）
        anchored_patterns = [
            r'到期还款日.{0,80}?Payment Due Date.{0,80}?(\d{4}[-/.]\d{1,2}[-/.]\d{1,2})',
            r'到期还款日.{0,80}?(\d{4}[-/.]\d{1,2}[-/.]\d{1,2})',
        ]
        anchored = self._search_anchored_due_date(anchored_patterns, full_text, clean_text)
        if anchored and self._append_due_date(bill_info, anchored):
            return

        # 回退：通用模式 + 邮件日窗口滤残值，取窗口内最晚日期
        patterns = [
            r'到期还款日.*?([0-9]{4}[-/.][0-9]{1,2}[-/.][0-9]{1,2})',
            r'还款日.*?([0-9]{4}[-/.][0-9]{1,2}[-/.][0-9]{1,2})',
        ]
        candidates = []
        for pattern in patterns:
            for match in re.findall(pattern, clean_text, re.DOTALL):
                norm = self._norm_date_str(match)
                if norm and norm not in candidates:
                    candidates.append(norm)
        if not candidates:
            return
        email_date = self._email_date(bill_info)
        if email_date:
            lo = email_date - timedelta(days=self.DUE_WINDOW_PAST_DAYS)
            hi = email_date + timedelta(days=self.DUE_WINDOW_FUTURE_DAYS)
            windowed = []
            for c in candidates:
                try:
                    d = datetime.strptime(c, '%Y-%m-%d').date()
                except Exception:
                    continue
                if lo <= d <= hi:
                    windowed.append(c)
            candidates = windowed
        if candidates:
            self._append_due_date(bill_info, max(candidates))


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
            # 通用：本期应还款金额(元) 9,104.00（兼容无 ￥ 符号的银行）
            r'本期应还款金额.*?([0-9,]+\.[0-9]{2})',
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
                self._append_due_date(bill_info, match)


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
            ChangAnBankExtractor(),
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


def get_sub_account(bank_name, subject):
    """识别银行子账户类型（还款日不同的独立账户，聚合时需分开）。

    招商银行「信用卡中心消费信贷账单」= 汽车分期（车贷），
    还款日固定在每月 28 日，与信用卡/分期卡（每月 6 日）不同，
    合并聚合会导致提醒金额和日期错误。

    招商银行「分期信用卡电子账单」= 分期卡，与个人消费信用卡
    还款日虽同为每月 6 日，但属于不同账户，须分别建任务，
    防止其中一笔还清勾选任务时连带把另一笔标记为已还
    （2026-10 招行分期卡逾期事故的根因之一）。

    Returns:
        str: 子账户标识（如 '车贷'、'分期卡'），无则返回 ''
    """
    if not bank_name or '招商' not in bank_name or not subject:
        return ''
    if '消费信贷' in subject:
        return '车贷'
    if '分期信用卡' in subject:
        return '分期卡'
    return ''
