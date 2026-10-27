#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
附件型历史账单回执抑制规则测试（2026-10-26 新增 / 2026-10-27 阈值收紧为 2）

覆盖：
  1. parse_statement_period / months_behind / is_historical_period 三个纯函数
     （主题期次解析、月差计算、历史月份判定 + 非法输入保守处理）
  2. is_bill_attachment / list_attachment_names（附件识别，排除图片装饰件）
  3. classify_attachment_receipt：命中「附件型 + 历史期次」才抑制；
     上月/当期（当月/次月）附件型仍必须告警；无附件 / 无期次 也告警
  4. collect_quality_alerts 路由：suppressed 进 attachment_bills，
     不再进 extraction_failures；真失败仍在 extraction_failures
  5. 端到端回归：真实兴业 YY「[202607-202607]」邮件形状（26 字节正文 +
     129510B PDF 附件）→ 命中抑制，且 bills 封数/金额不受影响
  6. check_reasonableness 闸门语义不变（P0-2 仍生效）
  7. 阈值语义（2026-10-27 QA 复核）：HISTORICAL_PERIOD_MONTHS_BEHIND=2，
     上月（behind=1）不抑制、前前月（behind=2）起才抑制。
     所有断言一律由模块常量推导，不硬编码 1/2，改阈值不会再破测试。

运行：
  "C:/Users/Administrator/.workbuddy/binaries/python/envs/default/Scripts/python.exe" test_attachment_suppress.py
"""

import sys
from datetime import date
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))

from this_month_bills import (  # noqa: E402
    ATTACHMENT_BILL_EXTENSIONS,
    HISTORICAL_PERIOD_MONTHS_BEHIND,
    classify_attachment_receipt,
    collect_quality_alerts,
    is_bill_attachment,
    is_historical_period,
    list_attachment_names,
    months_behind,
    parse_statement_period,
)

passed = failed = 0


def check(name, cond, detail=""):
    global passed, failed
    if cond:
        passed += 1
        print(f"  [OK] {name}")
    else:
        failed += 1
        print(f"  [FAIL] {name} {detail}")


# 固定「今天」为 2026-10-26（北京时间），所有期次判定都用它做基准
TODAY = date(2026, 10, 26)


def period_offset(months_back, base=None):
    """以基准日（默认 TODAY）为原点，返回 months_back 个自然月前的 'YYYYMM'。

    用函数推导而不是硬编码 '202608'/'202609'：阈值常量变化时，
    「上月 / 前前月 / 更早」这类语义断言仍自动指向正确的期次。
    """
    base = base or TODAY
    year, month = base.year, base.month - int(months_back)
    while month <= 0:
        month += 12
        year -= 1
    return '%04d%02d' % (year, month)


def expect_historical(period_end, base=None):
    """按模块常量推导期次「是否应判历史」（测试侧独立实现的期望值）。"""
    behind = months_behind(period_end, TODAY if base is None else base)
    if behind is None:
        return False
    return behind >= HISTORICAL_PERIOD_MONTHS_BEHIND

# 真实邮件的关键常量（2026-10-26 实测取证）
CIB_SUBJECT = '兴业银行信用卡[202607-202607]电子账单'
CIB_BODY = '附件为您的信用卡历史账单，请查收，谢谢。'
CIB_PDF_NAME = '信用卡历史账单[202607-202607].pdf'
CIB_PDF_SIZE = 129510


def build_cib_like_message(body=CIB_BODY, pdf_name=CIB_PDF_NAME,
                          subject=CIB_SUBJECT):
    """构造与真实兴业回执同形状的邮件（multipart/mixed：附件 + 26 字节正文）。"""
    msg = MIMEMultipart('mixed')
    msg['Subject'] = subject
    msg['From'] = 'creditcard@message.cib.com.cn'
    msg['To'] = 'rexrr@qq.com'
    msg['Date'] = 'Tue, 21 Jul 2026 19:53:34 +0800 (CST)'
    pdf = MIMEApplication(b'%PDF-1.4 fake', _subtype='octet-stream')
    pdf.add_header('Content-Disposition', 'attachment', filename=pdf_name)
    msg.attach(pdf)
    msg.attach(MIMEText(body, 'html', 'gbk'))
    return msg


def build_no_attachment_message():
    """构造无附件的普通 HTML 账单邮件。"""
    msg = MIMEMultipart('alternative')
    msg['Subject'] = CIB_SUBJECT
    msg['Date'] = 'Tue, 21 Jul 2026 19:53:34 +0800 (CST)'
    msg.attach(MIMEText(CIB_BODY, 'html', 'gbk'))
    return msg


def make_bill(**kwargs):
    """构造 bill_info 形状的字典，默认全字段齐全。"""
    bill = {
        'subject': CIB_SUBJECT,
        'date': 'Tue, 21 Jul 2026 19:53:34 +0800 (CST)',
        'amounts': [],
        'due_dates': [],
        'statement_dates': [],
        'statement_day': None,
        'credit_limit': None,
        'bank_name': '兴业银行',
        'source_label': 'YY',
    }
    bill.update(kwargs)
    return bill


print("== 1. parse_statement_period（主题期次解析）==")
check("方括号区间 [202607-202607] → 取结束月 202607",
      parse_statement_period(CIB_SUBJECT) == '202607',
      repr(parse_statement_period(CIB_SUBJECT)))
check("单月方括号 [202607] → 202607",
      parse_statement_period('兴业银行信用卡[202607]电子账单') == '202607')
check("中文年月 2026年10月 → 202610",
      parse_statement_period('兴业银行信用卡2026年10月电子账单') == '202610')
check("中文年月补零 2026年9月 → 202609",
      parse_statement_period('兴业银行信用卡2026年9月电子账单') == '202609')
check("跨月区间 [202601-202606] → 取结束月 202606",
      parse_statement_period('账单[202601-202606]') == '202606')
check("无期次主题 → None",
      parse_statement_period('广发信用卡还款提醒') is None)
check("非法月份 [202613] → None",
      parse_statement_period('账单[202613]') is None)
check("位数不足 [2026-2026] → None",
      parse_statement_period('账单[2026-2026]') is None)
check("空主题 → None", parse_statement_period('') is None)
check("None 主题 → None", parse_statement_period(None) is None)

print("\n== 2. months_behind（期次月差）==")
check("202607 vs 2026-10 → 3", months_behind('202607', TODAY) == 3,
      repr(months_behind('202607', TODAY)))
check("202610 vs 2026-10 → 0", months_behind('202610', TODAY) == 0)
check("202609 vs 2026-10 → 1", months_behind('202609', TODAY) == 1)
check("202611 vs 2026-10 → -1（未来期次）", months_behind('202611', TODAY) == -1)
check("跨年 202512 vs 2026-10 → 10", months_behind('202512', TODAY) == 10)
check("非法期次 → None", months_behind('2026', TODAY) is None)

print("\n== 3. is_historical_period（历史月份判定）==")
# 阈值下限 2 是需求本身（2026-10-27 QA 复核结论）：回退到 1 会把
# 「上月期次但还款日尚未到期」的附件账单静默掉（招行 202609 按
# 「账单日+20 天」还款日可能落在 2026-10-28），属真·漏单。
check("阈值常量 >= 2（回退到 1 会静默上月未到期账单）",
      HISTORICAL_PERIOD_MONTHS_BEHIND >= 2, HISTORICAL_PERIOD_MONTHS_BEHIND)
# 上限同样锁住：阈值 > 2 会让「前前月」重新天天告警，去噪目标失效。
check("阈值常量 == 2（取更大值则去噪目标失效）",
      HISTORICAL_PERIOD_MONTHS_BEHIND == 2, HISTORICAL_PERIOD_MONTHS_BEHIND)
# 恒定关系：判定结果必须与「月差 >= 常量」完全等价（不硬编码 1/2，
# 覆盖 0~5 个月差区间，含当月与次月）
check("恒定关系：is_historical_period ⇔ months_behind >= 常量（月差 0~5）",
      all(is_historical_period(period_offset(n), TODAY)
          == expect_historical(period_offset(n)) for n in range(6)))
check("202607 为历史（落后 3 个月）", is_historical_period('202607', TODAY) is True)
check("202608 为历史（落后 2 个月）", is_historical_period('202608', TODAY) is True)
check("上月 202609 不判历史（阈值 2：上月还款日可能尚未到期）",
      is_historical_period('202609', TODAY) is False,
      months_behind('202609', TODAY))
check("前前月（behind 恰为常量）起判历史",
      is_historical_period(period_offset(HISTORICAL_PERIOD_MONTHS_BEHIND), TODAY) is True)
check("上月（behind = 常量-1）不判历史",
      is_historical_period(period_offset(HISTORICAL_PERIOD_MONTHS_BEHIND - 1), TODAY)
      is False)
check("202610 为当期（当月）不判历史",
      is_historical_period('202610', TODAY) is False)
check("202611 为次月不判历史", is_historical_period('202611', TODAY) is False)
check("期次缺失 → 保守按当期（False）", is_historical_period(None, TODAY) is False)
check("期次非法 → 保守按当期（False）", is_historical_period('abc', TODAY) is False)

print("\n== 4. 附件识别 ==")
check("PDF 属账单类附件", is_bill_attachment(CIB_PDF_NAME) is True)
check("xlsx 属账单类附件", is_bill_attachment('账单.xlsx') is True)
check("大写扩展名 .PDF 也识别", is_bill_attachment('BILL.PDF') is True)
check("png 装饰图不算账单附件", is_bill_attachment('logo.png') is False)
check("gif 装饰图不算账单附件", is_bill_attachment('img_header.gif') is False)
check("空文件名不算", is_bill_attachment('') is False)
check("None 不算", is_bill_attachment(None) is False)
check("扩展名常量包含 .pdf", '.pdf' in ATTACHMENT_BILL_EXTENSIONS)

msg_cib = build_cib_like_message()
names = list_attachment_names(msg_cib)
check("真实形状邮件能列出 1 个附件", len(names) == 1, names)
check("附件名解码正确", names and names[0] == CIB_PDF_NAME, names)
check("msg=None 时返回空列表", list_attachment_names(None) == [])

print("\n== 5. classify_attachment_receipt（核心判定）==")
hit, why, files = classify_attachment_receipt(
    msg_cib, CIB_SUBJECT, 'Tue, 21 Jul 2026 19:53:34 +0800', today=TODAY)
check("兴业 202607 附件型回执 → 命中抑制", hit is True)
check("命中原因为历史账单回执", '历史账单回执' in why, why)
check("命中原因含期次 202607", '202607' in why, why)
check("命中原因含附件名", CIB_PDF_NAME in why, why)
check("返回账单类附件列表", files == [CIB_PDF_NAME], files)

# 前前月（月差恰为阈值）：仍按历史抑制 —— 这是去噪目标所在区段
period_old = period_offset(HISTORICAL_PERIOD_MONTHS_BEHIND)
subject_old = f'兴业银行信用卡[{period_old}-{period_old}]电子账单'
hit_old, why_old, _ = classify_attachment_receipt(
    build_cib_like_message(subject=subject_old), subject_old, None, today=TODAY)
check(f"前前月（{period_old}，behind={HISTORICAL_PERIOD_MONTHS_BEHIND}）→ 命中抑制",
      hit_old is True, why_old)
check("前前月命中原因为历史账单回执", '历史账单回执' in why_old, why_old)

hit_cur, why_cur, _ = classify_attachment_receipt(
    msg_cib, '兴业银行信用卡[202610-202610]电子账单', None, today=TODAY)
check("当期（202610）附件型账单 → 不抑制（仍告警）", hit_cur is False, why_cur)

hit_next, _, _ = classify_attachment_receipt(
    msg_cib, '兴业银行信用卡[202611-202611]电子账单', None, today=TODAY)
check("次月（202611）附件型账单 → 不抑制（仍告警）", hit_next is False)

hit_noperiod, _, _ = classify_attachment_receipt(
    msg_cib, '兴业银行信用卡电子账单', None, today=TODAY)
check("无期次可解析 → 不抑制（保守告警）", hit_noperiod is False)

hit_noatt, _, _ = classify_attachment_receipt(
    build_no_attachment_message(), CIB_SUBJECT, None, today=TODAY)
check("无附件 → 不抑制", hit_noatt is False)

hit_none, _, _ = classify_attachment_receipt(None, CIB_SUBJECT, None, today=TODAY)
check("msg=None → 不抑制（不误杀）", hit_none is False)

msg_png = MIMEMultipart('related')
img = MIMEApplication(b'\x89PNG', _subtype='png')
img.add_header('Content-Disposition', 'inline', filename='logo.png')
msg_png.attach(img)
msg_png.attach(MIMEText(CIB_BODY, 'html', 'gbk'))
hit_png, _, _ = classify_attachment_receipt(
    msg_png, CIB_SUBJECT, None, today=TODAY)
check("仅装饰图片附件 → 不抑制", hit_png is False)

msg_xlsx = MIMEMultipart('mixed')
xls = MIMEApplication(b'PK', _subtype='vnd.ms-excel')
xls.add_header('Content-Disposition', 'attachment', filename='账单[202605-202605].xlsx')
msg_xlsx.attach(xls)
msg_xlsx.attach(MIMEText(CIB_BODY, 'html', 'gbk'))
hit_xlsx, _, files_xlsx = classify_attachment_receipt(
    msg_xlsx, '某银行信用卡[202605-202605]电子账单', None, today=TODAY)
check("表格型历史账单附件也能抑制", hit_xlsx is True, hit_xlsx)
check("表格附件名正确返回", files_xlsx == ['账单[202605-202605].xlsx'], files_xlsx)

print("\n== 6. collect_quality_alerts 路由 ==")
suppressed_bill = make_bill(
    extraction_failed=True,
    failure_reason='CIBBankExtractor.extract_amount 所有模式落空（HTML 26 字节）',
    suppressed=True,
    attachment_receipt=True,
    suppress_reason='附件型历史账单回执：期次 202607',
    attachment_files=[CIB_PDF_NAME],
)
real_fail_bill = make_bill(
    subject='招商银行信用卡电子账单',
    bank_name='招商银行',
    extraction_failed=True,
    failure_reason='CMBBankExtractor.extract_amount 所有模式落空',
)
current_attach_bill = make_bill(
    subject='兴业银行信用卡[202610-202610]电子账单',
    extraction_failed=True,
    failure_reason='附件型账单，正文仅提示语',
    attachment_files=['账单[202610-202610].pdf'],
)
alerts = collect_quality_alerts(
    [suppressed_bill, real_fail_bill, current_attach_bill])

check("被抑制的回执不进 extraction_failures",
      all(f['subject'] != CIB_SUBJECT for f in alerts['extraction_failures']),
      [f['subject'] for f in alerts['extraction_failures']])
check("被抑制的回执进 attachment_bills",
      len(alerts['attachment_bills']) == 1,
      [a['subject'] for a in alerts['attachment_bills']])
check("attachment_bills 条目带 suppressed=True",
      alerts['attachment_bills'] and alerts['attachment_bills'][0]['suppressed'] is True)
check("attachment_bills 条目带附件名",
      alerts['attachment_bills'][0]['attachments'] == [CIB_PDF_NAME])
check("真失败仍在 extraction_failures（招商）",
      any(f['bank'] == '招商银行' for f in alerts['extraction_failures']))
check("当期附件型仍在 extraction_failures（不静默）",
      any(f['subject'] == '兴业银行信用卡[202610-202610]电子账单'
          for f in alerts['extraction_failures']),
      [f['subject'] for f in alerts['extraction_failures']])
check("extraction_failures 共 2 条（招商 + 当期附件型）",
      len(alerts['extraction_failures']) == 2,
      len(alerts['extraction_failures']))
check("attachment_bills 不进入 suspicious",
      alerts['suspicious'] == [])
check("attachment_bills 不进入 needs_review",
      alerts['needs_review'] == [])

alerts_empty = collect_quality_alerts([])
check("空输入仍返回全部键",
      set(alerts_empty.keys()) == {'extraction_failures', 'suspicious',
                                   'needs_review', 'email_failures',
                                   'unrecognized_subjects', 'attachment_bills'},
      sorted(alerts_empty.keys()))
check("空输入 attachment_bills 为空", alerts_empty['attachment_bills'] == [])

print("\n== 7. 端到端：兴业 YY 真实邮件形状 ==")
e2e_bill = make_bill(
    extraction_failed=True,
    failure_reason='CIBBankExtractor.extract_amount 所有模式落空（HTML 26 字节，文本无应还/金额关键词）',
    suppressed=True,
    suppress_reason='附件型历史账单回执：期次 202607',
    attachment_files=[CIB_PDF_NAME],
)
bills = [e2e_bill, make_bill(bank_name='广发银行', amounts=[{'value': 130.3, 'match': '本期账单金额表行'}],
                            due_dates=['2026-10-30']),
         make_bill(bank_name='兴业银行', amounts=[{'value': 1.0, 'match': '本期应还款总额 New Balance'}],
                   due_dates=['2026-11-20'])]
e2e_alerts = collect_quality_alerts(bills)
check("端到端：待人工提取为 0 条", len(e2e_alerts['extraction_failures']) == 0,
      e2e_alerts['extraction_failures'])
check("端到端：抑制清单 1 条", len(e2e_alerts['attachment_bills']) == 1)
check("端到端：账单封数不变（仍 3 封）", len(bills) == 3)
check("端到端：金额聚合不受影响",
      sum(a['value'] for b in bills for a in b['amounts']) == 131.3,
      sum(a['value'] for b in bills for a in b['amounts']))

print("\n== 8. check_reasonableness 闸门语义不变（P0-2）==")
from bank_extractors import BankExtractorFactory  # noqa: E402
cib = BankExtractorFactory().create_extractor('兴业银行')
gate_bill = make_bill(credit_limit=10200.0,
                      amounts=[{'value': 1.0, 'match': '本期应还款总额 New Balance'}])
cib.check_reasonableness(gate_bill)
check("小额带 match → suspicious=True（仍告警）", gate_bill.get('suspicious') is True)
check("小额文案含「提取自摘要区」",
      '提取自摘要区' in gate_bill.get('suspicious_reason', ''),
      gate_bill.get('suspicious_reason'))
check("「请人工核对」而非「疑似误提取」",
      '请人工核对' in gate_bill.get('suspicious_reason', ''))

gate_bill2 = make_bill(credit_limit=10200.0,
                       amounts=[{'value': 1.0}])
cib.check_reasonableness(gate_bill2)
check("小额无 match → 文案为「疑似误提取」",
      '疑似误提取' in gate_bill2.get('suspicious_reason', ''))

gate_bill3 = make_bill(credit_limit=10200.0,
                       amounts=[{'value': 5100.30, 'match': '本期应还款总额 New Balance'}])
cib.check_reasonableness(gate_bill3)
check("大额不触发 suspicious", gate_bill3.get('suspicious') is None)

gate_bill4 = make_bill(credit_limit=None, amounts=[{'value': 0.5}])
cib.check_reasonableness(gate_bill4)
check("额度未知不标记（保持原语义）", gate_bill4.get('suspicious') is None)

print("\n== 9. QA 增补：classify 级边界（质量复核 2026-10-27）==")
# 用例保留（QA 反例来源）。注意语义已随阈值收紧改写：
# 阈值 = 2 后，上月（202609，behind=1）不再算历史 → 必须告警、绝不抑制。
# 反例本身：招行 202609 账单按「账单日+20 天」还款日可能落在 2026-10-28，
# 若按阈值 1 抑制就会漏掉一笔即将到期的账单。
prev_subject = '兴业银行信用卡[202609-202609]电子账单'
hit_prev, why_prev, files_prev = classify_attachment_receipt(
    build_cib_like_message(subject=prev_subject), prev_subject, None, today=TODAY)
check("上月 202609 附件型回执 → 不抑制（还款日可能未到期，不得静默）",
      hit_prev is False, why_prev)
check("上月不抑制：原因文案为空，附件清单仍如实返回（供人工提取定位）",
      (why_prev, files_prev) == ('', [CIB_PDF_NAME]), (why_prev, files_prev))

# 未来期次必须保守告警（期次在未来绝不能抑制）
for period in ('202611', '202612'):
    subj = f'兴业银行信用卡[{period}-{period}]电子账单'
    h, _, _ = classify_attachment_receipt(msg_cib, subj, None, today=TODAY)
    check(f"未来期次 [{period}] → 不抑制", h is False)

# 无附件但期次历史：返回值语义（False, '', []）
h_na, w_na, f_na = classify_attachment_receipt(
    build_no_attachment_message(), CIB_SUBJECT, None, today=TODAY)
check("无附件时原因与附件列表均为空", (w_na, f_na) == ('', []), (w_na, f_na))

# 期次非法 + 有附件 → 保守告警
h_bad, _, _ = classify_attachment_receipt(
    msg_cib, '兴业银行信用卡[202607-202613]电子账单', None, today=TODAY)
check("区间结束月非法 [202607-202613] → 不抑制", h_bad is False)

# 压缩包类附件（内容未知）按账单类附件处理
msg_zip = MIMEMultipart('mixed')
z = MIMEApplication(b'PK', _subtype='zip')
z.add_header('Content-Disposition', 'attachment', filename='账单[202605-202605].zip')
msg_zip.attach(z)
msg_zip.attach(MIMEText(CIB_BODY, 'html', 'gbk'))
h_zip, _, f_zip = classify_attachment_receipt(
    msg_zip, '某银行信用卡[202605-202605]电子账单', None, today=TODAY)
check("zip 附件也按账单类附件抑制", h_zip is True and f_zip == ['账单[202605-202605].zip'])

# 全角方括号：解析不到期次 → 保守告警（记录当期限：银行改版式则噪声复发）
check("全角括号【202607-202607】解析不到期次",
      parse_statement_period('兴业银行信用卡【202607-202607】电子账单') is None)

# 特征化测试：主题含两个区间时只认第一个（已知限制，仅记录当前行为）
check("双区间主题只取第一个区间（已知限制）",
      parse_statement_period('账单[202607-202607]重发[202610-202610]') == '202607')

print("\n" + "=" * 60)
print(f"结果：{passed} 通过 / {failed} 失败（共 {passed + failed} 项）")
print("=" * 60)
sys.exit(0 if failed == 0 else 1)
