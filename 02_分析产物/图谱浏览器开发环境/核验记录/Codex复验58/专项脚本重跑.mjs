// 57号修复回归 · 历史覆盖 + 零等待快速导航 · 失败退出非零
import { chromium } from '/Users/larry/.workbuddy/binaries/node/workspace/node_modules/playwright/index.mjs';
import fs from 'fs';
const ROOT = '/Users/larry/WorkBuddy/2026-09-13-14-09-47';
const EV = `/tmp/atlas59-ev`;
const DEV = 'http://127.0.0.1:41839/atlas.html';
const R = { time: new Date().toISOString(), checks: [] };
const add = (id, name, pass, detail = '') => { R.checks.push({ id, name, pass, detail }); console.log(`${pass ? 'PASS' : 'FAIL'} [${id}] ${name}${detail ? ' — ' + detail : ''}`); };

const browser = await chromium.launch({ executablePath: '/Users/larry/Library/Caches/ms-playwright/chromium_headless_shell-1234/chrome-headless-shell-mac-arm64/chrome-headless-shell' });
const page = await (await browser.newContext({ viewport: { width: 390, height: 844 } })).newPage();
const errors = [];
page.on('pageerror', e => errors.push(e.message));

// 四位一体一致性断言: URL / atlasUI.selected / history.state.selected / 正文标题
async function expectConsistent(id, label) {
  const s = await page.evaluate(() => ({
    sel: window.atlasUI.getState().selected,
    histSel: window.history.state?.selected ?? null,
    h1: document.querySelector('#concept-title').textContent,
    defLen: document.querySelector('#definition').textContent.length
  }));
  const url = page.url();
  const urlOk = url.endsWith('#' + id);
  const ok = urlOk && s.sel === id && s.histSel === id && s.h1.length > 0 && s.defLen > 10;
  return { ok, detail: JSON.stringify({ url: url.split('#')[1] ?? '', sel: s.sel, histSel: s.histSel, h1: s.h1 }) };
}

// ---------- 场景1: 重新选回已读概念后后退, 历史条目不得被覆盖 ----------
await page.goto(`${DEV}#4-03`, { waitUntil: 'load' });
await page.waitForTimeout(1600);
await page.evaluate(() => {
  const d = document.querySelector('.neighbor-group[data-group="before"] .neighbor-card'); if (d) d.open = true;
  const g = document.querySelector('.neighbor-group[data-group="related"]'); if (g) g.open = true;
});
await page.waitForTimeout(150);
const openedCard = await page.evaluate(() => document.querySelector('.neighbor-group[data-group="before"] .neighbor-card[open]')?.dataset.neighbor ?? null);

await page.evaluate(() => window.atlasUI.selectConcept('3-07'));
await page.waitForTimeout(300);
await page.goBack(); await page.waitForTimeout(400);
let c = await expectConsistent('4-03', '后退回4-03');
add('S1-back', '后退回4-03四项一致', c.ok, c.detail);
const f1state = await page.evaluate(id => {
  const card = document.querySelector(`.neighbor-card[data-neighbor="${id}"]`);
  const group = document.querySelector('.neighbor-group[data-group="related"]');
  return { cardOpen: !!card?.open, body: card?.querySelector('.neighbor-reading')?.childElementCount ?? 0, relatedOpen: !!group?.open };
}, openedCard);
add('S1-f1keep', '后退后相邻展开保持(F1不回归)', f1state.cardOpen && f1state.body > 0 && f1state.relatedOpen, JSON.stringify(f1state));

await page.goForward(); await page.waitForTimeout(400);
c = await expectConsistent('3-07', '前进到3-07');
add('S1-fwd', '前进到3-07四项一致', c.ok, c.detail);

await page.evaluate(() => window.atlasUI.selectConcept('4-03'));  // 再次选回4-03(pushState新条目)
await page.waitForTimeout(450);
c = await expectConsistent('4-03', '再次选回4-03');
add('S1-reselect', '重新选回4-03四项一致', c.ok, c.detail);

await page.goBack(); await page.waitForTimeout(450);              // 关键: 应回3-07, 不得被4-03覆盖
c = await expectConsistent('3-07', '后退应回3-07(历史未被覆盖)');
add('S1-critical', '重新选回后再后退: URL/selected/state/正文=3-07', c.ok, c.detail);

await page.goForward(); await page.waitForTimeout(450);
c = await expectConsistent('4-03', '前进回4-03');
add('S1-fwd2', '前进回4-03四项一致', c.ok, c.detail);
const f1keep2 = await page.evaluate(id => {
  const card = document.querySelector(`.neighbor-card[data-neighbor="${id}"]`);
  const group = document.querySelector('.neighbor-group[data-group="related"]');
  return { cardOpen: !!card?.open, body: card?.querySelector('.neighbor-reading')?.childElementCount ?? 0, relatedOpen: !!group?.open };
}, openedCard);
add('S1-f1keep2', '前进回4-03后相邻展开仍保持', f1keep2.cardOpen && f1keep2.body > 0 && f1keep2.relatedOpen, JSON.stringify(f1keep2));

// ---------- 场景2: F2 零等待快速导航 ----------
await page.evaluate(() => window.atlasUI.selectConcept('3-04'));
await page.waitForTimeout(400);
await page.evaluate(() => { document.querySelector('#explanation').open = true; });
await page.waitForTimeout(300); // 等待保存(微任务级, 300ms富余)
await page.evaluate(() => { document.querySelector('#explanation').open = false; });
await page.goBack();   // 零额外等待
await page.waitForTimeout(350);
await page.goForward(); // 零额外等待
await page.waitForTimeout(400);
const f2a = await page.evaluate(() => ({ sel: window.atlasUI.getState().selected, exp: document.querySelector('#explanation').open }));
add('S2-collapse', '收起后零等待后退→前进: 说明保持收起', f2a.sel === '3-04' && f2a.exp === false, JSON.stringify(f2a));

await page.evaluate(() => { document.querySelector('#explanation').open = true; });
await page.goBack();
await page.waitForTimeout(350);
await page.goForward();
await page.waitForTimeout(400);
const f2b = await page.evaluate(() => ({ sel: window.atlasUI.getState().selected, exp: document.querySelector('#explanation').open }));
add('S2-expand', '展开后零等待后退→前进: 说明保持展开', f2b.sel === '3-04' && f2b.exp === true, JSON.stringify(f2b));

// ---------- E4-strict 保持 ----------
await page.evaluate(() => window.atlasUI.selectConcept('1-01'));
await page.waitForTimeout(350);
await page.evaluate(() => { window.scrollTo(0, 160); document.querySelector('#explanation').open = false; });
await page.waitForTimeout(600);
const e4c = await page.evaluate(() => ({ cam: window.atlasUI.getState().camera.position, exp: document.querySelector('#explanation').open, scroll: window.scrollY }));
await page.evaluate(() => window.atlasUI.selectConcept('2-03'));
await page.waitForTimeout(350);
await page.evaluate(() => window.atlasUI.selectConcept('6-01'));
await page.waitForTimeout(350);
await page.goBack(); await page.waitForTimeout(350);
await page.goBack(); await page.waitForTimeout(450);
const e4r = await page.evaluate(() => ({ cam: window.atlasUI.getState().camera.position, exp: document.querySelector('#explanation').open, scroll: window.scrollY }));
const camDiff = Math.hypot(e4r.cam.x - e4c.cam.x, e4r.cam.y - e4c.cam.y, e4r.cam.z - e4c.cam.z);
add('E4-strict', '概念/展开/滚动严格一致+相机精确恢复(<2)', e4r.exp === e4c.exp && e4r.scroll === e4c.scroll && camDiff < 2, `scroll=${e4c.scroll}/${e4r.scroll} exp=${e4c.exp}/${e4r.exp} camDiff=${camDiff.toFixed(4)}`);

add('X1', '全程无pageerror', errors.length === 0, errors.slice(0, 3).join('|'));

const fails = R.checks.filter(x => !x.pass);
fs.writeFileSync(`${EV}/57号修复回归结果-20261002.json`, JSON.stringify(R, null, 1));
console.log(`\n=== ${R.checks.length - fails.length}/${R.checks.length} PASS ===`);
await browser.close();
process.exit(fails.length ? 1 : 0);
