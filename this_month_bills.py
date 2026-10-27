#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
本月待还款账单查询（重构版）
- 使用模块化架构
- 职责分离：邮箱连接、邮件解码、HTML 解析、账单提取
- 策略模式：支持不同银行的特殊提取逻辑
"""

import os
import re
import email
import email.utils
import json
from datetime import datetime, timedelta, timezone
from collections import defaultdict

from email_client import EmailClient
from email_decoder import EmailDecoder
from bank_extractors import BankExtractorFactory, get_sub_account


# 支持多邮箱配置：优先使用 get_all_emails()，单邮箱配置仍向后兼容
from config import get_all_emails


# 北京时区（与仪表盘/聚合口径一致）
_BJ_TZ = timezone(timedelta(hours=8))


# ===== 附件型历史账单回执识别与告警抑制（2026-10-26） =====
#
# 背景（实测取证）：兴业银行「兴业银行信用卡[202607-202607]电子账单」
# 邮件 Date=Tue, 21 Jul 2026 19:53:34 +0800，MIME 只有两个 part：
#   [0.1] application/octet-stream base64 129510B，附件名
#         「信用卡历史账单[202607-202607].pdf」
#   [0.2] text/html charset=gbk 46B → 解码 26 字符提示语
#         「附件为您的信用卡历史账单，请查收，谢谢。」
# 真实账单（本期应还款总额 RMB 5,100.30 / 到期还款日 2026年07月31日 /
# 账单日 2026年07月11日）在 PDF 附件中。当前版本不解析附件，
# CIBBankExtractor.extract_amount 必然全部落空 → 每天同一条「待人工提取」
# 飞书告警。该期次（202607）距今 3 个月、与本月待还无关，属纯噪音。
#
# 设计约束：
#   1. 只改告警分类，不改 bills 入链与金额聚合（封数/总额零变化）；
#   2. 只有「提取失败 + 账单类附件 + 期次为历史月份（前前月及更早）」才抑制；
#      上月/当期/次月（含期次无法判定）的附件型账单仍照常进「待人工提取」告警
#      ——见下方 HISTORICAL_PERIOD_MONTHS_BEHIND 的阈值论证；
#   3. 判定逻辑全部为纯函数，可单测（见 test_attachment_suppress.py）。

# 账单类附件扩展名（排除 logo/图片等装饰性内联附件）
ATTACHMENT_BILL_EXTENSIONS = ('.pdf', '.xls', '.xlsx', '.et', '.zip', '.rar')

# 期次结束月落后当前月 >= N 个自然月即视为「历史」（默认 2：前前月及更早）
#
# 为什么不是 1（2026-10-27 QA 复核推翻原阈值）：
#   还款日并不一定落在账单月内，上月期次完全可能尚未到期：
#     - 兴业：202609 账单的到期还款日落在 2026-10-01（跨月）；
#     - 招行：存在「账单日 + 20 天」口径，202609 账单还款日可能落在 2026-10-28
#       （本地数据里确有「1 天后到期」的分组）。
#   阈值 1（非当月即历史）在每月 1-20 日期间，会把「上月期次但还款日还没到」
#   的附件型账单静默掉 → 真·漏单（比多告警严重得多）。
#   实测反例：招商银行信用卡[202609-202609]电子账单 + PDF 附件，
#   today=2026-10-27 → behind=1，旧阈值下 hit=True 被抑制。
#
# 为什么 2 安全：
#   账单期次 <= 前前月时，其到期还款日必然早于今天——账单日 + 最长免息期（约 25 天）
#   + 缓冲，最迟也在期次月份结束后的次月内到期；再往前推一个整月，
#   数学上不可能还有未到期的还款日，故抑制不会漏单。
#
# 代价（明确的已知取舍）：
#   上月（behind=1）的附件型账单会多告警一个月（每月最多 1-2 条 INFO 级噪音），
#   用「多一条告警」换取「绝不静默未到期账单」。
HISTORICAL_PERIOD_MONTHS_BEHIND = 2

# 主题中的期次：[202607-202607] 或 [202607]
_STATEMENT_PERIOD_BRACKET_RE = re.compile(
    r'\[\s*(\d{6})\s*(?:[-~]\s*(\d{6})\s*)?\]')
# 主题中的期次：2026年10月
_STATEMENT_PERIOD_CN_RE = re.compile(r'(\d{4})\s*年\s*(\d{1,2})\s*月')


def today_bj():
    """返回北京时间的当天 date（供期次判定与测试注入）。"""
    return datetime.now(_BJ_TZ).date()


def list_attachment_names(msg, decoder=None):
    """列出邮件附件名（已做 RFC2047 解码），无附件返回空列表。

    Args:
        msg: email.message.Message，可为 None
        decoder: EmailDecoder 实例，默认新建

    Returns:
        list[str]: 附件文件名列表
    """
    names = []
    if msg is None:
        return names
    decoder = decoder or EmailDecoder()
    try:
        for part in msg.walk():
            filename = part.get_filename()
            if filename:
                names.append(decoder.decode_mime_words(filename))
    except Exception:
        pass
    return names


def is_bill_attachment(filename):
    """判断文件名是否为「账单类附件」（纯函数）。"""
    if not filename:
        return False
    return filename.lower().endswith(ATTACHMENT_BILL_EXTENSIONS)


def parse_statement_period(subject):
    """从邮件主题解析账单期次结束月，返回 'YYYYMM' 或 None（纯函数）。

    支持：
      - [202607-202607] → '202607'（取区间结束月）
      - [202607]        → '202607'
      - 2026年10月      → '202610'
    无法解析（如纯通知类主题）返回 None —— 调用方应按「非历史」保守处理。
    """
    if not subject:
        return None
    match = _STATEMENT_PERIOD_BRACKET_RE.search(subject)
    if match:
        period = match.group(2) or match.group(1)
        return _validate_period(period)
    match = _STATEMENT_PERIOD_CN_RE.search(subject)
    if match:
        year, month = int(match.group(1)), int(match.group(2))
        if 1 <= month <= 12:
            return '%04d%02d' % (year, month)
    return None


def _validate_period(period):
    """校验 'YYYYMM' 合法性，非法返回 None。"""
    if not period or len(period) != 6 or not period.isdigit():
        return None
    month = int(period[4:])
    if not 1 <= month <= 12:
        return None
    return period


def months_behind(period_end, today=None):
    """期次结束月距今多少个自然月（纯函数）。

    Args:
        period_end: 'YYYYMM'
        today: datetime.date，默认北京时间今天

    Returns:
        int 或 None：期次非法返回 None；未来期次返回负数。
    """
    period_end = _validate_period(period_end)
    if not period_end:
        return None
    if today is None:
        today = today_bj()
    year, month = int(period_end[:4]), int(period_end[4:])
    return (today.year - year) * 12 + (today.month - month)


def is_historical_period(period_end, today=None):
    """期次是否属于「历史月份」（纯函数）。

    历史 = 期次结束月落后当前月 >= HISTORICAL_PERIOD_MONTHS_BEHIND。
    期次缺失/非法时返回 False —— 无法判定即按当期处理，保证不静默当期账单。
    """
    behind = months_behind(period_end, today=today)
    if behind is None:
        return False
    return behind >= HISTORICAL_PERIOD_MONTHS_BEHIND


def classify_attachment_receipt(msg, subject, date_str=None, today=None,
                                decoder=None):
    """判定邮件是否为「附件型历史账单回执」（可抑制告警）。

    命中需同时满足（两个条件缺一不可）：
      ① 邮件带账单类附件（PDF/表格/压缩包）——说明真实账单在附件里；
      ② 主题可解析出期次且该期次属历史月份（落后当前月 >=
         HISTORICAL_PERIOD_MONTHS_BEHIND，即前前月及更早）。
         上月/当月/次月一律不抑制：上月期次的还款日可能尚未到期
         （兴业 202609 账单落在 2026-10-01；招行 202609 账单
         按「账单日+20 天」可能落在 2026-10-28），抑制会漏单。

    Args:
        msg: email.message.Message（用于取附件），None 时判定为不命中
        subject: 邮件主题
        date_str: 邮件 Date 头（仅用于日志记录，不参与判定）
        today: datetime.date，默认北京时间今天（测试可注入）
        decoder: EmailDecoder 实例

    Returns:
        tuple[bool, str, list[str]]: (是否命中, 原因文案, 账单类附件名列表)
    """
    attachments = [n for n in list_attachment_names(msg, decoder)
                   if is_bill_attachment(n)]
    if not attachments:
        return False, '', []

    period_end = parse_statement_period(subject)
    if not is_historical_period(period_end, today=today):
        return False, '', attachments

    behind = months_behind(period_end, today=today)
    reason = (f"附件型历史账单回执：期次 {period_end}（落后当前月 {behind} 个月），"
              f"真实账单在附件 {'、'.join(attachments)} 中；"
              f"与本月待还无关，已抑制「待人工提取」告警（不推飞书）")
    return True, reason, attachments


class BillExtractor:
    """账单提取器（协调器）

    支持多邮箱：每个邮箱可配置 label（如 "YY"），
    账单的 source_label 字段会传递到 TickTick 任务标题和仪表盘显示。
    """
    
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
        # 长安银行
        '长安银行': '长安银行',
    }

    # 跳过的账单邮件主题关键词（不含金额的纯通知类邮件）
    # P0-5：「还款提醒」类邮件滞后一个周期且金额与上期相同，当账单处理会
    # 生成幽灵账单（如【广发卡 10月还款提醒】→ ¥48,611.36/10-06）；
    # 章程/公告/认证/授权书为银行通知而非账单；BOCHK 为扣账卡综合对账单，
    # 非信用卡账单（无可还款金额）。
    SKIP_SUBJECT_KEYWORDS = [
        '补制', '（补）', '(补)', '还款提醒', '提醒', '章程', '公告', '认证', '授权书',
        '领用合约', '更新版本', 'BOCHK',
    ]

    # 已知账单主题模式（P0-5 白名单，从 2026-10-23 邮件审计的
    # bill_email_subjects 归纳）：命中才会进入提取链；
    # 白名单外但含银行关键词的邮件只记 WARN，不静默入链。
    BILL_SUBJECT_PATTERNS = [
        '电子账单', '信用卡账单', '电子对账单', '对账单',
        '消费信贷账单', '账单', 'statement',
    ]
    
    def __init__(self):
        self.email_decoder = EmailDecoder()
        self.bank_factory = BankExtractorFactory()
        # 单邮箱故障记录（P0-4）：{email, label, error}
        self.email_failures = []
        # 白名单外命中银行关键词的主题（P0-5）：只 WARN 不入链
        self.unrecognized_subjects = []

    def fetch_and_extract(self, limit=100):
        """获取并提取账单（多邮箱模式）

        遍历 config.get_all_emails() 返回的所有邮箱，
        每封账单邮件会带上 source_label 字段。

        P0-4 单邮箱故障隔离：某个邮箱连接/拉取失败不影响其他邮箱，
        失败记入 self.email_failures 供告警。
        """
        all_bills = []
        emails_config = get_all_emails()

        if not emails_config:
            print("⚠️ 未配置任何邮箱，请检查 config.json 或环境变量")
            return all_bills

        print(f"📧 共配置 {len(emails_config)} 个邮箱")
        for i, em_cfg in enumerate(emails_config, 1):
            label_display = f" (label={em_cfg['label']})" if em_cfg['label'] else ""
            print(f"\n--- 邮箱 {i}/{len(emails_config)}: {em_cfg['address']}{label_display} ---")
            try:
                bills = self._fetch_from_one_email(em_cfg, limit=limit)
            except Exception as e:
                # 单邮箱故障隔离：记录并继续，不拖垮全盘
                self.email_failures.append({
                    'email': em_cfg['address'],
                    'label': em_cfg.get('label', ''),
                    'error': str(e),
                })
                print(f"❌ ERROR: 邮箱 {em_cfg['address']} 拉取失败（不影响其他邮箱）: {e}")
                continue
            all_bills.extend(bills)

        return all_bills

    def _fetch_from_one_email(self, em_cfg, limit=100):
        """从单个邮箱拉取并提取账单"""
        client = EmailClient(
            em_cfg['imap_server'],
            em_cfg['imap_port'],
            em_cfg['address'],
            em_cfg['password']
        )
        client.connect()
        
        try:
            emails = client.fetch_emails(limit=limit)
            bills_from_this = []
            
            for idx, msg in enumerate(emails, 1):
                subject = self.email_decoder.decode_mime_words(msg.get('Subject', ''))
                date = self.email_decoder.decode_mime_words(msg.get('Date', ''))
                
                html_body = self._extract_html_body(msg)
                
                if self._is_bill_email(subject):
                    # 跳过补制/提醒/公告类邮件（不含金额或非账单）
                    if self._is_skip_subject(subject):
                        print(f"[{idx}] ⏭️ 跳过通知类账单邮件: {subject}")
                        continue
                    # P0-5 主题白名单：白名单外的银行关键词邮件只 WARN 不入链
                    if not self._is_known_bill_subject(subject):
                        print(f"[{idx}] ⚠️ WARN: 非已知账单主题模式，仅记录不入链: {subject}")
                        self.unrecognized_subjects.append({
                            'subject': subject, 'date': date,
                            'email': em_cfg['address'], 'label': em_cfg.get('label', ''),
                        })
                        continue
                    print(f"[{idx}] {subject}")
                    bills = self.extract_from_html(html_body, subject, date, msg=msg)
                    # 给每个账单打上 source_label
                    for bill in bills:
                        bill['source_label'] = em_cfg.get('label', '')
                        bill['source_email'] = em_cfg['address']
                    bills_from_this.extend(bills)
            
            return bills_from_this
        finally:
            client.disconnect()

    def _is_skip_subject(self, subject):
        """判断是否应跳过此账单邮件（如补制/还款提醒类不含金额或非账单）"""
        for kw in self.SKIP_SUBJECT_KEYWORDS:
            if kw in subject:
                return True
        return False

    def _is_known_bill_subject(self, subject):
        """判断主题是否命中已知账单模式（白名单）。"""
        s = (subject or '').lower()
        return any(p.lower() in s for p in self.BILL_SUBJECT_PATTERNS)
    
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
    
    def extract_from_html(self, html_content, subject, date, msg=None):
        """从 HTML 中提取账单信息

        Args:
            html_content: 邮件 HTML 正文（第一个 text/html part）
            subject: 邮件主题
            date: 邮件 Date 头
            msg: 原始 email.message.Message（可选），供失败诊断识别
                附件型账单（正文仅提示语、真实账单在 PDF 附件中）
        """
        bills = []
        
        full_text = f"{subject}\n{html_content}"
        
        bank_name = self._identify_bank(full_text)
        if not bank_name:
            # 白名单主题但无法识别银行（如订阅类账单邮件）：只记 WARN
            print(f"  ⚠️ WARN: 无法识别银行的账单主题: {subject}")
            self.unrecognized_subjects.append({
                'subject': subject, 'date': date, 'reason': '无法识别银行',
            })
            return bills
        
        extractor = self.bank_factory.create_extractor(bank_name)
        full_text = extractor.preprocess_text(full_text)
        
        bill_info = {
            'subject': subject,
            'date': date,
            'amounts': [],
            'due_dates': [],
            'statement_dates': [],
            'statement_day': None,
            'credit_limit': None,
            'bank_name': bank_name
        }
        
        extractor.extract_amount(full_text, bill_info)
        extractor.extract_due_date(full_text, bill_info)
        # 额度 / 账单日：基类通用解析，失败不影响主流程
        try:
            extractor.extract_credit_limit(full_text, bill_info)
        except Exception:
            pass
        try:
            extractor.extract_statement_date(full_text, bill_info)
        except Exception:
            pass

        # 若只有 statement_day（如邮储「账单日06」），用邮件日或还款日补全年月
        if not bill_info.get('statement_dates') and bill_info.get('statement_day'):
            self._fill_statement_date_from_day(bill_info, date)
        
        if bill_info['amounts'] and not bill_info['due_dates']:
            # P0-3：不再编造「邮件日+20 天」假还款日——错日期比没日期危险。
            # 标记待人工确认并告警，由人工补真实还款日。
            bill_info['needs_review'] = True
            bill_info['review_reason'] = '金额已提取但还款日缺失（未编造默认日期，需人工确认）'
            print(f"  ⚠️ WARN: {bank_name} 金额已提取但还款日缺失，标记 needs_review（不编造日期）")

        if not bill_info['amounts']:
            # P0-1：识别为账单邮件但金额为空 → 标记提取失败，不再静默丢弃
            # （此前「有 due 无 amount」照常入链，滴答侧再静默跳过，全程零感知）
            bill_info['extraction_failed'] = True
            bill_info['failure_reason'] = self._diagnose_failure(
                bill_info, html_content, extractor, msg=msg)
            print(f"  ❌ ERROR: {bank_name} 金额提取失败 - {bill_info['failure_reason']}")

            # 附件型历史账单回执：命中则不进「待人工提取」告警，改记 attachment_bills
            hit, why, files = classify_attachment_receipt(
                msg, subject, date, decoder=self.email_decoder)
            bill_info['attachment_files'] = files
            if hit:
                bill_info['attachment_receipt'] = True
                bill_info['suppressed'] = True
                bill_info['suppress_reason'] = why
                print(f"  🔕 已抑制重复告警：{why}")

        # P0-2：提取层合理性闸门（额度×1%，先只告警不拦截）
        try:
            extractor.check_reasonableness(bill_info)
        except Exception:
            pass
        if bill_info.get('suspicious'):
            print(f"  ⚠️ WARN: {bank_name} {bill_info.get('suspicious_reason', '金额可疑')}")

        # 白名单内的账单邮件一律入链（含失败/待确认标记），不再静默丢弃
        bills.append(bill_info)
        self._print_bill_info(bill_info)
        
        return bills

    def _diagnose_failure(self, bill_info, html_content, extractor, msg=None):
        """生成提取失败原因（供「待人工提取」告警卡片定位问题）。

        附件型账单识别：若邮件带附件（如 PDF 账单），正文通常只有一句
        「附件为您的…账单，请查收」，金额在附件里——原因中注明附件名，
        让人工知道需读取附件而非调试提取规则（已知限制：不解析附件）。
        """
        extractor_name = type(extractor).__name__

        # 附件清单（RFC2231 编码名经 decode_mime_words 归一化）
        attachments = []
        if msg is not None:
            try:
                for part in msg.walk():
                    fname = part.get_filename()
                    if fname:
                        attachments.append(self.email_decoder.decode_mime_words(fname))
            except Exception:
                pass

        if attachments:
            return (f"{extractor_name}.extract_amount 所有模式落空：附件型账单，"
                    f"正文仅 {len(html_content or '')} 字节提示语，真实账单在附件 "
                    f"{'、'.join(attachments)} 中，需人工读取（当前版本不解析附件）")

        if not html_content or not html_content.strip():
            return f"{extractor_name}.extract_amount 落空：邮件无 HTML 正文（纯文本或解码失败）"
        try:
            from bs4 import BeautifulSoup
            text = ' '.join(BeautifulSoup(html_content, 'html.parser').get_text().split())
        except Exception:
            text = ''
        anchors = [kw for kw in ('应还', '账单金额', 'New Balance', 'RMB', '￥') if kw in text]
        if anchors:
            return (f"{extractor_name}.extract_amount 所有模式落空"
                    f"（HTML {len(html_content)} 字节，文本含关键词 {anchors}，疑版式不匹配）")
        return f"{extractor_name}.extract_amount 所有模式落空（HTML {len(html_content)} 字节，文本无应还/金额关键词）"

    def _fill_statement_date_from_day(self, bill_info, email_date_str):
        """仅有账单日「日」时，结合还款日/邮件日推断完整日期。"""
        day = bill_info.get('statement_day')
        if not day:
            return
        base = None
        for due in bill_info.get('due_dates') or []:
            try:
                base = datetime.strptime(due.replace('/', '-')[:10], '%Y-%m-%d')
                break
            except Exception:
                continue
        if base is None:
            try:
                email_date = email.utils.parsedate_tz(email_date_str)
                if email_date:
                    base = datetime(*email_date[:6])
            except Exception:
                pass
        if base is None:
            return
        # 账单日通常在还款日之前：若 day > 还款日 day，则账单在上月
        y, m = base.year, base.month
        if bill_info.get('due_dates'):
            try:
                due_d = base.day
                if day > due_d:
                    m -= 1
                    if m < 1:
                        m = 12
                        y -= 1
            except Exception:
                pass
        try:
            # 处理月末
            from calendar import monthrange
            last = monthrange(y, m)[1]
            d = min(int(day), last)
            s = f'{y:04d}-{m:02d}-{d:02d}'
            bill_info.setdefault('statement_dates', []).append(s)
        except Exception:
            pass
    
    def _set_default_due_date(self, bill_info, date):
        """已废弃（P0-3）：不再编造「邮件日+20 天」假还款日。

        错日期比没日期危险：假 deadline 会直接变成滴答任务。
        现在由 extract_from_html 标记 needs_review 并告警。
        保留此方法仅为向后兼容旧代码引用，不再产生任何日期。
        """
        return
    
    def _print_bill_info(self, bill_info):
        """打印账单信息"""
        bank_name = bill_info['bank_name']
        print(f"  ✓ {bank_name} - 金额:{len(bill_info['amounts'])} 还款日:{len(bill_info['due_dates'])}")
        if bill_info['amounts']:
            print(f"    金额：{[a['value'] for a in bill_info['amounts']][:3]}")
        if bill_info['due_dates']:
            print(f"    还款日：{bill_info['due_dates'][:3]}")
        if bill_info.get('credit_limit'):
            print(f"    额度：{bill_info['credit_limit']:,.0f}")
        if bill_info.get('statement_dates'):
            print(f"    账单日：{bill_info['statement_dates'][:2]}")
        if bill_info.get('extraction_failed'):
            print(f"    ❌ 提取失败：{bill_info.get('failure_reason', '')}")
        if bill_info.get('needs_review'):
            print(f"    ⚠️ 待人工确认：{bill_info.get('review_reason', '')}")
        if bill_info.get('suppressed'):
            print(f"    🔕 告警已抑制：{bill_info.get('suppress_reason', '')}")
        if bill_info.get('suspicious'):
            print(f"    ⚠️ 金额可疑：{bill_info.get('suspicious_reason', '')}")


def _aggregate_bill_groups(bills, should_include):
    """按 银行|子账户|label|还款日 聚合账单（get_upcoming_bills / get_overdue_bills 共用）。

    Args:
        bills: extract_from_html 产出的账单列表
        should_include: 回调 fn(days_until) -> bool，决定该还款日是否进入聚合

    Returns:
        dict: bank_key -> 聚合信息（total_amount / amounts / earliest_due_date 等）
    """
    # 使用北京时间的「日期」做比较，与仪表盘时区一致
    try:
        from datetime import timezone, timedelta as _td
        today = datetime.now(timezone(_td(hours=8))).date()
    except Exception:
        today = datetime.now().date()

    bank_bills = defaultdict(lambda: {
        'total_amount': 0,
        'amounts': [],
        'earliest_due_date': None,
        'source_label': '',
        'sub_account': ''
    })

    for bill in bills:
        bank_name = bill.get('bank_name')
        if not bank_name:
            continue

        source_label = bill.get('source_label', '')
        # 子账户拆分：同银行还款日不同的账户（如招行车贷 28 日 vs 信用卡 6 日）分开聚合，
        # 避免合并成一个错误的金额+还款日
        sub_account = get_sub_account(bank_name, bill.get('subject', ''))

        best_due_date = None
        best_days_until = None

        for due_date_str in bill.get('due_dates', []):
            due_date_str = due_date_str.replace('/', '-')

            parsed_date = None
            try:
                parsed_date = datetime.strptime(due_date_str, '%Y-%m-%d').date()
            except:
                continue

            days_until = (parsed_date - today).days

            # 包含今天 + 未来 + 短宽限过期，避免漏掉当日还款账单
            if should_include(days_until):
                if best_days_until is None or abs(days_until) < abs(best_days_until) or (
                    abs(days_until) == abs(best_days_until) and days_until > best_days_until
                ):
                    best_days_until = days_until
                    best_due_date = due_date_str

        if best_due_date and best_days_until is not None:
            # 按还款日分组：同银行不同还款日的账单分开（如邮储两张卡 09-27 与 10-07、
            # 工行旧账单 09-19 与新账单 10-19）；招行分期卡已按子账户单独拆分，
            # 即使与信用卡同在 6 日还款也不合并，与 ticktick_sync 分组一致
            bank_key = (f"{bank_name}|{sub_account}|{source_label}|{best_due_date}"
                        if sub_account else f"{bank_name}|{source_label}|{best_due_date}")
            bank_info = bank_bills[bank_key]
            bank_info['bank_name'] = bank_name
            bank_info['source_label'] = source_label
            bank_info['sub_account'] = sub_account

            for amount_info in bill.get('amounts', []):
                # 去重：同组内金额相同视为重复账单
                # （常见于原件 + Fw: 转发件内容一致，会导致金额翻倍）
                is_dup = any(
                    a['value'] == amount_info['value'] and a['due_date'] == best_due_date
                    for a in bank_info['amounts']
                )
                if is_dup:
                    continue
                bank_info['amounts'].append({
                    'value': amount_info['value'],
                    'due_date': best_due_date,
                    'days_until': best_days_until,
                    'email': bill['subject']
                })
                bank_info['total_amount'] += amount_info['value']

            # 组内所有账单还款日相同（按还款日分组），直接取值
            bank_info['earliest_due_date'] = {
                'date': best_due_date,
                'days_until': best_days_until
            }

    return bank_bills


def get_upcoming_bills(bills, days=None, include_overdue_days=3):
    """
    获取未来账单（按日期比较，避免「今天还款」被算成 -1 天漏掉）
    days: None 表示获取所有未来账单，数字表示未来多少天
    include_overdue_days: 包含已过期 N 天内的账单（默认 3 天，避免当天/时区边界漏单）

    多邮箱模式：同银行不同 source_label 分别聚合（key = bank_name|label）
    按还款日分组：同银行不同还款日的账单分开聚合（key 追加 |due_date，
    与 ticktick_sync 的分组保持一致），避免合并成错误总额+还款日错乱
    """
    def _should_include(days_until):
        if days_until < -include_overdue_days:
            return False
        return days is None or days_until <= days

    return _aggregate_bill_groups(bills, _should_include)


def get_overdue_bills(bills, grace_days=3):
    """获取超过宽限期仍未确认的账单分组（P0-6 可见性修复）。

    滴答侧 sync_bills 本就保留逾期任务直到用户勾选；报表/仪表盘此前用
    -3 天宽限把超期账单「隐藏」了。此函数按相同分组口径取出
    days_until < -grace_days 的账单，供报表/仪表盘展示（需人工核实是否已还）。
    注意：返回结果含总额为 0.00 的组（本期无需还款），展示侧应过滤。
    """
    def _should_include(days_until):
        return days_until < -grace_days

    return _aggregate_bill_groups(bills, _should_include)


def collect_quality_alerts(bills, email_failures=None, unrecognized=None):
    """汇总提取质量告警清单（P0-1/P0-2/P0-3/P0-4）。

    Returns:
        dict: {
            'extraction_failures': [...],  # 识别为账单但金额为空（需人工提取）
            'suspicious': [...],           # 金额低于额度×1%（疑似误抓）
            'needs_review': [...],         # 有金额无还款日（未编造日期）
            'email_failures': [...],       # 单邮箱故障
            'unrecognized_subjects': [...],# 白名单外的银行关键词邮件
            'attachment_bills': [...],     # 附件型历史账单回执（已抑制，不推飞书）
        }
    """
    def _entry(bill, reason):
        return {
            'bank': bill.get('bank_name', ''),
            'label': bill.get('source_label', ''),
            'subject': bill.get('subject', ''),
            'date': bill.get('date', ''),
            'due_dates': bill.get('due_dates', []),
            'amounts': [a.get('value') for a in bill.get('amounts', [])],
            'reason': reason,
            'suppressed': bool(bill.get('suppressed')),
            'attachments': bill.get('attachment_files', []),
        }

    failures, suspicious, needs_review, attachment_bills = [], [], [], []
    for bill in bills:
        if bill.get('extraction_failed'):
            if bill.get('suppressed'):
                # 附件型历史账单回执：与本月待还无关，不进「待人工提取」告警
                attachment_bills.append(_entry(bill, bill.get('suppress_reason', '')))
            else:
                failures.append(_entry(bill, bill.get('failure_reason', '')))
        if bill.get('suspicious'):
            suspicious.append(_entry(bill, bill.get('suspicious_reason', '')))
        if bill.get('needs_review'):
            needs_review.append(_entry(bill, bill.get('review_reason', '')))
    return {
        'extraction_failures': failures,
        'suspicious': suspicious,
        'needs_review': needs_review,
        'email_failures': list(email_failures or []),
        'unrecognized_subjects': list(unrecognized or []),
        'attachment_bills': attachment_bills,
    }


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


def generate_overdue_report(bank_bills, title="超过宽限期未确认账单（需人工核实是否已还）"):
    """打印超过 3 天宽限期仍未确认的账单（P0-6 可见性）。"""
    print("\n" + "="*80)
    print(title)
    print("="*80)

    rows = [(k, i) for k, i in bank_bills.items()
            if i['total_amount'] > 0 and i.get('earliest_due_date')]
    if not rows:
        print("\n无超过宽限期的未确认账单。")
        return 0

    rows.sort(key=lambda x: x[1]['earliest_due_date']['days_until'])
    total = 0
    for _, info in rows:
        due = info['earliest_due_date']['date']
        overdue_days = -info['earliest_due_date']['days_until']
        label = f" ({info['source_label']})" if info['source_label'] else ''
        sub = f"({info['sub_account']})" if info['sub_account'] else ''
        print(f"  ⏰ {info['bank_name']}{sub}{label} ¥{info['total_amount']:>12,.2f}  "
              f"还款日 {due}（已超期 {overdue_days} 天）")
        total += info['total_amount']
    print("-"*80)
    print(f"合计 ¥{total:,.2f}（滴答清单中对应任务仍保留，勾选完成后不再显示）")
    print("="*80)
    return total


def main():
    print("="*80)
    print("本月待还款账单查询（重构版）")
    print("="*80)
    
    extractor = BillExtractor()
    bills = extractor.fetch_and_extract(limit=100)
    
    print(f"\n共分析 {len(bills)} 封账单邮件")

    # 提取质量告警汇总（P0-1/P0-2/P0-3/P0-4）
    alerts = collect_quality_alerts(
        bills,
        email_failures=extractor.email_failures,
        unrecognized=extractor.unrecognized_subjects,
    )
    if alerts['extraction_failures'] or alerts['suspicious'] or alerts['needs_review'] or alerts['email_failures']:
        print("\n" + "!"*80)
        print("⚠️ 提取质量告警：")
        for f in alerts['extraction_failures']:
            print(f"  ❌ 待人工提取: {f['bank']}{('(' + f['label'] + ')') if f['label'] else ''} "
                  f"「{f['subject']}」 邮件 {f['date']} 还款日 {f['due_dates']} - {f['reason']}")
        for s in alerts['suspicious']:
            print(f"  ⚠️ 疑似误提取: {s['bank']}{('(' + s['label'] + ')') if s['label'] else ''} "
                  f"金额 {s['amounts']} - {s['reason']}")
        for n in alerts['needs_review']:
            print(f"  ⚠️ 待人工确认: {n['bank']}{('(' + n['label'] + ')') if n['label'] else ''} "
                  f"金额 {n['amounts']} - {n['reason']}")
        for e in alerts['email_failures']:
            print(f"  ❌ 邮箱故障: {e['email']} ({e.get('label', '')}) - {e['error']}")
        for a in alerts.get('attachment_bills', []):
            print(f"  🔕 附件型历史账单回执（已抑制告警，不推飞书）: {a['bank']}"
                  f"{('(' + a['label'] + ')') if a['label'] else ''} "
                  f"「{a['subject']}」 邮件 {a['date']} - {a['reason']}")
        print("!"*80)

    upcoming_bills = get_upcoming_bills(bills, days=None)
    total = generate_report(upcoming_bills, title="未来待还款账单汇总（所有未来账单）")
    
    upcoming_15 = get_upcoming_bills(bills, days=15)
    total_15 = generate_report(upcoming_15, title="近期待还款账单（未来 15 天内）")

    overdue_bills = get_overdue_bills(bills)
    generate_overdue_report(overdue_bills)
    
    with open('this_month_bills.json', 'w', encoding='utf-8') as f:
        json.dump({
            'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'total_bills': len(bills),
            'upcoming_total': total,
            'extraction_alerts': alerts,
            'bills': bills
        }, f, ensure_ascii=False, indent=2)
    
    print(f"\n详细数据已保存至：this_month_bills.json")


if __name__ == "__main__":
    main()
