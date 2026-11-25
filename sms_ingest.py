#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
短信接入常驻入口（sms_ingest.py）

架构（交接文档 2026-11-25）：
- 163 专用短信邮箱（config.json 的 sms_mail，不进 emails 数组，账单链路扫不到）
- 163 实测不支持 IMAP IDLE（capabilities 无 IDLE）→ 60 秒轮询 SEARCH UNSEEN，
  延迟约 1 分钟，满足 1-5 分钟目标
- 去重：Message-ID（缺失时用正文哈希），跨轮次持久化于 sms_state.json
- 解析：sms_rules.parse_sms（未命中的银行短信 → 复核队列 + 飞书告警）
- 状态：card_state.json（卡）/ loan_state（贷款，同文件内 loans 键）
- 事件：sms_events.jsonl append-only（验证码原文绝不落盘）
- 推送：OTP → WxPusher 即时私聊；复核/心跳 → 飞书群卡片（自带 event_id 去重）

运行：py -3.11 sms_ingest.py   （Ctrl+C 停止；可配合任务计划常驻）
"""
import sys
import os
import json
import time
import hashlib
import traceback
import datetime
import email as email_lib
from email.header import decode_header, make_header

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from email_client import EmailClient
from sms_rules import (
    parse_sms, apply_to_card_state, identify_bank,
    is_otp_like, extract_otp_code,
    CATEGORY_BILL, CATEGORY_REPAYMENT, CATEGORY_LIMIT, CATEGORY_OTP,
    CATEGORY_LOAN, CATEGORY_IGNORED, CATEGORY_REVIEW,
)
from config import _load_config_file

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CARD_STATE_PATH = os.path.join(BASE_DIR, 'card_state.json')
SMS_EVENTS_PATH = os.path.join(BASE_DIR, 'sms_events.jsonl')
SMS_STATE_PATH = os.path.join(BASE_DIR, 'sms_state.json')
CARDS_YAML_PATH = os.path.join(BASE_DIR, 'cards.yaml')

POLL_INTERVAL = 15          # 秒；163 无 IDLE，轮询即延迟上限。2026-11-25 从
                            # 60s 降至 15s（OTP 场景），长连接复用 + 轻量 SEARCH
HEARTBEAT_HOURS = 24        # 超过 24h 无任何转发邮件 → 飞书心跳告警
MAX_PROCESSED_MIDS = 5000   # 去重表上限（超出裁剪最旧）
RECENT_SCAN_WINDOW = 200    # 每轮扫描最近 200 封（Message-ID 去重后跳过旧邮件）

BJ_TZ = datetime.timezone(datetime.timedelta(hours=8))


def now_bj():
    return datetime.datetime.now(BJ_TZ)


def now_iso():
    return now_bj().isoformat(timespec='seconds')


# ---------- 状态读写 ----------

def load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f'WARN: 读取 {os.path.basename(path)} 失败: {e}')
    return default


def save_json(path, data):
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def append_event(record):
    with open(SMS_EVENTS_PATH, 'a', encoding='utf-8') as f:
        f.write(json.dumps(record, ensure_ascii=False) + '\n')


def load_cards_registry():
    """加载 cards.yaml 登记表。返回 {bank: [card_dict, ...]}。"""
    if not os.path.exists(CARDS_YAML_PATH):
        return {}
    try:
        import yaml
        data = yaml.safe_load(open(CARDS_YAML_PATH, 'r', encoding='utf-8')) or {}
    except Exception as e:
        print(f'WARN: cards.yaml 解析失败: {e}')
        return {}
    reg = {}
    for c in data.get('cards', []):
        reg.setdefault(c.get('bank', ''), []).append(c)
    return reg


# ---------- 邮件解析 ----------

def _decode(s):
    try:
        return str(make_header(decode_header(s or '')))
    except Exception:
        return s or ''


def extract_email_body(msg):
    """提取邮件正文文本（text/plain 优先，text/html 去 HTML 标签兜底）。"""
    bodies = []

    def _walk(m):
        ctype = m.get_content_type()
        if m.is_multipart():
            for p in m.get_payload():
                _walk(p)
        elif ctype == 'text/plain':
            payload = m.get_payload(decode=True)
            if payload:
                charset = m.get_content_charset() or 'utf-8'
                bodies.append((0, payload.decode(charset, errors='replace')))
        elif ctype == 'text/html':
            payload = m.get_payload(decode=True)
            if payload:
                charset = m.get_content_charset() or 'utf-8'
                html = payload.decode(charset, errors='replace')
                bodies.append((1, _strip_html(html)))

    _walk(msg)
    if not bodies:
        return ''
    bodies.sort(key=lambda x: x[0])
    return bodies[0][1].strip()


def _strip_html(html):
    try:
        from bs4 import BeautifulSoup
        text = BeautifulSoup(html, 'html.parser').get_text(separator='\n')
    except Exception:
        import re as _re
        text = _re.sub(r'<[^>]+>', '\n', html)
    # 压缩空白（保留换行，银行短信可能多段）
    lines = [ln.strip() for ln in text.splitlines()]
    return '\n'.join(ln for ln in lines if ln)


def sms_text_from_email(subject, body):
    """从邮件主题+正文拼出短信候选文本。

    iOS 快捷指令转发常见两种排布：主题=发件号码+正文=短信全文，或全文在主题。
    正文非空优先用正文；正文为空则用主题。若正文不含银行名而主题含号码/银行名，
    把主题作为首行并入候选（提升银行识别率）。
    """
    body = (body or '').strip()
    subject = (subject or '').strip()
    if body and identify_bank(body):
        return body
    if body and '信用卡' in body:
        return body
    if subject and not body:
        return subject
    if subject and identify_bank(subject) and not identify_bank(body):
        return subject + '\n' + body
    return body or subject


# ---------- OTP / 告警推送 ----------

def _post_json(url, payload, timeout=10):
    """POST JSON，返回 bool。用于 OTP 双渠道推送（WxPusher + 飞书）。"""
    import urllib.request
    try:
        req = urllib.request.Request(
            url, data=json.dumps(payload).encode('utf-8'),
            headers={'Content-Type': 'application/json'}, method='POST')
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status == 200
    except Exception as e:
        print(f'WARN: 推送请求失败 {url.split("/")[2]}: {type(e).__name__}')
        return False


def push_otp_content(bank, last4, raw_text, code, email_from):
    """验证码双渠道推送（2026-11-25 用户配置）：
    1) WxPusher（otp_wxpusher_app_token → 安卓 UID + 苹果 UID）
    2) 飞书工作通知机器人（otp_feishu_webhook_url）
    只推送，不落盘不写日志（码本体只出现在推送请求里，发完即弃）。"""
    tail = f"（尾号{last4}）" if last4 else ''
    head = bank or ''
    if code:
        content = f"🔐 {head}{tail} 验证码：{code}（5分钟内有效）"
        summary = f"验证码 {head}".strip()
    else:
        content = f"❓ {head}{tail} 疑似验证码短信（未提取到码）：\n{(raw_text or '')[:150]}"
        summary = f"疑似验证码 {head}".strip()

    cfg = _load_config_file()
    ok = False
    token = cfg.get('otp_wxpusher_app_token') or cfg.get('wxpusher_app_token')
    uids = cfg.get('otp_wxpusher_uids') or cfg.get('wxpusher_uids') or []
    if token and uids:
        ok |= _post_json('https://wxpusher.zjiecode.com/api/send/message', {
            'appToken': token, 'content': content, 'summary': summary,
            'contentType': 1, 'uids': uids,
        })
    hook = cfg.get('otp_feishu_webhook_url') or cfg.get('feishu_webhook_url')
    if hook:
        ok |= _post_json(hook, {'msg_type': 'text', 'content': {'text': content}})
    if not ok:
        print(f'WARN: OTP 推送失败（两渠道均未成功）{type(email_from).__name__}')
    return ok


def push_otp(parsed, email_from):
    """严格 OTP（已提取到码）推送入口。"""
    return push_otp_content(parsed.bank, parsed.last4, None, parsed.otp_code, email_from)


def push_review_alert(events, dedup_key):
    """复核队列 → 飞书群卡片。feishu_notify.send_extraction_alerts 无去重，
    这里按日 + dedup_key 自带去重（文档第 6 节要求）。"""
    if not events:
        return
    state = load_json(SMS_STATE_PATH, {})
    today = now_bj().strftime('%Y-%m-%d')
    alerted = state.get('review_alerted', {})
    if alerted.get(dedup_key) == today:
        return  # 今日已提醒过同类
    try:
        from feishu_notify import FeishuNotifier
        notifier = FeishuNotifier()
        lines = []
        for ev in events[:10]:
            lines.append(f"• {ev['bank'] or '未知银行'}｜{ev['subject'][:40]}｜"
                         f"{ev['review_reason']}（置信度 {ev['confidence']}）")
        text = (f"⚠️ 短信规则未命中待复核（{len(events)} 条，今日去重）\n"
                + '\n'.join(lines)
                + "\n\n请人工补充 sms_rules.py 模板后，将短信正文样本发到复核。")
        notifier.send_text(text)
        alerted.setdefault(dedup_key, today)
        state['review_alerted'] = alerted
        save_json(SMS_STATE_PATH, state)
    except Exception as e:
        print(f'WARN: 复核告警推送失败: {type(e).__name__}: {e}')


def check_heartbeat():
    """心跳告警：超过 24 小时没有任何转发邮件 → 飞书告警（每日最多一次）。"""
    state = load_json(SMS_STATE_PATH, {})
    last_ev = state.get('last_event_ts')
    if not last_ev:
        return  # 尚无基线（首次运行），不告警
    try:
        delta = now_bj() - datetime.datetime.fromisoformat(last_ev)
    except ValueError:
        return
    if delta < datetime.timedelta(hours=HEARTBEAT_HOURS):
        return
    today = now_bj().strftime('%Y-%m-%d')
    if state.get('heartbeat_alerted') == today:
        return
    try:
        from feishu_notify import FeishuNotifier
        notifier = FeishuNotifier()
        notifier.send_text(
            f"❗短信转发心跳中断：距上一封转发邮件已 {int(delta.total_seconds() // 3600)} 小时"
            f"（> {HEARTBEAT_HOURS}h）。请检查 iPhone 快捷指令自动化是否失效"
            f"（锁屏/低电量/专注模式/iOS 升级都可能中断）。")
        state['heartbeat_alerted'] = today
        save_json(SMS_STATE_PATH, state)
        print(f'HEARTBEAT ALERT: {int(delta.total_seconds() // 3600)}h 无事件，已告警')
    except Exception as e:
        print(f'WARN: 心跳告警推送失败: {type(e).__name__}: {e}')


# ---------- 核心处理 ----------

def match_card(parsed, registry):
    """按 bank+last4 匹配 cards.yaml 登记。返回 (card, is_registered)。
    尾号未登记但银行已登记 → 取该银行第一张启用卡（单卡用户常见情形）。"""
    cards = registry.get(parsed.bank or '', [])
    if not cards:
        return None, False
    if parsed.last4:
        for c in cards:
            if str(c.get('last4') or '') == parsed.last4:
                return c, True
    enabled = [c for c in cards if c.get('sms_enabled')]
    if len(enabled) == 1:
        return enabled[0], True
    if len(cards) == 1:
        return cards[0], True
    return None, True  # 多卡且无法定位尾号


def process_email(msg, registry, card_state_doc):
    """处理单封转发邮件。返回事件 dict（已决定是否落盘/推送）。"""
    subject = _decode(msg.get('Subject', ''))
    from_ = _decode(msg.get('From', ''))
    mid = (msg.get('Message-ID') or '').strip()
    date_hdr = msg.get('Date', '')
    body = extract_email_body(msg)
    text = sms_text_from_email(subject, body)

    # 事件 ID：Message-ID 优先，缺失用内容哈希（到达分钟粒度防重放）
    if mid:
        event_id = hashlib.sha1(mid.encode('utf-8')).hexdigest()[:20]
    else:
        minute = now_bj().strftime('%Y%m%d%H%M')
        event_id = hashlib.sha1((from_ + text + minute).encode('utf-8')).hexdigest()[:20]

    parsed = parse_sms(text)
    ts = now_iso()

    ev = {
        'event_id': event_id,
        'ts': ts,
        'date_hdr': date_hdr[:60],
        'subject': subject[:120],
        'from': from_[:80],
        'category': parsed.category,
        'bank': parsed.bank,
        'last4': parsed.last4,
        'fields': parsed.fields,
        'confidence': parsed.confidence,
        # 注意：otp_code 绝不写入事件日志
    }
    if parsed.category == CATEGORY_REVIEW:
        ev['review_reason'] = parsed.review_reason

    # OTP：立即推送（原文不进任何持久化存储）
    if parsed.category == CATEGORY_OTP and parsed.otp_code:
        ev['otp_pushed'] = push_otp(parsed, from_)
        # ev 不含码本体
        return ev

    # 广谱验证码（2026-11-25 用户规则）：非 OTP 分类但疑似验证码 → 双渠道加推。
    # 不 return：扣款/贷款类仍继续走状态机更新（推送与状态更新互不影响）。
    if parsed.category != CATEGORY_OTP and is_otp_like(text):
        ev['otp_like'] = True
        ev['otp_pushed'] = push_otp_content(parsed.bank, parsed.last4,
                                            text, extract_otp_code(text), from_)

    # 状态更新（bill/limit/repayment/loan）
    if parsed.category in (CATEGORY_BILL, CATEGORY_REPAYMENT, CATEGORY_LIMIT, CATEGORY_LOAN):
        card, is_registered = match_card(parsed, registry)
        if card is not None and card.get('sms_enabled') is False:
            ev['state_action'] = 'skipped-sms-disabled'
        else:
            if parsed.category == CATEGORY_LOAN:
                key = f"loan|{parsed.bank}|{parsed.fields.get('loan_note', '')}"
                state_entry = card_state_doc.setdefault('loans', {}).setdefault(key, {})
            else:
                key = f"{parsed.bank}|{parsed.last4 or ''}"
                state_entry = card_state_doc.setdefault('cards', {}).setdefault(key, {})
                state_entry.setdefault('registered', is_registered)
            changed, why = apply_to_card_state(state_entry, parsed, ts, event_id)
            ev['state_key'] = key
            ev['state_changed'] = changed
            if not changed:
                ev['state_action'] = why
            if not is_registered and parsed.category == CATEGORY_LIMIT:
                ev['unregistered_card'] = True
            # 逾期重点提醒（2026-11-25 用户要求）：飞书群红色告警
            if parsed.fields.get('overdue') and parsed.category == CATEGORY_LOAN:
                ev['overdue_alert'] = push_overdue_alert(parsed)
    elif parsed.category == CATEGORY_IGNORED:
        ev['ignored'] = True

    return ev


def push_overdue_alert(parsed):
    """贷款/信用卡逾期 → 飞书群重点告警（内容不含完整短信原文，只含要点）。"""
    try:
        from feishu_notify import FeishuNotifier
        notifier = FeishuNotifier()
        tail = f"（尾号{parsed.last4}）" if parsed.last4 else ''
        amt = parsed.fields.get('amount')
        amt_s = f" ¥{amt}" if amt is not None else ''
        text = (f"❗❗ 贷款/账单逾期提醒\n"
                f"{parsed.bank or '未知机构'}{tail}{amt_s}\n"
                f"来源：短信（{now_iso()}）。请立即核对还款。")
        notifier.send_text(text)
        return True
    except Exception as e:
        print(f'WARN: 逾期告警推送失败: {type(e).__name__}: {e}')
        return False


def run_once(client_holder, registry, card_state_doc):
    """单轮轮询。返回 (review_events, processed_any)。连接异常时重连。"""
    try:
        mail = client_holder.get('client') and client_holder['client'].mail
        if mail is None:
            sms_cfg = _load_config_file().get('sms_mail', {})
            client = EmailClient(sms_cfg.get('imap_server'), sms_cfg.get('imap_port', 993),
                                 sms_cfg.get('address'), sms_cfg.get('password'))
            client.connect()
            client_holder['client'] = client
            mail = client.mail

        mail.select('INBOX')
        # 关键：不依赖 UNSEEN（用户网页邮箱查看会把邮件标成已读，导致漏单）。
        # 改为全量拉最近邮件 + Message-ID 对 processed_mids 去重（2026-11-25 实测教训）
        typ, data = mail.search(None, 'ALL')
        if typ != 'OK':
            raise RuntimeError(f'SEARCH ALL failed: {typ}')
        ids = data[0].split() if data and data[0] else []
        ids = ids[-RECENT_SCAN_WINDOW:]
    except Exception as e:
        print(f'WARN: IMAP 连接异常，下轮重连: {type(e).__name__}: {e}')
        try:
            c = client_holder.get('client')
            if c:
                c.disconnect()
        except Exception:
            pass
        client_holder.clear()
        return [], False

    if not ids:
        print(f"[{now_bj().strftime('%H:%M:%S')}] 轮询：邮箱为空")
        return [], False

    state = load_json(SMS_STATE_PATH, {})
    processed = set(state.get('processed_mids', []))
    review_events = []
    processed_any = False
    new_count = 0
    counts = {}

    for eid in ids:
        try:
            typ, msg_data = mail.fetch(eid, '(BODY.PEEK[])')
            raw = None
            for part in msg_data:
                if isinstance(part, tuple):
                    raw = part[1]
                    break
            if raw is None:
                continue
            msg = email_lib.message_from_bytes(raw)
            mid = (msg.get('Message-ID') or '').strip()
            # 去重：Message-ID（缺失时回退内容哈希）已处理过 → 跳过
            dedup_key = mid if mid else 'hash:' + hashlib.sha1(
                ((msg.get('From') or '') + (msg.get('Date') or '')).encode('utf-8')).hexdigest()[:20]
            if dedup_key in processed:
                continue

            ev = process_email(msg, registry, card_state_doc)
            counts[ev['category']] = counts.get(ev['category'], 0) + 1
            append_event(ev)
            processed.add(dedup_key)
            new_count += 1
            if ev['category'] == CATEGORY_REVIEW:
                review_events.append(ev)
            processed_any = True
            print(f"[{now_bj().strftime('%H:%M:%S')}] {ev['category']:9s} "
                  f"{ev.get('bank') or '-':6s} {ev['subject'][:40]}"
                  + (f" → {ev.get('fields')}" if ev.get('fields') else ''))
            # 顺手标已读（仅提示用，处理不依赖它）
            try:
                mail.store(eid, '+FLAGS', '(\\Seen)')
            except Exception:
                pass
        except Exception as e:
            print(f'WARN: 处理邮件 {eid} 失败: {type(e).__name__}: {e}')
            traceback.print_exc(limit=2)

    # 去重表裁剪 + 心跳更新
    proc_list = sorted(processed)[-MAX_PROCESSED_MIDS:]
    state['processed_mids'] = proc_list
    state['last_poll_ts'] = now_iso()
    if processed_any:
        state['last_event_ts'] = now_iso()
        save_json(SMS_STATE_PATH, state)
        # 状态文件落盘（含 loans）
        card_state_doc['updated_at'] = now_iso()
        save_json(CARD_STATE_PATH, card_state_doc)
        # 可用额度 → 现金流日历（credit-card-planner limits.json）推送。
        # 内容未变化时脚本内部自动跳过提交；失败不影响短信主链路。
        try:
            from push_limits_to_planner import push_limits
            push_limits(reason='sms')
        except Exception as e:
            print(f'WARN: limits 推送异常: {type(e).__name__}: {e}')
    else:
        save_json(SMS_STATE_PATH, state)

    if new_count:
        print(f"[{now_bj().strftime('%H:%M:%S')}] 本轮新邮件 {new_count} 封: {counts}")
    else:
        print(f"[{now_bj().strftime('%H:%M:%S')}] 轮询正常（窗口 {len(ids)} 封，无新邮件）")
    return review_events, processed_any


def main():
    once = '--once' in sys.argv
    print(f'=== RBANK 短信接入启动 {now_iso()} ===')
    if not once:
        print(f'轮询间隔 {POLL_INTERVAL}s（163 无 IMAP IDLE，实测 capabilities 确认）')
    registry = load_cards_registry()
    card_state_doc = load_json(CARD_STATE_PATH, {'cards': {}, 'loans': {}})
    print(f'卡片登记: {sum(len(v) for v in registry.values())} 张；'
          f'已有状态: {len(card_state_doc.get("cards", {}))} 卡 / '
          f'{len(card_state_doc.get("loans", {}))} 贷款')

    client_holder = {}
    review_buffer = []
    poll_count = 0
    while True:
        try:
            review_events, _ = run_once(client_holder, registry, card_state_doc)
            if review_events:
                review_buffer.extend(review_events)
            poll_count += 1
            # 每 10 轮（约 10 分钟）集中推送一次复核告警（自带日级去重）
            if review_buffer and (poll_count % 10 == 0 or once):
                push_review_alert(review_buffer, 'review_queue')
                review_buffer = []
            # 心跳检查（每轮）
            check_heartbeat()
            if once:
                print('=== 单轮测试完成（--once）===')
                break
        except KeyboardInterrupt:
            print('收到停止信号，退出')
            break
        except Exception as e:
            print(f'ERROR: 主循环异常: {type(e).__name__}: {e}')
            traceback.print_exc(limit=3)
            if once:
                sys.exit(1)
        if once:
            break
        try:
            time.sleep(POLL_INTERVAL)
        except KeyboardInterrupt:
            print('收到停止信号，退出')
            break


if __name__ == '__main__':
    main()
