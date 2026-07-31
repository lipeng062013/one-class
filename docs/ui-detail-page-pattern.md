# 嘉壹启航 · 业务详情页 UI 模式

> 对 AI 说：**「按 docs/ui-detail-page-pattern.md 做详情页」** 即可对齐本站风格。  
> **列表页规范**：`docs/ui-list-page-pattern.md`  
> **内容宽度全局类**：`frontend/src/style.css` → `.oc-page-shell`  
> **参考实现**：`frontend/src/views/copies/CopyDetailView.vue`、`templates/TemplateDetailView.vue`、`materials/MaterialDetailView.vue`、`DashboardView.vue`（工作台同宽）

---

## 0. 内容宽度（与工作台强制一致）

| 项 | 值 | 说明 |
|----|-----|------|
| CSS 变量 | `--oc-content-max: 1680px` | 默认内容最大宽度 |
| 超宽变量 | `--oc-content-max-wide: 1760px` | 视口 ≥1720px 时略放宽 |
| 全局类 | **`.oc-page-shell`** | 根节点统一居中 + max-width |

### 0.1 新详情页必须这样做

```html
<div class="xxx-detail oc-page-shell" v-loading="loading">
  <!-- 顶栏 / Hero / 主体 … -->
</div>
```

```css
/* scoped 里只写页面自身间距，禁止再写 max-width / margin: 0 auto */
.xxx-detail {
  padding-bottom: 12px; /* 或 16px */
}
```

**禁止**：在 scoped 里写 `max-width: 1280px` / `1120px` 等「私货宽度」。  
**禁止**：详情页比工作台更窄或更宽（除非全屏沉浸页，如需例外须在文档登记）。

### 0.2 已对齐的页面

| 页面 | 根 class | 状态 |
|------|----------|------|
| 工作台 | `dashboard oc-page-shell` | ✅ 基准 |
| 文案详情 | `copy-detail oc-page-shell` | ✅ |
| 素材详情 | `mat-detail oc-page-shell` | ✅ |
| 文案/海报模板详情 | `tpl-detail oc-page-shell` | ✅ |
| 学生详情 | `student-detail-page oc-page-shell` | ✅ |
| GPT 生图 | `page oc-page-shell` | ✅ 同宽外壳 |

列表页一般**不**锁 `.oc-page-shell`（表格宜吃满主区），与详情/工作台的「内容型」页面区分。

---

## 1. 设计令牌

与列表页相同，见 `ui-list-page-pattern.md` §1。常用：

| Token | 用途 |
|-------|------|
| `--oc-page` / `--oc-card` | 页底 / 卡片底 |
| `--oc-border` / `--oc-ink` / `--oc-muted` | 边框与文字 |
| `--oc-primary` | 琥珀金主色 |
| `--oc-content-max` | **内容最大宽度** |

---

## 2. 页面骨架

```
┌ oc-page-shell ────────────────────────────────────┐  max 1680 / 1760
│  page-toolbar：返回 + 标题 | 主操作（复制/编辑/生成） │
│  hero：标题、标签、可选统计 pill                     │
│  （可选）告警条：禁用词 / 状态提示                    │
│  detail-grid：                                      │
│    ┌ content-panel ──┐  ┌ side-col ─────────────┐  │
│    │ 正文 / 编辑区    │  │ 元信息 / 变量说明      │  │
│    │                  │  │ 危险操作               │  │
│    └──────────────────┘  └───────────────────────┘  │
└─────────────────────────────────────────────────────┘
```

### 2.1 顶栏

- 使用全局 `.page-toolbar`
- `el-page-header` + `usePageBack('/父列表路径')`
- 右侧：主操作（复制全文、编辑、用此模板生成…）

### 2.2 Hero

- 米金渐变头图（与素材/文案详情一致）
- 展示：业务 ID、标题、状态/场景 Tag、时间

### 2.3 主体栅格

```css
.detail-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 14px;
}
@media (min-width: 992px) {
  .detail-grid {
    /* 左主右辅，比例可微调，勿改外层 oc-page-shell 宽度 */
    grid-template-columns: minmax(0, 1.3fr) minmax(280px, 0.8fr);
    gap: 16px;
  }
}
```

- **左**：正文、可编辑表单  
- **右**：元数据、说明、删除等；宽屏可 `position: sticky; top: 12px`

### 2.4 面板

```css
.panel {
  border: 1px solid var(--oc-border);
  border-radius: 14px;
  background: var(--oc-card);
  padding: 16px 18px;
  box-shadow: 0 4px 14px rgba(41, 37, 36, 0.03);
}
```

---

## 3. 路由与 API

| 类型 | 路由示例 | 列表回跳 |
|------|----------|----------|
| 资源详情 | `/copies/:id`、`/materials/:id` | `/copies`、`/materials` |
| 子类详情 | `/templates/copies/:id`、`/templates/posters/:id` | `/templates` |

- 后端提供 `GET /resource/{id}`
- 前端 `getXxx(id)` + 列表「详情」按钮 / 标题可点

侧栏高亮：在 `AppLayout` 的 `active` 中对 `/templates`、`/copies` 等使用 `startsWith`。

---

## 4. 新详情页检查清单

- [ ] 根节点带 **`oc-page-shell`**
- [ ] scoped **无**私自 `max-width` 与工作台冲突
- [ ] `usePageBack` 回列表
- [ ] PC：主从两列；WAP：单列
- [ ] 主操作在 toolbar；删除在侧栏危险区
- [ ] 在本文 §0.2 登记页面
- [ ] 若有列表入口：标题可点 +「详情」按钮（与文案/模板列表一致）

---

## 5. 与列表规范的关系

| 文档 | 管什么 |
|------|--------|
| `ui-list-page-pattern.md` | 筛选卡、表格、分页、移动卡片 |
| **本文** | 详情骨架、**内容宽度**、Hero、主从栅格 |

两者共用米金 token；**内容型页面宽度只认 `.oc-page-shell`**。
