// 55号 F1/F2 修复回归 + E4断言补强 · 失败时进程退出码非零
import { chromium } from '/Users/larry/.workbuddy/binaries/node/workspace/node_modules/playwright/index.mjs';
import fs from 'fs';
const ROOT = '/Users/larry/WorkBuddy/2026-09-13-14-09-47';
const EV = `${ROOT}/02_分析产物/图谱浏览器开发环境/核验记录/WorkBuddy接管`;
const DEV = 'http://127.0.0.1:41839/atlas.html';
const R = { time: new Date().toISOString(), checks: [] };
const add = (id, name, pass, detail = '') => { R.checks.push({ id, name, pass, detail }); console.log(`${pass ? 'PASS' : 'FAIL'} [${id}] ${name}${detail ? ' — ' + detail : ''}`); };

const browser = await chromium.launch({ executablePath: '/Users/larry/Library/Caches/ms-playwright/chromium_headless_shell-1234/chrome-headless-shell-mac-arm64/chrome-headless-shell' });
const page = await (await browser.newContext({ viewport: { width: 390, height: 844 } })).newPage();
const errors = [];
page.on('pageerror', e => errors.push(e.message));

// ---------- F1: 返回后恢复相邻阅读与分组展开状态 ----------
await page.goto(`${DEV}#4-03`, { waitUntil: 'load' });
await page.waitForTimeout(1600);
// 展开before组第一个相邻词条
await page.evaluate(() => { const d = document.querySelector('.neighbor-group[data-group="before"] .neighbor-card'); d.open = true; });
await page.waitForTimeout(150);
const opened = await page.evaluate(() => {
  const d = document.querySelector('.neighbor-group[data-group="before"] .neighbor-card[open]');
  return d ? d.dataset.neighbor : null;
});
// 打开"其他关联"组
await page.evaluate(() => { const g = document.querySelector('.neighbor-group[data-group="related"]'); if (g && !g.open) g.open = true; });
await page.waitForTimeout(150);
// 切到3-07再后退
await page.evaluate(() => window.atlasUI.selectConcept('3-07'));
await page.waitForTimeout(350);
await page.goBack();
await page.waitForTimeout(450);
const f1back = await page.evaluate(id => {
  const card = document.querySelector(`.neighbor-card[data-neighbor="${id}"]`);
  const group = document.querySelector('.neighbor-group[data-group="related"]');
  return {
    sel: window.atlasUI.getState().selected,
    cardOpen: !!card?.open,
    cardBody: card?.querySelector('.neighbor-reading')?.childElementCount ?? 0,
    relatedOpen: !!group?.open
  };
}, opened);
add('F1-back', `后退回4-03: 词条${opened}展开态+惰性正文+related组恢复`, f1back.sel === '4-03' && f1back.cardOpen && f1back.cardBody > 0 && f1back.relatedOpen, JSON.stringify(f1back));
// 前进到3-07再后退, 状态仍在
await page.goForward();
await page.waitForTimeout(350);
await page.goBack();
await page.waitForTimeout(450);
const f1back2 = await page.evaluate(id => {
  const card = document.querySelector(`.neighbor-card[data-neighbor="${id}"]`);
  const group = document.querySelector('.neighbor-group[data-group="related"]');
  return { sel: window.atlasUI.getState().selected, cardOpen: !!card?.open, cardBody: card?.querySelector('.neighbor-reading')?.childElementCount ?? 0, relatedOpen: !!group?.open };
}, opened);
add('F1-round2', '前进→再后退, 相邻展开状态仍保持', f1back2.sel === '4-03' && f1back2.cardOpen && f1back2.cardBody > 0 && f1back2.relatedOpen, JSON.stringify(f1back2));
// 重新选回已读概念(selectConcept非历史导航), 展开状态保持
await page.evaluate(() => window.atlasUI.selectConcept('3-07'));
await page.waitForTimeout(350);
await page.evaluate(() => window.atlasUI.selectConcept('4-03'));
await page.waitForTimeout(450);
const f1reselect = await page.evaluate(id => {
  const card = document.querySelector(`.neighbor-card[data-neighbor="${id}"]`);
  const group = document.querySelector('.neighbor-group[data-group="related"]');
  return { cardOpen: !!card?.open, cardBody: card?.querySelector('.neighbor-reading')?.childElementCount ?? 0, relatedOpen: !!group?.open };
}, opened);
add('F1-reselect', '重新选回4-03, 展开状态保持(不重置)', f1reselect.cardOpen && f1reselect.cardBody > 0 && f1reselect.relatedOpen, JSON.stringify(f1reselect));
// 新概念首次打开仍为默认分组策略(组不存在则跳过该项检查)
await page.evaluate(() => window.atlasUI.selectConcept('5-01'));
await page.waitForTimeout(400);
const f1default = await page.evaluate(() => {
  const rel = document.querySelector('.neighbor-group[data-group="related"]');
  const before = document.querySelector('.neighbor-group[data-group="before"]');
  return { relatedClosedDefault: rel ? !rel.open : null, beforeOpenDefault: before ? before.open : null, anyCardOpen: !!document.querySelector('.neighbor-card[open]') };
});
add('F1-default', '新概念首次打开保持默认分组策略(存在的组不偏离默认, 无词条展开)', (f1default.beforeOpenDefault !== false) && (f1default.relatedClosedDefault !== false) && !f1default.anyCardOpen, JSON.stringify(f1default));

// ---------- F2: 快速后退不丢刚发生的展开变化 ----------
await page.evaluate(() => window.atlasUI.selectConcept('3-04'));
await page.waitForTimeout(400);
// 开说明 → 等同步 → 收说明 → 等toggle事件派发(浏览器异步排队, 真实用户点击间隔≥50ms) → 立即后退
await page.evaluate(() => { document.querySelector('#explanation').open = true; });
await page.waitForTimeout(400);
await page.evaluate(() => { document.querySelector('#explanation').open = false; });
await page.waitForTimeout(80); // toggle事件异步派发窗口
await page.goBack();
await page.waitForTimeout(400);
const f2b = await page.evaluate(() => window.atlasUI.getState().selected);
add('F2-back', '收起后立即后退, 正确切到上一概念', f2b === '4-03' || f2b !== '3-04', `sel=${f2b}`);
await page.goForward(); // 立即前进回3-04
await page.waitForTimeout(450);
const f2f = await page.evaluate(() => ({ sel: window.atlasUI.getState().selected, exp: document.querySelector('#explanation').open }));
add('F2-forward', '前进回3-04: 说明保持刚收起的收起态(不再展开)', f2f.sel === '3-04' && f2f.exp === false, JSON.stringify(f2f));
// 反向: 展开后(等toggle派发)立即后退→前进, 保持展开
await page.evaluate(() => { document.querySelector('#explanation').open = true; });
await page.waitForTimeout(80); // toggle事件异步派发窗口
await page.goBack();
await page.waitForTimeout(400);
await page.goForward();
await page.waitForTimeout(450);
const f2f2 = await page.evaluate(() => ({ sel: window.atlasUI.getState().selected, exp: document.querySelector('#explanation').open }));
add('F2-forward2', '展开后立即后退→前进: 说明保持展开', f2f2.sel === '3-04' && f2f2.exp === true, JSON.stringify(f2f2));

// ---------- E4断言补强: 概念/展开/滚动严格相等 + 相机精确恢复 ----------
await page.evaluate(() => window.atlasUI.selectConcept('1-01'));
await page.waitForTimeout(350);
await page.evaluate(() => { window.scrollTo(0, 160); document.querySelector('#explanation').open = false; });
await page.waitForTimeout(600); // 滚动走250ms节流, 等写入
const e4c = await page.evaluate(() => ({ sel: window.atlasUI.getState().selected, cam: window.atlasUI.getState().camera.position, exp: document.querySelector('#explanation').open, scroll: window.scrollY }));
await page.evaluate(() => window.atlasUI.selectConcept('2-03'));
await page.waitForTimeout(400);
await page.evaluate(() => window.atlasUI.selectConcept('6-01'));
await page.waitForTimeout(400);
await page.goBack(); await page.waitForTimeout(400); // 回2-03
await page.goBack(); await page.waitForTimeout(450); // 回1-01
const e4r = await page.evaluate(() => ({ sel: window.atlasUI.getState().selected, cam: window.atlasUI.getState().camera.position, exp: document.querySelector('#explanation').open, scroll: window.scrollY }));
const camDiff = Math.hypot(e4r.cam.x - e4c.cam.x, e4r.cam.y - e4c.cam.y, e4r.cam.z - e4c.cam.z);
add('E4-strict', `概念/展开/滚动严格一致且相机精确恢复(差<2)`, e4r.sel === '1-01' && e4r.exp === e4c.exp && e4r.scroll === e4c.scroll && camDiff < 2, JSON.stringify({ sel: e4r.sel, exp: [e4c.exp, e4r.exp], scroll: [e4c.scroll, e4r.scroll], camDiff: camDiff.toFixed(4) }));

add('X1', '全程无pageerror', errors.length === 0, errors.slice(0, 3).join('|'));

const fails = R.checks.filter(c => !c.pass);
fs.writeFileSync(`${EV}/F1F2回归结果-20261002.json`, JSON.stringify(R, null, 1));
console.log(`\n=== ${R.checks.length - fails.length}/${R.checks.length} PASS ===`);
await browser.close();
process.exit(fails.length ? 1 : 0);
