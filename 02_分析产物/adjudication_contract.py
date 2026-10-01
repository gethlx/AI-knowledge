#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""adjudication_contract.py —— Adjudication 契约共享模块（32号 F3 程序闭环的唯一事实源）。

职责（32 号报告"剩余修正范围"）：
1. v2 写入契约的真实校验：直接用 jsonschema 加载 `03_交付物/p1_review_contract/
   edge_adjudication.v2.schema.json`，禁止任何手写副本与 schema 文件漂移；
   jsonschema 不可用时报错退出（fail-fast，不允许静默放行）。
2. 结构化结论 → 边记录的唯一映射 `build_edge_from_adjudication`：
   入边只取裁定记录的 adopted_relation / adopted_direction（结构化结论），
   绝不取评审投票；no_relation / insufficient_evidence / 非采纳状态一律不生成边。
3. 方向映射：direction := adopted_direction（build_graph.normalize 按
   target_to_source 归一化生效端点，保持不变）。

存量读取边界：1,907 条 v1 原对象按 edge_adjudication.schema.json（v1）界定，
经 multi_model_review.validate_adjudication_schema 的 v1 手写路径读取；
本模块不做 v1 校验，也不回写原件。
"""
import json
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
V2_SCHEMA_PATH = BASE / "03_交付物/p1_review_contract/edge_adjudication.v2.schema.json"

V2_SCHEMA_VERSION = "p1-contract-v2"

# 边生成白名单：只有这两种关系产生图边
EDGE_RELATIONS = ("related", "prerequisite")
# 两类"采纳但无边"的结论（32号：无关系/证据不足不得生成边）
NO_EDGE_RELATIONS = ("no_relation", "insufficient_evidence")

try:
    import jsonschema
except ImportError as _exc:  # fail-fast：契约校验不允许静默降级
    raise RuntimeError(
        "adjudication_contract 需要 jsonschema 库（受控环境已安装）。"
        "禁止在无 jsonschema 的环境下做契约校验——静默放行正是 32 号指出的缺陷。"
        f"原始错误：{_exc}"
    ) from _exc

with V2_SCHEMA_PATH.open(encoding="utf-8") as _fh:
    V2_SCHEMA = json.load(_fh)
_V2_VALIDATOR = jsonschema.Draft7Validator(V2_SCHEMA)


def validate_adjudication_v2(adj) -> list[str]:
    """按 v2 写入契约（真实 schema 文件）全量校验，返回错误列表（空=通过）。"""
    if not isinstance(adj, dict):
        return ["adjudication 不是 object"]
    errs = []
    for e in sorted(_V2_VALIDATOR.iter_errors(adj), key=lambda x: list(x.absolute_path)):
        loc = "/".join(str(p) for p in e.absolute_path) or "(root)"
        errs.append(f"{loc}: {e.message}")
    return errs


def build_edge_from_adjudication(adj: dict, pair_source: str, pair_target: str,
                                 extra: dict | None = None) -> tuple[dict | None, str | None]:
    """从 v2 裁定记录构造边记录。返回 (edge_or_None, skip_reason_or_None)。

    规则（32 号裁定）：
    - final_status 非 ACCEPTED_MODEL_ADJUDICATED → 不生成边；
    - adopted_relation=prerequisite → direction=adopted_direction（缺失即抛错，防御）；
    - adopted_relation=related → direction=None；
    - adopted_relation=no_relation / insufficient_evidence → 不生成边（附原因）；
    - 边记录同时保留 adopted_* 原始字段与 direction 消费字段，两者恒一致。
    """
    status = adj.get("final_status")
    if status != "ACCEPTED_MODEL_ADJUDICATED":
        return None, f"final_status={status} 非采纳状态，不生成边"
    rel = adj.get("adopted_relation")
    direction = adj.get("adopted_direction")
    if rel in NO_EDGE_RELATIONS:
        return None, f"adopted_relation={rel}：采纳为无关系/证据不足，不生成边"
    if rel not in EDGE_RELATIONS:
        raise ValueError(f"adopted_relation={rel!r} 不在边生成白名单，拒绝静默处理")
    if rel == "prerequisite":
        if direction not in ("source_to_target", "target_to_source"):
            raise ValueError(f"prerequisite 边方向非法：{direction!r}（v2 契约要求必填方向）")
    else:
        if direction is not None:
            raise ValueError(f"related 边方向必须为 null，实际 {direction!r}")
    edge = {
        "edge_id": f"edge:{rel}:{pair_source}->{pair_target}",
        "pair_id": adj["pair_id"],
        "source": pair_source,
        "target": pair_target,
        "relation_type": rel,
        "direction": direction,  # 消费字段（build_graph.normalize 读它）
        "adopted_relation": rel,  # 结构化结论原样保留，供审计与一致性断言
        "adopted_direction": direction,
        "status": status,
        "adjudicator": adj.get("adjudicator"),
        "adopted_by": adj.get("adopted_by", "orchestrator"),
        "schema_version": adj.get("schema_version", V2_SCHEMA_VERSION),
    }
    if extra:
        edge.update(extra)
    return edge, None
