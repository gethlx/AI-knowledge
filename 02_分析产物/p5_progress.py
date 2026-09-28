#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""p5_progress.py —— luna 全量提议实时进度探针（真相源=磁盘，不依赖任何会话记忆）
用法：python3 p5_progress.py   （随时跑，只读）"""
import json
import time
from datetime import datetime
from pathlib import Path

BASE = Path("/Users/larry/WorkBuddy/2026-09-13-14-09-47/02_分析产物")
PROPOSALS = BASE / "p5_candidates/proposals"
LOG = BASE / "luna_bridge_p5.log"
TOTAL = 4051


def main():
    files = sorted(PROPOSALS.glob("*.json"), key=lambda p: p.stat().st_mtime)
    n = len(files)
    print(f"=== luna 全量提议进度  {datetime.now().strftime('%H:%M:%S')} ===")
    print(f"完成: {n}/{TOTAL}  ({n/TOTAL:.1%})  剩余 {TOTAL-n} 对")

    if files:
        last = datetime.fromtimestamp(files[-1].stat().st_mtime)
        age_min = (datetime.now() - last).total_seconds() / 60
        # 速率：最近 10 分钟落盘数
        now = time.time()
        recent = sum(1 for p in files if now - p.stat().st_mtime < 600)
        rate = recent / 10 if recent else 0
        print(f"最近落盘: {last.strftime('%H:%M:%S')} ({age_min:.1f} 分钟前)")
        print(f"近10分钟速率: {recent} 对（≈{rate:.1f} 对/分钟）")
        if rate:
            eta = (TOTAL - n) / rate
            print(f"预计剩余: ~{eta/60:.1f} 小时")
        status = "✅ 正常" if age_min < 15 else "⛔ 疑似卡死（心跳>15分钟）"
        print(f"健康: {status}")

    # 终态分布（已落盘提议的关系类型）
    from collections import Counter
    c = Counter()
    for p in files:
        try:
            c[json.loads(p.read_text(encoding="utf-8")).get("relation_type", "?")] += 1
        except Exception:
            c["<解析失败>"] += 1
    if c:
        print("已提议分布:", dict(c))

    if LOG.is_file():
        lines = LOG.read_text(encoding="utf-8").splitlines()
        calls = [l for l in lines if "[LUNA-CALL]" in l]
        gives = [l for l in lines if "GIVE-UP" in l]
        if calls:
            print(f"本进程日志: {len(calls)} 次调用 | 弃单 {len(gives)} | 最后一行: {lines[-1][:80]}")


if __name__ == "__main__":
    main()
