#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""可用额度 → 现金流日历（credit-card-planner）推送脚本。

链路：本地 card_state.json（gitignore）+ cards.yaml（total_limit 登记值）
  → 脱敏 limits.json（仅 bank/last4/available_limit/total_limit/event_ts/source）
  → GitHub Contents API 提交到 vrbtc/credit-card-planner（public Pages 站）

说明：
- 云端 runner 没有 card_state.json（bank-bill-extractor 的 data.json 里
  sms_cards 恒为空），所以只能由本地推送，planner 站前端 fetch limits.json。
- 内容与远端一致时自动跳过提交（sha 比对），可放心高频调用。
- token 从 config.json 的 github_token 读取（config.json 已 gitignore），
  绝不写进任何 git 跟踪文件。

用法：
  py -3.11 push_limits_to_planner.py            # 推送到 GitHub
  py -3.11 push_limits_to_planner.py --local    # 只写本地 planner 克隆（测试用）
  py -3.11 push_limits_to_planner.py --dry-run  # 只打印，不写不推
"""
import base64
import json
import os
import sys
import urllib.error
import urllib.request

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CARD_STATE_PATH = os.path.join(BASE_DIR, 'card_state.json')
CARDS_YAML_PATH = os.path.join(BASE_DIR, 'cards.yaml')

PLANNER_LOCAL = r'D:\RTRAECODE\credit-card-planner'


def load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f'WARN: 读取 {os.path.basename(path)} 失败: {e}')
    return default


def build_limits_doc():
    """card_state.json + cards.yaml → 脱敏 limits 文档。无可用额度数据返回 None。"""
    state = load_json(CARD_STATE_PATH, {})
    total_by_key = {}
    if os.path.exists(CARDS_YAML_PATH):
        try:
            import yaml
            ydoc = yaml.safe_load(open(CARDS_YAML_PATH, 'r', encoding='utf-8')) or {}
            for c in ydoc.get('cards', []):
                total_by_key[f"{c.get('bank', '')}|{str(c.get('last4') or '')}"] = c.get('total_limit')
        except Exception as e:
            print(f'WARN: cards.yaml 解析失败: {e}')

    cards = []
    for key, st in (state.get('cards') or {}).items():
        if st.get('available_limit') is None:
            continue  # 建行2504 等暂无数据的卡不推送
        cards.append({
            'bank': st.get('bank') or key.split('|')[0],
            'last4': st.get('last4') or '',
            'available_limit': st.get('available_limit'),
            'total_limit': total_by_key.get(key),
            'event_ts': st.get('event_ts'),
            'source': st.get('source'),
        })
    if not cards:
        return None
    return {
        'updated_at': state.get('updated_at'),
        'source': 'RBANK sms ingest auto push',
        'cards': cards,
    }


def gh_api(repo, token, method, path, payload=None):
    url = f'https://api.github.com/repos/{repo}/contents/{path}'
    data = json.dumps(payload).encode('utf-8') if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        'Authorization': f'Bearer {token}',
        'Accept': 'application/vnd.github+json',
        'User-Agent': 'rbank-limits-push',
        'Content-Type': 'application/json',
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='replace')[:300]
        return e.code, {'message': body}


def push_limits(reason='manual', dry_run=False, local_only=False):
    """推送 limits.json。内容未变化时跳过。返回 'pushed'/'skipped'/'local'/None。"""
    doc = build_limits_doc()
    if not doc:
        print('push_limits: card_state.json 无可用额度数据，跳过')
        return None
    content = json.dumps(doc, ensure_ascii=False, indent=2) + '\n'
    print(f'push_limits[{reason}]: {len(doc["cards"])} 卡 · updated_at={doc["updated_at"]}')

    if dry_run:
        for c in doc['cards']:
            print(f'  {c["bank"]} ****{c["last4"]}  可用={c["available_limit"]}  总额={c["total_limit"]}  ({c["source"]})')
        return None

    if local_only:
        os.makedirs(PLANNER_LOCAL, exist_ok=True)
        with open(os.path.join(PLANNER_LOCAL, 'limits.json'), 'w', encoding='utf-8') as f:
            f.write(content)
        print(f'push_limits: 已写本地 {os.path.join(PLANNER_LOCAL, "limits.json")}')
        return 'local'

    cfg = load_json(os.path.join(BASE_DIR, 'config.json'), {})
    token = cfg.get('github_token')
    repo = cfg.get('planner_repo', 'vrbtc/credit-card-planner')
    branch = cfg.get('planner_branch', 'master')
    if not token:
        print('push_limits: config.json 缺 github_token，跳过')
        return None

    # 取远端 sha + 比对内容
    status, remote = gh_api(repo, token, 'GET', 'limits.json?ref=' + branch)
    if status == 200:
        remote_content = base64.b64decode(remote.get('content') or '').decode('utf-8')
        if remote_content.strip() == content.strip():
            print('push_limits: 远端内容一致，跳过提交')
            return 'skipped'
        sha = remote.get('sha')
    elif status == 404:
        sha = None
    else:
        print(f'push_limits: 读取远端失败 HTTP {status}: {remote.get("message", "")}')
        return None

    payload = {
        'message': f'limits: 可用额度自动同步 {doc.get("updated_at", "")} ({reason})',
        'content': base64.b64encode(content.encode('utf-8')).decode('ascii'),
        'branch': branch,
    }
    if sha:
        payload['sha'] = sha
    status, resp = gh_api(repo, token, 'PUT', 'limits.json', payload)
    if status in (200, 201):
        print(f'push_limits: 提交成功 commit={resp.get("commit", {}).get("sha", "")[:10]}')
        return 'pushed'
    print(f'push_limits: 提交失败 HTTP {status}: {resp.get("message", "")}')
    return None


if __name__ == '__main__':
    push_limits(
        reason='cli',
        dry_run='--dry-run' in sys.argv,
        local_only='--local' in sys.argv,
    )
