#!/usr/bin/env python
# -*- coding: utf-8 -*-
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

EMAIL_ADDRESS = _get('EMAIL_ADDRESS', '')
PASSWORD = _get('EMAIL_PASSWORD', '')
IMAP_SERVER = _get('IMAP_SERVER', 'imap.aliyun.com')
IMAP_PORT = int(_get('IMAP_PORT', '993'))
