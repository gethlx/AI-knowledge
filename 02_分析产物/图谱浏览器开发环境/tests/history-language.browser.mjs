/**
 * End-to-end regression against a running dev or production-preview server.
 * Run: ATLAS_BASE_URL=http://127.0.0.1:41839 node --test tests/history-language.browser.mjs
 * Requires the optional `playwright` package and its Chromium browser.
 * All app changes below use the rendered controls or browser navigation.
 */
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { chromium } from 'playwright';

const baseURL = process.env.ATLAS_BASE_URL || 'http://127.0.0.1:41839/';
const launchOptions = {
  ...(process.env.ATLAS_CHROMIUM_EXECUTABLE ? { executablePath: process.env.ATLAS_CHROMIUM_EXECUTABLE } : {}),
  ...(process.env.ATLAS_SOFTWARE_WEBGL === '1' ? { args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader'] } : {})
};
const source = JSON.parse(readFileSync(new URL('../src/ui/preview-data.json', import.meta.url)));
const english = JSON.parse(readFileSync(new URL('../src/ui/english-data.json', import.meta.url)));
const cards = new Map(source.cards.map(card => [card.card_id, card]));
const chineseNames = new Map(source.graph.nodes.map(node => [node.card_id, node.name]));
const expectedName = (id, language) => language === 'en' ? english.cards[id].name : chineseNames.get(id);
const expectedFields = (id, language) => language === 'en' ? english.cards[id].fields : cards.get(id).fields;
const options = width => ({ viewport: { width, height: 844 }, hasTouch: true, isMobile: true, deviceScaleFactor: 1 });
const address = suffix => new URL(suffix, baseURL).href;
const normalizeLabel = text => text.replace(/\n/g, /[\p{Script=Han}]/u.test(text) ? '' : ' ').replace(/\s+/g, ' ').trim();

async function ready(page) {
  await page.waitForFunction(() => window.atlasUI?.getState().graphReady === true, null, { timeout: 20_000 });
  await page.locator('#definition').waitFor({ state: 'visible' });
}

async function geometry(page) {
  return page.evaluate(() => {
    const state = atlasUI.getState();
    return {
      selected: state.selected, mode: state.mode, camera: state.camera,
      nodes: atlasUI.graph().graphData().nodes.map(({ id, x, y, z }) => ({ id, x, y, z }))
    };
  });
}

function closeGeometry(actual, expected, message) {
  assert.equal(actual.selected, expected.selected, `${message}: selected concept`);
  assert.equal(actual.mode, expected.mode, `${message}: graph mode`);
  const compare = (a, b, path) => {
    if (typeof a === 'number') assert.ok(Math.abs(a - b) < 1e-5, `${message}: ${path} (${a} vs ${b})`);
    else if (a && typeof a === 'object') {
      assert.deepEqual(Object.keys(a), Object.keys(b), `${message}: ${path} keys`);
      for (const key of Object.keys(a)) compare(a[key], b[key], `${path}.${key}`);
    } else assert.equal(a, b, `${message}: ${path}`);
  };
  compare(actual.camera, expected.camera, 'camera');
  compare(actual.nodes, expected.nodes, 'nodes');
}

async function settledGeometry(page) {
  // Wait for natural physics / camera transitions, without stopping or mutating the graph.
  let previous = await geometry(page), stable = 0;
  const deadline = Date.now() + 15_000;
  while (Date.now() < deadline) {
    await page.waitForTimeout(150);
    const current = await geometry(page);
    try { closeGeometry(current, previous, 'settling'); stable++; } catch { stable = 0; }
    if (stable >= 3) return current;
    previous = current;
  }
  throw new Error('Graph/camera did not settle within 15 seconds');
}

async function reading(page) {
  return page.evaluate(() => ({
    explanation: document.querySelector('#explanation').open,
    neighbors: document.querySelector('#neighbors').open,
    groups: [...document.querySelectorAll('#neighbor-list .neighbor-group')].map(el => [el.dataset.group, el.open]),
    cards: [...document.querySelectorAll('#neighbor-list .neighbor-card[open]')].map(el => el.dataset.neighbor)
  }));
}

async function expandReading(page) {
  // Explicitly exercise manual disclosure changes (including queued toggle events).
  await page.locator('#explanation > summary').tap();
  await page.locator('#explanation > summary').tap();
  if (!(await page.locator('#neighbors').evaluate(el => el.open))) await page.locator('#neighbors > summary').tap();
  const closedGroup = page.locator('#neighbor-list .neighbor-group:not([open]) > summary').first();
  if (await closedGroup.count()) await closedGroup.tap();
  const neighbor = page.locator('#neighbor-list .neighbor-card').first();
  await neighbor.locator(':scope > summary').tap();
  await neighbor.locator('.neighbor-reading > p').first().waitFor({ state: 'visible' });
  return reading(page);
}

async function assertEntry(page, id, language) {
  try {
    await page.waitForFunction(({ id, language }) => window.atlasUI?.getState().selected === id && atlasUI.getLanguage() === language, { id, language }, { timeout: 10_000 });
  } catch (cause) {
    const actual = await page.evaluate(() => ({ url: location.href, selected: window.atlasUI?.getState().selected, language: window.atlasUI?.getLanguage(), documentLanguage: document.documentElement.lang, title: document.querySelector('#concept-title')?.textContent }));
    throw new Error(`Expected ${id}/${language}; restored entry was ${JSON.stringify(actual)}`, { cause });
  }
  await page.waitForFunction(() => [...document.querySelectorAll('.neighbor-card[open]')].every(el => el.querySelector('.neighbor-reading > p')?.textContent));
  const state = await page.evaluate(() => {
    const sprites = [];
    atlasUI.graph().scene().traverse(object => { if (typeof object.text === 'string') sprites.push(object.text); });
    return {
      hash: location.hash, langQuery: new URLSearchParams(location.search).get('lang'),
      language: atlasUI.getLanguage(), documentLanguage: document.documentElement.lang,
      title: document.querySelector('#concept-title').textContent,
      pageTitle: document.title, definition: document.querySelector('#definition').textContent,
      definitionLabel: document.querySelector('.definition h2').textContent,
      draftHidden: document.querySelector('#translation-note').hidden,
      nodes: atlasUI.graph().graphData().nodes.map(({ id, name }) => ({ id, name })),
      accessible: [...document.querySelectorAll('#node-labels [data-concept]')].map(el => ({ id: el.dataset.concept, text: el.textContent, label: el.getAttribute('aria-label') })),
      sprites,
      expandedDefinitions: [...document.querySelectorAll('.neighbor-card[open]')].map(el => ({ id: el.dataset.neighbor, definition: el.querySelector('.neighbor-reading > p')?.textContent }))
    };
  });
  assert.equal(state.hash, `#${id}`);
  assert.equal(state.langQuery, language, 'URL explicitly identifies the displayed language');
  assert.equal(state.language, language);
  assert.equal(state.documentLanguage, language === 'en' ? 'en' : 'zh-CN');
  assert.equal(state.title, expectedName(id, language));
  assert.ok(state.pageTitle.startsWith(expectedName(id, language)));
  assert.equal(state.definition, expectedFields(id, language)['精确定义']);
  assert.equal(state.definitionLabel, language === 'en' ? 'Definition' : '定义');
  assert.equal(state.draftHidden, language !== 'en', 'English draft notice stays present');
  assert.equal(state.nodes.length, source.graph.nodes.length);
  assert.equal(state.accessible.length, source.graph.nodes.length);
  for (const node of state.nodes) assert.equal(node.name, expectedName(node.id, language), `graph node ${node.id}`);
  for (const node of state.accessible) {
    assert.equal(node.text, expectedName(node.id, language), `accessible graph node ${node.id}`);
    assert.ok(node.label.endsWith(node.text));
  }
  assert.deepEqual(state.sprites.map(normalizeLabel).sort(), state.nodes.map(node => normalizeLabel(node.name)).sort(), 'rendered graph sprite labels agree with the language');
  for (const card of state.expandedDefinitions) assert.equal(card.definition, expectedFields(card.id, language)['精确定义'], `expanded adjacent card ${card.id}`);
  const width = await page.evaluate(() => ({ body: document.body.scrollWidth, document: document.documentElement.scrollWidth, viewport: innerWidth }));
  assert.ok(Math.max(width.body, width.document) <= width.viewport + 1, `No horizontal overflow: ${JSON.stringify(width)}`);
}

async function searchFor(page, query, id) {
  await page.locator('.masthead [data-action="search"]').tap();
  await page.locator('#search-input').fill(query);
  const result = page.locator(`#results [data-concept="${id}"]`);
  await result.waitFor({ state: 'visible' });
  await result.tap();
}

async function assertCopiedEntry(browser, url, width, id, language) {
  const fresh = await browser.newContext(options(width));
  try {
    const page = await fresh.newPage();
    await page.goto(url);
    await ready(page);
    await assertEntry(page, id, language);
  } finally { await fresh.close(); }
}

for (const width of [320, 390]) {
  test(`touch ${width}px: language/history, reading, graph, reload, shared URLs`, { timeout: 120_000 }, async () => {
    const browser = await chromium.launch(launchOptions);
    const context = await browser.newContext(options(width));
    const errors = [];
    try {
      const page = await context.newPage();
      page.on('pageerror', error => errors.push(error.message));
      await page.goto(address('?lang=en#3-13'));
      await ready(page);
      const readingA = await expandReading(page);
      const geometryA = await settledGeometry(page);
      await assertEntry(page, '3-13', 'en');

      await searchFor(page, 'Large Language Model', '4-03');
      await assertEntry(page, '4-03', 'en');
      const readingB = await expandReading(page);
      const geometryB = await settledGeometry(page);
      // Put the switch back in view before measuring; tapping must not add scroll side effects.
      await page.locator('.masthead [data-action="language"]').scrollIntoViewIfNeeded();
      await page.locator('.masthead [data-action="language"]').tap();
      await assertEntry(page, '4-03', 'zh');
      closeGeometry(await settledGeometry(page), geometryB, 'language switch preserves camera/layout');
      assert.deepEqual(await reading(page), readingB, 'language switch preserves expanded reading');
      const chineseURL = page.url();

      await page.goBack();
      await assertEntry(page, '3-13', 'en');
      assert.deepEqual(await reading(page), readingA, 'Back restores entry A reading');
      closeGeometry(await settledGeometry(page), geometryA, 'Back restores entry A camera/layout');
      const englishURL = page.url();
      await assertCopiedEntry(browser, englishURL, width, '3-13', 'en');

      await page.goForward();
      await assertEntry(page, '4-03', 'zh');
      assert.deepEqual(await reading(page), readingB, 'Forward restores entry B reading');
      closeGeometry(await settledGeometry(page), geometryB, 'Forward restores entry B camera/layout');
      await assertCopiedEntry(browser, chineseURL, width, '4-03', 'zh');

      await page.reload();
      await ready(page);
      await assertEntry(page, '4-03', 'zh');
      await page.goBack();
      await assertEntry(page, '3-13', 'en');
      await page.reload();
      await ready(page);
      await assertEntry(page, '3-13', 'en');
      await page.goForward();
      await assertEntry(page, '4-03', 'zh');

      // Both search languages and the existing learning-level filter still work.
      for (const query of ['大语言模型', 'Large Language Model']) {
        await searchFor(page, query, '4-03');
        await assertEntry(page, '4-03', 'zh');
      }
      await page.locator('.masthead [data-action="directory"]').tap();
      await page.locator('#level-filter').selectOption('理解');
      const resultIDs = await page.locator('#results [data-concept]').evaluateAll(elements => elements.map(el => el.dataset.concept));
      assert.ok(resultIDs.length > 0);
      for (const id of resultIDs) assert.equal(cards.get(id).fields['认知层级'], '理解');
      await page.locator('[data-action="close-browser"]').tap();
      assert.deepEqual(errors, [], 'no browser exceptions');
    } finally { await context.close(); await browser.close(); }
  });
}

test('new visitor defaults to Chinese and a copied default-language URL stays Chinese', { timeout: 40_000 }, async () => {
  const browser = await chromium.launch(launchOptions);
  const context = await browser.newContext(options(390));
  try {
    const page = await context.newPage();
    await page.goto(address('#3-13'));
    await ready(page);
    await assertEntry(page, '3-13', 'zh');
    const chineseURL = page.url();
    await page.locator('.masthead [data-action="language"]').tap();
    await assertEntry(page, '3-13', 'en');
    await assertCopiedEntry(browser, chineseURL, 390, '3-13', 'zh');
  } finally { await context.close(); await browser.close(); }
});

test('saved preference, rapid language/Back, and repeated-concept entries stay independent', { timeout: 90_000 }, async () => {
  const browser = await chromium.launch(launchOptions);
  const context = await browser.newContext(options(390));
  try {
    const page = await context.newPage();
    await page.goto(address('#3-13'));
    await ready(page);
    await page.locator('.masthead [data-action="language"]').tap();
    await assertEntry(page, '3-13', 'en');

    // A fresh document with no language query resolves the existing preference and
    // records it in the URL, so later preference changes cannot reinterpret this entry.
    await page.goto(address('#3-13'));
    await ready(page);
    await assertEntry(page, '3-13', 'en');
    const firstReading = await expandReading(page);
    const preferredURL = page.url();
    await assertCopiedEntry(browser, preferredURL, 390, '3-13', 'en');
    await searchFor(page, 'Large Language Model', '4-03');
    await settledGeometry(page);
    await page.locator('.masthead [data-action="language"]').tap();
    // Deliberately do not wait for animation frames/settling after the language tap.
    await page.goBack();
    await assertEntry(page, '3-13', 'en');
    assert.deepEqual(await reading(page), firstReading);
    await page.goForward();
    await assertEntry(page, '4-03', 'zh');

    // Visit A again in Chinese, with a different disclosure state from the earlier
    // English A entry. History snapshots must win over the per-concept reading cache.
    await searchFor(page, '概率与不确定性', '3-13');
    await assertEntry(page, '3-13', 'zh');
    if (await page.locator('#explanation').evaluate(el => el.open)) await page.locator('#explanation > summary').tap();
    const secondReading = await reading(page);
    assert.equal(secondReading.explanation, false);
    await page.goBack();
    await assertEntry(page, '4-03', 'zh');
    await page.goBack();
    await assertEntry(page, '3-13', 'en');
    assert.deepEqual(await reading(page), firstReading, 'earlier A entry retains its own reading state');
    await page.goForward();
    await assertEntry(page, '4-03', 'zh');
    await page.goForward();
    await assertEntry(page, '3-13', 'zh');
    assert.deepEqual(await reading(page), secondReading, 'later A entry retains its own reading state');
  } finally { await context.close(); await browser.close(); }
});
