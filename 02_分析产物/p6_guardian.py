#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""p6_guardian.py —— P6 sol 裁定守护循环。

背景：单次后台运行的 bridge 进程曾被无声回收（16:06 死亡，75 分钟后才发现）。
本守护器循环拉起 sol_api_bridge（幂等：adjudication.json 已存在即 skip），
进程死亡/失败自动重启，直到全量完成或达到轮次上限。
每轮结束打印进度，供主控对账。
"""
import fcntl
import json
import subprocess
import sys
import time
from pathlib import Path

BASE = Path("/Users/larry/WorkBuddy/2026-09-13-14-09-47")
AN = BASE / "02_分析产物"
INBOX = AN / "p5_review/reviews_inbox_full"
PY = "/Users/larry/.workbuddy/binaries/python/versions/3.13.12/bin/python3"
LOG = AN / "p6_sol_run.log"
LOCK = Path("/tmp/p6_guardian.lock")

TOTAL = 1769
MAX_ROUNDS = 60
WORKERS = 3            # 6 并发疑似触发端点掐连接，降回 3
ROUND_TIMEOUT = 900    # 单轮 15 分钟无完成 → 强杀重启（bridge 幂等，零损失）

# 平台会清扫会话后台进程（16:06/17:40/17:54 三次实证）：
# 启动即 setsid 脱离进程组由启动命令负责；本脚本用 flock 单例锁防 cron 叠加。
_lockfh = open(LOCK, "w")
try:
    fcntl.flock(_lockfh, fcntl.LOCK_EX | fcntl.LOCK_NB)
except BlockingIOError:
    print("[GUARDIAN] 已有实例在跑（flock 持有），本次退出", flush=True)
    sys.exit(0)


def done_count() -> int:
    return len(list(INBOX.glob("*/adjudication.json")))


def main():
    for rnd in range(1, MAX_ROUNDS + 1):
        n = done_count()
        print(f"[GUARDIAN] round {rnd} start: {n}/{TOTAL}", flush=True)
        if n >= TOTAL:
            print(f"[GUARDIAN] 全量完成 {n}/{TOTAL}，退出", flush=True)
            return
        n2 = n
        killed = False
        try:
            with open(LOG, "a", encoding="utf-8") as lf:
                lf.write(f"\n===== GUARDIAN round {rnd} ({time.strftime('%H:%M:%S')}) =====\n")
                lf.flush()
                r = subprocess.run(
                    [PY, str(AN / "sol_api_bridge.py"),
                     "--pairs", str(AN / "p5_review/full_pairs.jsonl"),
                     "--inbox", "p5_review/reviews_inbox_full",
                     "--proposals-dir", "p5_candidates/proposals",
                     "--workers", str(WORKERS)],
                    cwd=AN, stdout=lf, stderr=subprocess.STDOUT,
                    timeout=ROUND_TIMEOUT)
        except subprocess.TimeoutExpired:
            killed = True
            print(f"[GUARDIAN] round {rnd} 超时 {ROUND_TIMEOUT}s（线程僵死），强杀进下一轮", flush=True)
        n2 = done_count()
        exit_info = f"超时强杀" if killed else f"exit={r.returncode}"
        print(f"[GUARDIAN] round {rnd} {exit_info} 进度 {n}→{n2}/{TOTAL}", flush=True)
        if n2 >= TOTAL:
            print(f"[GUARDIAN] 全量完成 {n2}/{TOTAL}，退出", flush=True)
            return
        if killed:
            print(f"[GUARDIAN] 10s 后重启下一轮", flush=True)
            time.sleep(10)
        elif r.returncode not in (0, 1):
            print(f"[GUARDIAN] 异常退出码 {r.returncode}，30s 后重启", flush=True)
            time.sleep(30)
        elif n2 == n:
            print(f"[GUARDIAN] 本轮零进展（可能熔断/端点故障），60s 后重试", flush=True)
            time.sleep(60)
    print(f"[GUARDIAN] 达到轮次上限 {MAX_ROUNDS}，进度 {done_count()}/{TOTAL}，交还主控", flush=True)


if __name__ == "__main__":
    main()
