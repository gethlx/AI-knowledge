import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { resolveLanguage, setLanguage, getLanguage, fieldsFor, englishName, wrapLabel, t } from '../src/ui/i18n.js';

const source = readFileSync(new URL('../src/ui/preview-data.json', import.meta.url));
const input = JSON.parse(source);
const english = JSON.parse(readFileSync(new URL('../src/ui/english-data.json', import.meta.url)));

test('English data covers every card and preserves the complete source field schema', () => {
  assert.equal(english._meta.source_sha256, createHash('sha256').update(source).digest('hex'));
  assert.equal(Object.keys(english.cards).length, input.cards.length);
  for (const card of input.cards) {
    const translated = english.cards[card.card_id];
    assert.ok(translated?.name, `Missing name: ${card.card_id}`);
    assert.equal(/[\p{Script=Han}]/u.test(translated.name), false, card.card_id);
    assert.deepEqual(Object.keys(translated.fields).sort(), Object.keys(card.fields).sort());
    for (const [key, value] of Object.entries(card.fields)) {
      const text = translated.fields[key];
      assert.equal(typeof text, 'string');
      if (value.trim()) assert.ok(text.trim(), `${card.card_id}: ${key}`);
      assert.equal(/[\p{Script=Han}]|\[\[FIELD_/u.test(text), false, `${card.card_id}: ${key}`);
      if (!value.trim() || value === '—') assert.equal(text, value);
    }
  }
});

test('explicit language links override saved preferences; blocked storage is safe', () => {
  const stored = { getItem: () => 'en' };
  const blocked = { getItem() { throw Error('blocked'); }, setItem() { throw Error('blocked'); } };
  assert.equal(resolveLanguage('?lang=zh', stored), 'zh');
  assert.equal(resolveLanguage('?lang=en', blocked), 'en');
  assert.equal(resolveLanguage('', stored), 'en');
  assert.equal(resolveLanguage('?lang=invalid', blocked), 'zh');
  assert.doesNotThrow(() => setLanguage('en', blocked));
  assert.equal(getLanguage(), 'en');
});

test('switching language selects the right text without mutating Chinese source', () => {
  const before = JSON.stringify(input);
  const card = input.cards.find(c => c.card_id === '3-13');
  const saved = {};
  setLanguage('en', { setItem: (k, v) => saved[k] = v });
  assert.match(fieldsFor(card)['精确定义'], /^Probability/);
  assert.equal(englishName(card), 'Probability / Uncertainty');
  assert.equal(saved['ai-atlas-language'], 'en');
  assert.equal(t('共{count}个概念', { count: 197 }), '197 concepts');
  setLanguage('zh');
  assert.strictEqual(fieldsFor(card), card.fields);
  assert.equal(t('共{count}个概念', { count: 197 }), '共197个概念');
  assert.equal(JSON.stringify(input), before);
});

test('English labels wrap at word boundaries and retain all words', () => {
  const title = 'Reinforcement Learning from Human Feedback (RLHF)';
  const wrapped = wrapLabel(title, 'en');
  assert.equal(wrapped.split('\n').join(' '), title);
  assert.ok(wrapped.includes('\n'));
  assert.equal(wrapLabel('概率与不确定性', 'zh'), '概率与不确定性');
});

test('every static interface translation is available in English', () => {
  const html = readFileSync(new URL('../index.html', import.meta.url), 'utf8');
  setLanguage('en');
  for (const [, key] of html.matchAll(/data-i18n(?:-aria-label|-placeholder)?="([^"]+)"/g)) {
    assert.equal(/[\p{Script=Han}]/u.test(t(key)), false, `Untranslated: ${key}`);
  }
});
