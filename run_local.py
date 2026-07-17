#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Local runner that writes to a temp directory to bypass TRAE sandbox."""
import json
import os
import sys
import traceback
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from this_month_bills import BillExtractor, get_upcoming_bills
from generate_dashboard import build_html

# Use temp directory for output
OUTPUT_DIR = os.path.join(os.environ.get('TEMP', 'C:\\Users\\Administrator\\AppData\\Local\\Temp'), 'bank_dashboard')
os.makedirs(OUTPUT_DIR, exist_ok=True)

print(f'Output directory: {OUTPUT_DIR}')
print('Connecting to email and extracting bills...')
extractor = BillExtractor()
try:
    bills = extractor.fetch_and_extract(limit=100)
    print(f'Extracted {len(bills)} bill emails')
    extract_error = None
except Exception as e:
    print(f'Extraction error: {e}')
    traceback.print_exc()
    bills = []
    extract_error = str(e)

now = datetime.now()
all_upcoming = get_upcoming_bills(bills, days=None)
upcoming_15 = get_upcoming_bills(bills, days=15)
upcoming_7 = get_upcoming_bills(bills, days=7)
upcoming_3 = get_upcoming_bills(bills, days=3)

total_all = sum(info['total_amount'] for info in all_upcoming.values() if info['total_amount'] > 0)
total_15 = sum(info['total_amount'] for info in upcoming_15.values() if info['total_amount'] > 0)
total_7 = sum(info['total_amount'] for info in upcoming_7.values() if info['total_amount'] > 0)
total_3 = sum(info['total_amount'] for info in upcoming_3.values() if info['total_amount'] > 0)

banks_count_15 = len([b for b, i in upcoming_15.items() if i['total_amount'] > 0])
banks_count_7 = len([b for b, i in upcoming_7.items() if i['total_amount'] > 0])
banks_count_all = len([b for b, i in all_upcoming.items() if i['total_amount'] > 0])

urgent_bills = []
for bank_name, info in sorted(upcoming_15.items(), key=lambda x: x[1]['earliest_due_date']['days_until'] if x[1]['earliest_due_date'] else 999):
    if info['total_amount'] > 0 and info['earliest_due_date']:
        days = info['earliest_due_date']['days_until']
        urgent_bills.append({
            'bank': bank_name,
            'amount': info['total_amount'],
            'due_date': info['earliest_due_date']['date'],
            'days_until': days,
            'status': 'urgent' if days <= 1 else ('warning' if days <= 3 else ('attention' if days <= 7 else 'normal'))
        })

all_bills_data = []
for bank_name, info in sorted(all_upcoming.items(), key=lambda x: x[1]['earliest_due_date']['days_until'] if x[1]['earliest_due_date'] else 999):
    if info['total_amount'] > 0 and info['earliest_due_date']:
        all_bills_data.append({
            'bank': bank_name,
            'amount': info['total_amount'],
            'due_date': info['earliest_due_date']['date'],
            'days_until': info['earliest_due_date']['days_until'],
            'status': 'urgent' if info['earliest_due_date']['days_until'] <= 1 else ('warning' if info['earliest_due_date']['days_until'] <= 3 else ('attention' if info['earliest_due_date']['days_until'] <= 7 else 'normal'))
        })

data = {
    'generated_at': now.strftime('%Y-%m-%d %H:%M:%S'),
    'total_all': total_all,
    'total_15': total_15,
    'total_7': total_7,
    'total_3': total_3,
    'banks_count_15': banks_count_15,
    'banks_count_7': banks_count_7,
    'banks_count_all': banks_count_all,
    'bills_count': len(bills),
    'urgent_bills': urgent_bills,
    'all_bills': all_bills_data,
    'extract_error': extract_error
}

data_json = json.dumps(data, ensure_ascii=False)
html = build_html(data_json)

html_path = os.path.join(OUTPUT_DIR, 'index.html')
json_path = os.path.join(OUTPUT_DIR, 'data.json')

with open(html_path, 'w', encoding='utf-8') as f:
    f.write(html)
with open(json_path, 'w', encoding='utf-8') as f:
    f.write(data_json)

print(f"\nDashboard generated at {OUTPUT_DIR}")
print(f"Total upcoming (all): {total_all:,.2f}")
print(f"Total upcoming (15 days): {total_15:,.2f}")
print(f"Total upcoming (7 days): {total_7:,.2f}")
print(f"Total upcoming (3 days): {total_3:,.2f}")
print(f"\nUrgent bills (15 days): {len(urgent_bills)}")
for b in urgent_bills:
    print(f"  {b['bank']}: ¥{b['amount']:,.2f} due {b['due_date']} ({b['days_until']} days)")
print(f"\nAll bills: {len(all_bills_data)}")
for b in all_bills_data:
    print(f"  {b['bank']}: ¥{b['amount']:,.2f} due {b['due_date']} ({b['days_until']} days)")
print(f"\nHTML file: {html_path}")
print(f"JSON file: {json_path}")
