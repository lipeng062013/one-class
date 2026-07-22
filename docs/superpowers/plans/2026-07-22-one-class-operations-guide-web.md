# 壹号教室运营指导互动网页 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 创建一个可直接发送、离线打开、适配手机与桌面的单文件中文互动网页，完整呈现已确认的壹号教室全年运营指导。

**Architecture:** 交付物是根目录下的一个自包含 HTML 文件，语义化 HTML 承载全部内容，内联 CSS 负责响应式与打印布局，内联 JavaScript 只负责目录、章节展开、打印和本地任务清单。使用 Node 内置测试做结构与内容回归检查，再用真实浏览器验证桌面、手机和打印行为。

**Tech Stack:** HTML5、CSS3、原生 JavaScript、Node.js `node:test`、浏览器响应式检查

---

## File Structure

- Create: `one-class-operations-guide.html` - 唯一可交付网页，包含全部正文、样式和交互。
- Create: `tests/operations-guide.test.mjs` - 读取 HTML 并验证章节、离线性、交互钩子、官方链接和响应式规则。
- Modify: `docs/superpowers/plans/2026-07-22-one-class-operations-guide-web.md` - 实施过程中更新复选框状态。

### Task 1: 建立失败的页面合同测试

**Files:**
- Create: `tests/operations-guide.test.mjs`
- Test: `tests/operations-guide.test.mjs`

- [x] **Step 1: 编写页面合同测试**

```javascript
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
```

- [x] **Step 2: 运行测试并确认因 HTML 尚不存在而失败**

Run: `node --test tests/operations-guide.test.mjs`

Expected: FAIL，错误包含无法读取 `one-class-operations-guide.html`。

- [x] **Step 3: 提交失败测试**

```powershell
git add -- tests/operations-guide.test.mjs
git commit -m "test: define operations guide contract"
```

### Task 2: 实现完整语义内容与视觉布局

**Files:**
- Create: `one-class-operations-guide.html`
- Test: `tests/operations-guide.test.mjs`

- [x] **Step 1: 创建自包含 HTML 骨架**

文件必须使用以下页面边界，并将规格中的全部已确认文字分别放入对应的 `section`：

```html
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>壹号教室全年运营指导</title>
  <style>
    :root { color-scheme: light; }
    * { box-sizing: border-box; }
    body { margin: 0; font-family: system-ui, sans-serif; }
  </style>
</head>
<body>
  <header class="topbar">壹号教室全年运营指导</header>
  <div class="app-shell">
    <nav class="sidebar" aria-label="章节导航"></nav>
    <main id="main-content">
      <section id="summary"></section>
      <section id="growth"></section>
      <section id="channels"></section>
      <section id="annual-plan"></section>
      <section id="cadence"></section>
      <section id="materials"></section>
      <section id="platform-playbooks"></section>
      <section id="reviews"></section>
      <section id="ai-stack"></section>
      <section id="automation-boundaries"></section>
      <section id="internal-tools"></section>
      <section id="official-learning"></section>
      <section id="learning-plan"></section>
      <section id="ninety-days"></section>
      <section id="roles-budget"></section>
      <section id="metrics"></section>
      <section id="compliance"></section>
      <section id="first-month-checklist"></section>
    </main>
  </div>
  <script></script>
</body>
</html>
```

- [x] **Step 2: 实现响应式与打印样式**

内联 CSS 使用固定设计变量 `--ink: #19221f`、`--green: #176b4d`、`--blue: #245f8f`、`--yellow: #d89a20`、`--risk: #b4423c`、`--paper: #ffffff`、`--surface: #f3f5f3`。桌面采用 `260px minmax(0, 1fr)` 两列；`max-width: 760px` 下改为单列和可展开顶部目录；表格容器提供横向滚动；`@media print` 隐藏导航与按钮、展开所有内容并避免标题孤立分页。

- [x] **Step 3: 填入全部已确认内容**

逐章写入设计规格第4节的18项信息架构，并保留这些精确数据：每周6至8小时、朋友圈每周4至5条、视频号每周1至2条、首月预算0至300元、后续工具预算300至800元、8至12周后评估自建工具、三个月有效咨询目标区间20%至40%。在合规章节明确结果不保证、未成年人隐私、真实评价和平台授权边界。

- [x] **Step 4: 运行合同测试**

Run: `node --test tests/operations-guide.test.mjs`

Expected: 4 tests PASS。

- [x] **Step 5: 提交语义内容与样式**

```powershell
git add -- one-class-operations-guide.html
git commit -m "feat: add responsive operations guide"
```

### Task 3: 实现目录、折叠、打印和本地清单

**Files:**
- Modify: `one-class-operations-guide.html`
- Test: `tests/operations-guide.test.mjs`

- [x] **Step 1: 增加原生交互脚本**

脚本定义并调用 `initMobileNav()`、`initSectionTracking()`、`initDisclosureControls()`、`initChecklist()`。清单存储键固定为 `one-class-first-month-checklist-v1`；读取损坏数据时回退为空对象；勾选后更新顶部完成数与百分比。打印按钮只调用 `window.print()`，不上传数据。

- [x] **Step 2: 增加无 JavaScript 降级规则**

正文默认完整显示；仅在脚本启动后给 `<html>` 添加 `js` 类并启用折叠。提供 `<noscript>` 提示“互动功能不可用，但全部运营内容仍可正常阅读”。

- [x] **Step 3: 扩充合同测试**

在 `tests/operations-guide.test.mjs` 增加断言，检查固定存储键、四个初始化函数名、`noscript`、`aria-expanded` 和打印按钮，确保交互结构不会在后续编辑中丢失。

- [x] **Step 4: 运行测试**

Run: `node --test tests/operations-guide.test.mjs`

Expected: 所有测试 PASS。

- [x] **Step 5: 提交交互功能**

```powershell
git add -- one-class-operations-guide.html tests/operations-guide.test.mjs
git commit -m "feat: add guide navigation and checklist"
```

### Task 4: 浏览器响应式与交付验证

**Files:**
- Modify: `one-class-operations-guide.html`（仅在验证发现问题时）
- Test: `tests/operations-guide.test.mjs`

- [x] **Step 1: 在桌面视口验证**

用真实浏览器以约 `1440x900` 打开本地 HTML，确认左侧导航固定、正文不遮挡、表格可读、章节高亮和全部展开/收起可用。

- [x] **Step 2: 在手机视口验证**

以约 `390x844` 验证顶部目录、按钮换行、表格横向滚动、长中文词语和清单标签均不溢出。

- [x] **Step 3: 验证交互与持久化**

勾选至少两个首月任务，刷新页面并确认勾选状态和完成比例保留；再恢复未勾选状态，避免交付文件在用户浏览器中带测试状态。

- [x] **Step 4: 验证打印**

触发打印预览，确认导航和互动按钮隐藏、所有章节展开、全年表格与90天计划未缺失。

- [x] **Step 5: 运行最终检查并提交**

Run: `node --test tests/operations-guide.test.mjs`

Expected: 全部 PASS，浏览器控制台无错误。

```powershell
git add -- one-class-operations-guide.html tests/operations-guide.test.mjs docs/superpowers/plans/2026-07-22-one-class-operations-guide-web.md
git commit -m "chore: verify operations guide delivery"
```
