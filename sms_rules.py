#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
短信解析规则引擎（sms_rules.py）

设计原则（对应交接文档第 5 节）：
1. 只用「通用银行短信结构」做匹配（可用额度/本期应还/最低还款/到期还款日/
   还款成功/扣款/验证码），不编造任何具体银行的专属模板；
   具体银行模板等真实样本进入复核队列后再人工补充。
2. 分类结果：bill / repayment / limit / otp / loan / ignored / review
3. 命中银行关键词但结构未解析 → review（复核队列 + 告警）；
   无银行关键词 → ignored（非银行短信，只计数不告警）。
4. 0.00 是合法金额（兴业/长安踩坑教训），金额正则必须接受 0。
5. 来源优先级与乱序守卫由调用方（sms_ingest.py）执行，本模块只负责解析。
"""
import re
from dataclasses import dataclass, field

# ===== 分类常量 =====
CATEGORY_BILL = 'bill'            # 账单：本期应还/最低还款/到期还款日
CATEGORY_REPAYMENT = 'repayment'  # 还款成功/已扣款
CATEGORY_LIMIT = 'limit'          # 可用额度变动
CATEGORY_OTP = 'otp'              # 验证码（只推私聊，不落盘原文）
CATEGORY_LOAN = 'loan'            # 房贷/车贷/贷款/分期扣款（独立 loan_state）
CATEGORY_IGNORED = 'ignored'      # 非银行短信：营销/快递/个人，只计数
CATEGORY_REVIEW = 'review'        # 银行相关但规则未命中 → 复核队列 + 告警

# ===== 银行识别 =====
# 短信正文银行名关键词（含简称；与 this_month_bills.BANK_MAP 保持同口径）
BANK_KEYWORDS = [
    '交通银行', '招商银行', '中国银行', '建设银行', '工商银行', '农业银行',
    '兴业银行', '中信银行', '光大银行', '民生银行', '浦发银行', '平安银行',
    '广发银行', '华夏银行', '邮储银行', '邮政储蓄', '中银香港', '长安银行',
    'BOCHK', 'CMB', 'ICBC',
    # 简称（真实短信常用，如「交行信用卡」「建行储蓄卡」）
    '交行', '建行', '工行', '农行', '中行', '招行', '浦发', '光大',
    '广发', '民生', '中信', '兴业', '华夏', '邮储', '长安',
]
# 常见别名 → 标准名（含真实银行短信常用的简称：交行/建行/招行/工行等）
BANK_ALIASES = {
    '邮政储蓄': '邮储银行', 'BOCHK': '中银香港', '中银': '中银香港',
    'CMB': '招商银行', 'ICBC': '工商银行',
    '交行': '交通银行', '建行': '建设银行', '工行': '工商银行',
    '农行': '农业银行', '中行': '中国银行', '招行': '招商银行',
    '浦发': '浦发银行', '光大': '光大银行', '平安': '平安银行',
    '广发': '广发银行', '民生': '民生银行', '中信': '中信银行',
    '兴业': '兴业银行', '华夏': '华夏银行', '邮储': '邮储银行',
    '长安': '长安银行',
}

# 银行通用短信服务号（公开真实号码，仅用于参考展示，不作为解析依据——
# iOS 快捷指令转发的邮件 From 是用户自选地址，发件人白名单由 cards.yaml 配置）
BANK_SMS_SENDERS = {
    '交通银行': ['95559'], '招商银行': ['95555'], '中国银行': ['95566'],
    '建设银行': ['95533'], '工商银行': ['95588'], '农业银行': ['95599'],
    '兴业银行': ['95561'], '中信银行': ['95558'], '光大银行': ['95595'],
    '民生银行': ['95568'], '浦发银行': ['95528'], '平安银行': ['95511'],
    '广发银行': ['95508'], '华夏银行': ['95577'], '邮储银行': ['95580'],
    '长安银行': ['96890'],
}

# ===== 金额/日期/尾号通用正则 =====
# 金额：¥1,234.56 / 1234.56 元 / 0.00（0 是合法值，兴业/长安教训）
RE_AMOUNT = re.compile(r'([0-9][0-9,]*(?:\.[0-9]{1,2})?)\s*元?')
RE_AMOUNT_PREFIX = re.compile(r'[¥￥]\s*([0-9][0-9,]*(?:\.[0-9]{1,2})?)')

RE_LAST4 = re.compile(r'尾号(?:为)?(\d{4})|\*{2,}(\d{4})|[（(]([A-Za-z]*\d{4})[）)]')

RE_DATE_FULL = re.compile(r'(\d{4})[-/年](\d{1,2})[-/月](\d{1,2})日?')
RE_DATE_MD = re.compile(r'(\d{1,2})月(\d{1,2})日')

# ===== 分类关键词（通用结构，非银行专属模板） =====
# 2026-11-25 用户补充：OTP 关键词扩到"安全码/确认码/口令"及英文变体
KW_OTP = re.compile(
    r'验证码|动态码|校验码|安全码|确认码|口令|dynamic\s*code|verification\s*code|'
    r'security\s*code|passcode|OTP', re.IGNORECASE)
KW_LIMIT = re.compile(r'可用额度|剩余可用|可用余额|额度已调整|额度调整')
KW_BILL = re.compile(r'本期应还|本期账单应还|应还金额|最低还款|到期还款日|账单金额')
KW_REPAYMENT = re.compile(
    r'还款成功|还款到账|已还款|还款入账|扣款成功|已扣款|自动扣款|提前还款成功')
KW_LOAN = re.compile(r'房贷|车贷|住房贷款|汽车贷款|消费贷款|个人贷款|分期|贷款')
# 2026-11-25 用户要求：逾期未还款是重点提醒类
KW_OVERDUE = re.compile(r'逾期|宽限期已过|催收')
KW_MARKETING = re.compile(
    r'退订回|回T退订|退订请|优惠|积分兑换|抽奖|立减|满减|扫码领|分期好礼|'
    r'点击链接|戳此|限时|优惠券|返现', re.IGNORECASE)


def _parse_amount(text, start=0):
    """从 text[start:] 起解析第一个金额，返回 float 或 None。接受 0.00。"""
    m = RE_AMOUNT_PREFIX.search(text, start)
    if not m:
        m = RE_AMOUNT.search(text, start)
        if not m:
            return None
    try:
        return float(m.group(1).replace(',', ''))
    except (ValueError, IndexError):
        return None


def _parse_date(text):
    """解析日期字符串，优先完整日期（2026-11-15），其次月日（11月15日）。
    返回 'YYYY-MM-DD' 或 None。月日格式年份取短信到达年份（由调用方传入上下文，
    本函数保守返回当前年份，乱序守卫由调用方做）。"""
    import datetime
    m = RE_DATE_FULL.search(text)
    if m:
        try:
            d = datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            return d.isoformat()
        except ValueError:
            pass
    m = RE_DATE_MD.search(text)
    if m:
        year = datetime.date.today().year
        try:
            d = datetime.date(year, int(m.group(1)), int(m.group(2)))
            # 跨月账单：如果解析出的日期比今天早 6 个月以上，可能是去年（如
            # 1 月收到 12 月到期日）——回退一年会导致未来日错判，这里保持
            # 当前年并交给复核置信度兜底
            return d.isoformat()
        except ValueError:
            pass
    return None


def _extract_last4(text):
    m = RE_LAST4.search(text)
    if m:
        for g in m.groups():
            if g:
                return g[-4:]
    return None


def identify_bank(text):
    """从正文识别银行，返回标准银行名或 None。长关键词优先（'邮政储蓄'先于'邮'）。"""
    upper = text.upper()
    for kw in BANK_KEYWORDS:
        if kw in text or kw.upper() in upper:
            return BANK_ALIASES.get(kw, kw)
    return None


@dataclass
class ParsedSms:
    """单条短信解析结果（结构化事件的核心字段）。"""
    category: str                    # bill/repayment/limit/otp/loan/ignored/review
    bank: str = None                 # 标准银行名（ignored 类可为 None）
    last4: str = None                # 卡尾号（无卡号的贷款类为 None）
    fields: dict = field(default_factory=dict)  # 解析出的业务字段
    confidence: str = 'low'          # high / medium / low
    review_reason: str = None        # 进复核队列时的原因
    otp_code: str = None             # 仅 otp 类；调用方推送后必须丢弃，不得落盘


def parse_sms(body):
    """解析一条短信正文（已从邮件中提取），返回 ParsedSms。

    解析顺序（互斥分类，先特殊后一般）：
    1. 验证码 —— 最高优先，避免账单里偶然含"验证码"字样误分类
    2. 营销/退订 → ignored
    3. 房贷/车贷/贷款扣款 → loan
    4. 还款成功 → repayment
    5. 可用额度 → limit
    6. 账单（应还/最低还款/到期日）→ bill
    7. 含银行关键词但未命中 → review
    8. 无银行关键词 → ignored
    """
    if not body or not body.strip():
        return ParsedSms(category=CATEGORY_IGNORED, confidence='low')

    bank = identify_bank(body)
    last4 = _extract_last4(body)

    # 1. 验证码
    if KW_OTP.search(body):
        # 验证码主体：紧跟"验证码"后面的 4-8 位数字
        code = None
        m = re.search(r'[:：\s]?(\d{4,8})\s*(?:，|,|。|；|;|$)?', body[KW_OTP.search(body).end():])
        m2 = re.search(r'(?:验证码|动态码|校验码)[:：]?\s*(\d{4,8})', body)
        if m2:
            code = m2.group(1)
        elif m:
            code = m.group(1)
        if code:
            return ParsedSms(category=CATEGORY_OTP, bank=bank, last4=last4,
                             otp_code=code, confidence='high')
        # 含"验证码"但提不出码 → 复核，绝不猜
        return ParsedSms(category=CATEGORY_REVIEW, bank=bank, last4=last4,
                         review_reason='疑似验证码但无法提取', confidence='low')

    # 2. 明确营销 → 忽略
    if KW_MARKETING.search(body) and not (KW_LIMIT.search(body) or KW_BILL.search(body)
                                          or KW_REPAYMENT.search(body)):
        return ParsedSms(category=CATEGORY_IGNORED, bank=bank, confidence='low')

    # 3. 房贷/车贷/贷款/分期扣款（无卡号，进独立 loan_state）
    if KW_LOAN.search(body) and KW_REPAYMENT.search(body):
        amount = _parse_amount(body)
        if amount is not None:
            return ParsedSms(category=CATEGORY_LOAN, bank=bank,
                             fields={'amount': amount,
                                     'loan_note': KW_LOAN.search(body).group(0)},
                             confidence='medium')
        return ParsedSms(category=CATEGORY_REVIEW, bank=bank,
                         review_reason='贷款扣款但无金额', confidence='low')

    # 3.5 逾期类（2026-11-25 用户要求重点提醒）：贷款/信用卡逾期 → loan+overdue
    # 金额只认"逾期金额/逾期款/逾期本息"关键词，避免"逾期3天"的 3 被误当金额
    if KW_OVERDUE.search(body):
        m = re.search(r'逾期(?:金额|款|本息)[:：]?\s*[¥￥]?\s*'
                      r'([0-9][0-9,]*(?:\.[0-9]{1,2})?)', body)
        if m:
            amount = float(m.group(1).replace(',', ''))
            return ParsedSms(category=CATEGORY_LOAN, bank=bank, last4=last4,
                             fields={'amount': amount,
                                     'loan_note': '逾期未还款',
                                     'overdue': True},
                             confidence='medium')
        return ParsedSms(category=CATEGORY_REVIEW, bank=bank, last4=last4,
                         review_reason='逾期类短信但无明确逾期金额（重点人工确认）',
                         confidence='low')

    # 4. 还款成功
    if KW_REPAYMENT.search(body):
        amount = _parse_amount(body)
        if amount is not None:
            return ParsedSms(category=CATEGORY_REPAYMENT, bank=bank, last4=last4,
                             fields={'amount': amount}, confidence='medium')
        return ParsedSms(category=CATEGORY_REVIEW, bank=bank, last4=last4,
                         review_reason='还款类但无金额', confidence='low')

    # 5. 可用额度：只改 available_limit，不碰账单字段
    if KW_LIMIT.search(body):
        m = KW_LIMIT.search(body)
        amount = _parse_amount(body, m.end())
        if amount is not None:
            return ParsedSms(category=CATEGORY_LIMIT, bank=bank, last4=last4,
                             fields={'available_limit': amount}, confidence='medium')
        return ParsedSms(category=CATEGORY_REVIEW, bank=bank, last4=last4,
                         review_reason='额度类但金额解析失败', confidence='low')

    # 6. 账单：本期应还 + 最低还款 + 到期还款日（三者尽量全取）
    if KW_BILL.search(body):
        fields = {}
        ok = False
        m = re.search(r'(?:本期应还|应还金额|本期账单应还|账单金额)[:：]?\s*'
                      r'[¥￥]?\s*([0-9][0-9,]*(?:\.[0-9]{1,2})?)', body)
        if m:
            fields['statement_balance'] = float(m.group(1).replace(',', ''))
            ok = True
        m = re.search(r'最低还款[:：]?\s*[¥￥]?\s*([0-9][0-9,]*(?:\.[0-9]{1,2})?)', body)
        if m:
            fields['min_due'] = float(m.group(1).replace(',', ''))
            ok = True
        due = _parse_date(body)
        if due:
            fields['due_date'] = due
            ok = True
        if ok:
            # 三字段中 >=2 个 → high；仅 1 个 → medium；否则复核
            n = len(fields)
            conf = 'high' if n >= 2 else 'medium'
            return ParsedSms(category=CATEGORY_BILL, bank=bank, last4=last4,
                             fields=fields, confidence=conf)
        return ParsedSms(category=CATEGORY_REVIEW, bank=bank,
                         review_reason='账单类关键词但字段解析不全', confidence='low')

    # 7/8. 有银行名或信用卡关键词 → 复核；都无 → 忽略
    if bank:
        return ParsedSms(category=CATEGORY_REVIEW, bank=bank, last4=last4,
                         review_reason='银行短信但规则未命中（模板待补充）',
                         confidence='low')
    if '信用卡' in body or '贷记卡' in body:
        return ParsedSms(category=CATEGORY_REVIEW, bank=bank, last4=last4,
                         review_reason='信用卡相关短信但无法识别银行且规则未命中',
                         confidence='low')
    return ParsedSms(category=CATEGORY_IGNORED, bank=None, confidence='low')


# ===== card_state 更新规则（来源优先级 + 乱序守卫由 sms_ingest 调用） =====

def apply_to_card_state(state, parsed, event_ts, event_id):
    """把解析结果应用到单张卡状态（或 loan_state），返回 (changed, reason)。

    规则（文档 5.2/5.3）：
    - limit 类只改 available_limit，不碰账单字段
    - bill 类改 statement_balance/min_due/due_date，不碰 available_limit
    - repayment 类标记 last_repayment（不清空账单字段，账单以邮件为权威源）
    - 乱序守卫：event_ts 早于现有 event_ts 直接丢弃
    """
    import datetime
    if parsed.category in (CATEGORY_OTP, CATEGORY_IGNORED, CATEGORY_REVIEW):
        return False, 'no-state-category'

    # 乱序守卫
    old_ts = state.get('event_ts')
    if old_ts:
        try:
            if datetime.datetime.fromisoformat(event_ts) < datetime.datetime.fromisoformat(old_ts):
                return False, 'out-of-order-dropped'
        except ValueError:
            pass

    changed = False
    f = parsed.fields
    if parsed.category == CATEGORY_LIMIT and 'available_limit' in f:
        state['available_limit'] = f['available_limit']
        changed = True
    elif parsed.category == CATEGORY_BILL:
        for k in ('statement_balance', 'min_due', 'due_date'):
            if k in f:
                state[k] = f[k]
                changed = True
    elif parsed.category == CATEGORY_REPAYMENT and 'amount' in f:
        state['last_repayment'] = {'amount': f['amount'], 'event_ts': event_ts}
        changed = True
    elif parsed.category == CATEGORY_LOAN and 'amount' in f:
        state['last_repayment'] = {'amount': f['amount'], 'event_ts': event_ts,
                                   'loan_note': f.get('loan_note', ''),
                                   'overdue': bool(f.get('overdue'))}
        changed = True
    else:
        return False, 'no-mapped-fields'

    if changed:
        state['event_ts'] = event_ts
        state['source'] = 'sms'
        state['event_id'] = event_id
        state['confidence'] = parsed.confidence
        if parsed.last4:
            state['last4'] = parsed.last4
        if parsed.bank:
            state['bank'] = parsed.bank
    return changed, 'ok'


# ===== 广谱验证码识别（2026-11-25 用户规则，用于双渠道推送） =====
# 用户规则：正文满足以下任一即视为验证码类短信：
#   1) 去掉转发尾注后基本是纯数字
#   2) 含"验证码"三字
#   3) 含"码"或"扣"（含英文 code）且伴随 4-8 位独立数字
#   4) 含"安全确认码"及各种"码"类词
# 注意：这是"加推"判定，不改变状态机分类（扣款类短信仍会更新贷款/还款状态）。

RE_FWD_SUFFIX = re.compile(r'[-—－－\s]*发自我的\s*\w*\s*iPhone.*$', re.IGNORECASE)
RE_STANDALONE_CODE = re.compile(r'(?<!\d)(\d{4,8})(?!\d)')


def _strip_forward_suffix(text):
    """去掉 iOS 转发尾注「发自我的 iPhone」及其后内容。"""
    return RE_FWD_SUFFIX.sub('', text or '').strip()


def extract_otp_code(body):
    """提取 4-8 位验证码：优先「XX码：123456」结构，否则取首个独立 4-8 位数字。
    提不出返回 None（绝不猜）。"""
    core = _strip_forward_suffix(body)
    if not core:
        return None
    m = re.search(
        r'(?:验证码|校验码|动态码|安全码|确认码|口令|code)[^\d]{0,8}(\d{4,8})',
        core, re.IGNORECASE)
    if m:
        return m.group(1)
    m = RE_STANDALONE_CODE.search(core)
    return m.group(1) if m else None


def is_otp_like(body):
    """广谱验证码判定（命中任一规则即 True；营销类一律排除）。"""
    core = _strip_forward_suffix(body)
    if not core:
        return False
    if KW_MARKETING.search(core):
        return False
    # 规则1：纯数字（转发正文常带少量空白）
    if re.fullmatch(r'[\d\s]{4,}', core):
        return True
    # 规则2/4：验证码/动态码/安全码/确认码/口令 等码类词
    if KW_OTP.search(core):
        return True
    # 规则3（英文版）：code/verification + 独立 4-8 位数字
    if re.search(r'code|verification|security', core, re.IGNORECASE) \
            and RE_STANDALONE_CODE.search(core):
        return True
    # 规则3（中文）：含"码"或"扣" + 独立 4-8 位数字
    if RE_STANDALONE_CODE.search(core) and ('码' in core or '扣' in core):
        return True
    return False
