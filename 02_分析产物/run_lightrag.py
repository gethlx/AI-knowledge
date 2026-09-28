#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LightRAG 初始导入与索引构建脚本 —— 银河AI通识课程体系 · 知识地图总纲 v3.9.6

用法：
    # 1) 先设置 API 凭据（必填）：
    export OPENAI_API_KEY="sk-..."                          # 调用密钥（Vimox Router）
    export LIGHTRAG_BASE_URL="https://router.vimox.cn/v1"   # OpenAI 兼容端点（可选，默认此值）
    export LIGHTRAG_MODEL="gpt-5.6-luna"                    # 抽取模型（可选，默认此值，选型见 11 号报告）
    export LIGHTRAG_EMBED_MODEL="glm-embedding-3-pro"       # 向量模型（可选，默认此值）

    # 2) 运行：
    /Users/larry/.workbuddy/binaries/python/envs/default/bin/python run_lightrag.py

设计要点（对应 v3.9.6 口径）：
  1. 每卡一块：自定义 chunking_func 按 ◆◆◆ 分隔符切，保证 197 卡 = 197 块，不跨卡截断；
  2. 实体对齐：addon_params["entity_types_guidance"] 写死「只认 197 卡规范名（卡号+中文名）」；
  3. 关系语义：抽取提示词限定为「教学先修 prerequisite」与「相关 related」，必须给出处；
  4. 边不可信：抽取产出的所有关系一律视为「AI 提议，未核验」，导出后须走人工裁决流程
     （见 03_交付物/09-知识图谱建边路径调研.md），不得直接作前向决策依据。
"""
import asyncio
import os
import sys

BASE = "/Users/larry/WorkBuddy/2026-09-13-14-09-47"
INPUT_DOC = os.environ.get(
    "LIGHTRAG_INPUT",
    f"{BASE}/02_分析产物/lightrag_input/总纲197卡-摄入版.md")
WORKDIR = os.environ.get("LIGHTRAG_WORKDIR", f"{BASE}/02_分析产物/lightrag_workdir")
EDGES_OUT = f"{WORKDIR}/proposed_edges.json"

# ---------- 0. 凭据检查（缺 key 直接给出明确指引，不做半途报错） ----------
API_KEY = os.environ.get("OPENAI_API_KEY", "")
BASE_URL = os.environ.get("LIGHTRAG_BASE_URL", "https://router.vimox.cn/v1")
MODEL = os.environ.get("LIGHTRAG_MODEL", "gpt-5.6-luna")
EMBED_MODEL = os.environ.get("LIGHTRAG_EMBED_MODEL", "glm-embedding-3-pro")

if not API_KEY:
    print("⛔ 缺少 OPENAI_API_KEY，无法调用抽取模型。请先执行：")
    print('   export OPENAI_API_KEY="你的密钥"')
    print(f"   （端点默认 {BASE_URL}，模型默认 {MODEL}，可用 LIGHTRAG_BASE_URL / LIGHTRAG_MODEL 覆盖）")
    sys.exit(2)

# ---------- 1. 实体类型与抽取语义（v3.9.6 口径写死） ----------
ENTITY_TYPES_GUIDANCE = """实体类型（只允许以下一类）：
- "AI概念"：必须对应输入文本中某张概念卡。实体命名规范：使用卡的规范名「卡号 中文名」
  （如「1-01 人工智能」「3-04 大模型」）。禁止使用变体名、简称、英文名或任何不在
  【卡号｜中文名｜…】标题行中出现的名称。若一段文本中不包含任何卡标题行所定义的概念，
  则不得产出实体。

关系类型（只允许以下两类）：
- "先修"（prerequisite）：从 A 指向 B，表示「学生需要先理解 A，才可能理解 B」。
  判断依据只能是卡中内容的教学逻辑（定义依赖、原理依赖、认知层级递进），不得凭常识臆测。
- "相关"（related）：A 与 B 在教学中存在对照、易混或延伸关系，但无先后依赖。

每条关系必须附 evidence 字段：引用支撑该关系的原句（来自卡的哪个字段、什么内容）。
无法给出 evidence 的关系一律不要输出。"""

# ---------- 2. 自定义分块：按 ◆◆◆ 切，一卡一块 ----------
def chunk_by_card(tokenizer, content, override_fulltext_embed=None, split_only=False,
                  overlap_token_size=100, max_token_size=1200, *args, **kwargs):
    """LightRAG legacy 6 参 chunking_func。返回 [{'tokens': int, 'content': str}, ...]"""
    parts = [p.strip() for p in content.split("◆◆◆") if p.strip()]
    chunks = []
    for p in parts:
        tokens = len(tokenizer.encode(p)) if hasattr(tokenizer, "encode") else len(p) // 2
        chunks.append({"tokens": tokens, "content": p})
    return chunks

# ---------- 3. 组装 LightRAG ----------
from lightrag import LightRAG, QueryParam
from lightrag.utils import EmbeddingFunc
from lightrag.llm.openai import openai_complete_if_cache, openai_embed

async def llm_model_func(prompt, system_prompt=None, history_messages=None, **kwargs):
    return await openai_complete_if_cache(
        MODEL,
        prompt,
        system_prompt=system_prompt,
        history_messages=history_messages or [],
        base_url=BASE_URL,
        api_key=API_KEY,
        **kwargs,
    )

async def _embed_impl(texts):
    return await openai_embed(
        texts,
        model=EMBED_MODEL,
        base_url=BASE_URL,
        api_key=API_KEY,
    )

embedding_dim = int(os.environ.get("LIGHTRAG_EMBED_DIM", "4096"))  # glm-embedding-3-pro 实测 4096 维
embedding_func = EmbeddingFunc(
    embedding_dim=embedding_dim,
    max_token_size=8192,
    func=_embed_impl,
)

rag = LightRAG(
    working_dir=WORKDIR,
    llm_model_func=llm_model_func,
    llm_model_name=MODEL,
    embedding_func=embedding_func,
    chunking_func=chunk_by_card,
    addon_params={"language": "Simplified Chinese",
                   "entity_types_guidance": ENTITY_TYPES_GUIDANCE},
    llm_model_max_async=4,
)

# ---------- 4. 导入 + 索引构建 ----------
async def main():
    with open(INPUT_DOC, encoding="utf-8") as f:
        text = f.read()
    n_cards = text.count("【")
    print(f"摄入文档：{INPUT_DOC}")
    print(f"  卡块数（按【计数）：{n_cards}　总字符：{len(text):,}")

    print("\n开始导入（每卡一块，抽取实体与关系）……")
    await rag.initialize_storages()
    try:
        await rag.ainsert(text)
    finally:
        await rag.finalize_storages()

    print("✅ 索引构建完成。workdir 内容：")
    for fn in sorted(os.listdir(WORKDIR)):
        p = os.path.join(WORKDIR, fn)
        if os.path.isfile(p):
            print(f"  {fn:32} {os.path.getsize(p):>10,} B")

    # ---------- 5. 导出候选边（全部标记「AI 提议，未核验」） ----------
    _export_edges(rag, EDGES_OUT)

def _export_edges(rag, out_path):
    """从 networkx 图导出候选边清单，统一打上「AI 提议，未核验」标记。"""
    import json
    g = None
    for attr in ("chunk_graph", "entities_graph", "_graph"):
        g = getattr(rag, attr, None)
        if g is not None:
            break
    if g is None:
        print("（未找到图对象，跳过边导出——用 storage 文件检查）")
        return
    edges = []
    for u, v, d in g.edges(data=True):
        edges.append({
            "source": u, "target": v,
            "relation": d.get("relation", d.get("description", "")),
            "weight": d.get("weight"),
            "evidence": (d.get("description") or "")[:500],
            "status": "AI提议-未核验",   # ← v3.9.6 口径：未经人工裁决，不得作前向决策依据
        })
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"note": "全部边为 AI 提议，未经人工核验；裁决流程见 09-知识图谱建边路径调研.md",
                    "count": len(edges), "edges": edges}, f, ensure_ascii=False, indent=2)
    print(f"✅ 候选边导出：{out_path}（{len(edges)} 条，全部 status=AI提议-未核验）")

if __name__ == "__main__":
    asyncio.run(main())
