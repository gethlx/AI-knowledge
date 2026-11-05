import english from './english-data.json' with { type: 'json' };

const STORAGE_KEY = 'ai-atlas-language';
export function resolveLanguage(search, storage) {
  const requested = new URLSearchParams(search).get('lang');
  if (requested === 'en' || requested === 'zh') return requested;
  try { return storage?.getItem(STORAGE_KEY) === 'en' ? 'en' : 'zh'; }
  catch { return 'zh'; }
}
let language = 'zh';
export const getLanguage = () => language;
export function setLanguage(value, storage) {
  language = value === 'en' ? 'en' : 'zh';
  try { storage?.setItem(STORAGE_KEY, language); } catch { /* Reading works without storage. */ }
  return language;
}
export function fieldsFor(card) {
  return language === 'en' ? english.cards[card.card_id]?.fields ?? card.fields : card.fields;
}
export const englishName = card => english.cards[card.card_id]?.name ?? card.en;
export function wrapLabel(text, locale = language) {
  if (locale !== 'en') return text.length > 8 ? text.match(/.{1,8}/gu).join('\n') : text;
  const lines = [''];
  for (const word of text.split(/\s+/)) {
    const last = lines.length - 1;
    if (lines[last] && lines[last].length + word.length + 1 > 22) lines.push(word);
    else lines[last] += (lines[last] ? ' ' : '') + word;
  }
  return lines.join('\n');
}

const en = {
  '神奇科学AI知识图册': 'Amazing Science · AI Knowledge Atlas',
  '神奇科学': 'Amazing Science',
  'AI知识图册': 'AI Knowledge Atlas',
  '神奇科学AI知识图册首页': 'AI Knowledge Atlas home',
  '跳到概念正文': 'Skip to concept',
  '图册导航': 'Atlas navigation',
  '展开或收起关系网': 'Show or hide the concept graph',
  '查找概念': 'Find a concept',
  '概念目录': 'Concept directory',
  '关系网探索': 'Explore the concept graph',
  '全景': 'Overview',
  '放大关系网': 'Zoom in',
  '缩小关系网': 'Zoom out',
  '定位当前概念': 'Locate the current concept',
  '开始缓慢旋转': 'Start slow rotation',
  '暂停旋转': 'Pause rotation',
  '关系网操作提示': 'Graph controls and help',
  '完整关系网': 'Full concept graph',
  '个概念': 'concepts',
  '条关系': 'connections',
  '展开关系网': 'Open graph',
  '定义': 'Definition',
  '解释说明': 'Explanation',
  '收起说明': 'Collapse',
  '展开阅读': 'Read more',
  '相邻概念': 'Connected concepts',
  '点开名称即可在此阅读。': 'Open a concept to read it here.',
  '概念浏览': 'Browse concepts',
  '返回阅读': 'Back to reading',
  '搜索概念名称（中文或英文）': 'Search in English or Chinese',
  '认知层级': 'Learning level',
  '全部层级': 'All levels',
  '识记': 'Remember',
  '理解': 'Understand',
  '应用': 'Apply',
  '分析评价': 'Analyze / evaluate',
  '待定': 'Not yet assigned',
  '输入时显示匹配名称，点击即可阅读': 'Matching names appear as you type. Select one to read.',
  '浏览全部概念': 'Browse all concepts',
  '探索关系网': 'Explore the graph',
  '知道了': 'Got it',
  '原版图册：gethlx': 'Original atlas by gethlx',
  '当前概念：': 'Current concept: ',
  '例如：': 'Example: ',
  '常见误解：': 'Common misconception: ',
  '反例：': 'Counterexample: ',
  '使用时留意：': 'Keep in mind: ',
  '理解本概念前，可先了解以下概念。': 'Start with these concepts before exploring this one. ',
  '以下概念以本概念为基础。': 'These concepts build on this one. ',
  '以下概念与本概念直接关联。': 'These concepts are directly related. ',
  '以下概念按关系分组。': 'Concepts are grouped by their relationship. ',
  '先了解这些概念': 'Start with these',
  '以它为基础': 'Builds on this concept',
  '相关联的概念': 'Related concepts',
  '暂无相邻概念。': 'No connected concepts yet.',
  '阅读': 'Read ',
  '共{count}个概念': '{count} concepts',
  '输入中文或英文概念名称，查找你想了解的内容。': 'Enter a concept name in English or Chinese to start exploring.',
  '匹配概念名称（中文或英文） · {count}个': 'Matching concept names · {count}',
  '没有匹配的概念。试试更短的词，或浏览全部概念。': 'No matching concepts. Try a shorter search or browse the directory.',
  '学习{target}前，先了解“{source}”。': 'Before exploring {target}, learn about {source}.',
  '{source}与{target}存在关联。': '{source} is related to {target}.',
  '三维视图已暂停（图形上下文丢失）。正文、搜索、目录和相邻概念清单仍可正常使用；刷新页面可恢复三维视图。': 'The 3D view has paused because the graphics context was lost. Reading, search, the directory, and connected concepts still work. Refresh to restore the graph.',
  '三维视图暂时无法加载。你仍可阅读正文，并在相邻概念清单中继续浏览。': 'The 3D view could not load. You can still read the text and explore the connected concepts.',
  '拖动小节点或名称，可拉动节点并带动邻近概念和连线重新排布。拖动空白处旋转视图；鼠标右键或双指移动平移，双指拉开或捏合缩放。滚轮围绕指针缩放，也可用加减按钮。名称保持可读大小。': 'Drag a node or its label to move it and rearrange nearby connections. Drag empty space to rotate. Right-drag or move two fingers to pan; pinch to zoom. Use the scroll wheel or the + and − buttons to zoom. Labels stay readable.',
  '点击节点或名称，阅读它的详情并定位一次；随后可自由移动、旋转和缩放。名称随眼前的视野呈现，不局限于当前概念的邻居。点“全景”查看全部197个概念，点定位按钮回到当前阅读的概念。': 'Select a node or label to read and locate that concept, then move freely around the graph. Labels appear across the current view, including concepts beyond the immediate neighbors. Choose Overview to see all 197 concepts, or the locate button to return to the concept you are reading.',
  '箭头表示理解后一个概念前，需要先了解前一个；其他连线表示关联。远近和连线长度仅用于排布，不代表知识关系强弱。': 'Arrows point from a prerequisite to the concept that builds on it. Other lines show associations. Distances and line lengths are only for layout; they do not measure the strength of a relationship.',
  '正文与相邻概念均在当前位置向下展开。': 'Explanations and connected concepts expand below, without leaving your place.',
  '英文内容为机器翻译草稿，教学表述仍待审校。': 'English explanations are machine-translated drafts; educational wording is still under review.'
};
export function t(key, values = {}) {
  const template = language === 'en' ? en[key] ?? key : key;
  return template.replace(/\{(\w+)\}/g, (match, key) => values[key] ?? match);
}
export function applyDocumentLanguage(root = document) {
  root.documentElement.lang = language === 'en' ? 'en' : 'zh-CN';
  root.querySelectorAll('[data-i18n]').forEach(el => el.textContent = t(el.dataset.i18n));
  for (const attr of ['aria-label', 'placeholder']) {
    root.querySelectorAll(`[data-i18n-${attr}]`).forEach(el => el.setAttribute(attr, t(el.getAttribute(`data-i18n-${attr}`))));
  }
  root.querySelectorAll('[data-action="language"]').forEach(button => {
    button.textContent = language === 'en' ? '中文' : 'English';
    button.lang = language === 'en' ? 'zh-CN' : 'en';
    button.setAttribute('aria-label', language === 'en' ? 'Switch to Chinese' : '切换到英文');
  });
  root.querySelector('#translation-note').hidden = language !== 'en';
}
