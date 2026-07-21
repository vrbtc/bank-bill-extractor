#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
import os
import sys
import traceback
from datetime import datetime, timezone, timedelta

# 北京时区（UTC+8），用于 generated_at 显示，避免 GitHub Actions runner 的 UTC 误读
BJ_TZ = timezone(timedelta(hours=8))

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

    # Push today's all TickTick tasks to Feishu group (optional, won't fail the build if errors occur)
    # 注意：现在推送的是今日所有代办（从 TickTick 拉取），不再依赖账单数据
    try:
        push_to_feishu()
    except Exception as e:
        print(f'Feishu push warning: {e}')

    now = datetime.now(BJ_TZ)  # 北京时间，避免 runner UTC
    all_upcoming = get_upcoming_bills(bills, days=None)
    upcoming_15 = get_upcoming_bills(bills, days=15)
    upcoming_7 = get_upcoming_bills(bills, days=7)
    upcoming_3 = get_upcoming_bills(bills, days=3)

    # 过滤已在滴答清单完成的银行：
    # 调用 TickTick API 拉取"信用卡还款"项目所有未完成任务标题，
    # 凡是 bills 里有但 TickTick 里没有对应任务的银行 = 用户已完成 → 从仪表盘移除
    # 云端 runner 没有 completed_titles.json，这是唯一能让云端感知完成状态的方式
    try:
        active_titles = _get_active_ticktick_titles()
        if active_titles:
            completed = set()
            completed |= _filter_completed_banks(all_upcoming, active_titles)
            _filter_completed_banks(upcoming_15, active_titles)
            _filter_completed_banks(upcoming_7, active_titles)
            _filter_completed_banks(upcoming_3, active_titles)
            if completed:
                print(f"Filtered {len(completed)} completed banks from dashboard: {completed}")
    except Exception as e:
        print(f"TickTick completed-filter warning: {e}")

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


def _get_active_ticktick_titles():
    """从 TickTick 拉取"信用卡还款"项目所有未完成任务标题集合。

    用于感知用户已完成的银行：凡是在 bills 里有但 TickTick 里
    没有对应任务的银行 = 用户已完成（或删除）→ 仪表盘不显示。

    云端 runner 没有 completed_titles.json 本地文件，这是唯一能让云端
    感知完成状态的方式。
    """
    api_key = os.environ.get('TICKTICK_API_KEY', '').strip()
    if not api_key:
        config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.json')
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    api_key = json.load(f).get('ticktick_api_key', '').strip()
            except Exception:
                pass
    if not api_key:
        return set()

    from ticktick_api import TickTickAPI
    api = TickTickAPI(api_key=api_key)
    project_id = api.find_or_create_project("信用卡还款")
    tasks = api.get_project_tasks(project_id)
    return {t.get("title", "") for t in tasks}


def _filter_completed_banks(upcoming_dict, active_titles):
    """从 upcoming_dict 里删除已在 TickTick 完成的银行（原地修改）。

    匹配规则：用银行全称+总额构造任务标题 `💳 {abbr} {total:.2f} 元`，
    如果该标题不在 active_titles 里，视为用户已完成。

    Returns:
        set[str]: 被移除的银行名集合
    """
    from ticktick_sync import TickTickSync
    to_remove = []
    for bank_name, info in upcoming_dict.items():
        total = info.get('total_amount', 0)
        if total <= 0:
            continue
        abbr = TickTickSync._bank_abbr(bank_name)
        title = f"💳 {abbr} {total:.2f} 元"
        if title not in active_titles:
            to_remove.append(bank_name)
    for bank_name in to_remove:
        del upcoming_dict[bank_name]
    return set(to_remove)


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

    # 云端 runner 没有本地 ticktick_completed_titles.json，
    # 无法感知用户在滴答清单里手动完成的任务，若对逾期账单也同步会重建已完成的任务。
    # 所以云端只处理「未来账单」（days_until >= 0），逾期账单交给本地 daily_run.py 处理。
    today_bj = datetime.now(BJ_TZ).date()
    future_bills = []
    skipped_overdue = 0
    for bill in bills:
        bank = bill.get('bank_name', '')
        has_future = False
        for dd in bill.get('due_dates', []):
            try:
                d = datetime.strptime(str(dd).replace('/', '-'), '%Y-%m-%d').date()
                if (d - today_bj).days >= 0:
                    has_future = True
                    break
            except Exception:
                pass
        if has_future:
            future_bills.append(bill)
        else:
            skipped_overdue += 1
    if skipped_overdue:
        print(f"  Skipped {skipped_overdue} overdue bills (云端不处理逾期账单，交给本地 daily_run.py)")

    bills_data = {
        'generated_at': datetime.now(BJ_TZ).strftime('%Y-%m-%d %H:%M:%S'),
        'bills': future_bills
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
        print(f"  Updated: {result.get('total_updated', 0)} (reminder time fix)")
        if result.get('errors'):
            print(f"  Errors: {result['errors']}")
        for c in result.get('created', []):
            if 'error' not in c:
                print(f"    + {c['title']}")
            else:
                print(f"    ! {c['bank']}: {c['error']}")
        for u in result.get('updated', []):
            print(f"    ↻ {u['title']} (reminder updated)")
    else:
        print(f"  Sync info: {result.get('message', 'unknown')}")
    print('--- TickTick Sync Done ---\n')


def push_to_feishu():
    """Push today's all TickTick tasks to Feishu group.

    现在推送的是今日所有代办（从 TickTick 拉取），不再仅是账单汇总。
    账单任务作为代办的一部分自然包含在内。
    需要 TICKTICK_API_KEY 和 FEISHU_WEBHOOK_URL。
    """
    try:
        from feishu_notify import FeishuNotifier
    except Exception as e:
        print(f'Feishu push: import failed ({e}), skipping')
        return

    webhook_url = os.environ.get('FEISHU_WEBHOOK_URL', '').strip()
    if not webhook_url:
        print('Feishu push: FEISHU_WEBHOOK_URL not configured, skipping')
        return

    # 需要 TICKTICK_API_KEY 来拉取今日代办
    api_key = os.environ.get('TICKTICK_API_KEY', '').strip()
    if not api_key:
        config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.json')
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    api_key = json.load(f).get('ticktick_api_key', '').strip()
            except Exception:
                pass

    if not api_key:
        print('Feishu push: TICKTICK_API_KEY not configured, cannot fetch today tasks, skipping')
        return

    print('\n--- Feishu Push (代办提醒) ---')
    notifier = FeishuNotifier(webhook_url=webhook_url)

    # 按北京时间小时区分推送范围：
    #   上午运行（hour < 14，对应 11:00 cron）→ 推送未来 4 天待办（含今天+明天+后天+大后天）
    #   下午运行（hour >= 14，对应 17:00 cron）→ 只推送今日到期 + 逾期（紧急提醒）
    now_bj_hour = datetime.now(BJ_TZ).hour
    if now_bj_hour < 14:
        days = 4
        print(f"  模式：上午（北京 {now_bj_hour} 时）→ 推送未来 4 天待办")
    else:
        days = 1
        print(f"  模式：下午（北京 {now_bj_hour} 时）→ 推送今日 + 逾期紧急提醒")

    result = notifier.send_today_tasks(api_key=api_key, days=days)
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
    <div class="subtitle">定时从邮箱提取（每日 11:00 / 17:00 北京时间），查看待还款账单</div>
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
  document.getElementById("updateTime").textContent = "更新时间：" + DATA.generated_at + "（北京时间）";

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
