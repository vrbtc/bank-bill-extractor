#!/usr/bin/env python
# -*- coding: utf-8 -*-

import subprocess
import sys
import os
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
TASK_NAME = "BankBillDaily"
XML_FILE = SCRIPT_DIR / "BankBillDaily_task.xml"
BAT_FILE = SCRIPT_DIR / "daily_run.bat"


def is_admin():
    try:
        import ctypes
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False


def run_as_admin(cmd):
    import ctypes
    ctypes.windll.shell32.ShellExecuteW(None, "runas", "cmd.exe", f'/c {cmd}', None, 0)


def create_task():
    if not XML_FILE.exists():
        print(f"[ERROR] XML file not found: {XML_FILE}")
        return False

    cmd = f'schtasks /Create /TN "{TASK_NAME}" /XML "{XML_FILE}" /F'
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)

    if result.returncode == 0:
        print(f"[OK] Task '{TASK_NAME}' registered successfully!")
        return True
    else:
        print(f"[ERROR] Failed: {result.stderr.strip()}")
        return False


def delete_task():
    cmd = f'schtasks /Delete /TN "{TASK_NAME}" /F'
    subprocess.run(cmd, shell=True, capture_output=True)


def query_task():
    cmd = f'schtasks /Query /TN "{TASK_NAME}" /V /FO LIST'
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.returncode == 0:
        print(result.stdout)
    else:
        print(f"Task '{TASK_NAME}' not found.")


def test_run():
    cmd = f'schtasks /Run /TN "{TASK_NAME}"'
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.returncode == 0:
        print(f"[OK] Task '{TASK_NAME}' triggered.")
    else:
        print(f"[ERROR] {result.stderr.strip()}")


def main():
    if not is_admin():
        print("=" * 50)
        print("  Need admin privilege to register task")
        print("  Requesting elevation...")
        print("=" * 50)

        if len(sys.argv) < 2 or sys.argv[1] != "--elevated":
            import ctypes
            params = f'"{sys.executable}" "{__file__}" --elevated'
            ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, f'"{__file__}" --elevated', str(SCRIPT_DIR), 1)
            sys.exit(0)

    print()
    print("=" * 50)
    print("  Bank Bill Daily Task Setup")
    print("=" * 50)
    print()

    delete_task()
    if create_task():
        print()
        print(f"  Task Name:    {TASK_NAME}")
        print(f"  Schedule:     Daily at 09:00")
        print(f"  Script:       {BAT_FILE}")
        print(f"  Log:          {SCRIPT_DIR / 'daily_run.log'}")
        print()
        print("  Commands:")
        print(f"    Query:  schtasks /Query /TN \"{TASK_NAME}\"")
        print(f"    Run:    schtasks /Run /TN \"{TASK_NAME}\"")
        print(f"    Delete: schtasks /Delete /TN \"{TASK_NAME}\" /F")
        print(f"    Change: schtasks /Change /TN \"{TASK_NAME}\" /ST 08:00")
        print()
    else:
        print("\n[ERROR] Registration failed. Try running as administrator.")
        input("Press Enter to exit...")


if __name__ == "__main__":
    main()
