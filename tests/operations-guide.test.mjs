import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const htmlPath = new URL('../one-class-operations-guide.html', import.meta.url);
const sectionIds = [
  'summary', 'growth', 'channels', 'annual-plan', 'cadence', 'materials',
  'platform-playbooks', 'reviews', 'ai-stack', 'automation-boundaries',
  'internal-tools', 'official-learning', 'learning-plan', 'ninety-days',
  'roles-budget', 'metrics', 'compliance', 'first-month-checklist'
];

async function loadHtml() {
  return readFile(htmlPath, 'utf8');
}

test('delivers a standalone Chinese operations guide', async () => {
  const html = await loadHtml();
  assert.match(html, /<html lang="zh-CN">/);
  assert.match(html, /<meta name="viewport"/);
  assert.match(html, /壹号教室全年运营/);
  assert.doesNotMatch(html, /<script[^>]+src=/i);
  assert.doesNotMatch(html, /<link[^>]+rel=["']stylesheet/i);
});

test('contains every approved guide section', async () => {
  const html = await loadHtml();
  for (const id of sectionIds) {
    assert.match(html, new RegExp(`id=["']${id}["']`), `missing section ${id}`);
  }
  for (const phrase of ['嘉定新城', '朋友圈', '视频号', '大众点评', '美团', '30/60/90', '8周学习']) {
    assert.ok(html.includes(phrase), `missing approved content: ${phrase}`);
  }
});

test('includes responsive, print and local checklist behavior', async () => {
  const html = await loadHtml();
  assert.match(html, /@media\s*\([^)]*max-width:\s*760px/);
  assert.match(html, /@media\s+print/);
  assert.match(html, /localStorage/);
  assert.match(html, /window\.print\(\)/);
  assert.match(html, /data-checklist-item/);
});

test('links only to the approved official learning sources', async () => {
  const html = await loadHtml();
  for (const url of [
    'https://www.feishu.cn/product/base',
    'https://docs.dify.ai/zh/home',
    'https://docs.n8n.io/learning-paths',
    'https://docs.coze.cn/guides_welcome'
  ]) {
    assert.ok(html.includes(url), `missing official source: ${url}`);
  }
});
