#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
配置加载模块
支持多邮箱配置（向后兼容单邮箱环境变量）

配置优先级：
1. 环境变量（CI/CD）—— 单邮箱模式向后兼容
2. config.json 的 "emails" 数组 —— 多邮箱模式
3. config.json 的单邮箱字段 —— 向后兼容
"""
import json
import os


def _load_config_file():
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.json')
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {}


_config = _load_config_file()


def _get(key, default=None):
    return os.environ.get(key, _config.get(key.lower(), default))


# ===== 单邮箱模式（向后兼容，用于 GitHub Actions 等环境变量场景） =====
EMAIL_ADDRESS = _get('EMAIL_ADDRESS', '')
PASSWORD = _get('EMAIL_PASSWORD', '')
IMAP_SERVER = _get('IMAP_SERVER', 'imap.aliyun.com')
IMAP_PORT = int(_get('IMAP_PORT', '993'))


def get_all_emails():
    """
    获取所有邮箱配置（多邮箱模式）

    Returns:
        list[dict]: 每个邮箱一个 dict，字段：
            - address: 邮箱地址
            - password: 授权码
            - imap_server: IMAP 服务器
            - imap_port: 端口
            - label: 来源标注（如 "YY"），可为空字符串

    优先级：
        1. config.json 的 "emails" 数组
        2. 环境变量 / 单邮箱配置（向后兼容，label=""）

    环境变量也支持多邮箱：通过 EMAILS_JSON 传入 JSON 字符串
    （用于 GitHub Actions，避免 secrets 过多）
    """
    emails = []

    # 方式1: EMAILS_JSON 环境变量（GitHub Actions 推荐）
    emails_json_str = os.environ.get('EMAILS_JSON', '')
    if emails_json_str:
        try:
            emails = json.loads(emails_json_str)
        except Exception:
            pass

    # 方式2: config.json 的 "emails" 数组
    if not emails and 'emails' in _config:
        emails = _config.get('emails', [])

    # 方式3: 单邮箱回退（向后兼容）
    if not emails and EMAIL_ADDRESS and PASSWORD:
        emails = [{
            'address': EMAIL_ADDRESS,
            'password': PASSWORD,
            'imap_server': IMAP_SERVER,
            'imap_port': IMAP_PORT,
            'label': ''
        }]

    # 规范化：确保每条都有 label 字段（默认空字符串）
    for em in emails:
        if 'label' not in em:
            em['label'] = ''
        if 'imap_server' not in em or not em['imap_server']:
            em['imap_server'] = 'imap.aliyun.com'
        if 'imap_port' not in em or not em['imap_port']:
            em['imap_port'] = 993
        else:
            em['imap_port'] = int(em['imap_port'])

    return emails
