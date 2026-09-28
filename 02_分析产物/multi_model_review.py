#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P1 多模型互审编排器（dry-run / live）。

依据：03_交付物/14-知识图谱实施规划最终裁定版.md 3.1（主控换防）、3.2（输入隔离）、
3.3（裁定规则）、8.4（P1 最低可运行接口）、8.5（gpt-5.6-sol 稳定性协议）；
契约：03_交付物/p1_review_contract/{edge_review,edge_adjudication}.schema.json、redline_rules.json。

职责边界（3.1）：本编排器是"编排主控"（glm5.3-flash 编排层）的程序化执行体——
只做流程推进、程序校验、采纳 gpt-5.6-sol 裁定建议并落盘；**绝不自行裁定**。
sol 不可用/超时/重试耗尽 → ADJUDICATION_DEFERRED（挂起补裁，不放行）。

live 模式下评审意见来自 reviews_inbox/<pair_id>/<reviewer>.json（由编排主控在
WorkBuddy 会话里经 subagent 生成后放入）；裁定建议来自
reviews_inbox/<pair_id>/adjudication.json。dry-run 模式全部走内置 fixture。

纯标准库实现（json/hashlib/re/argparse/pathlib/dataclasses），Python 3.13。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable

# ---------------------------------------------------------------------------
# 常量与契约
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_BASELINE_DIR = BASE_DIR / "p0_baseline"
DEFAULT_WORKDIR = BASE_DIR / "p1_review_run"
DEFAULT_REVIEWS_DIR = Path("reviews_inbox")

PROMPT_VERSION = "p1-review-v1"
PROMPT_TEMPLATE = (
    "P1 三路独立盲评 Prompt | guideline_version=annotation_guidelines v1 | "
    "输入：CARD_A/CARD_B 卡文快照（允许字段：认知层级/精确定义/常见误解/典型案例/"
    "反例/深度上限/安全与伦理边界/教学类比/来源依据）+ pair_id + 关系定义 + "
    "edge_review.schema.json 输出契约。禁止读取 04_归档/前置后续-作废字段归档.csv；"
    "禁止引用作废字段（前置概念/后续概念）；evidence.quote 必须逐字引用卡文。"
)

SCHEMA_VERSION = "p1-contract-v1"

REVIEWERS: tuple[str, ...] = ("reviewer_glm", "reviewer_deepseek", "reviewer_hy4")
REVIEWER_MODELS = {
    "reviewer_glm": "glm5.3-flash",
    "reviewer_deepseek": "deepseek4.1flash",
    "reviewer_hy4": "hy4",
}
ADJUDICATOR_ID = "gpt-5.6-sol(via-subagent)"
ADJUDICATOR_ROLE = "adjudicator"

# 8.5 sol 稳定性协议
SOL_TIMEOUT_SECONDS = 120          # 单次调用超时占位参数（真实 subagent 调用由会话层执行）
SOL_RETRY_DELAYS: tuple[int, ...] = (0, 30, 60)   # 指数退避：0s / 30s / 60s
SOL_MAX_RETRIES = 3
CIRCUIT_BREAKER_THRESHOLD = 10     # 连续 10 个 ADJUDICATION_DEFERRED → 熔断

# 状态（14 号裁定第一节 + 3.3）
ST_ACCEPTED = "ACCEPTED_MODEL_ADJUDICATED"
ST_REJECTED = "REJECTED_MODEL_ADJUDICATED"
ST_ESCALATE = "ESCALATE_HUMAN"
ST_DEFERRED = "ADJUDICATION_DEFERRED"
ST_REVIEW_INCOMPLETE = "REVIEW_INCOMPLETE"
# 终态：重跑跳过；DEFERRED / REVIEW_INCOMPLETE 可补跑（幂等，缓存键不变）
TERMINAL_STATUSES = {ST_ACCEPTED, ST_REJECTED, ST_ESCALATE}

# 红线动作（redline_rules.json）
REDLINE_ESCALATE_RULES = {"R1", "R2", "R3", "R4", "R7", "R8"}

R1_KEYWORDS = ("安全风险", "伦理风险", "医疗风险", "法律风险", "未成年人风险", "课程阻塞性错误")
R2_KEYWORDS = ("卡文矛盾", "证据不成立")
R8_PATTERN = re.compile(r"前置概念|后续概念")

PAIR_ID_PATTERN = re.compile(r"^[^\s_]+__[^\s_]+$")

REVIEW_REQUIRED_FIELDS = (
    "pair_id", "reviewer_id", "model_requested", "model_returned",
    "relation_type", "direction", "evidence", "reason", "confidence",
    "input_card_hash", "prompt_hash", "status",
)
REVIEWER_IDS = set(REVIEWERS)
RELATION_TYPES = {"prerequisite", "related", "no_relation", "insufficient_evidence"}
DIRECTIONS = {"source_to_target", "target_to_source", None}
OPINION_STATUSES = {"REVIEW_COMPLETED", "REVIEW_FAILED", "REVIEW_INCOMPLETE"}

ADJUDICATION_REQUIRED_FIELDS = (
    "pair_id", "adjudicator", "final_status", "adopted_by", "rationale",
    "residual_risks", "reviewer_agreement", "escalation_reason", "schema_version",
)
ADJ_FINAL_STATUSES = {ST_ACCEPTED, ST_REJECTED, ST_ESCALATE, ST_DEFERRED}


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def cache_key(pair_id: str, role: str, prompt_version: str, card_content_hash: str) -> str:
    """幂等缓存键 = sha256(pair_id + role + prompt_version + card_content_hash)。"""
    return sha256_text(f"{pair_id}|{role}|{prompt_version}|{card_content_hash}")


class SolUnavailableError(Exception):
    """gpt-5.6-sol 不可用 / 超时 / 返回非法（8.5 协议，视同失败计入重试）。"""


class CircuitBreakerError(Exception):
    """连续 10 个 ADJUDICATION_DEFERRED → 熔断，暂停裁定阶段（8.5 规则 4）。"""

    def __init__(self, report: dict[str, Any]):
        super().__init__("circuit breaker triggered")
        self.report = report


# ---------------------------------------------------------------------------
# 数据加载
# ---------------------------------------------------------------------------

def load_card_evidence(baseline_dir: Path) -> dict[str, dict[str, Any]]:
    cards: dict[str, dict[str, Any]] = {}
    path = baseline_dir / "card_evidence.jsonl"
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            cards[rec["card_id"]] = rec
    return cards


def load_canonical_ids(baseline_dir: Path) -> set[str]:
    data = json.loads((baseline_dir / "canonical_entities.json").read_text(encoding="utf-8"))
    return {c["card_id"] for c in data["cards"]}


def default_pairs(cards: dict[str, dict[str, Any]]) -> list["PairTask"]:
    """dry-run 默认：K1 前 5 对演示（轴 1 前六张卡的两两相邻对）。"""
    axis1 = sorted(cid for cid, c in cards.items() if cid.startswith("1-"))
    head = axis1[:6]
    return [make_pair(f"{head[i]}__{head[i + 1]}", cards) for i in range(5)]


def make_pair(pair_id: str, cards: dict[str, dict[str, Any]]) -> "PairTask":
    source, target = pair_id.split("__", 1)
    return PairTask(pair_id=pair_id, source=source, target=target)


# ---------------------------------------------------------------------------
# 手写 Schema 校验器（required / enum / 类型 / 条件约束，不装第三方库）
# ---------------------------------------------------------------------------

def _is_str(v: Any) -> bool:
    return isinstance(v, str)


def validate_review_schema(op: Any) -> list[str]:
    """校验 ReviewOpinion（edge_review.schema.json 的手写等价实现）。"""
    errs: list[str] = []
    if not isinstance(op, dict):
        return ["opinion 不是 object"]
    extra = set(op) - set(REVIEW_REQUIRED_FIELDS)
    if extra:
        errs.append(f"additionalProperties: {sorted(extra)}")
    for f in REVIEW_REQUIRED_FIELDS:
        if f not in op:
            errs.append(f"缺少必填字段 {f}")
    if errs:
        return errs

    if not (_is_str(op["pair_id"]) and 3 <= len(op["pair_id"]) <= 80 and PAIR_ID_PATTERN.match(op["pair_id"])):
        errs.append("pair_id 不合法")
    if op["reviewer_id"] not in REVIEWER_IDS:
        errs.append("reviewer_id 不在枚举内")
    for f in ("model_requested", "model_returned", "reason", "input_card_hash", "prompt_hash"):
        if not (_is_str(op[f]) and len(op[f]) >= 1):
            errs.append(f"{f} 必须为非空字符串")
    if op["relation_type"] not in RELATION_TYPES:
        errs.append("relation_type 不在枚举内")
    if op["direction"] not in DIRECTIONS:
        errs.append("direction 不在枚举内")
    if op["status"] not in OPINION_STATUSES:
        errs.append("status 不在枚举内")

    conf = op["confidence"]
    if isinstance(conf, bool) or not isinstance(conf, (int, float)) or not (0 <= conf <= 1):
        errs.append("confidence 必须为 [0,1] 数值")

    # 条件约束：prerequisite 必须有方向；其余 relation_type 方向必须为 null
    if op["relation_type"] == "prerequisite":
        if op["direction"] not in ("source_to_target", "target_to_source"):
            errs.append("prerequisite 要求 direction 为 source_to_target/target_to_source")
    else:
        if op["direction"] is not None:
            errs.append("非 prerequisite 时 direction 必须为 null")

    ev = op["evidence"]
    if not isinstance(ev, list):
        errs.append("evidence 必须为数组")
    else:
        if op["status"] == "REVIEW_COMPLETED" and len(ev) < 1:
            errs.append("REVIEW_COMPLETED 要求 evidence 至少 1 条")
        for i, item in enumerate(ev):
            if not isinstance(item, dict):
                errs.append(f"evidence[{i}] 不是 object")
                continue
            if set(item) - {"card_id", "field", "quote"}:
                errs.append(f"evidence[{i}] 有 additionalProperties")
            for k in ("card_id", "field", "quote"):
                if not (_is_str(item.get(k)) and len(item[k]) >= 1):
                    errs.append(f"evidence[{i}].{k} 必须为非空字符串")
    return errs


def validate_adjudication_schema(adj: Any) -> list[str]:
    """校验 Adjudication（edge_adjudication.schema.json 的手写等价实现）。"""
    errs: list[str] = []
    if not isinstance(adj, dict):
        return ["adjudication 不是 object"]
    extra = set(adj) - set(ADJUDICATION_REQUIRED_FIELDS)
    if extra:
        errs.append(f"additionalProperties: {sorted(extra)}")
    for f in ADJUDICATION_REQUIRED_FIELDS:
        if f not in adj:
            errs.append(f"缺少必填字段 {f}")
    if errs:
        return errs

    if not (_is_str(adj["pair_id"]) and 3 <= len(adj["pair_id"]) <= 80 and PAIR_ID_PATTERN.match(adj["pair_id"])):
        errs.append("pair_id 不合法")
    if adj["adjudicator"] != ADJUDICATOR_ID:
        errs.append("adjudicator 必须为 gpt-5.6-sol(via-subagent)")
    if adj["final_status"] not in ADJ_FINAL_STATUSES:
        errs.append("final_status 不在枚举内")
    if adj["adopted_by"] != "orchestrator":
        errs.append("adopted_by 必须为 orchestrator")
    if not (_is_str(adj["rationale"]) and adj["rationale"]):
        errs.append("rationale 必须为非空字符串")
    if not (_is_str(adj["reviewer_agreement"]) and adj["reviewer_agreement"]):
        errs.append("reviewer_agreement 必须为非空字符串")
    if not (_is_str(adj["schema_version"]) and adj["schema_version"]):
        errs.append("schema_version 必须为非空字符串")
    rr = adj["residual_risks"]
    if not isinstance(rr, list) or not all(_is_str(x) and x for x in rr):
        errs.append("residual_risks 必须为非空字符串数组")
    er = adj["escalation_reason"]
    if adj["final_status"] == ST_ESCALATE:
        if not (_is_str(er) and er):
            errs.append("ESCALATE_HUMAN 要求 escalation_reason 非空")
    else:
        if er is not None:
            errs.append("非 ESCALATE_HUMAN 时 escalation_reason 必须为 null")
    return errs


# ---------------------------------------------------------------------------
# 程序化校验：逐字证据 / 规范实体 / 旧字段回流 / 红线扫描
# ---------------------------------------------------------------------------

def check_evidence_verbatim(op: dict[str, Any], pair: "PairTask",
                            cards: dict[str, dict[str, Any]]) -> tuple[list[dict[str, str]], bool]:
    """逐字子串校验 + 表外卡号校验。返回 (redline_hits, opinion_valid)。

    R6：quote 与输入卡文允许字段全文不完全一致 → INVALIDATE_OPINION；
    R7：evidence.card_id 超出 pair 两张规范卡 → ESCALATE_HUMAN，且该意见无效。
    """
    hits: list[dict[str, str]] = []
    valid = True
    pair_cards = {pair.source, pair.target}
    for ev in op.get("evidence", []):
        cid, fld, quote = ev.get("card_id", ""), ev.get("field", ""), ev.get("quote", "")
        if cid not in cards or cid not in pair_cards:
            hits.append({"rule_id": "R7", "detail": f"证据卡号 {cid} 为表外卡号（非本 pair 规范卡）"})
            valid = False
            continue
        field_text = cards[cid].get("fields", {}).get(fld)
        if field_text is None or quote not in field_text:
            hits.append({"rule_id": "R6", "detail": f"{cid}.{fld} 的 quote 未通过逐字子串校验"})
            valid = False
    return hits, valid


def scan_opinion_text(op: dict[str, Any]) -> list[dict[str, str]]:
    """旧字段回流扫描（R8）+ 安全/矛盾关键词扫描（R1/R2），扫描意见全文文本。"""
    blob = json.dumps(op, ensure_ascii=False)
    hits: list[dict[str, str]] = []
    if R8_PATTERN.search(blob):
        hits.append({"rule_id": "R8", "detail": "意见文本引用作废字段（前置概念/后续概念），数据链路疑似被旧字段回流污染"})
    reason = op.get("reason", "")
    if any(k in reason for k in R1_KEYWORDS):
        hits.append({"rule_id": "R1", "detail": "评审意见涉及安全/伦理/医疗/法律/未成年人风险或课程阻塞性错误"})
    if any(k in reason for k in R2_KEYWORDS):
        hits.append({"rule_id": "R2", "detail": "评审意见发现卡文矛盾或证据不成立"})
    return hits


def check_pair_entities(pair: "PairTask", canonical_ids: set[str]) -> list[dict[str, str]]:
    """规范实体校验：pair 端点必须在 P0 冻结的规范卡清单中（R7）。"""
    hits = []
    for cid in (pair.source, pair.target):
        if cid not in canonical_ids:
            hits.append({"rule_id": "R7", "detail": f"pair 端点 {cid} 不在 canonical_entities（197 张规范卡）中"})
    return hits


def check_bidirectional(pair: "PairTask", opinions: list[dict[str, Any]],
                        graph_state: "GraphState") -> list[dict[str, str]]:
    """R4：同一候选对同时存在 A→B 与 B→A 的有效先修主张。"""
    hits = []
    pre_dirs = {o["direction"] for o in opinions if o["valid"] and o["relation_type"] == "prerequisite"}
    if len(pre_dirs) > 1:
        hits.append({"rule_id": "R4", "detail": f"有效先修方向冲突: {sorted(d for d in pre_dirs if d)}"})
    reversed_pair_id = f"{pair.target}__{pair.source}"
    rev = graph_state.edges.get(reversed_pair_id)
    if rev and rev["relation_type"] == "prerequisite" and any(
            o["valid"] and o["relation_type"] == "prerequisite" and o["direction"] == "source_to_target"
            for o in opinions) and pair.source < pair.target:
        hits.append({"rule_id": "R4", "detail": "与历史已裁定反向先修边互为双向"})
    return hits


# ---------------------------------------------------------------------------
# 8.4 接口：validate_opinion / route_adjudication
# ---------------------------------------------------------------------------

def validate_opinion(op: Any, pair: "PairTask", cards: dict[str, dict[str, Any]],
                     expected_card_hash: str, expected_prompt_hash: str) -> "OpinionEval":
    """8.4 接口：validate_opinion(opinion, card_evidence) -> ValidationResult。

    Schema 不合 / 状态非 REVIEW_COMPLETED / 哈希不匹配 → 该路视为缺员（REVIEW_INCOMPLETE）；
    R6/R7 证据校验失败 → 该意见无效（不计入一致票），但该路评审本身已完成。
    """
    ev = OpinionEval(reviewer_id=str(op.get("reviewer_id", "?")) if isinstance(op, dict) else "?")
    ev.raw = op if isinstance(op, dict) else None
    schema_errs = validate_review_schema(op)
    if schema_errs:
        ev.invalid_reasons = [f"schema: {e}" for e in schema_errs]
        return ev
    if op["status"] != "REVIEW_COMPLETED":
        ev.invalid_reasons = [f"status={op['status']}（该路未完成）"]
        return ev
    if op["input_card_hash"] != expected_card_hash:
        ev.invalid_reasons = ["input_card_hash 与本次输入卡文快照不匹配"]
        return ev
    if op["prompt_hash"] != expected_prompt_hash:
        ev.invalid_reasons = ["prompt_hash 与本次评审 Prompt 不匹配"]
        return ev

    ev.redline_hits.extend(scan_opinion_text(op))
    ev_hits, ev_valid = check_evidence_verbatim(op, pair, cards)
    ev.redline_hits.extend(ev_hits)
    if not ev_valid:
        ev.invalid_reasons.append("证据校验失败（R6/R7），意见降级为无效意见")
        return ev

    ev.valid = True
    return ev


def route_adjudication(adj: dict[str, Any], redline_hits: list[dict[str, str]],
                       graph_state: "GraphState", pair: "PairTask") -> tuple[str, list[dict[str, str]]]:
    """8.4 接口：route_adjudication(adjudication, graph_state) -> FinalStatus。

    sol 建议先经红线 R1-R10 复核：ACCEPTED 若命中 R1/R2/R3/R4 → 强制 ESCALATE_HUMAN；
    R9 高影响项记录 SOL_RECHECK_REQUIRED（sol 已按协议复核，仅留痕）。
    返回 (final_status, 生效的 rule_hits)。
    """
    status = adj["final_status"]
    rule_ids = {h["rule_id"] for h in redline_hits}
    applied: list[dict[str, str]] = [h for h in redline_hits if h["rule_id"] in REDLINE_ESCALATE_RULES]

    if status == ST_ACCEPTED and rule_ids & REDLINE_ESCALATE_RULES:
        status = ST_ESCALATE
        applied.append({"rule_id": "route", "detail": "sol 建议为接受，但命中升级红线，按红线动作覆盖"})
    if pair.high_influence:
        applied.append({"rule_id": "R9", "detail": "SOL_RECHECK_REQUIRED：高影响项已由 gpt-5.6-sol 复核（协议要求，非多数票放行）"})
    return status, applied


# ---------------------------------------------------------------------------
# Provider 抽象
# ---------------------------------------------------------------------------

@dataclass
class PairTask:
    pair_id: str
    source: str
    target: str
    high_influence: bool = False


@dataclass
class OpinionEval:
    reviewer_id: str
    raw: dict[str, Any] | None = None
    valid: bool = False
    invalid_reasons: list[str] = field(default_factory=list)
    redline_hits: list[dict[str, str]] = field(default_factory=list)

    def to_summary(self) -> dict[str, Any]:
        return {
            "reviewer_id": self.reviewer_id,
            "valid": self.valid,
            "relation_type": self.raw.get("relation_type") if self.raw else None,
            "direction": self.raw.get("direction") if self.raw else None,
            "invalid_reasons": self.invalid_reasons,
            "redline_hits": self.redline_hits,
        }


class ReviewProvider:
    """三路独立评审 Provider。live：读 reviews_inbox；dry-run：fixture。"""

    reviewer_id = ""
    model_requested = ""

    def get_opinion(self, pair: PairTask, bundle: dict[str, Any]) -> Any:
        raise NotImplementedError


class LiveReviewProvider(ReviewProvider):
    """live 模式外部钩子：读取预生成的意见文件（由 WorkBuddy 会话经 subagent 生成后放入）。

    文件缺失 / JSON 非法 → 返回 None（该路 REVIEW_INCOMPLETE，不得补齐后宣称完成互审）。
    """

    def __init__(self, reviewer_id: str, reviews_dir: Path):
        self.reviewer_id = reviewer_id
        self.model_requested = REVIEWER_MODELS[reviewer_id]
        self.reviews_dir = reviews_dir

    def get_opinion(self, pair: PairTask, bundle: dict[str, Any]) -> Any:
        path = self.reviews_dir / pair.pair_id / f"{self.reviewer_id}.json"
        if not path.is_file():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None


class DryRunReviewProvider(ReviewProvider):
    """dry-run 内置 fixture：不依赖外部输入，从真实卡文生成确定性意见。"""

    # 演示计划：覆盖 接受/related/拒绝/少数不确定/方向冲突 五种裁定路径
    PLAN = {
        "1-01__1-02": ("prerequisite", "source_to_target"),
        "1-02__1-03": ("related", None),
        "1-03__1-04": ("no_relation", None),
        "1-04__1-05": ("prerequisite", "source_to_target"),   # 第三路 insufficient_evidence
        "1-05__1-06": "direction_conflict",                    # 两路 A→B，一路 B→A
    }

    def __init__(self, reviewer_id: str, index: int):
        self.reviewer_id = reviewer_id
        self.model_requested = REVIEWER_MODELS[reviewer_id]
        self.index = index

    def _quote(self, cards: dict[str, dict[str, Any]], cid: str) -> dict[str, str]:
        return {"card_id": cid, "field": "精确定义",
                "quote": cards[cid]["fields"]["精确定义"]}

    def get_opinion(self, pair: PairTask, bundle: dict[str, Any]) -> Any:
        cards = bundle["cards"]
        plan = self.PLAN.get(pair.pair_id, ("related", None))
        if plan == "direction_conflict":
            direction = "target_to_source" if self.index == 0 else "source_to_target"
            relation, dir_out = "prerequisite", direction
            reason = "两卡卡文的精确定义显示二者存在先后支撑关系，方向依据卡文表述确定。"
        else:
            relation, dir_out = plan
            if relation == "insufficient_evidence":
                relation = "insufficient_evidence"
            if self.index == 2 and pair.pair_id == "1-04__1-05":
                relation, dir_out = "insufficient_evidence", None
                reason = "两卡卡文的精确定义不足以确定是否存在直接关系，证据不足。"
            elif relation == "no_relation":
                reason = "两卡卡文的精确定义分别描述不同对象，卡文未体现直接关系。"
            elif relation == "related":
                reason = "两卡卡文的精确定义在概念上相互关联，卡文支撑 related 判断。"
            else:
                reason = "两卡卡文的精确定义显示先修支撑关系，方向依据卡文表述确定。"

        evidence = [self._quote(cards, pair.source)]
        if relation != "insufficient_evidence":
            evidence.append(self._quote(cards, pair.target))
        return {
            "pair_id": pair.pair_id,
            "reviewer_id": self.reviewer_id,
            "model_requested": self.model_requested,
            "model_returned": self.model_requested,
            "relation_type": relation,
            "direction": dir_out,
            "evidence": evidence,
            "reason": reason,
            "confidence": 0.85,
            "input_card_hash": bundle["card_content_hash"],
            "prompt_hash": bundle["prompt_hash"],
            "status": "REVIEW_COMPLETED",
        }


class AdjudicationProvider:
    """gpt-5.6-sol（经 subagent 按需拉起）裁定建议 Provider。"""

    def adjudicate(self, pair: PairTask, bundle: dict[str, Any],
                   graph_state: "GraphState") -> dict[str, Any]:
        raise NotImplementedError


class DryRunAdjudicationProvider(AdjudicationProvider):
    """dry-run fixture 裁定建议：确定性实现 3.3 裁定规则表（对有效票，不看无效意见）。"""

    def adjudicate(self, pair: PairTask, bundle: dict[str, Any],
                   graph_state: "GraphState") -> dict[str, Any]:
        opinions: list[OpinionEval] = bundle["opinions"]
        valid = [o for o in opinions if o.valid]
        votes = [(o.raw["relation_type"], o.raw["direction"]) for o in valid]
        esc_hits = [h for h in bundle["redline_hits"] if h["rule_id"] in REDLINE_ESCALATE_RULES]

        def make(final: str, rationale: str, escalation_reason: str | None = None,
                 minority: bool = False) -> dict[str, Any]:
            return {
                "pair_id": pair.pair_id,
                "adjudicator": ADJUDICATOR_ID,
                "final_status": final,
                "adopted_by": "orchestrator",
                "rationale": rationale + (
                    "；少数意见为 INSUFFICIENT_EVIDENCE（minority_uncertain）。" if minority
                    else "；反对意见已逐项复核，未采信多数票简单放行。" if final == ST_ESCALATE else ""),
                "residual_risks": ["模型裁定，未人工逐条核验"] + (
                    ["少数意见存在不确定性（minority_uncertain）"] if minority else []),
                "reviewer_agreement": self._agreement_text(valid, opinions),
                "escalation_reason": escalation_reason,
                "schema_version": SCHEMA_VERSION,
            }

        if esc_hits:
            ids = sorted({h["rule_id"] for h in esc_hits})
            return make(ST_ESCALATE,
                        f"红线核查命中 {','.join(ids)}：{'；'.join(h['detail'] for h in esc_hits)}。",
                        escalation_reason=f"红线命中 {'/'.join(ids)}（超出自动裁定边界）")
        if not votes:
            return make(ST_ESCALATE, "无有效评审意见，无法构成一致结论。",
                        escalation_reason="三路意见均无效，证据不足")

        from collections import Counter
        cnt = Counter(votes)
        top, top_n = cnt.most_common(1)[0]
        detail = f"有效票分布 {dict(cnt)}；证据逐字命中情况已逐条复核。"
        if len(cnt) == 1:
            (rel, _dir) = top
            if rel == "no_relation":
                return make(ST_REJECTED, detail + "三路一致为 NO_RELATION，无有效证据支持关系。")
            if rel == "insufficient_evidence":
                return make(ST_ESCALATE, detail + "三路一致证据不足。",
                            escalation_reason="三路一致 INSUFFICIENT_EVIDENCE，证据不足")
            return make(ST_ACCEPTED, detail + "有效意见全部一致，证据足以支持关系。")
        # 分歧：2 对 1
        minority = [v for v in votes if v != top]
        if top_n == 2 and len(minority) == 1 and minority[0][0] == "insufficient_evidence":
            return make(ST_ACCEPTED, detail + "两路一致、一路证据不足，支持意见证据充分且无红线。",
                        minority=True)
        return make(ST_ESCALATE, detail + "两路一致、一路明确反对，已记录反对理由。",
                    escalation_reason="二对一分歧：少数派明确反对，不得简单多数放行")

    @staticmethod
    def _agreement_text(valid: list[OpinionEval], opinions: list[OpinionEval]) -> str:
        parts = []
        for o in opinions:
            state = "有效" if o.valid else f"无效({';'.join(o.invalid_reasons) or '未知'})"
            raw = o.raw or {}
            parts.append(f"{o.reviewer_id}:{raw.get('relation_type')}/{raw.get('direction')}[{state}]")
        n_valid = len(valid)
        if n_valid == 3:
            head = "三路评审收齐"
        else:
            head = f"仅 {n_valid} 路有效意见"
        return head + "：" + "；".join(parts)


class LiveAdjudicationProvider(AdjudicationProvider):
    """live 模式：读取 reviews_inbox/<pair_id>/adjudication.json（sol 经 subagent 生成后放入）。

    文件缺失或 JSON 非法 → 抛 SolUnavailableError，由编排器按 8.5 协议重试后 DEFERRED。
    """

    def __init__(self, reviews_dir: Path):
        self.reviews_dir = reviews_dir

    def adjudicate(self, pair: PairTask, bundle: dict[str, Any],
                   graph_state: "GraphState") -> dict[str, Any]:
        path = self.reviews_dir / pair.pair_id / "adjudication.json"
        if not path.is_file():
            raise SolUnavailableError(f"adjudication 文件缺失: {path}（单次超时 {SOL_TIMEOUT_SECONDS}s 视同失败）")
        try:
            adj = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            raise SolUnavailableError(f"adjudication JSON 非法: {exc}") from exc
        errs = validate_adjudication_schema(adj)
        if errs:
            raise SolUnavailableError(f"adjudication Schema 不合: {';'.join(errs)}")
        return adj


# ---------------------------------------------------------------------------
# GraphState 与 DAG 校验（自引用 / 重复 / 双向 / Tarjan SCC）
# ---------------------------------------------------------------------------

class GraphState:
    """已接受边集合（含历史运行），pair_id → 边记录。"""

    def __init__(self) -> None:
        self.edges: dict[str, dict[str, Any]] = {}

    def load(self, accepted_path: Path) -> None:
        if not accepted_path.is_file():
            return
        with accepted_path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                self.edges[rec["pair_id"]] = rec

    def add(self, record: dict[str, Any]) -> None:
        self.edges[record["pair_id"]] = record

    def remove(self, pair_id: str) -> dict[str, Any] | None:
        return self.edges.pop(pair_id, None)

    def rewrite(self, accepted_path: Path) -> None:
        accepted_path.parent.mkdir(parents=True, exist_ok=True)
        with accepted_path.open("w", encoding="utf-8") as fh:
            for rec in self.edges.values():
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")

    def prerequisite_adjacency(self) -> tuple[list[str], dict[str, list[str]], dict[tuple[str, str], str]]:
        nodes: list[str] = []
        adj: dict[str, list[str]] = {}
        edge_by_arc: dict[tuple[str, str], str] = {}
        for rec in self.edges.values():
            if rec["relation_type"] != "prerequisite":
                continue
            s, t = rec["source"], rec["target"]
            if s not in adj:
                nodes.append(s)
                adj[s] = []
            if t not in adj:
                nodes.append(t)
                adj[t] = []
            adj[s].append(t)
            edge_by_arc[(s, t)] = rec["pair_id"]
        return nodes, adj, edge_by_arc


def tarjan_scc(nodes: list[str], adj: dict[str, list[str]]) -> list[list[str]]:
    """迭代式 Tarjan 强连通分量。"""
    index: dict[str, int] = {}
    low: dict[str, int] = {}
    on_stack: set[str] = set()
    stack: list[str] = []
    sccs: list[list[str]] = []
    counter = 0

    for root in nodes:
        if root in index:
            continue
        work: list[tuple[str, Iterable[str], int]] = [(root, iter(adj.get(root, ())), 0)]
        index[root] = low[root] = counter
        counter += 1
        stack.append(root)
        on_stack.add(root)
        while work:
            v, it, _ = work[-1]
            advanced = False
            for w in it:
                if w not in index:
                    index[w] = low[w] = counter
                    counter += 1
                    stack.append(w)
                    on_stack.add(w)
                    work.append((w, iter(adj.get(w, ())), 0))
                    advanced = True
                    break
                if w in on_stack:
                    if index[w] < low[v]:
                        low[v] = index[w]
            if advanced:
                continue
            work.pop()
            if work:
                u = work[-1][0]
                if low[v] < low[u]:
                    low[u] = low[v]
            if low[v] == index[v]:
                comp: list[str] = []
                while True:
                    w = stack.pop()
                    on_stack.discard(w)
                    comp.append(w)
                    if w == v:
                        break
                sccs.append(comp)
    return sccs


def check_dag(graph_state: GraphState) -> list[dict[str, Any]]:
    """对 accepted 先修边跑 自引用/重复/双向/Tarjan SCC 检测。

    返回违规项列表；每项含 type 与涉事 pair_id 集合。
    """
    violations: list[dict[str, Any]] = []
    nodes, adj, edge_by_arc = graph_state.prerequisite_adjacency()

    # 自引用（R5 生成期应剔除，仍兜底检测）
    self_loops = sorted(pid for (s, t), pid in edge_by_arc.items() if s == t)
    if self_loops:
        violations.append({"type": "self_reference", "pair_ids": self_loops})

    # 双向（R4）
    seen: set[str] = set()
    bidir: list[str] = []
    for (s, t), pid in edge_by_arc.items():
        if (t, s) in edge_by_arc and pid not in seen:
            bidir.extend([pid, edge_by_arc[(t, s)]])
            seen.add(pid)
            seen.add(edge_by_arc[(t, s)])
    if bidir:
        violations.append({"type": "bidirectional", "pair_ids": sorted(bidir)})

    # 环（Tarjan SCC，size>1 即成环 → R3）
    cyclic: list[str] = []
    for comp in tarjan_scc(nodes, adj):
        if len(comp) > 1:
            for s in comp:
                for t in adj.get(s, ()):
                    if t in comp:
                        cyclic.append(edge_by_arc[(s, t)])
    if cyclic:
        violations.append({"type": "prerequisite_cycle", "pair_ids": sorted(set(cyclic))})

    # 重复边（同一有序弧出现多条不同 pair 记录——正常为唯一，兜底）
    arc_count: dict[tuple[str, str], int] = {}
    for (s, t) in edge_by_arc:
        arc_count[(s, t)] = arc_count.get((s, t), 0) + 1
    dup = sorted(pid for (s, t), pid in edge_by_arc.items() if arc_count[(s, t)] > 1)
    if dup:
        violations.append({"type": "duplicate_edge", "pair_ids": dup})
    return violations


# ---------------------------------------------------------------------------
# 编排主控
# ---------------------------------------------------------------------------

OUTPUT_FILES = {
    "accepted": "accepted_model_adjudicated_edges.jsonl",
    "rejected": "rejected_model_adjudicated.jsonl",
    "escalation": "escalation_queue.jsonl",
    "deferred": "deferred_queue.jsonl",
    "incomplete": "review_incomplete_queue.jsonl",
    "decisions": "decisions.jsonl",
}


class Orchestrator:
    def __init__(
        self,
        workdir: Path,
        cards: dict[str, dict[str, Any]],
        canonical_ids: set[str],
        review_providers: list[ReviewProvider],
        adjudication_provider: AdjudicationProvider,
        prompt_version: str = PROMPT_VERSION,
        retry_delays: tuple[int, ...] = SOL_RETRY_DELAYS,
        breaker_threshold: int = CIRCUIT_BREAKER_THRESHOLD,
        sleep_fn: Callable[[float], None] | None = None,
    ) -> None:
        self.workdir = Path(workdir)
        self.cards = cards
        self.canonical_ids = canonical_ids
        self.review_providers = review_providers
        self.adjudication_provider = adjudication_provider
        self.prompt_version = prompt_version
        self.retry_delays = retry_delays[:SOL_MAX_RETRIES]
        self.breaker_threshold = breaker_threshold
        self.sleep_fn = sleep_fn  # 8.5 退避在 dry-run/单测中不真实 sleep，仅记录
        self.prompt_hash = sha256_text(PROMPT_TEMPLATE + prompt_version)

        self.workdir.mkdir(parents=True, exist_ok=True)
        self.paths = {k: self.workdir / v for k, v in OUTPUT_FILES.items()}
        for path in self.paths.values():  # 产物文件占位（增量追加写）
            path.touch(exist_ok=True)
        self.graph_state = GraphState()
        self.graph_state.load(self.paths["accepted"])
        self.decided: dict[str, dict[str, Any]] = {}   # pair_id → 终态决策（缓存键）
        self._load_decisions()

    # ---- 断点续跑 -------------------------------------------------------

    def _load_decisions(self) -> None:
        path = self.paths["decisions"]
        if not path.is_file():
            return
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                if rec.get("final_status") in TERMINAL_STATUSES:
                    self.decided[rec["pair_id"]] = rec

    def _append(self, key: str, record: dict[str, Any]) -> None:
        path = self.paths[key]
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
            fh.flush()

    # ---- 评审输入构造 ---------------------------------------------------

    def build_bundle_base(self, pair: PairTask) -> dict[str, Any]:
        card_content = {cid: self.cards[cid]["fields"] for cid in (pair.source, pair.target)
                        if cid in self.cards}
        card_content_hash = sha256_text(json.dumps(card_content, ensure_ascii=False, sort_keys=True))
        return {
            "pair_id": pair.pair_id,
            "cards": {cid: self.cards[cid] for cid in (pair.source, pair.target) if cid in self.cards},
            "card_content": card_content,
            "card_content_hash": card_content_hash,
            "prompt_hash": self.prompt_hash,
            "prompt_version": self.prompt_version,
        }

    # ---- 8.5 sol 稳定性协议 ---------------------------------------------

    def call_sol(self, pair: PairTask, bundle: dict[str, Any]) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
        attempts: list[dict[str, Any]] = []
        for i, delay in enumerate(self.retry_delays):
            if delay and self.sleep_fn is not None:
                self.sleep_fn(delay)
            try:
                adj = self.adjudication_provider.adjudicate(pair, bundle, self.graph_state)
                errs = validate_adjudication_schema(adj)
                if errs:
                    raise SolUnavailableError("返回内容非法（Schema 不合）: " + "; ".join(errs))
                return adj, attempts
            except Exception as exc:  # 8.5：非法返回视同失败，计入重试
                attempts.append({
                    "attempt": i + 1,
                    "delay_before_seconds": delay,
                    "timeout_seconds": SOL_TIMEOUT_SECONDS,
                    "error": str(exc),
                    "at": now_iso(),
                })
        return None, attempts

    # ---- 单 pair 主流程 ---------------------------------------------------

    def process_pair(self, pair: PairTask) -> dict[str, Any]:
        pair_cache_key = "pending"
        bundle_base = self.build_bundle_base(pair)
        pair_cache_key = cache_key(pair.pair_id, "review", self.prompt_version,
                                   bundle_base["card_content_hash"])

        # R5 自引用：生成阶段应剔除，流入即直接作废（REJECT_PAIR，不进裁定）
        if pair.source == pair.target:
            rec = {"event": "SELF_REF_REJECT", "pair_id": pair.pair_id,
                   "cache_key": pair_cache_key, "final_status": ST_REJECTED,
                   "reason": "R5 自引用边（A→A）无意义，直接作废该 pair", "decided_at": now_iso()}
            self._append("decisions", rec)
            self._append("rejected", {"pair_id": pair.pair_id, "source": pair.source,
                                      "target": pair.target, "final_status": ST_REJECTED,
                                      "reason": "R5 自引用", "cache_key": pair_cache_key,
                                      "decided_at": now_iso()})
            return {"final_status": ST_REJECTED, "event": "SELF_REF_REJECT"}

        # 三路意见收集 + 程序化校验（Schema/逐字证据/规范实体/旧字段回流）
        evals: list[OpinionEval] = []
        redline_hits: list[dict[str, str]] = []
        missing: list[str] = []
        for provider in self.review_providers:
            raw = provider.get_opinion(pair, bundle_base)
            if raw is None:
                missing.append(provider.reviewer_id)
                evals.append(OpinionEval(reviewer_id=provider.reviewer_id,
                                         invalid_reasons=["意见文件缺失或不可解析（该路缺员）"]))
                continue
            ev = validate_opinion(raw, pair, self.cards,
                                  bundle_base["card_content_hash"], bundle_base["prompt_hash"])
            evals.append(ev)
            redline_hits.extend(ev.redline_hits)

        # 规范实体 / 双向检查
        redline_hits.extend(check_pair_entities(pair, self.canonical_ids))
        redline_hits.extend(check_bidirectional(pair, [e.to_summary() for e in evals],
                                                self.graph_state))

        # 评审缺员 → REVIEW_INCOMPLETE（不得补齐后宣称完成互审；补跑可重试）
        if missing or all(not e.valid for e in evals):
            rec = {"event": "REVIEW_INCOMPLETE", "pair_id": pair.pair_id,
                   "cache_key": pair_cache_key, "final_status": ST_REVIEW_INCOMPLETE,
                   "missing_reviewers": missing,
                   "details": [e.to_summary() for e in evals],
                   "decided_at": now_iso()}
            self._append("decisions", rec)
            self._append("incomplete", {"pair_id": pair.pair_id,
                                        "missing_reviewers": missing,
                                        "cache_key": pair_cache_key, "at": now_iso()})
            return {"final_status": ST_REVIEW_INCOMPLETE, "event": "REVIEW_INCOMPLETE"}

        # 汇总 review_bundle → 拉起 sol（8.5 协议）
        bundle = {"pair_id": pair.pair_id, "cards": bundle_base["cards"],
                  "card_content_hash": bundle_base["card_content_hash"],
                  "opinions": evals, "redline_hits": redline_hits}
        adj, attempts = self.call_sol(pair, bundle)
        if adj is None:
            rec = {"event": "ADJUDICATED", "pair_id": pair.pair_id, "cache_key": pair_cache_key,
                   "final_status": ST_DEFERRED, "redline_hits": redline_hits,
                   "sol_attempts": attempts, "adjudication": None,
                   "reviewers": [e.to_summary() for e in evals], "decided_at": now_iso()}
            self._append("decisions", rec)
            self._append("deferred", {"pair_id": pair.pair_id,
                                      "reason": "R10 gpt-5.6-sol 不可用/超时/3 次重试耗尽",
                                      "sol_attempts": attempts, "cache_key": pair_cache_key,
                                      "deferred_at": now_iso()})
            return {"final_status": ST_DEFERRED, "event": "ADJUDICATED", "sol_attempts": attempts}

        # 红线 R1-R10 复核路由 → 主控采纳建议并落盘
        final_status, applied_hits = route_adjudication(adj, redline_hits, self.graph_state, pair)
        edge_pair_ids = {pair.pair_id}
        if final_status == ST_ACCEPTED:
            confidence_values = [e.raw["confidence"] for e in evals if e.raw and e.valid]
            rel = _vote_relation(evals)
            edge = {
                "edge_id": f"edge:{rel}:{pair.source}->{pair.target}",
                "pair_id": pair.pair_id,
                "source": pair.source,
                "target": pair.target,
                "relation_type": _vote_relation(evals),
                "direction": _vote_direction(evals),
                "status": ST_ACCEPTED,
                "adjudicator": ADJUDICATOR_ID,
                "adopted_by": "orchestrator",
                "adjudicated_at": now_iso(),
                "review_independence": {
                    "model_sources": [REVIEWER_MODELS[r.reviewer_id] for r in self.review_providers],
                    "input_isolated": True,
                },
                "evidence_match": True,
                "minority_uncertain": "minority_uncertain" in adj["rationale"],
                "model_confidence": round(sum(confidence_values) / len(confidence_values), 4) if confidence_values else None,
                "high_influence": pair.high_influence,
                "cache_key": pair_cache_key,
                "prompt_version": self.prompt_version,
                "schema_version": SCHEMA_VERSION,
            }
            self.graph_state.add(edge)
            self._append("accepted", edge)
        elif final_status == ST_REJECTED:
            self._append("rejected", {"pair_id": pair.pair_id, "source": pair.source,
                                      "target": pair.target, "final_status": ST_REJECTED,
                                      "reason": adj["rationale"], "adjudication": adj,
                                      "cache_key": pair_cache_key, "decided_at": now_iso()})
        elif final_status == ST_ESCALATE:
            self._append("escalation", {"pair_id": pair.pair_id, "source": pair.source,
                                        "target": pair.target, "final_status": ST_ESCALATE,
                                        "escalation_reason": adj["escalation_reason"],
                                        "redline_hits": applied_hits, "adjudication": adj,
                                        "cache_key": pair_cache_key, "decided_at": now_iso()})

        rec = {"event": "ADJUDICATED", "pair_id": pair.pair_id, "cache_key": pair_cache_key,
               "final_status": final_status, "redline_hits": applied_hits,
               "sol_attempts": attempts, "adjudication": adj,
               "reviewers": [e.to_summary() for e in evals], "decided_at": now_iso()}
        self._append("decisions", rec)
        return {"final_status": final_status, "event": "ADJUDICATED", "redline_hits": applied_hits}

    # ---- 批处理主循环 -----------------------------------------------------

    def run(self, pairs: list[PairTask]) -> dict[str, Any]:
        summary: dict[str, Any] = {
            "total": len(pairs), "processed": 0, "skipped": 0,
            ST_ACCEPTED: 0, ST_REJECTED: 0, ST_ESCALATE: 0,
            ST_DEFERRED: 0, ST_REVIEW_INCOMPLETE: 0,
            "breaker_triggered": False, "dag_violations": [],
        }
        consecutive_deferred = 0
        processed_pairs: list[PairTask] = []

        for pair in pairs:
            base = self.build_bundle_base(pair)
            key = cache_key(pair.pair_id, "review", self.prompt_version, base["card_content_hash"])
            if pair.pair_id in self.decided:
                summary["skipped"] += 1
                continue
            try:
                outcome = self.process_pair(pair)
            except CircuitBreakerError:
                raise
            summary["processed"] += 1
            processed_pairs.append(pair)
            summary[outcome["final_status"]] += 1
            if outcome["final_status"] == ST_DEFERRED:
                consecutive_deferred += 1
                if consecutive_deferred >= self.breaker_threshold:
                    summary["breaker_triggered"] = True
                    summary["breaker_report"] = {
                        "message": f"连续 {consecutive_deferred} 个 ADJUDICATION_DEFERRED，熔断暂停裁定阶段（8.5 规则 4）",
                        "deferred_pairs": [p.pair_id for p in processed_pairs[-consecutive_deferred:]],
                        "note": "已完成的评审数据保留不丢；请检查 gpt-5.6-sol 可用性后补跑 deferred_queue.jsonl",
                    }
                    raise CircuitBreakerError(summary)
            else:
                consecutive_deferred = 0

        # 每批结束：对 accepted 先修边跑 DAG 校验
        violations = check_dag(self.graph_state)
        summary["dag_violations"] = violations
        if violations:
            print("[DAG 告警] accepted 先修边检测到拓扑冲突，涉事边降级为 ESCALATE_HUMAN：")
            for v in violations:
                print(f"  - {v['type']}: {v['pair_ids']}")
            self._downgrade_edges(violations)
        return summary

    def _downgrade_edges(self, violations: list[dict[str, Any]]) -> None:
        downgraded: list[str] = []
        for v in violations:
            for pid in v["pair_ids"]:
                edge = self.graph_state.remove(pid)
                if edge is None:
                    continue
                downgraded.append(pid)
                self._append("escalation", {
                    "pair_id": pid, "source": edge["source"], "target": edge["target"],
                    "final_status": ST_ESCALATE,
                    "escalation_reason": f"R3 dag_conflict：DAG 校验发现 {v['type']}，涉事边由 ACCEPTED 降级，不得自动删旧边或强行放行",
                    "redline_hits": [{"rule_id": "R3", "detail": f"DAG {v['type']}"}],
                    "downgraded_from": ST_ACCEPTED, "decided_at": now_iso(),
                })
                self._append("decisions", {
                    "event": "DAG_DOWNGRADE", "pair_id": pid, "final_status": ST_ESCALATE,
                    "reason": f"DAG {v['type']}", "decided_at": now_iso(),
                })
        if downgraded:
            self.graph_state.rewrite(self.paths["accepted"])


def _vote_relation(evals: list[OpinionEval]) -> str:
    for e in evals:
        if e.valid:
            return e.raw["relation_type"]
    return "related"


def _vote_direction(evals: list[OpinionEval]) -> str | None:
    for e in evals:
        if e.valid:
            return e.raw["direction"]
    return None


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def load_pairs_file(path: Path, cards: dict[str, dict[str, Any]]) -> list[PairTask]:
    pairs: list[PairTask] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            pair_id = rec["pair_id"]
            pair = make_pair(pair_id, cards)
            pair.high_influence = bool(rec.get("high_influence", False))
            pairs.append(pair)
    return pairs


def build_providers(mode: str, reviews_dir: Path) -> tuple[list[ReviewProvider], AdjudicationProvider]:
    if mode == "live":
        reviewers = [LiveReviewProvider(r, reviews_dir) for r in REVIEWERS]
        adjudicator: AdjudicationProvider = LiveAdjudicationProvider(reviews_dir)
    else:
        reviewers = [DryRunReviewProvider(r, i) for i, r in enumerate(REVIEWERS)]
        adjudicator = DryRunAdjudicationProvider()
    return reviewers, adjudicator


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="P1 多模型互审编排器（dry-run/live）")
    parser.add_argument("--pairs", type=Path, default=None,
                        help="候选对 jsonl；dry-run 缺省时生成 K1 前 5 对演示")
    parser.add_argument("--mode", choices=["dry-run", "live"], default="dry-run")
    parser.add_argument("--workdir", type=Path, default=DEFAULT_WORKDIR)
    parser.add_argument("--reviews-dir", type=Path, default=DEFAULT_REVIEWS_DIR)
    parser.add_argument("--baseline-dir", type=Path, default=DEFAULT_BASELINE_DIR)
    args = parser.parse_args(argv)

    if args.mode == "live" and args.pairs is None:
        parser.error("live 模式必须提供 --pairs")

    cards = load_card_evidence(args.baseline_dir)
    canonical_ids = load_canonical_ids(args.baseline_dir)
    pairs = load_pairs_file(args.pairs, cards) if args.pairs else default_pairs(cards)
    reviewers, adjudicator = build_providers(args.mode, args.reviews_dir)

    orch = Orchestrator(workdir=args.workdir, cards=cards, canonical_ids=canonical_ids,
                        review_providers=reviewers, adjudication_provider=adjudicator)
    try:
        summary = orch.run(pairs)
    except CircuitBreakerError as exc:
        print("[熔断报告]")
        for k, v in exc.report.items():
            print(f"  {k}: {v}")
        return 3

    print(f"[multi_model_review] mode={args.mode} pairs={summary['total']} "
          f"processed={summary['processed']} skipped={summary['skipped']} "
          f"accepted={summary[ST_ACCEPTED]} rejected={summary[ST_REJECTED]} "
          f"escalated={summary[ST_ESCALATE]} deferred={summary[ST_DEFERRED]} "
          f"review_incomplete={summary[ST_REVIEW_INCOMPLETE]}")
    print(f"产物目录: {args.workdir.resolve()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
