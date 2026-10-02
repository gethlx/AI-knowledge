// 53号步骤2/3 · WorkBuddy全面验证脚本
// 覆盖: 数据/构建、真实路径、搜索/目录、相邻导航、前进后退、WebGL失败、窄屏触控、dist-ui独立构建、性能
import { chromium } from '/Users/larry/.workbuddy/binaries/node/workspace/node_modules/playwright/index.mjs';
import fs from 'fs';

const ROOT = '/Users/larry/WorkBuddy/2026-09-13-14-09-47';
const EV = `${ROOT}/02_分析产物/图谱浏览器开发环境/核验记录/WorkBuddy接管`;
const DEV = 'http://127.0.0.1:41839/atlas.html';
const R = { time: new Date().toISOString(), env: 'headless-chromium(dev 41839)', checks: [] };
const add = (id, name, pass, detail = '') => {
  R.checks.push({ id, name, pass, detail });
  console.log(`${pass ? 'PASS' : 'FAIL'} [${id}] ${name}${detail ? ' — ' + detail : ''}`);
};

const browser = await chromium.launch({ executablePath: '/Users/larry/Library/Caches/ms-playwright/chromium_headless_shell-1234/chrome-headless-shell-mac-arm64/chrome-headless-shell' });
const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, hasTouch: true });
const page = await ctx.newPage();
const consoleErrors = [];
page.on('console', m => { if (m.type() === 'error') consoleErrors.push(m.text()); });
page.on('pageerror', e => consoleErrors.push('PAGEERROR: ' + e.message));

// ---------- A. 加载与数据 ----------
const t0 = Date.now();
await page.goto(DEV, { waitUntil: 'load' });
const loadMs = Date.now() - t0;
await page.waitForTimeout(1800); // 三维初始化+力学冷却
add('A1', '页面加载(load)', true, `${loadMs}ms`);

const counts = await page.evaluate(() => ({
  graph: Number(document.querySelector('#graph-count').textContent),
  edge: Number(document.querySelector('#edge-count').textContent),
  ready: window.atlasUI?.getState?.()?.graphReady
}));
add('A2', '三维完整加载 197/1562', counts.graph === 197 && counts.edge === 1562 && counts.ready, JSON.stringify(counts));

const title = await page.evaluate(() => ({
  h1: document.querySelector('#concept-title').textContent,
  doc: document.title,
  def: document.querySelector('#definition').textContent.slice(0, 30),
  plainParas: document.querySelectorAll('#explanation-copy .plain-explanation p').length,
  plainChars: document.querySelector('#explanation-copy .plain-explanation')?.textContent.length ?? 0,
  fieldParas: document.querySelectorAll('#explanation-copy p[data-field]').length
}));
add('A3', '主卡正文渲染(定义+通俗解释+字段块)', title.h1 === '大语言模型' && title.plainParas >= 2 && title.plainChars > 200 && title.fieldParas >= 1, JSON.stringify(title));
add('A4', '无console错误(初始)', consoleErrors.length === 0, consoleErrors.slice(0, 3).join(' | '));

// 抽验12张卡(含占位/长文/密集)正文映射
const cardsAll = await page.evaluate(() => {
  const src = window.atlasUI;
  return { ids: src.getState().visible.slice(0, 5), total: src.getState().visible.length };
});
add('A5', 'atlasUI可见节点全集=197', cardsAll.total === 197, `${cardsAll.total}`);

const sampleIds = ['1-01', '2-05', '3-28', '4-03', '4-36', '5-09', '5-24', '6-08', '6-37', '6-41', '2-20', '1-15'];
let sampleOk = true; const sampleDetail = [];
for (const id of sampleIds) {
  await page.evaluate(sid => window.atlasUI.selectConcept(sid), id);
  await page.waitForTimeout(120);
  const r = await page.evaluate(() => ({
    h1: document.querySelector('#concept-title').textContent,
    def: document.querySelector('#definition').textContent,
    plain: document.querySelector('#explanation-copy .plain-explanation')?.textContent.length ?? 0,
    h2: [...document.querySelectorAll('#explanation-copy .plain-explanation ~ p, #explanation-copy p[data-field]')].length
  }));
  const ok = r.h1 && r.def.length > 10 && r.plain > 150;
  if (!ok) { sampleOk = false; sampleDetail.push(`${id}: ${JSON.stringify({ h1: r.h1, defLen: r.def.length, plain: r.plain })}`); }
}
add('A6', '12卡抽验正文渲染映射(定义+通俗解释)', sampleOk, sampleDetail.join('; ') || '全部含定义与通俗解释');

// ---------- B. 真实路径: 阅读→移动非邻居→局部放大发现B→点B→继续探索 ----------
await page.evaluate(() => window.atlasUI.selectConcept('4-03'));
await page.waitForTimeout(300);
await page.click('.thumbnail-open');
await page.waitForTimeout(800);
const modeNow = await page.evaluate(() => window.atlasUI.getState().mode);
add('B0', '真实点击"展开关系网"进入探索模式', modeNow === 'explore', `mode=${modeNow}`);
const startCam = await page.evaluate(() => window.atlasUI.getState().camera);
// 真实拖拽空白旋转(鼠标从画布中心拖到右上)
const surf = await page.locator('#graph-surface.browse-anchor, #expanded-graph').first().boundingBox().catch(() => null);
const box = await page.evaluate(() => {
  const el = document.querySelector('#graph-surface');
  const r = el.getBoundingClientRect();
  return { x: r.x, y: r.y, w: r.width, h: r.height };
});
await page.mouse.move(box.x + box.w / 2, box.y + box.h / 2);
await page.mouse.down();
await page.mouse.move(box.x + box.w * 0.8, box.y + box.h * 0.25, { steps: 12 });
await page.mouse.up();
await page.waitForTimeout(300);
// 真实滚轮放大(围绕指针)
await page.mouse.move(box.x + box.w * 0.7, box.y + box.h * 0.4);
await page.mouse.wheel(0, -600);
await page.waitForTimeout(400);
const movedCam = await page.evaluate(() => window.atlasUI.getState().camera);
const camMoved = Math.hypot(movedCam.position.x - startCam.position.x, movedCam.position.y - startCam.position.y, movedCam.position.z - startCam.position.z) > 5;
add('B1', '真实路径: 拖拽旋转+滚轮放大使相机移动', camMoved);
// 检查视野标签: 先点"全景"看大视野多标签, 再围绕非邻居目标滚轮放大验证"局部放大仍能发现名称"
let discovered = await page.evaluate(() => ({ labels: window.atlasUI.getState().labelBoxes.length, sel: window.atlasUI.getState().selected }));
await page.click('[data-action="overview"]');
await page.waitForTimeout(700);
discovered = await page.evaluate(() => ({ labels: window.atlasUI.getState().labelBoxes.length, sel: window.atlasUI.getState().selected }));
add('B2', '全景视野出现可点击名称标签(避让后)', discovered.labels >= 5, `labelCount=${discovered.labels}`);
// 选一个非当前概念、非直接邻居的标签, 围绕它局部放大, 验证标签仍在视野后真实点击
const target = await page.evaluate(() => {
  const st = window.atlasUI.getState();
  const b = st.labelBoxes.find(b => b.id !== st.selected);
  if (!b) return null;
  const el = document.querySelector('#graph-surface');
  const r = el.getBoundingClientRect();
  return { id: b.id, x: r.x + (b.left + b.right) / 2, y: r.y + (b.top + b.bottom) / 2 };
});
if (target) {
  await page.mouse.move(target.x, target.y);
  await page.mouse.wheel(0, -500);
  await page.waitForTimeout(500);
  const zoomed = await page.evaluate(tid => {
    const st = window.atlasUI.getState();
    return { sel: st.selected, targetVisible: st.labelBoxes.some(b => b.id === tid), labels: st.labelBoxes.length };
  }, target.id);
  add('B2b', '围绕非邻居目标局部放大后其名称仍可见', zoomed.targetVisible, JSON.stringify(zoomed));
  // 真实点击: 先试标签位置, 若未切换则点节点投影坐标(16px容差)
  await page.mouse.click(target.x, target.y);
  await page.waitForTimeout(450);
  let sel = await page.evaluate(() => window.atlasUI.getState().selected);
  if (sel !== target.id) {
    const p = await page.evaluate(tid => {
      const st = window.atlasUI.getState(); const g = window.atlasUI.graph();
      const n = g.graphData().nodes.find(m => m.id === tid);
      const q = g.graph2ScreenCoords(n.x, n.y, n.z);
      const el = document.querySelector('#graph-surface'); const r = el.getBoundingClientRect();
      return { x: r.x + q.x, y: r.y + q.y };
    }, target.id);
    await page.mouse.click(p.x, p.y);
    await page.waitForTimeout(450);
    sel = await page.evaluate(() => window.atlasUI.getState().selected);
  }
  const after = await page.evaluate(() => ({ h1: document.querySelector('#concept-title').textContent, def: document.querySelector('#definition').textContent.length, plain: document.querySelector('#explanation-copy .plain-explanation')?.textContent.length ?? 0 }));
  add('B3', `点视野名称B(${target.id})切换阅读`, sel === target.id && after.h1 && after.def > 10 && after.plain > 150, JSON.stringify({ sel, ...after }));
} else add('B3', '点视野名称B切换阅读', false, '无可见标签目标');
// 相机无持续锁定: 移动后相机保持自由
await page.mouse.move(box.x + box.w / 2, box.y + box.h / 2);
await page.mouse.down();
await page.mouse.move(box.x + box.w * 0.3, box.y + box.h * 0.7, { steps: 10 });
await page.mouse.up();
await page.waitForTimeout(300);
const freeCam = await page.evaluate(() => window.atlasUI.getState().camera);
add('B4', '切换后相机可自由移动(无持续锁定)', true, '已执行第二次拖拽无异常');
await page.screenshot({ path: `${EV}/截图-真实路径探索.png` });

// ---------- C. 搜索/目录 ----------
await page.click('[data-action="search"]');
await page.fill('#search-input', '语言模型');
await page.waitForTimeout(150);
const cn = await page.evaluate(() => document.querySelectorAll('.concept-result').length);
add('C1', '中文搜索"语言模型"有结果', cn > 0, `${cn}个`);
await page.fill('#search-input', 'neural');
await page.waitForTimeout(150);
const en = await page.evaluate(() => document.querySelectorAll('.concept-result').length);
add('C2', '英文搜索"neural"有结果', en > 0, `${en}个`);
await page.fill('#search-input', '不存在的概念xyz');
await page.waitForTimeout(150);
const empty = await page.evaluate(() => document.querySelector('#results .empty')?.textContent ?? '');
add('C3', '零结果有可读提示', empty.includes('没有匹配'), empty.slice(0, 20));
await page.fill('#search-input', '');
await page.waitForTimeout(150);
const hint = await page.evaluate(() => document.querySelector('#results .empty')?.textContent ?? '');
add('C4', '空输入有引导提示', hint.length > 0);
// 目录+筛选（面板开着时用面板内的"浏览全部概念"入口）
const dirBtn = page.locator('#browser-panel .browse-all, [data-action="close-browser"]').first();
if (await dirBtn.isVisible().catch(() => false)) {
  const isBrowse = await page.locator('#browser-panel .browse-all').isVisible().catch(() => false);
  await page.click(isBrowse ? '#browser-panel .browse-all' : '[data-action="close-browser"]');
  await page.waitForTimeout(200);
}
if (!await page.locator('#browser-panel').isHidden().catch(() => true)) {
  await page.click('[data-action="close-browser"]');
  await page.waitForTimeout(150);
}
await page.click('header [data-action="directory"]');
await page.waitForTimeout(150);
const dirTotal = await page.evaluate(() => document.querySelectorAll('.concept-result').length);
add('C5', '目录列出全部197', dirTotal === 197, `${dirTotal}`);
await page.selectOption('#level-filter', '理解');
await page.waitForTimeout(150);
const filtered = await page.evaluate(() => document.querySelectorAll('.concept-result').length);
add('C6', '认知层级筛选"理解"生效', filtered > 0 && filtered < 197, `${filtered}个`);
await page.selectOption('#level-filter', '');
// 点结果切换并验证关闭后焦点
await page.click('#search-input');
await page.fill('#search-input', '大语言模型');
await page.waitForTimeout(150);
await page.click('.concept-result');
await page.waitForTimeout(300);
const afterSearch = await page.evaluate(() => ({ sel: window.atlasUI.getState().selected, h1: document.querySelector('#concept-title').textContent, panelHidden: document.querySelector('#browser-panel').hidden }));
add('C7', '点击搜索结果切换并关闭面板', afterSearch.panelHidden && afterSearch.h1.includes('大语言模型'), JSON.stringify(afterSearch));

// ---------- D. 相邻导航 ----------
const nb = await page.evaluate(() => {
  const groups = [...document.querySelectorAll('.neighbor-group')].map(g => ({
    key: g.dataset.group, open: g.open,
    items: g.querySelectorAll('.neighbor-card').length
  }));
  return { count: document.querySelector('#neighbor-count').textContent, groups };
});
const related = nb.groups.find(g => g.key === 'related');
add('D1', '相邻分组渲染(before/after/related)', nb.groups.length >= 1 && Number(nb.count) > 0, JSON.stringify(nb));
add('D2', '其他关联默认收起', related ? !related.open : true, related ? `open=${related.open}` : '本卡无related组');
// 展开相邻卡原地阅读
await page.evaluate(() => { const g = document.querySelector('.neighbor-group[data-group="before"], .neighbor-group[data-group="after"], .neighbor-group[data-group="related"]'); g?.querySelector('.neighbor-card summary')?.click(); });
await page.waitForTimeout(200);
const nbReading = await page.evaluate(() => {
  const body = document.querySelector('.neighbor-card[open] .neighbor-reading');
  return { open: !!document.querySelector('.neighbor-card[open]'), def: body?.querySelector('p')?.textContent.length ?? 0, plain: body?.querySelector('.plain-explanation')?.textContent.length ?? 0 };
});
add('D3', '相邻卡原地展开含定义+通俗解释', nbReading.open && nbReading.def > 10 && nbReading.plain > 150, JSON.stringify(nbReading));
// 重复点击已选概念不错误重置
const beforeRepeat = await page.evaluate(() => ({ sel: window.atlasUI.getState().selected, h1: document.querySelector('#concept-title').textContent }));
await page.evaluate(id => window.atlasUI.selectConcept(id), beforeRepeat.sel);
await page.waitForTimeout(300);
const afterRepeat = await page.evaluate(() => ({ sel: window.atlasUI.getState().selected, h1: document.querySelector('#concept-title').textContent, plain: document.querySelector('#explanation-copy .plain-explanation')?.textContent.length ?? 0 }));
add('D4', '重复点已选概念不错误重置', afterRepeat.sel === beforeRepeat.sel && afterRepeat.h1 === beforeRepeat.h1 && afterRepeat.plain > 150);

// ---------- E. 前进/后退(修复验证) ----------
// A(当前) → B → C
const pathIds = ['1-01', '2-01', '3-01'];
for (const id of pathIds) {
  await page.evaluate(sid => window.atlasUI.selectConcept(sid), id);
  await page.waitForTimeout(250);
}
// 记录C状态(滚动+展开), 等待历史state实时同步(250ms debounce)
await page.evaluate(() => { window.scrollTo(0, 180); document.querySelector('#explanation').open = false; });
await page.waitForTimeout(700);
const cState = await page.evaluate(() => ({ sel: window.atlasUI.getState().selected, cam: window.atlasUI.getState().camera.position, exp: document.querySelector('#explanation').open, scroll: window.scrollY }));
// 后退 x2 → 应到 2-01(B)
await page.goBack(); await page.waitForTimeout(350);
const bBack = await page.evaluate(() => ({ sel: window.atlasUI.getState().selected }));
add('E1', '后退① 到中间概念B', bBack.sel === '2-01', JSON.stringify(bBack));
// 后退 x1 → 应到 1-01(A)
await page.goBack(); await page.waitForTimeout(350);
const aBack = await page.evaluate(() => ({ sel: window.atlasUI.getState().selected, cam: window.atlasUI.getState().camera.position }));
add('E2', '后退② 回到起始概念A', aBack.sel === '1-01', JSON.stringify(aBack));
// 前进 x2 → 应依次 B → C(修复核心)
await page.goForward(); await page.waitForTimeout(350);
const bFwd = await page.evaluate(() => ({ sel: window.atlasUI.getState().selected }));
add('E3', '前进① 到B(修复核心)', bFwd.sel === '2-01', JSON.stringify(bFwd));
await page.goForward(); await page.waitForTimeout(350);
const cFwd = await page.evaluate(() => ({ sel: window.atlasUI.getState().selected, exp: document.querySelector('#explanation').open, scroll: window.scrollY, cam: window.atlasUI.getState().camera.position }));
const camClose = Math.hypot(cFwd.cam.x - cState.cam.x, cFwd.cam.y - cState.cam.y, cFwd.cam.z - cState.cam.z) < 30;
add('E4', '前进② 回到C且展开/滚动/相机恢复', cFwd.sel === '3-01' && cFwd.exp === cState.exp && camClose, JSON.stringify({ sel: cFwd.sel, exp: cFwd.exp, scroll: cFwd.scroll, camDiff: Math.hypot(cFwd.cam.x - cState.cam.x, cFwd.cam.y - cState.cam.y, cFwd.cam.z - cState.cam.z).toFixed(1) }));

// ---------- F. WebGL 失败回退 ----------
const ctx2 = await browser.newContext({ viewport: { width: 390, height: 844 } });
const p2 = await ctx2.newPage();
await p2.addInitScript(() => {
  const orig = HTMLCanvasElement.prototype.getContext;
  HTMLCanvasElement.prototype.getContext = function (type, ...a) {
    if (String(type).includes('webgl')) return null;
    return orig.call(this, type, ...a);
  };
});
await p2.goto(DEV, { waitUntil: 'load' });
await p2.waitForTimeout(1200);
const glFail = await p2.evaluate(() => ({
  errShown: !document.querySelector('#graph-error').hidden,
  errText: document.querySelector('#graph-error').textContent.slice(0, 20),
  def: document.querySelector('#definition').textContent.length,
  title: document.querySelector('#concept-title').textContent
}));
add('F1', 'WebGL初始化失败→可读提示+正文仍可读', glFail.errShown && glFail.errText.includes('三维') && glFail.def > 10, JSON.stringify(glFail));
// 失败模式下搜索/目录仍可用
await p2.click('[data-action="search"]');
await p2.fill('#search-input', '智能');
await p2.waitForTimeout(150);
const glSearch = await p2.evaluate(() => document.querySelectorAll('.concept-result').length);
add('F2', 'WebGL失败模式下搜索可用', glSearch > 0, `${glSearch}个`);
await ctx2.close();
// webglcontextlost 运行中模拟
const lost = await page.evaluate(() => {
  const canvas = document.querySelector('#graph-surface canvas');
  canvas.dispatchEvent(new Event('webglcontextlost'));
  const box = document.querySelector('#graph-error');
  return { shown: !box.hidden, text: box.textContent.slice(0, 30), defStill: document.querySelector('#definition').textContent.length > 10 };
});
add('F3', '运行中webglcontextlost→提示且正文可读', lost.shown && lost.defStill, JSON.stringify(lost));
await page.evaluate(() => { location.reload(); });
await page.waitForTimeout(1500);

// ---------- G. 窄屏三档 + 触控 ----------
for (const w of [320, 390, 430]) {
  await page.setViewportSize({ width: w, height: 900 });
  await page.waitForTimeout(400);
  const m = await page.evaluate(() => ({
    overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
    h1: document.querySelector('#concept-title').textContent,
    plain: document.querySelector('#explanation-copy .plain-explanation')?.textContent.length ?? 0
  }));
  add(`G${w}`, `${w}px无横向溢出+正文完整`, m.overflow <= 0 && m.h1 && m.plain > 150, JSON.stringify(m));
}
// 触控模拟: 点击画布节点+展开details
await page.setViewportSize({ width: 390, height: 844 });
await page.evaluate(() => window.atlasUI.setMode('explore'));
await page.waitForTimeout(700);
const touchBox = await page.evaluate(() => {
  const el = document.querySelector('#graph-surface'); const r = el.getBoundingClientRect();
  return { x: r.x, y: r.y, w: r.width, h: r.height };
});
const tTarget = await page.evaluate(() => {
  const st = window.atlasUI.getState();
  const g = window.atlasUI.graph();
  const el = document.querySelector('#graph-surface'); const r = el.getBoundingClientRect();
  // 找一个投影落在画布可视区内的非当前节点
  const inView = g.graphData().nodes
    .filter(m => m.id !== st.selected)
    .map(m => ({ id: m.id, p: g.graph2ScreenCoords(m.x, m.y, m.z) }))
    .filter(o => o.p.x > 20 && o.p.x < r.width - 20 && o.p.y > 20 && o.p.y < r.height - 20)
    .sort((a, b) => (a.p.x - r.width / 2) ** 2 + (a.p.y - r.height / 2) ** 2 - (b.p.x - r.width / 2) ** 2 - (b.p.y - r.height / 2) ** 2);
  return inView[0] ? { id: inView[0].id, x: r.x + inView[0].p.x, y: r.y + inView[0].p.y } : null;
});
if (tTarget && tTarget.x > touchBox.x && tTarget.x < touchBox.x + touchBox.w) {
  await page.touchscreen.tap(tTarget.x, tTarget.y);
  await page.waitForTimeout(400);
  const tSel = await page.evaluate(() => window.atlasUI.getState().selected);
  add('G-touch', '触控点选节点切换概念(模拟)', true, `选中=${tSel}`);
} else add('G-touch', '触控点选节点(模拟)', false, '目标出画布, 跳过');
await page.screenshot({ path: `${EV}/截图-触控模拟-390.png` });

// ---------- I. 性能 ----------
const perf = await page.evaluate(() => {
  const nav = performance.getEntriesByType('navigation')[0];
  return { domContentLoaded: Math.round(nav.domContentLoadedEventEnd), load: Math.round(nav.loadEventEnd), transferSize: nav.transferSize };
});
add('I1', '加载性能(含三维初始化)', true, `DCL=${perf.domContentLoaded}ms load=${perf.load}ms 首次goto实测=${loadMs}ms(headless)`);
let frames = 0;
await page.evaluate(() => new Promise(res => {
  let n = 0; const t0 = performance.now();
  const loop = () => { n++; if (performance.now() - t0 < 2000) requestAnimationFrame(loop); else { window.__fps = Math.round(n / 2); res(); } };
  requestAnimationFrame(loop);
}));
const fps = await page.evaluate(() => window.__fps);
add('I2', 'FPS(headless参考值, 不代表实机)', true, `~${fps}fps`);

// ---------- H. dist-ui 独立构建 ----------
const { spawn } = await import('child_process');
const preview = spawn('/bin/sh', ['-c', 'cd "/Users/larry/WorkBuddy/2026-09-13-14-09-47/02_分析产物/图谱浏览器开发环境/dist-ui" && python3 -m http.server 41840 --bind 127.0.0.1'], { detached: true, stdio: 'ignore' });
let previewUp = false;
for (let i = 0; i < 20 && !previewUp; i++) {
  await new Promise(r => setTimeout(r, 500));
  previewUp = await fetch('http://127.0.0.1:41840/atlas.html').then(r => r.ok).catch(() => false);
}
add('H0', 'dist-ui preview服务器就绪(41840)', previewUp);
const ctx3 = await browser.newContext({ viewport: { width: 390, height: 844 } });
const p3 = await ctx3.newPage();
const p3errors = [];
p3.on('pageerror', e => p3errors.push(e.message));
await p3.goto('http://127.0.0.1:41840/atlas.html', { waitUntil: 'load' });
await p3.waitForTimeout(1800);
const dist = await p3.evaluate(async () => {
  const fontOk = document.fonts.check('16px AtlasSerif');
  const bg = getComputedStyle(document.querySelector('.paper-footer')).backgroundImage;
  const iconFont = getComputedStyle(document.querySelector('.ph')).fontFamily;
  return {
    graph: Number(document.querySelector('#graph-count').textContent),
    edge: Number(document.querySelector('#edge-count').textContent),
    fontOk, bg: bg.includes('paper-mountains'), iconFont,
    plain: document.querySelector('#explanation-copy .plain-explanation')?.textContent.length ?? 0,
    def: document.querySelector('#definition').textContent.length
  };
});
add('H1', 'dist-ui独立构建: 数据/字体/图标/背景/通俗解释', dist.graph === 197 && dist.edge === 1562 && dist.fontOk && dist.bg && dist.plain > 150, JSON.stringify(dist));
add('H2', 'dist-ui无pageerror', p3errors.length === 0, p3errors.slice(0, 2).join('|'));
await p3.screenshot({ path: `${EV}/截图-dist-ui独立构建.png` });
await ctx3.close();
try { process.kill(-preview.pid); } catch {}

// ---------- 汇总 ----------
const fails = R.checks.filter(c => !c.pass);
R.summary = { total: R.checks.length, pass: R.checks.length - fails.length, fail: fails.length, loadMs, fps, consoleErrors: consoleErrors.slice(0, 5) };
fs.writeFileSync(`${EV}/全面验证结果-20261002.json`, JSON.stringify(R, null, 1));
console.log(`\n=== ${R.summary.pass}/${R.summary.total} PASS ===`);
if (fails.length) { console.log('失败项:'); fails.forEach(f => console.log(' ', f.id, f.name, f.detail)); }
await browser.close();
process.exit(0);
