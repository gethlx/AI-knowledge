#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""p17 规划审核驱动：复用 sol_api_bridge 的配置与重试骨架，把 17号升级案送 sol 独立审核。
输出：02_分析产物/p17_sol_review/sol_plan_review.md + raw_response.json
[SOL-CALL] 日志照常打印，供主公 Vimox 控制台对账。
"""
import json
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

BASE = Path("/Users/larry/WorkBuddy/2026-09-13-14-09-47")
sys.path.insert(0, str(BASE / "02_分析产物"))
from sol_api_bridge import load_sol_config  # 复用官方配置加载

OUT_DIR = BASE / "02_分析产物/p17_sol_review"
DOC_14 = BASE / "03_交付物/14-知识图谱实施规划最终裁定版.md"
DOC_17 = BASE / "03_交付物/17-P5结构化送审与P75图级整体审升级案.md"
PREV_REVIEW = BASE / "02_分析产物/p17_sol_review/sol_plan_review.md"
PREV_REVIEW2 = BASE / "02_分析产物/p17_sol_review/sol_plan_review_v22.md"
PREV_REVIEW3 = BASE / "02_分析产物/p17_sol_review/sol_plan_review_v23.md"
TIMEOUT = 300
RETRY_DELAYS = (0, 60, 120)

PROMPT = """你是 gpt-5.6-sol，以独立裁定建议角色，对一份知识图谱实施规划升级案做【第四轮复审】。

背景：一审 F-01~F-13（"需修订后执行"，文件C）；二审 N-01~N-06（"仍需修订"，文件D）；三审（文件E）确认 N-01~N-06 全部已解决，遗留 4 项必须修改项（M-1 light 复核操作定义 / M-2 租约原子领取 / M-3 压缩算法确定性 / M-4 偏差生效硬绑主公终批）。编排方现提交 v2.4（文件B）。

请阅读五份文件：
===== 文件A：14号裁定版 =====
{doc14}

===== 文件B：17号升级案 v2.4 =====
{doc17}

===== 文件C：一审报告 =====
{prev}

===== 文件D：二审报告 =====
{prev2}

===== 文件E：三审报告 =====
{prev3}

===== 四审任务 =====
1. 逐条验收 M-1~M-4：判定【已解决/部分解决/未解决】，引用 v2.4 条款为证；
2. 快速核查此前全部已解决项是否被 v2.4 意外回退；
3. 最终裁定三选一：通过（可执行）/ 仍需修订 / 不可执行；若"通过"，列出生效前需主公终批确认的事项清单。

直说不客套；依据不足明确写"依据不足"。
"""


def call_sol(prompt: str) -> str:
    cfg = load_sol_config()
    body = json.dumps({
        "model": cfg["model"],
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
    }).encode("utf-8")
    req = urllib.request.Request(
        cfg["url"], data=body, method="POST",
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {cfg['key']}"},
    )
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    dt = time.time() - t0
    print(f"[SOL-CALL] t={time.strftime('%H:%M:%S')} 耗时={dt:.1f}s model_returned={data.get('model', '?')} pair_id=PLAN_REVIEW_17", flush=True)
    return data["choices"][0]["message"]["content"]


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    prompt = PROMPT.format(doc14=DOC_14.read_text(encoding="utf-8"),
                           doc17=DOC_17.read_text(encoding="utf-8"),
                           prev=PREV_REVIEW.read_text(encoding="utf-8"),
                           prev2=PREV_REVIEW2.read_text(encoding="utf-8"),
                           prev3=PREV_REVIEW3.read_text(encoding="utf-8"))
    print(f"[INFO] prompt {len(prompt)} chars, timeout={TIMEOUT}s", flush=True)
    last_err = None
    for i, delay in enumerate(RETRY_DELAYS):
        if delay:
            time.sleep(delay)
        try:
            text = call_sol(prompt)
            (OUT_DIR / "raw_response.json").write_text(
                json.dumps({"attempt": i + 1, "content": text}, ensure_ascii=False, indent=1),
                encoding="utf-8")
            (OUT_DIR / "sol_plan_review_v24.md").write_text(text, encoding="utf-8")
            print(f"[DONE] 第{i+1}次尝试成功，报告已写 {OUT_DIR / 'sol_plan_review.md'}", flush=True)
            return
        except Exception as exc:
            last_err = exc
            print(f"[RETRY] 第{i+1}次失败：{exc}", flush=True)
    print(f"[FAIL] 3 次全败，最后错误：{last_err}", flush=True)
    sys.exit(1)


if __name__ == "__main__":
    main()
