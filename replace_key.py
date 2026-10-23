"""Replace leaked API_KEY in all files during git filter-branch.

⚠️ 2026-10-23 安全整改：
1. Key 不再硬编码，从 config.json 的 ticktick_api_key 读取；
2. 原模块级遍历替换代码会在 import 时误改文件（曾把 config.json 的真 Key
   覆盖成占位符），已包进 main() 保护——只有直接运行本脚本才执行替换。
"""
import json
import os
import sys


def _load_leaked_key():
    cfg_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
    if os.path.exists(cfg_path):
        try:
            with open(cfg_path, encoding="utf-8") as f:
                return json.load(f).get("ticktick_api_key", "")
        except Exception:
            pass
    return ""


REPLACEMENT = "REDACTED_API_KEY"


def clean_tree(root="."):
    """遍历 root，把 LEAKED_KEY 替换为 REPLACEMENT。仅在直接运行时调用。"""
    leaked = _load_leaked_key()
    if not leaked:
        print("config.json 中未找到 ticktick_api_key，无需替换")
        return
    for dirpath, dirs, files in os.walk(root):
        if ".git" in dirs:
            dirs.remove(".git")
        for fname in files:
            fpath = os.path.join(dirpath, fname)
            try:
                with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                if leaked in content:
                    with open(fpath, "w", encoding="utf-8") as f:
                        f.write(content.replace(leaked, REPLACEMENT))
                    print(f"  Cleaned: {fpath}")
            except Exception:
                pass


if __name__ == "__main__":
    clean_tree(sys.argv[1] if len(sys.argv) > 1 else ".")
