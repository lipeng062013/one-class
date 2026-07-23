import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const htmlPath = new URL('../one-class-operations-guide.html', import.meta.url);
const workflowPath = new URL('../.github/workflows/deploy-pages.yml', import.meta.url);
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

test('hides interactive controls from printed copies', async () => {
  const html = await loadHtml();
  assert.match(html, /@media print[\s\S]*#reset-checklist[\s\S]*display:\s*none\s*!important/);
});

test('exposes accessible interaction hooks', async () => {
  const html = await loadHtml();
  for (const functionName of ['initMobileNav', 'initSectionTracking', 'initDisclosureControls', 'initChecklist']) {
    assert.match(html, new RegExp(`function ${functionName}\\(`), `missing ${functionName}`);
  }
  assert.match(html, /<noscript>/);
  assert.match(html, /aria-expanded=/);
  assert.match(html, /one-class-first-month-checklist-v1/);
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

test('deploys only the guide through the official GitHub Pages workflow', async () => {
  const workflow = await readFile(workflowPath, 'utf8');
  assert.match(workflow, /name: Deploy GitHub Pages/);
  assert.match(workflow, /pages:\s*write/);
  assert.match(workflow, /id-token:\s*write/);
  assert.match(workflow, /name:\s*github-pages/);
  assert.match(workflow, /cp one-class-operations-guide\.html _site\/index\.html/);
  assert.match(workflow, /actions\/upload-pages-artifact@v3/);
  assert.match(workflow, /path:\s*_site/);
  assert.match(workflow, /actions\/deploy-pages@v4/);
});

test('starts with only the summary and current 90-day actions expanded when JavaScript runs', async () => {
  const html = await loadHtml();
  assert.match(html, /const defaultOpenSectionIds = new Set\(\['summary', 'ninety-days'\]\)/);
  assert.match(html, /item\.open = defaultOpenSectionIds\.has\(item\.closest\('\.guide-section'\)\?\.id\)/);
});

test('keeps progress and disclosure commands available on mobile', async () => {
  const html = await loadHtml();
  assert.match(html, /class="mobile-tools"/);
  assert.match(html, /data-disclosure-action="expand"/);
  assert.match(html, /data-disclosure-action="collapse"/);
  assert.match(html, /@media \(max-width: 760px\)[\s\S]*\.header-progress\s*\{[^}]*display:\s*grid/);
  assert.doesNotMatch(html, /@media \(max-width: 760px\)[\s\S]*\.header-progress\s*\{\s*display:\s*none/);
});

test('shows a qualified 90-day target in the first screen', async () => {
  const html = await loadHtml();
  assert.match(html, /class="ninety-day-target"/);
  assert.match(html, /90天目标（不承诺）/);
  assert.match(html, /有效咨询量较首月基线争取提升20%-40%/);
});

test('exposes visible focus, current navigation semantics and honest collapse behavior', async () => {
  const html = await loadHtml();
  assert.match(html, /\.command:focus-visible\s*\{[^}]*outline:\s*3px solid/);
  assert.match(html, /setAttribute\('aria-current', 'location'\)/);
  assert.match(html, /details\.forEach\(\(item\) => \{ item\.open = false; \}\)/);
  assert.match(html, /审批后可选：1000-2000元付费推广测试/);
});
