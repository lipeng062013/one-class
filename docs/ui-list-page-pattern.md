# 嘉壹启航 · 业务列表页 UI 模式（给学生信息列表为模板）

> 对 AI 说：**「按 docs/ui-list-page-pattern.md 做列表页」** 即可对齐本站风格。  
> **标准模板**：`frontend/src/views/students/StudentListView.vue`  
> **全局样式**：`frontend/src/style.css`（`.pc-filters` / `.pc-table-card` / `.pager-bar.pc-pager` / `.pc-avatar` 等）  
> **详情页 / 内容宽度**：`docs/ui-detail-page-pattern.md`（业务页满宽；仅工作台限宽）

---

## 0. 内容宽度（列表 vs 详情）

| 页面类型 | 宽度策略 |
|----------|----------|
| **列表页**（表格式） | 一般**不**加 `.oc-page-shell`，表格吃满 `el-main` 主区 |
| **详情 / 上传 / 生成等** | 根节点 `class="… oc-page-shell"`，**吃满主区**（不限宽） |
| **工作台** | `class="dashboard oc-page-shell"`，限宽 **1680px**（≥1720 时 **1760px**） |

CSS 变量（`style.css` `:root`，**仅工作台**使用）：

- `--oc-content-max: 1680px`
- `--oc-content-max-wide: 1760px`

新做详情页请读 **`docs/ui-detail-page-pattern.md`**，不要在 scoped 里再写 `max-width: 720/1280px` 等私货。

---

## 0.0 wap/pad：从详情返回列表定位（必做）

> 用户**从本模块详情返回**时，应回到离开时的滚动位置与已展开条数。  
> **侧栏切换到其它业务页时禁止恢复**，否则会串页错位。

| 项 | 说明 |
|----|------|
| 组合式 | `frontend/src/composables/useListScrollRestore.ts` |
| 无限滚动 | `useInfiniteScroll` 的 `ensureVisible(n)` |
| 滚动容器 | `.layout .main`（AppLayout）或 `.mobile-shell .body` |

**规则：**

| 导航 | 行为 |
|------|------|
| 列表 → **本模块详情**（如 `/copies/12`） | **保存**滚动 + 可见条数 |
| 详情 → 列表 | **恢复**后清除快照 |
| 列表 → 其它页（工作台 / 另一列表等） | **清除**快照，不保存 |
| 查询 / 重置 | `clearSnapshot()`，回顶 |

**禁止**在 `onBeforeUnmount` 里再存一次（此时 `.main` 可能已是详情滚动，会把正确快照覆盖成 0）。

**接入清单：**

1. `useListScrollRestore('业务key', { visibleCount, enabled: isCompact })`，并在 `DETAIL_MATCHERS` 登记详情路径
2. `load()`：有快照则 `ensureVisible`，否则 `resetInfinite`；结束后 `void restoreScroll()`
3. 查询 / 重置：`clearSnapshot()`

已接入：素材 / 文案 / 海报 / 线索 / 学生 / 用户 / 成长中心 / 模板 / 老师端学生列表。  
其中海报 / 线索 / 用户 / 成长中心无独立详情匹配时，离开一律清快照（不误恢复）。

---

## 0.1 已对齐的列表页（本规范主体）

| 页面 | 路径 | 分页 | 首字头像 `pc-avatar` |
|------|------|------|----------------------|
| 学生信息（模板） | `students/StudentListView.vue` | ✅ | ✅ 人物 |
| 线索管理 | `leads/LeadListView.vue` | ✅ | ✅ 人物 |
| 用户管理 | `users/UserListView.vue` | ✅ | ✅ 人物 |
| 素材管理 | `materials/MaterialListView.vue` | ✅ | ❌ 内容 |
| 文案列表 | `copies/CopyListView.vue` | ✅ | ❌ 内容 |
| 海报列表 | `posters/PosterListView.vue` | ✅ | ❌ 内容（用缩略图） |
| 模板管理 | `templates/TemplateViews.vue` | ✅ | ❌ 内容 |
| 成长中心（话术/异议/禁用词） | `knowledge/KnowledgeView.vue` | ✅ | ❌ 内容 |

**规则：只有「人」相关列表用首字头像；素材/文案/海报/模板/成长中心等用 `pc-title-text` 纯标题，禁止 `pc-avatar`。**

---

## 1. 设计令牌（米金轻奢）

| Token | 用途 | 值 |
|-------|------|-----|
| `--oc-page` | 页面底 | `#faf8f3` |
| `--oc-card` | 卡片底 | `#fffdf8` |
| `--oc-border` | 边框 | `#e8e0d0` |
| `--oc-ink` | 主文字 | `#44403c` |
| `--oc-muted` | 次要文字 | `#78716c` |
| `--oc-primary` | 主色（琥珀金） | `#a16207` |
| `--oc-primary-hover` | 主色悬停 | `#86530a` |
| 表头底 | PC 表格 | `#f5f0e6` |
| 行悬停 | 表格 | `#faf6ee` |

---

## 2. 页面骨架（与学生信息一致）

```
┌ page-toolbar ─────────────────────────────────┐
│  el-page-header（短标题+返回）   [操作按钮组]   │
└───────────────────────────────────────────────┘
┌ pc-filters 筛选卡 ────────────────────────────┐
│  左：筛选条件 +「N 项生效」                      │
│  右：摘要胶囊「业务名 · 共 N 条 · 已选 N」        │
│  表单项：下拉/输入 + 查询/重置                   │
└───────────────────────────────────────────────┘
┌ pc-table-card ────────────────────────────────┐
│  （可选）pc-selection-bar 批量条                │
│  el-table stripe + 米金表头                     │
└───────────────────────────────────────────────┘
┌ pager-bar pc-pager ───────────────────────────┐
│  [首页 plain]  el-pagination  [末页 plain]      │
└───────────────────────────────────────────────┘
```

### 2.1 顶栏

- 全局 `.page-toolbar`
- 主按钮：`class="tb-btn tb-btn--primary"` + `type="primary"` + 图标（`Plus`）
- **禁止**在标题正下方堆长说明；统计放筛选卡右上摘要胶囊

### 2.2 筛选卡（PC）

```html
<el-card class="filters pc-filters" shadow="never">
  <div class="pc-filters-head">
    <div class="pc-filters-head-main">
      <span class="pc-filters-title">筛选条件</span>
      <span v-if="activeCount" class="pc-filters-badge">{{ activeCount }} 项生效</span>
    </div>
    <div class="pc-list-summary">
      <span class="pc-list-summary__label">业务名</span>
      <span>共 <strong>{{ total }}</strong> 条</span>
      <span v-if="selected">已选 <strong>{{ selected }}</strong></span>
    </div>
  </div>
  <el-form class="filter-form pc-filter-form" :inline="true">…</el-form>
</el-card>
```

样式已在全局 `style.css`（渐变底、圆角 12、摘要胶囊）。

### 2.3 表格卡（PC）

```html
<el-card class="pc-table-card" shadow="never" v-loading="loading">
  <div v-if="selectedCount" class="pc-selection-bar">…</div>
  <div class="table-scroll">
    <el-table
      stripe
      :header-cell-style="pcHeaderStyle"
      :data="pagedRows"
    >…</el-table>
  </div>
</el-card>
```

```ts
const pcHeaderStyle = {
  background: '#f5f0e6',
  color: '#44403c',
  fontWeight: '600',
  borderBottomColor: '#e8e0d0',
}
```

- 标题列：
  - **人物列表**：`.pc-name-cell` + `.pc-avatar` + `.pc-name-text`
  - **内容列表**：仅 `.pc-title-text`（**不要** avatar）
- 状态：`el-tag` + `effect="plain" round`
- 操作列：`.pc-ops` 右对齐 link 按钮

### 2.4 PC 底部分页（必须）

> 全局：`.pager-bar.pc-pager`（`style.css`）  
> **凡有列表数据的业务页，PC 端都必须有分页**；无数据不渲染分页条。  
> **位置**：PC 分页在**页面底部**（内容少时 flex 沉底，内容多时 sticky 贴主区底）。  
> wap/pad：卡片 + `useInfiniteScroll`，**不要**底部分页。

```html
<div v-if="total > 0" class="pager-bar pc-pager">
  <el-button size="small" plain :disabled="page <= 1" @click="goFirstPage">首页</el-button>
  <el-pagination
    v-model:current-page="page"
    v-model:page-size="pageSize"
    :page-sizes="[10, 20, 50, 100]"
    :total="total"
    :pager-count="5"
    background
    layout="total, sizes, prev, pager, next, jumper"
  />
  <el-button size="small" plain :disabled="page >= totalPages" @click="goLastPage">末页</el-button>
</div>
```

| 项 | 要求 |
|----|------|
| class | **必须** `pager-bar` + `pc-pager` |
| 首页/末页 | `size="small" plain` |
| PAGE_SIZES | `[10, 20, 50, 100]`，默认 20 |
| layout | `total, sizes, prev, pager, next, jumper` |
| 视觉 | 米金卡片条：圆角 12、边框、`#fffdf8` 底 |

### 2.5 服务端分页（推荐，素材/学生已落地）

> **禁止**再一次拉全量后在前端 `slice`。接口返回 `{ items, total, page, page_size }`。

```ts
// GET /xxx?page=1&page_size=20&…filters
// data: { items, total, page, page_size }

const PAGE_SIZES = [10, 20, 50, 100]
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const rows = ref<T[]>([]) // PC：当前页；wap：累计已加载

// PC：翻页 / 改 pageSize → 重新请求，替换 rows
// wap/pad：触底 page++ → 请求下一页，append 到 rows；筛选变化 page=1 清空重载
```

筛选变化后 `page = 1` 并重新请求；`sessionStorage` 可记忆 page/pageSize/filters。  
参考：`MaterialListView.vue`、`StudentListView.vue`；API：`api/paging.ts`。

---

## 3. wap / pad（≤991px）

### 3.1 布局

优先 **CSS 双布局**（避免 `isCompact` 首帧误判）：

```css
.xxx-pc { display: none; }
.xxx-m  { display: block; }
@media (min-width: 992px) {
  .xxx-pc { display: block; }
  .xxx-m  { display: none !important; }
}
```

`COMPACT_MAX = 991`（`useBreakpoint.ts`）。

### 3.2 矮筛选

搜索行 + 1～2 个下拉 +「更多」折叠；下拉 `teleported` + `strategy: 'fixed'` + 高 z-index popper。

### 3.3 卡片 + 无限滚动

- 圆角 12–14、边框 2px `--oc-border`
- `useInfiniteScroll`，chunk=10
- 底部哨兵文案：加载中 / 上拉更多 / 已全部 N 条

### 3.4 图片类（海报）

- 每行 ≥2 列；预览固定高度 + `object-fit: contain`
- 不用 `pc-avatar`

---

## 4. 首字头像使用边界

| 列表类型 | 示例 | PC 标题列 |
|----------|------|-----------|
| 人物 | 学生、线索、用户 | ✅ `pc-avatar` + 姓名 |
| 内容/作品 | 素材、文案、海报、模板、成长中心 | ❌ 只用 `pc-title-text` |

---

## 5. 给 AI 的指令模板

```text
请按 docs/ui-list-page-pattern.md（以学生信息 StudentListView 为模板）实现/改版「XXX列表」：
1. PC：page-toolbar + pc-filters（摘要胶囊）+ pc-table-card 米金表 + pager-bar pc-pager
2. 分页：PAGE_SIZES=[10,20,50,100]，首页/末页 plain，layout=total,sizes,prev,pager,next,jumper
3. 若是人物列表：姓名列用 pc-avatar；若是内容列表：禁止 pc-avatar，用 pc-title-text
4. wap/pad：CSS 双布局；矮筛选；卡片+useInfiniteScroll（不要底部分页）
5. 统计放筛选卡摘要，不要堆在标题下
6. 共用样式优先用 frontend/src/style.css 已有 class
```

---

## 6. 反模式（不要做）

1. 标题下挂长灰字说明/统计  
2. 内容类列表加 `pc-avatar`  
3. PC 无分页或「裸分页」（无 `pc-pager` 卡片条、无首页/末页）  
4. 窄列 `el-select` 挤出 `..`  
5. wap 默认展开全部筛选占半屏  
6. 仅靠首帧 `isCompact` 切布局导致闪一下  
7. 图片列表 `cover` 乱裁 + 无限缩小  
