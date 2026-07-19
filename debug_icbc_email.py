#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""拉取工商银行邮件并打印关键片段，用于修复金额/还款日提取。"""

import re
import sys
from bs4 import BeautifulSoup

from config import EMAIL_ADDRESS, PASSWORD, IMAP_SERVER, IMAP_PORT
from email_client import EmailClient
from email_decoder import EmailDecoder
from bank_extractors import BankExtractorFactory


def clean_text(html):
    soup = BeautifulSoup(html or "", "html.parser")
    text = soup.get_text(separator=" ")
    text = text.replace("\xa0", " ").replace("&nbsp;", " ")
    text = text.replace("&yen;", "￥").replace("¥", "￥")
    return " ".join(text.split())


def dump_contexts(label, text, keywords, window=120):
    print(f"\n===== {label} contexts =====")
    for kw in keywords:
        for m in re.finditer(re.escape(kw), text, re.IGNORECASE):
            start = max(0, m.start() - window)
            end = min(len(text), m.end() + window)
            snippet = text[start:end]
            print(f"\n-- keyword: {kw!r} @ {m.start()} --")
            print(snippet)


def main():
    client = EmailClient(IMAP_SERVER, IMAP_PORT, EMAIL_ADDRESS, PASSWORD)
    client.connect()
    decoder = EmailDecoder()
    emails = client.fetch_emails(limit=200)
    print(f"fetched {len(emails)} emails")

    found = 0
    factory = BankExtractorFactory()
    extractor = factory.create_extractor("工商银行")

    for idx, msg in enumerate(emails, 1):
        subject = decoder.decode_mime_words(msg.get("Subject", ""))
        if not any(k in subject for k in ("工商", "ICBC", "Peony", "牡丹")):
            # also catch English-only subjects
            if "ICBC" not in subject.upper() and "Peony" not in subject:
                continue

        date = decoder.decode_mime_words(msg.get("Date", ""))
        print("\n" + "=" * 72)
        print(f"[{idx}] SUBJECT: {subject}")
        print(f"DATE: {date}")

        html_body = ""
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/html":
                    html_body = decoder.decode_html_content(part)
                    break
        else:
            if msg.get_content_type() == "text/html":
                html_body = decoder.decode_html_content(msg)

        print(f"HTML length: {len(html_body or '')}")
        text = clean_text(html_body)
        print(f"Clean text length: {len(text)}")
        print(f"Clean text head(800):\n{text[:800]}")

        keywords = [
            "本期应还",
            "New Balance",
            "应还金额",
            "最低还款",
            "到期还款",
            "Payment Due",
            "Statement Date",
            "账单日",
            "RMB",
            "￥",
            "22,212",
            "22212",
            "2,212",
            "2212",
        ]
        dump_contexts("CLEAN", text, keywords, window=150)

        # All money-like numbers near keywords
        amounts = re.findall(r"[0-9]{1,3}(?:,[0-9]{3})+\.[0-9]{2}|[0-9]+\.[0-9]{2}", text)
        print("\n===== all amount-like numbers (first 40) =====")
        print(amounts[:40])

        # HTML raw contexts (tags kept)
        dump_contexts("RAW HTML", html_body or "", [
            "本期应还", "New Balance", "到期还款", "Payment Due", "最低还款"
        ], window=250)

        bill_info = {
            "subject": subject,
            "date": date,
            "amounts": [],
            "due_dates": [],
            "bank_name": "工商银行",
        }
        full = f"{subject}\n{html_body}"
        extractor.extract_amount(full, bill_info)
        extractor.extract_due_date(full, bill_info)
        print("\n===== CURRENT EXTRACTOR RESULT =====")
        print(bill_info)

        found += 1
        if found >= 3:
            break

    client.disconnect()
    print(f"\nDone. ICBC emails dumped: {found}")
    if found == 0:
        print("WARNING: no ICBC emails found in latest 200 messages")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
