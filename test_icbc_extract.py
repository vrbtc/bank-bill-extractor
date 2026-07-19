#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""工商银行账单提取器单元测试"""

from bank_extractors import BankExtractorFactory, ICBCBankExtractor

# 模拟工行牡丹卡对账单的常见 HTML / 文本形态
SAMPLES = [
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
    {
        "name": "用户确认金额 2212.13",
        "html": """
        <html><body>
        <p>中国工商银行客户对账单(ICBC Peony Card Bank Statement)</p>
        <p>到期还款日 Payment Due Date 2026/07/24</p>
        <p>本期应还金额 New Balance RMB 2,212.13</p>
        <p>最低还款额 Min.Payment RMB 221.21</p>
        </body></html>
        """,
        "expect_amount": 2212.13,
        "expect_due": "2026-07-24",
    },
]


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

    print(f"\n结果: {passed}/{len(SAMPLES)} 通过")
    return passed == len(SAMPLES)


if __name__ == "__main__":
    import sys
    sys.exit(0 if run_tests() else 1)
