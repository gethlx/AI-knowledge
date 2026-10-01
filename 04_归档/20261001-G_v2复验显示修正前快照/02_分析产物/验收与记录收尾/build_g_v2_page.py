#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
F4 整改：按 G_v2 数据生成展示页面 graph.html（31 号报告收尾顺序第 3 步）。

以 G_v1_展示修正版/graph.html 为骨架做字符串手术：
1. 数据块整体替换为 G_v2 graph.json（1,562 边）；
2. 标题/横幅更新为 G_v2 基线（graph_version 0bd1a09cd159）；
3. 修复 v1 缺陷：tooltip 只显示第一行 → 改为多行 HTML 浮层，
   先修边提示带方向端点（src ⇒ tgt）；
4. 新增节点点击详情面板：入边/出边清单（先修带方向、相关无向），
   关系清单直接由页面内 EDGES 按 effective 端点计算，保证与所画边一致；
5. 节点定义来自重建后的 node_summaries.json（F1 产物）。
页面渲染逻辑（先修 marker-end 箭头指向 effective_target）与 v1 一致，未改动语义。
"""
import json, sys, pathlib

ROOT = pathlib.Path("/Users/larry/WorkBuddy/2026-09-13-14-09-47")
V1_HTML = ROOT / "03_交付物/G_v1_展示修正版/graph.html"
V2_DIR = ROOT / "03_交付物/G_v2_模型裁定版"
OUT = V2_DIR / "graph.html"

g = json.loads((V2_DIR / "graph.json").read_text())
summaries = json.loads((V2_DIR / "node_summaries.json").read_text())
meta = g["meta"]
nodes, edges = g["nodes"], g["edges"]

assert len(nodes) == meta["node_count"] == 197
assert len(edges) == meta["edge_count"] == 1562
assert meta["graph_version"] == "0bd1a09cd159"

# 节点定义映射（F1 重建摘要）
defs = {n["card_id"]: n.get("definition", "") for n in summaries}
assert len(defs) == 197 and all(defs.values()), "存在空定义"

def json_embed(obj):
    s = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    return s.replace("</", "<\\/")  # 防 </script> 提前闭合

tpl = V1_HTML.read_text()

# ---------- 1. 数据块边界 ----------
data_start = tpl.find("const NODES=[")
data_end = tpl.find("];\nconst svg=")
assert data_start > 0 and data_end > data_start, "v1 数据块边界定位失败"

# ---------- 2. 标题 / 横幅 ----------
old_title = tpl[tpl.find("<title>"): tpl.find("</title>") + len("</title>")]
new_title = "<title>银河AI通识课程知识图谱 G_v2（模型裁定版 · 186 对按原始最终裁定恢复入图）</title>"

old_banner = '<span class="b">⚠ 模型裁定，未人工逐条核验（多模型互审 + 主控采纳 gpt-5.6-sol 裁定建议 + 红线升级）</span>'
new_banner = (f'<span class="b">G_v2 · graph_version {meta["graph_version"]} · 模型裁定未人工逐条核验'
              f'（229 对按原始最终裁定重分流：186 恢复 / 43 排除，主公明示豁免人工验收）</span>')
assert old_banner in tpl, "v1 横幅定位失败"

head = tpl[:data_start].replace(old_title, new_title).replace(old_banner, new_banner)

# ---------- 3. 详情面板 + 浮层提示框（插在 #wrap 之前）----------
panel_html = '''
<div id="tipbox" style="display:none;position:fixed;pointer-events:none;background:#111827;color:#fff;
  font-size:12px;line-height:1.5;padding:6px 10px;border-radius:6px;z-index:50;max-width:340px;white-space:pre-line"></div>
<div id="panel" style="display:none;position:fixed;top:0;right:0;width:340px;height:100%;background:#fff;
  border-left:1px solid #e5e7eb;box-shadow:-4px 0 16px rgba(0,0,0,.08);z-index:40;overflow-y:auto;padding:16px">
  <div style="display:flex;justify-content:space-between;align-items:center">
    <b id="panel-title" style="font-size:14px"></b>
    <button onclick="document.getElementById('panel').style.display='none'"
      style="border:none;background:none;font-size:16px;cursor:pointer;color:#6b7280">✕</button>
  </div>
  <div id="panel-body" style="font-size:12.5px;margin-top:10px;line-height:1.7"></div>
</div>
'''
wrap_at = head.find('<div id="wrap">')
head = head[:wrap_at] + panel_html + head[wrap_at:]

# ---------- 4. 新数据块 + 增强 JS ----------
js = r'''const NODES=__NODES__;
const EDGES=__EDGES__;
const DEFS=__DEFS__;
const svg=document.getElementById('g'),NS='http://www.w3.org/2000/svg';
const axisNames={'1':'K1 人类、智能与机器','2':'K2 数据、表征与知识','3':'K3 算法、模型与学习','4':'K4 生成式AI、交互与智能体','5':'K5 AI应用、工程与创新','6':'K6 社会、伦理与未来'};
const colX=a=>120+((+a)-1)*420, colY=i=>80+ (i%14)*150, colSub=i=>Math.floor(i/14);
function pos(n){const a=n.axis,i=NODES.filter(x=>x.axis===n.axis).findIndex(x=>x.card_id===n.card_id);
 return {x:colX(a)+colSub(i)*160, y:colY(i)};}
const el=(t,at)=>{const e=document.createElementNS(NS,t);for(const k in at)e.setAttribute(k,at[k]);return e;};
const byId=Object.fromEntries(NODES.map(n=>[n.card_id,n]));
const RTNAME={prerequisite:'先修',related:'相关'};
// —— 关系清单按 effective 端点从 EDGES 现算，保证与画出的边一致 ——
function relsOf(id){
  const ins=EDGES.filter(e=>e.effective_target===id), outs=EDGES.filter(e=>e.effective_source===id);
  return {ins,outs,degree:ins.length+outs.length};
}
const edgeG=el('g',{});svg.appendChild(edgeG);
const nodeG=el('g',{});svg.appendChild(nodeG);
const tipbox=document.getElementById('tipbox');
function showTip(lines,ev){tipbox.textContent=lines.join('\n');tipbox.style.display='block';moveTip(ev);}
function moveTip(ev){tipbox.style.left=Math.min(ev.clientX+14,innerWidth-360)+'px';tipbox.style.top=(ev.clientY+10)+'px';}
function hideTip(){tipbox.style.display='none';}
function draw(){
 edgeG.innerHTML='';nodeG.innerHTML='';
 const showPre=document.getElementById('fPre').checked, showRel=document.getElementById('fRel').checked;
 const ax=document.getElementById('axisSel').value;
 const vis=new Set(NODES.filter(n=>!ax||n.axis===ax).map(n=>n.card_id));
 let nDrawn=0;
 for(const e of EDGES){
   if(e.relation_type==='prerequisite'&&!showPre)continue;
   if(e.relation_type==='related'&&!showRel)continue;
   if(!vis.has(e.effective_source)||!vis.has(e.effective_target))continue;
   const a=byId[e.effective_source],b=byId[e.effective_target];
   if(!a||!b)continue;
   const p1=pos(a),p2=pos(b),mx=(p1.x+p2.x)/2,my=(p1.y+p2.y)/2;
   const isPre=e.relation_type==='prerequisite';
   const line=el('path',{d:`M${p1.x},${p1.y} Q${mx},${my-30} ${p2.x},${p2.y}`,fill:'none',
     stroke:isPre?'#2563eb':'#9333ea','stroke-width':1.2,opacity:0.55});
   if(isPre)line.setAttribute('marker-end','url(#arr)');
   line.addEventListener('mouseenter',()=>line.setAttribute('stroke-width',3));
   line.addEventListener('mouseleave',()=>line.setAttribute('stroke-width',1.2));
   const tip= isPre
     ? [`${e.effective_source} ⇒ ${e.effective_target}（先修）`,
        `方向：${a.name} 是 ${b.name} 的先修`,
        `edge_id: ${e.edge_id} · 置信度: ${e.model_confidence??'-'} · 状态: ${e.status}`]
     : [`${e.effective_source} — ${e.effective_target}（相关）`,
        `edge_id: ${e.edge_id} · 置信度: ${e.model_confidence??'-'} · 状态: ${e.status}`];
   line.addEventListener('mousemove',ev=>showTip(tip,ev));
   line.addEventListener('mouseleave',hideTip);
   edgeG.appendChild(line);nDrawn++;
 }
 for(const n of NODES){
   if(ax&&n.axis!==ax)continue;
   const p=pos(n),g=el('g',{transform:`translate(${p.x},${p.y})`,cursor:'pointer'});
   g.appendChild(el('circle',{r:26,fill:'#fff',stroke:LEVEL_C[n.level]||'#6b7280','stroke-width':2}));
   const t=el('text',{'text-anchor':'middle','font-size':9,y:4});
   t.textContent=n.card_id;g.appendChild(t);
   const nm=el('text',{'text-anchor':'middle','font-size':10.5,y:42,fill:'#111827'});
   nm.textContent=n.name.length>10?n.name.slice(0,10)+'…':n.name;g.appendChild(nm);
   const r=relsOf(n.card_id);
   g.addEventListener('mousemove',ev=>showTip(
     [n.canonical_name,`${axisNames[n.axis]||n.axis} · ${n.level} · 度 ${r.degree}`,n.en||'','（点击查看关系清单）'],ev));
   g.addEventListener('mouseleave',hideTip);
   g.addEventListener('click',()=>openPanel(n));
   nodeG.appendChild(g);
 }
 document.getElementById('cnt').textContent=`（197 卡 / ${EDGES.length} 边 · 当前绘制 ${nDrawn} 边）`;
}
function esc(s){const d=document.createElement('div');d.textContent=s==null?'':String(s);return d.innerHTML;}
function edgeLine(e,self,dir){
  const other=dir==='in'?e.effective_source||e.from:e.effective_target||e.to;
  const oname=byId[other]?byId[other].name:other;
  const rt=e.relation_type||e.rt||'related';
  if(rt==='prerequisite'){
    return dir==='in'
      ? `▲ <a href="#" data-card="${other}">${esc(other)} ${esc(oname)}</a> ⇒ 本卡（先修）`
      : `▼ 本卡 ⇒ <a href="#" data-card="${other}">${esc(other)} ${esc(oname)}</a>（先修）`;
  }
  return `◆ <a href="#" data-card="${other}">${esc(other)} ${esc(oname)}</a>（相关）`;
}
function openPanel(n){
  const r=relsOf(n.card_id);
  document.getElementById('panel-title').textContent=n.canonical_name;
  const d=DEFS[n.card_id]||'';
  let h=`<div style="color:#6b7280">${esc(n.en||'')}</div>
    <div>${esc(axisNames[n.axis]||n.axis)} · 层级 ${esc(n.level)} · 状态 ${esc(n.status)}</div>
    <div style="margin:6px 0;color:#374151"><b>度：</b>${r.degree}（入 ${r.ins.length} / 出 ${r.outs.length}）</div>
    <div style="color:#374151"><b>定义：</b>${esc(d)}</div>
    <div style="margin-top:10px"><b>入边（${r.ins.length}）</b><ul style="padding-left:18px;margin:4px 0">`;
  h+=r.ins.map(e=>`<li>${edgeLine(e,n.card_id,'in')}</li>`).join('')||'<li>无</li>';
  h+=`</ul><b>出边（${r.outs.length}）</b><ul style="padding-left:18px;margin:4px 0">`;
  h+=r.outs.map(e=>`<li>${edgeLine(e,n.card_id,'out')}</li>`).join('')||'<li>无</li>';
  h+='</ul>';
  document.getElementById('panel-body').innerHTML=h;
  document.getElementById('panel').style.display='block';
  document.getElementById('panel-body').querySelectorAll('a[data-card]').forEach(a=>{
    a.addEventListener('click',ev=>{ev.preventDefault();const t=byId[a.dataset.card];if(t)openPanel(t);});
  });
}
const LEVEL_C={'识记':'#059669','理解':'#2563eb','应用':'#d97706','分析评价':'#dc2626','待定':'#9ca3af'};
const defs=el('defs',{});defs.innerHTML='<marker id="arr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="#2563eb"/></marker>';
svg.appendChild(defs);
const sel=document.getElementById('axisSel');
for(const k in axisNames){const o=document.createElement('option');o.value=k;o.textContent=axisNames[k];sel.appendChild(o);}
document.getElementById('fPre').onchange=draw;document.getElementById('fRel').onchange=draw;sel.onchange=draw;
draw();
'''
js = js.replace("__NODES__", json_embed(nodes))
js = js.replace("__EDGES__", json_embed(edges))
js = js.replace("__DEFS__", json_embed(defs))

out_html = head + js + "</script>\n</body>\n</html>\n"
OUT.write_text(out_html)
print(f"已生成 {OUT}（{len(out_html)} 字节）")

# ---------- 自校验 ----------
import re
chk = OUT.read_text()
assert chk.count("const NODES=") == 1 and chk.count("const EDGES=") == 1
# 内嵌数据能被独立解析回来
m = re.search(r"const NODES=(\[.*?\]);\nconst EDGES=(\[.*?\]);\nconst DEFS=(\{.*?\});\n", chk, re.S)
assert m, "数据块正则回读失败"
nodes2 = json.loads(m.group(1).replace("<\\/", "</"))
edges2 = json.loads(m.group(2).replace("<\\/", "</"))
defs2 = json.loads(m.group(3).replace("<\\/", "</"))
assert len(nodes2) == 197 and len(edges2) == 1562 and len(defs2) == 197
# 边端点全部可解析
ids = {n["card_id"] for n in nodes2}
bad = [e for e in edges2 if e["effective_source"] not in ids or e["effective_target"] not in ids]
assert not bad, f"端点缺失 {len(bad)}"
pre = sum(1 for e in edges2 if e["relation_type"] == "prerequisite")
rel = sum(1 for e in edges2 if e["relation_type"] == "related")
assert (pre, rel) == (78, 1484), (pre, rel)
print("自校验 ✓：197 节点 / 1562 边（先修 78 + 相关 1484）/ 端点全覆盖 / 定义 197 条 / 数据块可回读")
