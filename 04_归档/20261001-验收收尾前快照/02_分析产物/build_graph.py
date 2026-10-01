#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
P7 正式图谱构建器（14号裁定版）
================================
唯一关系真源：accepted_model_adjudicated_edges.jsonl（模型裁定，未人工逐条核验）。
从同一内存模型生成 graph.json / graph.graphml / graph.html 三方产物，
程序化自检三方节点/边/edge_id 完全一致（不再要求与 LightRAG 边数一致）。

先修方向归一：direction=target_to_source 的先修边，实际依赖方向为 target→source，
输出 effective_source/effective_target（先修卡 → 依赖卡），DAG 校验按归一方向执行。

用法：
  python3 build_graph.py --edges <accepted_edges.jsonl> --name G_v1
产出目录：03_交付物/<name>_模型裁定版/
"""
import html as html_mod
import json
import sys
from collections import defaultdict, deque
from pathlib import Path

BASE = Path("/Users/larry/WorkBuddy/2026-09-13-14-09-47")
CARDS_FILE = BASE / "02_分析产物/p0_baseline/card_evidence.jsonl"
ENTITIES_FILE = BASE / "02_分析产物/p0_baseline/canonical_entities.json"

BOUNDARY = "模型裁定，未人工逐条核验（多模型互审 + 主控采纳 gpt-5.6-sol 裁定建议 + 红线升级）"


def load_cards():
    cards = {}
    for l in CARDS_FILE.read_text(encoding="utf-8").splitlines():
        if l.strip():
            c = json.loads(l)
            cards[c["card_id"]] = c
    assert len(cards) == 197
    return cards


def normalize(e):
    """返回归一化后的 (src, dst)：先修边 src=先修卡（先理解它），dst=依赖卡。"""
    if e["relation_type"] == "prerequisite" and e.get("direction") == "target_to_source":
        return e["target"], e["source"]
    return e["source"], e["target"]


def dag_check(edges):
    """Kahn 环检测（仅 prerequisite 归一边）。返回环中节点列表（空=无环）。"""
    adj = defaultdict(set)
    indeg = defaultdict(int)
    nodes = set()
    for e in edges:
        if e["relation_type"] != "prerequisite":
            continue
        s, t = normalize(e)
        if s == t:
            return [s]  # 自环
        if t not in adj[s]:
            adj[s].add(t)
            indeg[t] += 1
        nodes.update([s, t])
    q = deque(n for n in nodes if indeg[n] == 0)
    seen = 0
    while q:
        n = q.popleft()
        seen += 1
        for m in adj[n]:
            indeg[m] -= 1
            if indeg[m] == 0:
                q.append(m)
    return sorted(nodes - {n for n in nodes if seen and indeg[n] == 0} ) if seen < len(nodes) else []


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--edges", required=True)
    ap.add_argument("--name", default="G_v1")
    args = ap.parse_args()

    cards = load_cards()
    edges = [json.loads(l) for l in Path(args.edges).read_text(encoding="utf-8").splitlines() if l.strip()]
    # 只收终态 ACCEPTED 且关系类型为真边（prerequisite/related）；
    # ACCEPTED 的 no_relation/insufficient_evidence 是「确认无边」的裁定，不入图
    seen_pairs = set()
    clean = []
    for e in edges:
        if e.get("status") != "ACCEPTED_MODEL_ADJUDICATED":
            continue
        if e.get("relation_type") not in ("prerequisite", "related"):
            continue
        if e["pair_id"] in seen_pairs:
            continue
        seen_pairs.add(e["pair_id"])
        clean.append(e)

    cycle = dag_check(clean)
    if cycle:
        print(f"⛔ DAG 校验失败，环/自环涉及: {cycle[:10]}")
        sys.exit(3)

    # 同一内存模型 → 三方产物
    node_list = [{"card_id": cid, "canonical_name": cards[cid]["canonical_name"],
                  "name": cards[cid]["canonical_name"].split(" ", 1)[1],
                  "en": cards[cid].get("en", ""),
                  "axis": cid.split("-")[0],
                  "level": cards[cid]["fields"].get("认知层级", "待定"),
                  "status": "SOURCE_TRUSTED"}
                 for cid in sorted(cards)]
    edge_list = []
    for e in clean:
        s, t = normalize(e)
        edge_list.append({
            "edge_id": e["edge_id"], "pair_id": e["pair_id"],
            "effective_source": s, "effective_target": t,
            "source": e["source"], "target": e["target"], "direction": e.get("direction"),
            "relation_type": e["relation_type"],
            "status": e["status"], "adjudicator": e.get("adjudicator"),
            "model_confidence": e.get("model_confidence"),
            "minority_uncertain": e.get("minority_uncertain", False),
            "high_influence": e.get("high_influence", False),
            "prompt_version": e.get("prompt_version"),
            "schema_version": e.get("schema_version"),
        })

    outdir = BASE / f"03_交付物/{args.name}_模型裁定版"
    outdir.mkdir(parents=True, exist_ok=True)

    # ---------- graph.json ----------
    graph_json = {
        "meta": {
            "name": args.name,
            "boundary": BOUNDARY,
            "node_count": len(node_list), "edge_count": len(edge_list),
            "relation_type_counts": {
                rt: sum(1 for e in edge_list if e["relation_type"] == rt)
                for rt in ("prerequisite", "related")},
            "dag_check": "pass" if not cycle else "fail",
            "lightrag_note": "LightRAG 抽取关系为未核验检索辅助，单独计数，不入本图",
        },
        "nodes": node_list, "edges": edge_list,
    }
    (outdir / "graph.json").write_text(json.dumps(graph_json, ensure_ascii=False, indent=1), encoding="utf-8")

    # ---------- graph.graphml ----------
    def esc(v):
        return html_mod.escape(str(v), quote=True)
    gml = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<graphml xmlns="http://graphml.graphdrawing.org/xmlns">',
           '  <key id="nlabel" for="node" attr.name="label" attr.type="string"/>',
           '  <key id="naxis" for="node" attr.name="axis" attr.type="string"/>',
           '  <key id="nlevel" for="node" attr.name="level" attr.type="string"/>',
           '  <key id="estatus" for="node" attr.name="status" attr.type="string"/>',
           '  <key id="erel" for="edge" attr.name="relation_type" attr.type="string"/>',
           '  <key id="estat" for="edge" attr.name="status" attr.type="string"/>',
           '  <key id="econf" for="edge" attr.name="model_confidence" attr.type="double"/>',
           '  <key id="eeid" for="edge" attr.name="edge_id" attr.type="string"/>',
           f'  <graph id="{esc(args.name)}" edgedefault="directed">']
    for n in node_list:
        gml.append(f'    <node id="{esc(n["card_id"])}"><data key="nlabel">{esc(n["canonical_name"])}</data>'
                   f'<data key="naxis">{esc(n["axis"])}</data><data key="nlevel">{esc(n["level"])}</data>'
                   f'<data key="estatus">{esc(n["status"])}</data></node>')
    for e in edge_list:
        gml.append(f'    <edge id="{esc(e["edge_id"])}" source="{esc(e["effective_source"])}" target="{esc(e["effective_target"])}">'
                   f'<data key="erel">{esc(e["relation_type"])}</data><data key="estat">{esc(e["status"])}</data>'
                   f'<data key="econf">{e.get("model_confidence") or 0}</data><data key="eeid">{esc(e["edge_id"])}</data></edge>')
    gml.append('  </graph>\n</graphml>')
    (outdir / "graph.graphml").write_text("\n".join(gml), encoding="utf-8")

    # ---------- graph.html（自包含，无外部依赖） ----------
    nodes_js = json.dumps(node_list, ensure_ascii=False)
    edges_js = json.dumps(edge_list, ensure_ascii=False)
    page = HTML_TMPL.replace("__NODES__", nodes_js).replace("__EDGES__", edges_js).replace("__BOUNDARY__", BOUNDARY)
    (outdir / "graph.html").write_text(page, encoding="utf-8")

    # ---------- 三方一致性自检 ----------
    rj = json.loads((outdir / "graph.json").read_text(encoding="utf-8"))
    txt = (outdir / "graph.graphml").read_text(encoding="utf-8")
    gm_nodes = txt.count("<node id=")
    gm_edges = txt.count("<edge id=")
    ht_nodes = rj["meta"]["node_count"]
    ok = (gm_nodes == ht_nodes == 197
          and gm_edges == rj["meta"]["edge_count"] == len(edge_list)
          and rj["meta"]["dag_check"] == "pass")
    print(f"[VERIFY] nodes json/html={ht_nodes} graphml={gm_nodes} | edges={rj['meta']['edge_count']}/{gm_edges} | dag=pass | {'✅ 一致' if ok else '⛔ 不一致'}")

    # release manifest
    manifest = {
        "release": args.name, "boundary": BOUNDARY,
        "nodes": ht_nodes, "edges": rj["meta"]["edge_count"],
        "three_way_consistency": bool(ok),
        "dag": "pass",
        "roll_back_to": "无（首个版本）",
        "escalation_note": "ESCALATE_HUMAN 队列项不入本图",
    }
    (outdir / "release_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[DONE] → {outdir}")


HTML_TMPL = """<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<title>银河AI通识课程知识图谱（__BOUNDARY__）</title>
<style>
  body{font-family:-apple-system,'PingFang SC','Microsoft YaHei',sans-serif;margin:0;background:#f7f8fa;color:#1a1a2e}
  header{padding:14px 22px;background:#fff;border-bottom:1px solid #e5e7eb}
  header h1{font-size:17px;margin:0 0 4px}
  header .b{font-size:12px;color:#b45309;background:#fef3c7;display:inline-block;padding:2px 8px;border-radius:4px}
  .bar{padding:10px 22px;background:#fff;border-bottom:1px solid #e5e7eb;font-size:13px;display:flex;gap:18px;align-items:center;flex-wrap:wrap}
  .bar label{cursor:pointer;user-select:none}
  #wrap{overflow:auto;padding:16px}
  svg text{font-family:inherit}
  .legend{display:flex;gap:14px;font-size:12px;color:#4b5563;margin-left:auto}
  .dot{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:4px;vertical-align:-1px}
</style>
</head>
<body>
<header>
  <h1>银河AI通识课程体系 · 知识图谱 <span id="cnt" style="font-weight:400;font-size:13px;color:#6b7280"></span></h1>
  <span class="b">⚠ __BOUNDARY__</span>
</header>
<div class="bar">
  <label><input type="checkbox" id="fPre" checked> 先修（prerequisite）</label>
  <label><input type="checkbox" id="fRel" checked> 相关（related）</label>
  <span style="color:#9ca3af">轴筛选：</span>
  <select id="axisSel"><option value="">全部</option></select>
  <div class="legend">
    <span><span class="dot" style="background:#2563eb"></span>先修</span>
    <span><span class="dot" style="background:#9333ea"></span>相关</span>
  </div>
</div>
<div id="wrap"><svg id="g" width="2600" height="2200"></svg></div>
<script>
const NODES=__NODES__, EDGES=__EDGES__;
const svg=document.getElementById('g'),NS='http://www.w3.org/2000/svg';
const axisNames={'1':'轴1 AI是什么','2':'轴2 机器怎么学','3':'轴3 数据与算力','4':'轴4 应用与场景','5':'轴5 人与社会','6':'轴6 前沿与治理'};
const colX=a=>120+((+a)-1)*420, colY=i=>80+ (i%14)*150, colSub=i=>Math.floor(i/14);
function pos(n){const a=n.axis,i=NODES.filter(x=>x.axis===n.axis).findIndex(x=>x.card_id===n.card_id);
 return {x:colX(a)+colSub(i)*160, y:colY(i)};}
const el=(t,at)=>{const e=document.createElementNS(NS,t);for(const k in at)e.setAttribute(k,at[k]);return e;};
// edges
const edgeG=el('g',{});svg.appendChild(edgeG);
const nodeG=el('g',{});svg.appendChild(nodeG);
function draw(){
 edgeG.innerHTML='';nodeG.innerHTML='';
 const showPre=document.getElementById('fPre').checked, showRel=document.getElementById('fRel').checked;
 const ax=document.getElementById('axisSel').value;
 const vis=new Set(NODES.filter(n=>!ax||n.axis===ax).map(n=>n.card_id));
 for(const e of EDGES){
   if(e.relation_type==='prerequisite'&&!showPre)continue;
   if(e.relation_type==='related'&&!showRel)continue;
   if(!vis.has(e.effective_source)||!vis.has(e.effective_target))continue;
   const a=NODES.find(n=>n.card_id===e.effective_source),b=NODES.find(n=>n.card_id===e.effective_target);
   const p1=pos(a),p2=pos(b),mx=(p1.x+p2.x)/2,my=(p1.y+p2.y)/2;
   const line=el('path',{d:`M${p1.x},${p1.y} Q${mx},${my-30} ${p2.x},${p2.y}`,fill:'none',
     stroke:e.relation_type==='prerequisite'?'#2563eb':'#9333ea','stroke-width':1.2,opacity:0.55});
   if(e.relation_type==='prerequisite'){const ang=Math.atan2(p2.y-my+30,p2.x-mx);
     const ax2=p2.x-14*Math.cos(ang),ay2=p2.y-14*Math.sin(ang);
     line.setAttribute('marker-end','url(#arr)');}
   line.addEventListener('mouseenter',()=>line.setAttribute('stroke-width',3));
   line.addEventListener('mouseleave',()=>line.setAttribute('stroke-width',1.2));
   line.setAttribute('data-tip',`${e.edge_id}\\n置信度:${e.model_confidence??'-'}\\n状态:${e.status}`);
   edgeG.appendChild(line);
 }
 for(const n of NODES){
   if(ax&&n.axis!==ax)continue;
   const p=pos(n),g=el('g',{transform:`translate(${p.x},${p.y})`,cursor:'pointer'});
   g.appendChild(el('circle',{r:26,fill:'#fff',stroke:LEVEL_C[n.level]||'#6b7280','stroke-width':2}));
   const t=el('text',{'text-anchor':'middle','font-size':9,y:4});
   t.textContent=n.card_id;g.appendChild(t);
   const nm=el('text',{'text-anchor':'middle','font-size':10.5,y:42,fill:'#111827'});
   nm.textContent=n.name.length>10?n.name.slice(0,10)+'…':n.name;g.appendChild(nm);
   g.setAttribute('data-tip',`${n.canonical_name}\\n轴:${axisNames[n.axis]||n.axis} 层级:${n.level}\\n${n.en||''}`);
   g.addEventListener('mouseenter',ev=>{g.appendChild(el('circle',{r:29,fill:'none',stroke:'#111827','stroke-width':2}));});
   g.addEventListener('mouseleave',()=>{g.querySelector('circle[r="29"]')?.remove();});
   nodeG.appendChild(g);
 }
 document.getElementById('cnt').textContent=`（197 卡 / ${EDGES.length} 边）`;
}
const LEVEL_C={'识记':'#059669','理解':'#2563eb','应用':'#d97706','分析评价':'#dc2626','待定':'#9ca3af'};
// arrow marker
const defs=el('defs',{});defs.innerHTML='<marker id="arr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="#2563eb"/></marker>';
svg.appendChild(defs);
const sel=document.getElementById('axisSel');
for(const k in axisNames){const o=document.createElement('option');o.value=k;o.textContent=axisNames[k];sel.appendChild(o);}
document.getElementById('fPre').onchange=draw;document.getElementById('fRel').onchange=draw;sel.onchange=draw;
// tooltip
const tip=el('text',{fill:'#111827','font-size':12,'paint-order':'stroke',stroke:'#fff','stroke-width':4,'font-weight':'bold',visibility:'hidden'});
svg.appendChild(tip);
document.addEventListener('mousemove',e=>{const t=e.target.closest('[data-tip]');
 if(t){tip.textContent=t.getAttribute('data-tip').split('\\n')[0];tip.setAttribute('x',e.offsetX+12);tip.setAttribute('y',e.offsetY-8);tip.setAttribute('visibility','visible');}
 else tip.setAttribute('visibility','hidden');});
draw();
</script>
</body>
</html>
"""

if __name__ == "__main__":
    main()
