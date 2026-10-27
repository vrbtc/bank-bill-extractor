#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
本地兜底看门狗（2026-10-24 新增）

解决的问题：GitHub Actions cron 延迟 3-5.5 小时且偶尔跳过/堵塞，某个推送档位
可能当天漏推。本机（Windows）若开机，由本脚本每 30 分钟检查一次：
已过兜底截止时间的档位，若今天还没人推送 → 本机接管推送。

安全边界（重要，防双写）：
- **不写滴答清单**：不建/不改任何任务，只读取滴答任务后发送通知；
  滴答任务数据与完成状态仍由云端单边维护（P0-7 铁律不变）。
- **去重与云端共用**：推送成功后写 run_log.jsonl 的 event="push" 记录，
  并立即 commit+push 回 origin/main；云端每次运行先 pull 再判定，双方不重复推送。
- **无待办不推送**：与云端同规则，拉不到未完成待办直接跳过。
- **依赖 .git**：无 .git 的离线副本（如 RBANK-dev 沙箱）拒绝运行——
  没有 git 就无法感知云端是否已推送，盲目兜底会变成重复推送源。

典型部署（活跃部署 D:\\RTRAECODE\\RBANK）：
    Windows 计划任务 BankBillFallback 每 30 分钟跑一次 local_fallback.bat，
    后者调用本脚本。注册命令（管理员 CMD）：
    schtasks /Create /TN "BankBillFallback" /XML "D:\\RTRAECODE\\RBANK\\BankBillFallback_task.xml" /F

本地调试：
    python local_fallback.py --status      # 查看各档位今日推送状态与截止时间
    python local_fallback.py --dry-run     # 只报告会推什么，不发送不提交
    python local_fallback.py               # 立即执行一次兜底检查
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
LOG_FILE = SCRIPT_DIR / "local_fallback.log"
BJ_TZ = timezone(timedelta(hours=8))
MAX_LOG_LINES = 500


def log(msg):
    line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
        _rotate()
    except Exception:
        pass


def _rotate():
    try:
        if not LOG_FILE.exists():
            return
        lines = LOG_FILE.read_text(encoding="utf-8").splitlines(keepends=True)
        if len(lines) > MAX_LOG_LINES:
            LOG_FILE.write_text("".join(lines[-MAX_LOG_LINES:]), encoding="utf-8")
    except Exception:
        pass


def has_git():
    return (SCRIPT_DIR / ".git").exists()


def git(args, timeout=180):
    """在项目目录执行 git 命令，返回 (returncode, 合并输出)。"""
    try:
        r = subprocess.run(["git"] + args, cwd=str(SCRIPT_DIR),
                           capture_output=True, text=True, timeout=timeout)
        return r.returncode, (r.stdout or "") + (r.stderr or "")
    except Exception as e:
        return 1, str(e)


def git_pull_state():
    """拉取云端最新状态（含 run_log.jsonl 里的云端推送记录）。"""
    rc, out = git(["pull", "--rebase", "origin", "main"])
    if rc == 0:
        log("git pull --rebase 成功（已获取云端最新推送记录）")
        return True
    log(f"WARN: git pull --rebase 失败（{out.strip()[:200]}），使用本地状态继续")
    return False


def git_push_marks():
    """把本地产生的推送标记立刻推回 origin，让云端也看到（防双推）。"""
    git(["add", "run_log.jsonl"])
    rc, out = git(["commit", "-m", "chore: local fallback push marks [skip ci]"])
    if rc != 0 and "nothing to commit" not in out and "no changes added" not in out:
        log(f"WARN: git commit 失败（{out.strip()[:200]}）")
        return False
    rc, out = git(["pull", "--rebase", "origin", "main"])
    if rc != 0:
        log(f"WARN: push 前 pull --rebase 失败（{out.strip()[:200]}）")
    rc, out = git(["push"])
    if rc == 0:
        log("推送标记已回传 origin/main")
        return True
    log(f"WARN: git push 失败（{out.strip()[:200]}），稍后由 auto-sync 重试")
    return False


def _load_config():
    p = SCRIPT_DIR / "config.json"
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _prepare_env():
    """本地没有 GitHub Secrets 环境变量，从 config.json 补足（不覆盖已有环境变量）。"""
    cfg = _load_config()
    if not os.environ.get("FEISHU_WEBHOOK_URL"):
        os.environ["FEISHU_WEBHOOK_URL"] = cfg.get("feishu_webhook_url", "")
    if not os.environ.get("TICKTICK_API_KEY"):
        os.environ["TICKTICK_API_KEY"] = cfg.get("ticktick_api_key", "")


def wxpusher_enabled():
    if os.environ.get("WXPUSHER_ENABLED", "").strip().lower() in ("1", "true", "yes"):
        return True
    return bool(_load_config().get("wxpusher_enabled", False))


def latest_slot(slots):
    """从到期未推档位中取截止时间最晚（最新）的一个。

    每次运行每渠道只补一个档位：宽限期内可能同时有多个档位到期
    （如 evening 22:00 与 t2200 22:45），但它们内容相同（今日+逾期），
    只补最新的一个，避免一次运行连发多条。
    """
    return slots[-1] if slots else None


def show_status():
    """查看各档位今日推送状态与兜底截止时间。"""
    from push_schedule import (PUSH_SLOTS, SLOT_FALLBACK_DEADLINE,
                               WXPUSHER_SLOTS, already_pushed_today)
    now = datetime.now(BJ_TZ)
    print(f"当前北京时间：{now.strftime('%Y-%m-%d %H:%M')}")
    print(f"{'档位':<10}{'窗口(北京)':<16}{'兜底截止':<10}{'飞书':<8}{'WXpusher':<10}")
    for s in PUSH_SLOTS:
        f_mark = "已推" if already_pushed_today("feishu", s["id"]) else "未推"
        if s["id"] in WXPUSHER_SLOTS:
            w_mark = "已推" if already_pushed_today("wxpusher", s["id"]) else "未推"
        else:
            w_mark = "不推送"
        win = f"{s['start']}-{s['end']}"
        print(f"{s['id']:<10}{win:<16}{SLOT_FALLBACK_DEADLINE.get(s['id'], '-'):<10}{f_mark:<8}{w_mark:<10}")


def run_once(dry_run=False):
    log("=" * 50)
    log("本地兜底检查开始" + ("（dry-run，不发送不提交）" if dry_run else ""))

    if not has_git():
        log("跳过：当前目录无 .git（离线副本无法感知云端是否已推送，禁止兜底，避免重复推送）")
        return 0

    git_pull_state()
    _prepare_env()

    sys.path.insert(0, str(SCRIPT_DIR))
    import generate_dashboard as gd
    from push_schedule import due_unpaid_slots, WXPUSHER_SLOTS

    now = datetime.now(BJ_TZ)
    log(f"当前北京时间 {now.strftime('%Y-%m-%d %H:%M')}")

    acted = False

    # 飞书：全部档位可兜底，每次只补截止时间最晚的一个
    feishu_due = due_unpaid_slots("feishu", now_bj=now)
    target = latest_slot(feishu_due)
    if target:
        skipped = [s["id"] for s in feishu_due[:-1]]
        if skipped:
            log(f"飞书兜底：{','.join(skipped)} 档已过宽限期不再补推（内容与最新档位重复）")
        log(f"飞书兜底触发：{target['id']} 档（{target['label']}）今日未推送且已过兜底截止时间")
        try:
            gd.push_to_feishu(dry_run=dry_run, slot_id=target["id"])
        except Exception as e:
            log(f"ERROR: 飞书兜底 {target['id']} 失败 - {e}")
        acted = True

    # WXpusher：仅 t1700/t2200 兜底，同样每次只补最晚的一个
    if wxpusher_enabled():
        wx_due = due_unpaid_slots("wxpusher", now_bj=now, allowed_slots=WXPUSHER_SLOTS)
        target = latest_slot(wx_due)
        if target:
            skipped = [s["id"] for s in wx_due[:-1]]
            if skipped:
                log(f"WXpusher 兜底：{','.join(skipped)} 档已过宽限期不再补推（内容与最新档位重复）")
            log(f"WXpusher 兜底触发：{target['id']} 档（{target['label']}）今日未推送且已过兜底截止时间")
            try:
                gd.push_to_wxpusher(dry_run=dry_run, slot_id=target["id"])
            except Exception as e:
                log(f"ERROR: WXpusher 兜底 {target['id']} 失败 - {e}")
            acted = True
    else:
        log("WXpusher 未启用（wxpusher_enabled=false 且未设 WXPUSHER_ENABLED），跳过微信兜底")

    if not acted:
        log("无需兜底：所有已过截止时间的档位今天均已推送（或尚未到截止时间）")
        return 0

    if not dry_run:
        git_push_marks()
    log("本地兜底检查结束")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="RBANK 本地兜底看门狗（GitHub 延迟/漏跑时本地接管推送）")
    parser.add_argument("--dry-run", action="store_true", help="只报告会推什么，不发送不提交")
    parser.add_argument("--status", action="store_true", help="查看各档位今日推送状态与截止时间")
    args = parser.parse_args()

    if args.status:
        show_status()
    else:
        sys.exit(run_once(dry_run=args.dry_run))
