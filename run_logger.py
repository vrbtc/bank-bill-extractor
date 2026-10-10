#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""运行日志留存模块：关键事件以 JSON Lines 追加写入 run_log.jsonl。

本文件会被 git 追踪，本地运行后由 AutoGitHubSync 计划任务（每 10 分钟
git add -A + push）自动推送到 GitHub；云端 GitHub Actions 运行后由
deploy.yml 的「Commit run log」步骤推回 main 分支，实现全链路日志留存。

事件类型：
  run_summary       一次完整运行的结果摘要（daily_run / 云端部署）
  create_task       创建滴答清单任务
  update_task       精确匹配更新已存在任务（刷新还款日/提醒）
  rename_task       模糊匹配改名更新（旧标题 → 新标题）
  complete_task     系统标记完成（如清理旧格式重复任务）
  delete_task       删除任务（旧格式清理）
  detect_completed  检测到用户手动完成任务
  dashboard         仪表盘生成摘要
"""

import json
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path

_BJ_TZ = timezone(timedelta(hours=8))
LOG_FILE = Path(__file__).parent / "run_log.jsonl"
MAX_LINES = 4000       # 超过后截断
KEEP_LINES = 3000      # 截断后保留最近行数


def log_event(event, **fields):
    """追加一条事件日志。写入失败不影响主流程。

    Args:
        event: 事件类型（见模块 docstring）
        **fields: 事件字段（bank / amount / title / due_date / task_id 等）
    """
    try:
        rec = {
            "ts": datetime.now(_BJ_TZ).strftime("%Y-%m-%d %H:%M:%S"),
            "event": event,
            # 云端运行时 GitHub Actions 注入 GITHUB_ACTIONS=true
            "source": "github_actions" if os.environ.get("GITHUB_ACTIONS") == "true" else "local",
        }
        rec.update(fields)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        _rotate()
    except Exception:
        pass


def _rotate():
    """防止日志无限增长：超过 MAX_LINES 行时只保留最近 KEEP_LINES 行。"""
    try:
        if not LOG_FILE.exists():
            return
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()
        if len(lines) > MAX_LINES:
            with open(LOG_FILE, "w", encoding="utf-8") as f:
                f.writelines(lines[-KEEP_LINES:])
    except Exception:
        pass
