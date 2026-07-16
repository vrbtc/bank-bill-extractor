#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
import os
import sys
import traceback
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from this_month_bills import BillExtractor, get_upcoming_bills


def generate_dashboard():
    output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'gh-pages')
    os.makedirs(output_dir, exist_ok=True)

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

    # Sync to TickTick (optional, won't fail the build if errors occur)
    if bills and not extract_error:
        try:
            sync_to_ticktick(bills)
        except Exception as e:
            print(f'TickTick sync warning: {e}')

    # Push to Feishu group (optional, won't fail the build if errors occur)
    if bills and not extract_error:
        try:
            push_to_feishu(bills)
        except Exception as e:
            print(f'Feishu push warning: {e}')

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

    with open(os.path.join(output_dir, 'index.html'), 'w', encoding='utf-8') as f:
        f.write(html)

    with open(os.path.join(output_dir, 'data.json'), 'w', encoding='utf-8') as f:
        f.write(data_json)

    print(f"Dashboard generated at {output_dir}")
    print(f"Total upcoming (all): {total_all:,.2f}")
    print(f"Total upcoming (15 days): {total_15:,.2f}")
    return True


def sync_to_ticktick(bills):
    """Sync bills to TickTick. Optional - skips if API key not configured."""
    try:
        from ticktick_sync import TickTickSync
    except Exception as e:
        print(f'TickTick sync: import failed ({e}), skipping')
        return

    # Check if API key is configured
    api_key = os.environ.get('TICKTICK_API_KEY', '')
    if not api_key:
        config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.json')
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    api_key = config.get('ticktick_api_key', '')
            except Exception:
                pass

    if not api_key:
        print('TickTick sync: TICKTICK_API_KEY not configured, skipping')
        return

    print('\n--- TickTick Sync ---')
    sync = TickTickSync(api_key=api_key)

    bills_data = {
        'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'bills': bills
    }

    # Clean up old tasks first
    try:
        cleanup = sync.cleanup_old_tasks()
        print(f"  Cleaned up {cleanup['deleted']} expired tasks, {cleanup['remaining']} remaining")
    except Exception as e:
        print(f"  Cleanup warning: {e}")

    # Sync new bills
    result = sync.sync_bills(bills_data)
    if result.get('success'):
        print(f"  Created: {result['total_created']} tasks")
        print(f"  Skipped: {result['total_skipped']} (already exist)")
        if result.get('errors'):
            print(f"  Errors: {result['errors']}")
        for c in result.get('created', []):
            if 'error' not in c:
                print(f"    + {c['title']}")
            else:
                print(f"    ! {c['bank']}: {c['error']}")
    else:
        print(f"  Sync info: {result.get('message', 'unknown')}")
    print('--- TickTick Sync Done ---\n')


def push_to_feishu(bills):
    """Push bills summary to Feishu group. Optional - won't fail the build if errors occur."""
    try:
        from feishu_notify import FeishuNotifier
    except Exception as e:
        print(f'Feishu push: import failed ({e}), skipping')
        return

    # webhook URL can be overridden via env var, otherwise uses default
    webhook_url = os.environ.get('FEISHU_WEBHOOK_URL', '')

    print('\n--- Feishu Push ---')
    notifier = FeishuNotifier(webhook_url=webhook_url if webhook_url else None)

    bills_data = {
        'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'bills': bills
    }

    result = notifier.send_bills_summary(bills_data)
    print(f"  Push result: {result.get('StatusMessage', result)}")
    print('--- Feishu Push Done ---\n')


def build_html(data_json):
    return '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>银行账单仪表盘</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "PingFang SC", "Microsoft YaHei", sans-serif; background: #0f172a; color: #e2e8f0; min-height: 100vh; }
.container { max-width: 960px; margin: 0 auto; padding: 24px 16px; }
.header { text-align: center; margin-bottom: 32px; }
.header h1 { font-size: 28px; font-weight: 700; background: linear-gradient(135deg, #60a5fa, #a78bfa); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin-bottom: 8px; }
.header .subtitle { color: #94a3b8; font-size: 14px; }
.header .update-time { color: #64748b; font-size: 12px; margin-top: 4px; }
.error-banner { background: #7f1d1d; border: 1px solid #dc2626; color: #fca5a5; padding: 12px 16px; border-radius: 8px; margin-bottom: 20px; font-size: 14px; }
.stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-bottom: 32px; }
.stat-card { background: #1e293b; border-radius: 12px; padding: 20px; border: 1px solid #334155; transition: transform 0.2s; }
.stat-card:hover { transform: translateY(-2px); }
.stat-card.urgent { border-color: #dc2626; background: linear-gradient(135deg, #1e293b, #450a0a); }
.stat-card.warning { border-color: #f59e0b; background: linear-gradient(135deg, #1e293b, #451a03); }
.stat-card.attention { border-color: #eab308; }
.stat-card .label { font-size: 13px; color: #94a3b8; margin-bottom: 8px; }
.stat-card .value { font-size: 28px; font-weight: 700; }
.stat-card .value.red { color: #f87171; }
.stat-card .value.orange { color: #fb923c; }
.stat-card .value.yellow { color: #facc15; }
.stat-card .value.blue { color: #60a5fa; }
.stat-card .sub { font-size: 12px; color: #64748b; margin-top: 4px; }
.section-title { font-size: 18px; font-weight: 600; margin-bottom: 16px; display: flex; align-items: center; gap: 8px; }
.section-title .dot { width: 8px; height: 8px; border-radius: 50%; background: #60a5fa; }
.bills-list { display: flex; flex-direction: column; gap: 12px; margin-bottom: 32px; }
.bill-card { background: #1e293b; border-radius: 10px; padding: 16px 20px; border: 1px solid #334155; display: flex; justify-content: space-between; align-items: center; transition: all 0.2s; }
.bill-card:hover { border-color: #475569; }
.bill-card.status-urgent { border-left: 4px solid #dc2626; }
.bill-card.status-warning { border-left: 4px solid #f59e0b; }
.bill-card.status-attention { border-left: 4px solid #eab308; }
.bill-card.status-normal { border-left: 4px solid #22c55e; }
.bill-left { display: flex; align-items: center; gap: 16px; }
.bank-icon { width: 40px; height: 40px; border-radius: 10px; display: flex; align-items: center; justify-content: center; font-size: 18px; font-weight: 700; background: #334155; color: #94a3b8; flex-shrink: 0; }
.bill-info .bank-name { font-size: 16px; font-weight: 600; }
.bill-info .due-date { font-size: 13px; color: #94a3b8; margin-top: 2px; }
.bill-right { text-align: right; }
.bill-amount { font-size: 20px; font-weight: 700; }
.bill-days { font-size: 13px; margin-top: 2px; }
.bill-days.urgent { color: #f87171; }
.bill-days.warning { color: #fb923c; }
.bill-days.attention { color: #facc15; }
.bill-days.normal { color: #4ade80; }
.badge { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; margin-left: 8px; }
.badge.urgent { background: #dc2626; color: #fff; }
.badge.warning { background: #f59e0b; color: #000; }
.empty-state { text-align: center; padding: 48px 24px; color: #64748b; }
.empty-state .icon { font-size: 48px; margin-bottom: 12px; }
.footer { text-align: center; padding: 24px 0; color: #475569; font-size: 12px; border-top: 1px solid #1e293b; margin-top: 32px; }
@media (max-width: 600px) {
  .stats-grid { grid-template-columns: 1fr 1fr; }
  .stat-card .value { font-size: 22px; }
  .bill-card { flex-direction: column; align-items: flex-start; gap: 8px; }
  .bill-right { text-align: left; }
}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <h1>&#x1F3E6; 银行账单仪表盘</h1>
    <div class="subtitle">自动从邮箱提取，实时查看待还款账单</div>
    <div class="update-time" id="updateTime"></div>
  </div>
  <div id="errorBanner"></div>
  <div class="stats-grid" id="statsGrid"></div>
  <div class="section-title"><span class="dot"></span>近期待还款（15天内）</div>
  <div class="bills-list" id="urgentList"></div>
  <div class="section-title"><span class="dot" style="background:#475569"></span>全部待还款账单</div>
  <div class="bills-list" id="allList"></div>
  <div class="footer">银行账单自动提取系统 &middot; 数据仅供参考，请以实际账单为准</div>
</div>
<script>
const DATA = ''' + data_json + ''';

function fmt(n) { return "\u00A5" + n.toLocaleString("zh-CN", {minimumFractionDigits: 2, maximumFractionDigits: 2}); }

function render() {
  document.getElementById("updateTime").textContent = "更新时间：" + DATA.generated_at;

  if (DATA.extract_error) {
    document.getElementById("errorBanner").innerHTML = '<div class="error-banner">\u26A0\uFE0F 上次提取出现错误：' + DATA.extract_error + '</div>';
  }

  const stats = [
    { label: "3天内紧急", value: fmt(DATA.total_3), cls: "urgent", vcls: "red", sub: DATA.total_3 > 0 ? "\u26A0\uFE0F 请尽快还款" : "\u2705 无紧急账单" },
    { label: "7天内待还", value: fmt(DATA.total_7), cls: "warning", vcls: "orange", sub: DATA.banks_count_7 + " 家银行" },
    { label: "15天内待还", value: fmt(DATA.total_15), cls: "attention", vcls: "yellow", sub: DATA.banks_count_15 + " 家银行" },
    { label: "全部待还总额", value: fmt(DATA.total_all), cls: "", vcls: "blue", sub: DATA.banks_count_all + " 家银行，" + DATA.bills_count + "封账单" }
  ];

  document.getElementById("statsGrid").innerHTML = stats.map(function(s) {
    return '<div class="stat-card ' + s.cls + '"><div class="label">' + s.label + '</div><div class="value ' + s.vcls + '">' + s.value + '</div><div class="sub">' + s.sub + '</div></div>';
  }).join("");

  function billCard(b) {
    var icon = b.bank.charAt(0);
    var badge = b.days_until <= 1 ? '<span class="badge urgent">紧急</span>' : (b.days_until <= 3 ? '<span class="badge warning">注意</span>' : '');
    var daysCls = b.days_until <= 1 ? "urgent" : (b.days_until <= 3 ? "warning" : (b.days_until <= 7 ? "attention" : "normal"));
    var daysText = b.days_until === 0 ? "今天到期" : (b.days_until === 1 ? "明天到期" : b.days_until + "天后");
    return '<div class="bill-card status-' + b.status + '"><div class="bill-left"><div class="bank-icon">' + icon + '</div><div class="bill-info"><div class="bank-name">' + b.bank + badge + '</div><div class="due-date">到期日：' + b.due_date + '</div></div></div><div class="bill-right"><div class="bill-amount">' + fmt(b.amount) + '</div><div class="bill-days ' + daysCls + '">' + daysText + '</div></div></div>';
  }

  var urgentList = document.getElementById("urgentList");
  if (DATA.urgent_bills.length === 0) {
    urgentList.innerHTML = '<div class="empty-state"><div class="icon">&#x1F389;</div><div>15天内没有待还款账单</div></div>';
  } else {
    urgentList.innerHTML = DATA.urgent_bills.map(billCard).join("");
  }

  var allList = document.getElementById("allList");
  if (DATA.all_bills.length === 0) {
    allList.innerHTML = '<div class="empty-state"><div class="icon">&#x1F4ED;</div><div>暂无账单数据</div></div>';
  } else {
    allList.innerHTML = DATA.all_bills.map(billCard).join("");
  }
}

render();
</script>
</body>
</html>'''


if __name__ == "__main__":
    generate_dashboard()
