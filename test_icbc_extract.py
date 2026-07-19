#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""工商银行账单提取器单元测试（含真实牡丹卡邮件格式）"""

from bank_extractors import BankExtractorFactory, ICBCBankExtractor

# 模拟工行牡丹卡对账单的常见 HTML / 文本形态
SAMPLES = [
    {
        "name": "真实邮件格式 22,212.13/RMB + 贷记卡到期还款日",
        "html": """
        <html><body>
        <p>中国工商银行客户对账单(ICBC Peony Card Bank Statement)</p>
        <table>
          <tr><td>贷记卡到期还款日</td><td></td><td align=right>2026年7月19日</td></tr>
        </table>
        <p>账单周期 2026年06月01日—2026年06月30日 对账单生成日 2026年06月30日</p>
        <p>需 还 款 明 细 （特别提示:请按照以下账户分别还款）</p>
        <table>
          <tr><td>卡号后四位</td><td>币种</td><td>应还款额</td><td>最低还款额</td><td>信用额度</td></tr>
          <tr><td>9889(牡丹贷记卡)</td><td>人民币(本位币)</td>
              <td>22,212.13/RMB</td><td>2,221.21/RMB</td><td>80,000.00/RMB</td></tr>
          <tr><td>合计</td><td>人民币(本位币)</td>
              <td>22,212.13/RMB</td><td>2,221.21/RMB</td><td>/</td></tr>
        </table>
        </body></html>
        """,
        "expect_amount": 22212.13,
        "expect_due": "2026-07-19",
    },
    {
        "name": "标准中英双语摘要",
        "html": """
        <html><body>
        <p>中国工商银行客户对账单(ICBC Peony Card Bank Statement)</p>
        <table>
          <tr><td>账单日 Statement Date</td><td>2026/06/04</td></tr>
          <tr><td>到期还款日 Payment Due Date</td><td>2026/06/24</td></tr>
          <tr><td>信用额度 Credit Limit</td><td>RMB 50,000.00</td></tr>
          <tr><td>本期应还金额 New Balance</td><td>RMB 3,456.78</td></tr>
          <tr><td>最低还款额 Min.Payment</td><td>RMB 345.68</td></tr>
        </table>
        </body></html>
        """,
        "expect_amount": 3456.78,
        "expect_due": "2026-06-24",
    },
    {
        "name": "中文年月日 + ￥",
        "html": """
        <div>
          尊敬的客户，您的工商银行信用卡对账单如下：
          到期还款日：2026年07月22日
          本期应还金额：￥12,800.50
          最低还款额：￥1,280.05
        </div>
        """,
        "expect_amount": 12800.50,
        "expect_due": "2026-07-22",
    },
    {
        "name": "纯 New Balance 英文",
        "html": """
        <p>ICBC Peony Card Bank Statement</p>
        <p>Payment Due Date: 2026-07-15</p>
        <p>New Balance: RMB 888.00</p>
        <p>Minimum Payment: RMB 88.80</p>
        """,
        "expect_amount": 888.00,
        "expect_due": "2026-07-15",
    },
    {
        "name": "表格标签并排数值",
        "html": """
        <p>本期应还金额 New Balance 最低还款额 Min Payment</p>
        <p>RMB 2,100.00 RMB 210.00</p>
        <p>到期还款日 Payment Due Date 2026/07/10</p>
        """,
        "expect_amount": 2100.00,
        "expect_due": "2026-07-10",
    },
]


def test_upcoming_includes_due_today():
    """还款日=今天时，不应因 datetime 差值变成 -1 而漏掉"""
    from this_month_bills import get_upcoming_bills
    from datetime import datetime, timezone, timedelta

    today = datetime.now(timezone(timedelta(hours=8))).date()
    due = today.strftime("%Y-%m-%d")
    bills = [{
        "subject": "中国工商银行客户对账单(ICBC Peony Card Bank Statement)",
        "date": "Thu, 2 Jul 2026 09:19:12 +0800 (CST)",
        "amounts": [{"value": 22212.13, "currency": "CNY"}],
        "due_dates": [due],
        "bank_name": "工商银行",
    }]
    result = get_upcoming_bills(bills, days=None)
    assert "工商银行" in result, "今日到期的工行账单应进入 upcoming"
    assert abs(result["工商银行"]["total_amount"] - 22212.13) < 0.01
    assert result["工商银行"]["earliest_due_date"]["days_until"] == 0
    print("[PASS] 今日到期账单不会被过滤")


def run_tests():
    factory = BankExtractorFactory()
    extractor = factory.create_extractor("工商银行")
    assert isinstance(extractor, ICBCBankExtractor), "工厂应返回 ICBCBankExtractor"
    print(f"工厂路由 OK -> {type(extractor).__name__}\n")

    passed = 0
    for sample in SAMPLES:
        bill_info = {
            "subject": "中国工商银行客户对账单(ICBC Peony Card Bank Statement)",
            "date": "Thu, 2 Jul 2026 09:19:12 +0800 (CST)",
            "amounts": [],
            "due_dates": [],
            "bank_name": "工商银行",
        }
        text = sample["html"]
        text = extractor.preprocess_text(text)
        extractor.extract_amount(text, bill_info)
        extractor.extract_due_date(text, bill_info)

        amounts = [a["value"] for a in bill_info["amounts"]]
        dues = bill_info["due_dates"]
        ok_amt = amounts == [sample["expect_amount"]]
        ok_due = sample["expect_due"] in dues

        status = "PASS" if (ok_amt and ok_due) else "FAIL"
        print(f"[{status}] {sample['name']}")
        print(f"  amount: {amounts} (expect {sample['expect_amount']})")
        print(f"  due:    {dues} (expect {sample['expect_due']})")
        if ok_amt and ok_due:
            passed += 1
        else:
            print("  !! mismatch")

    try:
        test_upcoming_includes_due_today()
        passed += 1
        total = len(SAMPLES) + 1
    except Exception as e:
        print(f"[FAIL] 今日到期过滤测试: {e}")
        total = len(SAMPLES) + 1

    print(f"\n结果: {passed}/{total} 通过")
    return passed == total


if __name__ == "__main__":
    import sys
    sys.exit(0 if run_tests() else 1)
