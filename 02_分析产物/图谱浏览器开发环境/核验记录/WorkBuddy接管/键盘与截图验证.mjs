// 键盘可用性 + 窄屏截图补充验证
import { chromium } from '/Users/larry/.workbuddy/binaries/node/workspace/node_modules/playwright/index.mjs';
import fs from 'fs';
const ROOT = '/Users/larry/WorkBuddy/2026-09-13-14-09-47';
const EV = `${ROOT}/02_分析产物/图谱浏览器开发环境/核验记录/WorkBuddy接管`;
const DEV = 'http://127.0.0.1:41839/atlas.html';
const R = { time: new Date().toISOString(), checks: [] };
const add = (id, name, pass, detail = '') => { R.checks.push({ id, name, pass, detail }); console.log(`${pass ? 'PASS' : 'FAIL'} [${id}] ${name}${detail ? ' — ' + detail : ''}`); };

const browser = await chromium.launch({ executablePath: '/Users/larry/Library/Caches/ms-playwright/chromium_headless_shell-1234/chrome-headless-shell-mac-arm64/chrome-headless-shell' });
const page = await (await browser.newContext({ viewport: { width: 390, height: 844 } })).newPage();
await page.goto(DEV, { waitUntil: 'load' });
await page.waitForTimeout(1500);

// K1: Tab 到跳转链接与按钮可聚焦
await page.keyboard.press('Tab'); await page.keyboard.press('Tab');
const focused1 = await page.evaluate(() => document.activeElement?.tagName + '.' + (document.activeElement?.className ?? ''));
add('K1', 'Tab键可聚焦控件', focused1.includes('A') || focused1.includes('BUTTON'), `焦点=${focused1}`);

// K2: Escape 关闭搜索面板
await page.click('[data-action="search"]');
await page.waitForTimeout(150);
await page.keyboard.press('Escape');
await page.waitForTimeout(150);
const closed = await page.evaluate(() => document.querySelector('#browser-panel').hidden);
add('K2', 'Escape关闭搜索面板', closed);

// K3: 目录中键盘选择概念（Tab到结果按钮+Enter）
await page.click('[data-action="directory"]');
await page.waitForTimeout(150);
await page.keyboard.press('Tab'); // 到search输入
await page.keyboard.press('Tab'); // 到第一个结果
await page.keyboard.press('Enter');
await page.waitForTimeout(400);
const kbSel = await page.evaluate(() => ({ sel: window.atlasUI.getState().selected, hidden: document.querySelector('#browser-panel').hidden }));
add('K3', '键盘Enter选择目录概念', !kbSel.hidden === false && kbSel.sel !== '4-03', JSON.stringify(kbSel));

// K4: 图内 a11y 节点按钮存在且可聚焦（explore模式）
await page.evaluate(() => window.atlasUI.setMode('explore'));
await page.waitForTimeout(400);
const a11y = await page.evaluate(() => {
  const btns = [...document.querySelectorAll('.graph-a11y-node')];
  if (!btns.length) return { count: 0 };
  btns[0].focus();
  return { count: btns.length, focused: document.activeElement?.classList?.contains('graph-a11y-node'), label: btns[0].getAttribute('aria-label') };
});
add('K4', '图内197个键盘可读节点按钮', a11y.count === 197 && a11y.focused, `count=${a11y.count} label=${a11y.label ?? ''}`);

// K5: 长文卡（1-16发展史 定义较长的密集文本）窄屏阅读
await page.setViewportSize({ width: 320, height: 700 });
await page.evaluate(() => window.atlasUI.selectConcept('1-16'));
await page.waitForTimeout(300);
await page.evaluate(() => { document.querySelector('#explanation').open = true; });
await page.waitForTimeout(200);
const long = await page.evaluate(() => ({
  overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
  plainLen: document.querySelector('#explanation-copy .plain-explanation')?.textContent.length ?? 0,
  fieldLen: document.querySelector('#explanation-copy')?.textContent.length ?? 0
}));
add('K5', '320px长文卡无溢出且通俗解释完整', long.overflow <= 0 && long.plainLen > 200 && long.fieldLen > 300, JSON.stringify(long));
await page.screenshot({ path: `${EV}/截图-320px长文卡.png`, fullPage: false });
await page.setViewportSize({ width: 390, height: 844 });
await page.screenshot({ path: `${EV}/截图-390px正文.png` });
await page.setViewportSize({ width: 430, height: 930 });
await page.screenshot({ path: `${EV}/截图-430px正文.png` });

R.summary = { total: R.checks.length, pass: R.checks.filter(c => c.pass).length };
fs.writeFileSync(`${EV}/键盘验证结果-20261002.json`, JSON.stringify(R, null, 1));
console.log(`\n=== ${R.summary.pass}/${R.summary.total} PASS ===`);
await browser.close();
process.exit(0);
