# -*- coding: utf-8 -*-
"""「知识地图总目录表 v3.9」交互版生成器。

结构约定：
  - 每个知识轴一张 <table>；表体为自适应网格（一行 3–10 条）
  - 每条知识卡 = 一条 card 行（只显示中文名 + 英文名）
  - 每条卡自带一条 detail-row（简介），默认 display:none
  - 展开时不改动本行：把 detail-row 用 grid order 摆到「该卡所在视觉行的正下方」，
    物理 DOM 顺序始终是「card → 自己的 detail」，因此打印/导出 PDF 顺序天然正确
数据内容零改动，仅改版式与交互。
"""
import re
import io

SRC = "/Users/larry/WorkBuddy/2026-09-13-11-54-50/.bak/银河AI通识课程-知识地图-总目录表-v3.9.原版.html"
OUT = "/Users/larry/WorkBuddy/2026-09-13-11-54-50/银河AI通识课程-知识地图-总目录表-v3.9.html"


def md_fix(text):
    """正文里残留的 markdown **加粗** 渲染为 <strong>，逐行处理，不跨行配对。"""
    return "\n".join(re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", ln) for ln in text.split("\n"))


src = io.open(SRC, encoding="utf-8").read()

eyebrow = re.search(r'<div class="eyebrow">(.*?)</div>', src, re.S).group(1).strip()
h1 = re.search(r"<h1>(.*?)</h1>", src, re.S).group(1).strip()
title = re.search(r"<title>(.*?)</title>", src, re.S).group(1).strip()

sections = []
for m in re.finditer(r"<section>(.*?)</section>", src, re.S):
    body = m.group(1)
    h2 = re.search(r"<h2>(.*?)</h2>", body, re.S).group(1).strip()
    scope = re.search(r'<div class="scope">(.*?)</div>', body, re.S).group(1).strip()
    cards = []
    for r in re.finditer(
        r'<tr><td class="name">(.*?)</td><td class="def">(.*?)</td></tr>', body, re.S
    ):
        name_html, def_html = r.group(1), r.group(2)
        cid = re.search(r'<span class="id">(.*?)</span>', name_html, re.S).group(1).strip()
        cn = re.search(r'<span class="cn">(.*?)</span>', name_html, re.S).group(1).strip()
        en = re.search(r'<span class="en">(.*?)</span>', name_html, re.S).group(1).strip()
        cards.append((cid, cn, en, md_fix(def_html.strip())))
    sections.append((h2, scope, cards))

tot = sum(len(c) for _, _, c in sections)
assert tot == 197, tot


def split_h2(h2):
    no = re.search(r'<span class="axno">(.*?)</span>', h2, re.S).group(1).strip()
    en = re.search(r'<span class="axen">(.*?)</span>', h2, re.S).group(1).strip()
    cnt = re.search(r'<span class="axcnt">(.*?)</span>', h2, re.S).group(1).strip()
    zh = re.sub(r'<span class="axno">.*?</span>', "", h2, flags=re.S)
    zh = re.sub(r'<span class="axen">.*?</span>', "", zh, flags=re.S)
    zh = re.sub(r'<span class="axcnt">.*?</span>', "", zh, flags=re.S)
    return no, zh.strip(), en, cnt


CSS = """
:root{
  --bg:#f7f8fb; --card:#ffffff; --line:#e6eaf3; --line2:#cfd7e6;
  --tx:#1c2438; --tx2:#5a6780; --tx3:#8a94ab;
  --ax:#3b5bdb; --ax2:#2f49b3; --soft:#eef2fb; --hl:#f4f7fe; --panel:#f6f8fe;
}
*{box-sizing:border-box}
html,body{margin:0;padding:0}
body{background:var(--bg);color:var(--tx);line-height:1.7;
  font-family:-apple-system,BlinkMacSystemFont,"PingFang SC","Hiragino Sans GB","Microsoft YaHei",system-ui,sans-serif;
  font-size:14.5px;-webkit-font-smoothing:antialiased;scroll-behavior:smooth}
.wrap{max-width:1600px;margin:0 auto;padding:38px 28px 90px}
header{border-bottom:2px solid var(--tx);padding-bottom:20px;margin-bottom:18px}
.eyebrow{font-size:12px;letter-spacing:.22em;color:var(--ax);font-weight:700;text-transform:uppercase}
h1{font-size:27px;margin:8px 0 8px;letter-spacing:-.3px}
.sub{color:#4a5468;font-size:14px;max-width:900px}
.sub b{color:var(--ax)}
.meta{display:flex;flex-wrap:wrap;gap:8px;margin-top:14px}
.chip{background:var(--soft);border:1px solid var(--line);border-radius:999px;padding:4px 12px;font-size:12.5px;color:#4a5468}
.chip b{color:var(--tx)}

/* ── 吸顶控制条 ───────────────────────────── */
.bar{position:sticky;top:0;z-index:30;display:flex;align-items:center;gap:10px;flex-wrap:wrap;
  margin:0 -28px 24px;padding:10px 28px;background:rgba(247,248,251,.9);
  -webkit-backdrop-filter:saturate(180%) blur(10px);backdrop-filter:saturate(180%) blur(10px);
  border-bottom:1px solid var(--line2)}
.bar .lab{font-size:12.5px;color:var(--tx3);white-space:nowrap}
.bar .lab b{color:var(--tx)}
.jump{display:flex;gap:6px;flex-wrap:wrap;margin-left:auto}
.jump a{font-size:12.5px;text-decoration:none;color:#4a5468;background:#fff;border:1px solid var(--line2);
  border-radius:8px;padding:3px 9px;transition:.15s}
.jump a:hover{background:var(--ax);border-color:var(--ax);color:#fff}
.btn{font-size:12.5px;padding:4px 12px;border-radius:8px;border:1px solid var(--line2);background:#fff;
  color:#3b4661;cursor:pointer;transition:.15s;white-space:nowrap;font-family:inherit}
.btn:hover{border-color:var(--ax);color:var(--ax);background:#fff}
.btn.primary{background:var(--ax);border-color:var(--ax);color:#fff}
.btn.primary:hover{background:var(--ax2);border-color:var(--ax2);color:#fff}

/* ── 每个知识轴一张表格 ────────────────────── */
section{margin-bottom:34px;scroll-margin-top:74px}
h2{font-size:19px;margin:0 0 4px;display:flex;align-items:baseline;gap:10px;flex-wrap:wrap}
.axno{background:var(--ax);color:#fff;border-radius:8px;padding:2px 10px;font-size:13px;font-weight:800}
.axen{color:var(--tx3);font-size:12.5px;font-weight:500}
.axcnt{margin-left:auto;color:var(--ax);font-size:12.5px;font-weight:700}
.ax-tg{font:inherit;font-size:12px;color:#3b4661;background:#fff;border:1px solid var(--line2);
  border-radius:7px;padding:2px 9px;cursor:pointer;transition:.15s;white-space:nowrap}
.ax-tg:hover{border-color:var(--ax);color:var(--ax)}
.scope{color:var(--tx3);font-size:12.5px;margin:0 0 10px;max-width:920px}

table{display:block;width:100%;background:var(--card);border:1px solid var(--line2);
  border-radius:12px;overflow:hidden;font-size:13.8px}
thead{display:block;background:var(--soft);border-bottom:1px solid var(--line2)}
thead th{display:block;text-align:left;padding:9px 16px;font-size:12.5px;color:#4a5468;font-weight:600}
.thwrap{display:flex;align-items:center;justify-content:space-between;gap:12px}
.thhint{font-weight:400;color:var(--tx3);font-size:12px}

tbody{display:grid;grid-template-columns:repeat(auto-fill,minmax(184px,1fr));align-items:stretch}
tr.card{display:contents}
td.cell{min-width:0;padding:0;background:var(--card);
  border-right:1px solid var(--line);border-bottom:1px solid var(--line)}

/* ── 卡片（默认收起：只显示中英文名） ──────── */
.row-tg{position:relative;display:block;width:100%;height:100%;padding:10px 12px 11px 26px;
  border:0;background:none;font:inherit;color:inherit;text-align:left;cursor:pointer;transition:background .15s}
.row-tg:hover{background:var(--hl)}
.row-tg:focus-visible{outline:2px solid var(--ax);outline-offset:-2px}
.chev{position:absolute;left:11px;top:16px;width:0;height:0;
  border-left:5px solid var(--tx3);border-top:4.5px solid transparent;border-bottom:4.5px solid transparent;
  transform-origin:25% 50%;transition:transform .22s ease}
.row-tg:hover .chev{border-left-color:var(--ax)}
tr.open .chev{transform:rotate(90deg);border-left-color:var(--ax)}
tr.open>.cell{background:var(--soft)}
.cn{font-weight:700}
.en{display:block;color:var(--tx3);font-size:12.3px;margin-top:1px}

/* ── 简介行：由 JS 用 order 摆到「本行正下方」，本行高度与布局不变 ── */
tr.detail-row{display:none}
tr.detail-row.is-open{display:contents}
td.detail-cell{grid-column:1/-1;min-width:0;padding:0;background:var(--panel)}
.dwrap{display:grid;grid-template-rows:0fr;transition:grid-template-rows .26s ease}
tr.detail-row.expanded .dwrap{grid-template-rows:1fr}
.dinner{overflow:hidden}
.dbox{padding:11px 20px 15px;background:var(--panel);
  border-top:1px solid #dbe2f2;border-bottom:1px solid #dbe2f2}
.dhead{font-size:11.5px;color:var(--tx3);margin-bottom:5px}
.dhead b{color:var(--tx);font-size:12.5px;font-weight:700}
.dhead .en{display:inline;font-size:11.5px;margin:0 0 0 7px;color:var(--tx3)}
.def{white-space:pre-wrap;color:#39425a;font-size:13.4px;line-height:1.85;
  padding-left:14px;border-left:2px solid #dde3f2}
.def strong{color:#161d2e;font-weight:800}

footer{border-top:1px solid var(--line2);margin-top:40px;padding-top:18px;color:var(--tx3);font-size:12.5px}

@media (max-width:900px){
  tbody{grid-template-columns:repeat(auto-fill,minmax(168px,1fr))}
}
@media (max-width:620px){
  .wrap{padding:24px 14px 60px}
  .bar{margin:0 -14px 20px;padding:9px 14px}
  .jump{display:none}
  .thhint{display:none}
  tbody{grid-template-columns:repeat(auto-fill,minmax(150px,1fr))}
  .dbox{padding:10px 14px 14px}
}
@media print{
  body{background:#fff;font-size:11.6px}
  .wrap{max-width:none;padding:10mm 8mm}
  .bar{display:none}
  .ax-tg{display:none}
  section{break-inside:auto;margin-bottom:20px}
  table{border-radius:0}
  /* 打印回到「一卡一行、全部展开」；grid order 在块级布局中自动失效，
     打印顺序 = DOM 原始顺序（每条简介紧跟自己的卡片），无需重排 */
  tbody{display:block}
  tr.card{display:block}
  td.cell{display:block;border-right:none}
  tr.detail-row{display:block !important}
  td.detail-cell{display:block}
  .dwrap{grid-template-rows:1fr !important}
  .chev{display:none}
  .row-tg{padding-left:16px;background:none !important}
  .dhead{display:none}
  .def,.dbox{break-inside:avoid}
}
"""

JS = """
<script>
(function(){
  var cards = Array.prototype.slice.call(document.querySelectorAll('tr.card'));
  var lab   = document.querySelector('.bar .lab b.state');
  var map   = {};
  Array.prototype.forEach.call(document.querySelectorAll('tr.detail-row'), function(d){
    map[d.getAttribute('data-for')] = d;
  });

  function detailOf(card){
    var b = card.querySelector('.row-tg');
    return b ? map[b.getAttribute('data-id')] : null;
  }
  function setRow(card, open){
    card.classList.toggle('open', open);
    var b = card.querySelector('.row-tg');
    if(b) b.setAttribute('aria-expanded', open ? 'true' : 'false');
  }

  /* 按视觉行分组：同一行（顶部坐标相同）算一组。组内卡片依次编号，该组已展开的
     简介行排在组内全部卡片之后 —— 于是简介行正好落在「本行正下方」，本行卡片的
     高度、列数、位置都不受影响。

     关键：测量前先把所有简介行临时隐藏。否则会踩两个坑：
       ① 若先清空 order 再量，量到的是被打乱后的布局；
       ② 窗口变窄导致列数变化时，用「旧 order + 新宽度」的中间态去量，分组会算错。
     隐藏简介行后量到的就是纯净的卡片网格，分组永远正确。order 以 10 为步长避免并列。 */
  function place(){
    var tbs = Array.prototype.slice.call(document.querySelectorAll('tbody'));
    var hidden = [];
    Array.prototype.forEach.call(document.querySelectorAll('tr.detail-row.is-open'), function(d){
      d.style.display = 'none';
      hidden.push(d);
    });

    var plans = tbs.map(function(tb){
      var rows = Array.prototype.slice.call(tb.querySelectorAll('tr.card'));
      var groups = [], g = null;
      rows.forEach(function(r){
        var top = Math.round(r.firstElementChild.getBoundingClientRect().top);
        if(g && Math.abs(g.top - top) <= 2){ g.rows.push(r); }
        else { g = {top:top, rows:[r]}; groups.push(g); }
      });
      return {tb:tb, groups:groups};
    });

    plans.forEach(function(p){
      Array.prototype.forEach.call(p.tb.querySelectorAll('td'), function(td){
        td.style.order = '';
      });
      var n = 0;
      p.groups.forEach(function(grp){
        grp.rows.forEach(function(r){ r.firstElementChild.style.order = (n++) * 10; });
        grp.rows.forEach(function(r){
          if(!r.classList.contains('open')) return;
          var d = detailOf(r);
          if(d) d.firstElementChild.style.order = (n++) * 10;
        });
      });
    });

    hidden.forEach(function(d){ d.style.display = ''; });
  }

  function expand(d){
    if(!d) return;
    d.classList.add('is-open');
    requestAnimationFrame(function(){
      requestAnimationFrame(function(){ d.classList.add('expanded'); });
    });
  }
  function collapse(d){
    if(!d) return;
    d.classList.remove('expanded');
    setTimeout(function(){
      if(!d.classList.contains('expanded')) d.classList.remove('is-open');
    }, 300);
  }

  function refresh(){
    var n = document.querySelectorAll('tr.card.open').length;
    if(lab) lab.textContent = n;
    Array.prototype.forEach.call(document.querySelectorAll('section'), function(sec){
      var all = sec.querySelectorAll('tr.card'), on = sec.querySelectorAll('tr.card.open');
      var btn = sec.querySelector('.ax-tg');
      if(!btn) return;
      var full = all.length > 0 && on.length === all.length;
      btn.textContent = full ? '收起本轴' : '展开本轴';
      btn.setAttribute('aria-pressed', full ? 'true' : 'false');
    });
  }

  cards.forEach(function(card){
    var b = card.querySelector('.row-tg');
    if(!b) return;
    b.addEventListener('click', function(){
      var open = !card.classList.contains('open');
      var d = detailOf(card);
      setRow(card, open);
      if(open){ place(); expand(d); }
      else { collapse(d); setTimeout(place, 310); }
      refresh();
    });
  });

  Array.prototype.forEach.call(document.querySelectorAll('[data-all]'), function(btn){
    btn.addEventListener('click', function(){
      var open = btn.getAttribute('data-all') === 'open';
      var list = [];
      cards.forEach(function(card){
        setRow(card, open);
        var d = detailOf(card);
        if(!d) return;
        if(open){ d.classList.add('is-open'); list.push(d); }
        else { d.classList.remove('expanded'); }
      });
      place();
      if(open){
        requestAnimationFrame(function(){ requestAnimationFrame(function(){
          list.forEach(function(d){ d.classList.add('expanded'); });
        }); });
      } else {
        setTimeout(function(){
          list.forEach(function(d){ if(!d.classList.contains('expanded')) d.classList.remove('is-open'); });
        }, 300);
      }
      refresh();
    });
  });

  Array.prototype.forEach.call(document.querySelectorAll('.ax-tg'), function(btn){
    btn.addEventListener('click', function(){
      var sec = btn.closest('section');
      var list = sec.querySelectorAll('tr.card');
      var open = sec.querySelectorAll('tr.card.open').length !== list.length;
      var dets = [];
      Array.prototype.forEach.call(list, function(card){
        setRow(card, open);
        var d = detailOf(card);
        if(!d) return;
        if(open){ d.classList.add('is-open'); dets.push(d); }
        else { d.classList.remove('expanded'); }
      });
      place();
      if(open){
        requestAnimationFrame(function(){ requestAnimationFrame(function(){
          dets.forEach(function(d){ d.classList.add('expanded'); });
        }); });
      } else {
        setTimeout(function(){
          dets.forEach(function(d){ if(!d.classList.contains('expanded')) d.classList.remove('is-open'); });
        }, 300);
      }
      refresh();
    });
  });

  /* 窗口宽度变化 → 每行列数变化 → 重新计算各简介行该落在哪一行之下 */
  var timer;
  window.addEventListener('resize', function(){
    clearTimeout(timer);
    timer = setTimeout(place, 150);
  });

  refresh();
  place();
})();
</script>
"""

parts = []
parts.append('<!DOCTYPE html>\n<html lang="zh-CN">\n<head>\n<meta charset="utf-8">\n')
parts.append('<meta name="viewport" content="width=device-width,initial-scale=1">\n')
parts.append("<title>%s</title>\n" % title)
parts.append("<style>%s</style>\n</head>\n<body>\n<div class=\"wrap\">\n" % CSS)

parts.append('<header>\n  <div class="eyebrow">%s</div>\n' % eyebrow)
parts.append("  <h1>%s</h1>\n" % h1)
parts.append(
    "  <div class=\"sub\">全部 <b>%d</b> 条知识卡按六条知识主轴分类平铺，<b>每个知识轴一张表格</b>："
    "卡片按宽度自适应分列排布（一行 3–10 条），默认只显示中英文名称、简介收起；"
    "点击任意卡片，简介在该卡<b>所在行的正下方</b>整行展开，本行高度与左右卡片位置均不受影响，"
    "也可整轴或全部展开。数据与《知识地图总纲 v3.9》同源生成，文字未作改动。</div>\n" % tot
)
meta = re.search(r'<div class="meta">(.*?)</div>', src, re.S).group(1).strip()
meta += '<span class="chip">交互 <b>默认收起 · 点击展开</b></span>'
parts.append('  <div class="meta">%s</div>\n</header>\n' % meta)

parts.append('<div class="bar">\n')
parts.append('  <span class="lab">共 <b>%d</b> 条 · 已展开 <b class="state">0</b> 条</span>\n' % tot)
parts.append('  <button class="btn primary" type="button" data-all="open">全部展开</button>\n')
parts.append('  <button class="btn" type="button" data-all="close">全部收起</button>\n')
parts.append('  <nav class="jump">\n')
for i in range(1, len(sections) + 1):
    parts.append('    <a href="#ax%d">轴%d</a>\n' % (i, i))
parts.append('  </nav>\n</div>\n')

for idx, (h2, scope, cards) in enumerate(sections, start=1):
    no, zh, en, cnt = split_h2(h2)
    parts.append('<section id="ax%d">\n' % idx)
    parts.append(
        '  <h2><span class="axno">%s</span>%s<span class="axen">%s</span>'
        '<span class="axcnt">%s</span>'
        '<button class="ax-tg" type="button" aria-pressed="false">展开本轴</button></h2>\n'
        % (no, zh, en, cnt)
    )
    parts.append('  <div class="scope">%s</div>\n' % scope)
    parts.append("  <table>\n")
    parts.append(
        '    <thead><tr><th><div class="thwrap"><span>知识卡（中英文）· 一行自适应 3–10 条</span>'
        '<span class="thhint">默认收起 · 点击卡片在该行正下方展开简介</span></div></th></tr></thead>\n'
    )
    parts.append("    <tbody>\n")
    for cid, cn, en_t, d in cards:
        parts.append(
            '      <tr class="card">\n        <td class="cell">\n'
            '          <button class="row-tg" type="button" data-id="%s" aria-expanded="false">'
            '<span class="chev" aria-hidden="true"></span>'
            '<span class="cn">%s</span><span class="en">%s</span></button>\n'
            "        </td>\n      </tr>\n" % (cid, cn, en_t)
        )
        parts.append(
            '      <tr class="detail-row" data-for="%s">\n        <td class="detail-cell">\n'
            '          <div class="dwrap"><div class="dinner"><div class="dbox">\n'
            '            <div class="dhead">简介 · <b>%s</b><span class="en">%s</span></div>\n'
            '            <div class="def">%s</div>\n'
            "          </div></div></div>\n"
            "        </td>\n      </tr>\n" % (cid, cn, en_t, d)
        )
    parts.append("    </tbody>\n  </table>\n</section>\n")

parts.append(
    '<footer>共 %d 条知识卡 · 6 条知识主轴 · 数据基线 v3.9 · 交互版'
    "（默认收起，点击卡片在所在行正下方展开简介）<br>"
    "编号与文字内容与《银河AI通识课程·知识地图总纲 v3.9》一致，本页仅调整展示与交互方式。</footer>\n" % tot
)
parts.append("</div>\n" + JS + "</body>\n</html>\n")

out = "".join(parts)
io.open(OUT, "w", encoding="utf-8").write(out)
print("written", OUT, len(out), "chars")
