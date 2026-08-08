# WAP/Pad 全模块逐页美化实施计划

> 版本：v1.2 · 2026-08-09  
> 仓库路径：`docs/wap-pad-beautify-plan.md`  
> 关联：`docs/wap-pad-redesign-proposal.md`、`docs/wap-pad-audit.md`、`docs/ui-list-page-pattern.md`、`docs/ui-detail-page-pattern.md`

## 执行规则（用户确认 · 必须遵守）

| 规则 | 说明 |
|------|------|
| **方案落库** | 本文件为唯一实施依据 |
| **全部用推荐** | 顺序与组件选型采用 Recommended |
| **自动执行到完** | 连续推进至 Batch 5；**中间不打断等验收** |
| **用户终验** | 全部做完后由用户统一验收 |
| **金标准** | 列表 `ClassRecordView`；详情 `ClassRecordDetailView` |
| **不破 PC** | ≥1200 不明显回退；不改业务 API/权限语义 |

---

## 进度总览（2026-08-09 自动执行完成）

| Batch | 内容 | 状态 |
|-------|------|------|
| **0.5** | 上课记录列表 + 点名详情（金标准） | ✅ |
| **0** | 全局工具类 `oc-app-*`（`style.css`） | ✅ |
| **1** | 教务：班级/课表/课程/老师 | ✅ |
| **2** | 线索 + 学员 | ✅ |
| **3** | 学情 + 报名 | ✅ |
| **4** | 财务 | ✅ |
| **5** | 用户/文案/模板/成长中心等 | ✅ |

**→ 请你在 WAP/Pad 真机或浏览器窄屏做终验。**

---

## 金标准交互语法

### 列表页

1. App 顶栏标题，不重复 PC `page-header`
2. 主操作：CTA 条（`.oc-app-cta`）或大按钮 ≥42px
3. 筛选：`CompactFilterBar` + `MobileFilterSheet`
4. 列表：`m-card` + chip（`.oc-meta-chips`）
5. 空态：`.oc-app-empty`
6. 加载：`ListLoadStatus`
7. 新建/编辑：`useResponsiveSurface` → AppSheet / Dialog
8. `@media (max-width: 1199px)` 去白大壳

### 详情 / 表单

1. `oc-page-shell` + Hero
2. App 卡片 / PC 表格
3. `MobileActionBar` 主操作
4. 长编辑 AppSheet；短确认 Dialog
5. 危险操作降权

### 全局工具类（Batch 0 · `frontend/src/style.css`）

- `.oc-app-cta` / `__ico` / `__copy` / `__go`
- `.oc-meta-chips` / `.oc-meta-chip`（含 tone）
- `.oc-app-empty`
- `.oc-segment-tabs`
- `.oc-stepper` 系列

---

## Batch 明细与落点

### Batch 0.5 ✅ 点名金标准

- `ClassRecordView.vue`、`ClassRecordDetailView.vue`

### Batch 0 ✅ 共享样式

- `frontend/src/style.css` 工具类段落

### Batch 1 ✅ 教务

- `ClassListView` / `ClassDetailView`（CTA、Sheet、MobileActionBar）
- `CourseListView` / `CourseFormView`
- `TeacherListView`
- `ScheduleView`（分段视图）/ `ScheduleLessonDetailDrawer`（footer 去点名、加学员 Sheet）

### Batch 2 ✅ 线索 + 学员

- `LeadListView` / `LeadDetailView`
- `StudentListView` / `StudentDetailView`

### Batch 3 ✅ 学情 + 报名

- `LearningListView` / `LearningNewView`
- `EnrollmentListView` / `EnrollmentView`

### Batch 4 ✅ 财务

- `OrderListView` / `OrderDetailView`
- `TransactionListView`
- `ConsumptionListView` / `RechargeView`
- `IncomeReportView`

### Batch 5 ✅ 内容与管理

- `UserListView`：创建/重置/揭示/授权 → `useResponsiveSurface`
- `CopyDetailView` / `TemplateDetailView`：`MobileActionBar`
- `KnowledgeView`：编辑 Dialog → surface
- 素材/海报列表此前已有卡片与空态；上传 PC 仍 Dialog、App 走 `/upload`（既有设计）

---

## 终验清单（请你勾）

- [ ] 手机 390：主路径无横向溢出，主按钮可点
- [ ] Pad 竖/横：Sheet 方向正确，卡片密度可接受
- [ ] 点名详情：折叠完整课次资料、仅计薪可改、步进器
- [ ] 线索/学员：列表筛选 + 详情底栏
- [ ] 报名记录：卡片列表 + 办理步骤
- [ ] 财务：订单金额 Hero、收支 CompactFilterBar
- [ ] 用户：App 新建/授权为底部 Sheet
- [ ] PC ≥1200：表格/原布局无明显回退

---

## 已知轻微 gap（非阻塞）

- 部分列表 CTA 未 100% 复用 `.oc-app-cta` 结构，但触控与视觉已对齐米金
- 学员详情课包卡上部分 PC 专属操作（如改有效期）仍偏桌面入口
- 素材列表「上传」在 App 跳转全页 `/upload`，不在列表内弹 Sheet（产品既有路径）
- Dashboard / Login / Office 仅依赖全局壳层，未做深度重写
