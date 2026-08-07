# WAP / Pad Responsive Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立统一的 WAP/Pad 响应式交互能力，并在三类代表性列表中验证无横向拖动的移动操作模式。

**Architecture:** 保留现有 Vue 页面、API 和权限逻辑，通过共享断点、Sheet、底部操作栏及移动卡片切换展示。PC 路径保持原样，紧凑设备使用现有列表数据和事件处理器，避免复制业务状态。

**Tech Stack:** Vue 3、TypeScript、Element Plus、Vite、CSS Media Queries、Playwright

---

### Task 1: Responsive foundation

**Files:**
- Modify: `frontend/src/composables/useBreakpoint.ts`
- Modify: `frontend/src/style.css`
- Create: `frontend/src/components/MobileActionBar.vue`
- Create: `frontend/src/components/MobileFilterSheet.vue`

- [x] 扩展断点状态并保持现有 `isMobile`、`isCompact` API 兼容。
- [x] 增加 44px 触控目标、安全区域、紧凑布局和防溢出全局规则。
- [x] 实现底部固定操作栏，支持主操作、次操作和安全区域。
- [x] 实现筛选 Sheet，支持标题、已选数量、重置、确认和自定义筛选内容。
- [x] 运行 `npm run typecheck`，预期退出码为 0。

### Task 2: Student list validation

**Files:**
- Modify: `frontend/src/views/students/StudentListView.vue`

- [x] 检查 360px 卡片字段、操作入口、展开内容和空状态。
- [x] Pad 竖屏使用双列卡片，WAP 使用单列卡片。
- [x] 把复杂筛选接入统一 Sheet，并保留筛选与滚动恢复。
- [x] 验证卡片复选、批量删除、批量转交和取消选择均保留触控入口。

### Task 3: Lead list validation

**Files:**
- Modify: `frontend/src/views/leads/LeadListView.vue`

- [x] 将筛选和移动操作容器统一到公共组件。
- [x] 确保状态、负责人、联系方式和最近跟进无需横向拖动即可查看。
- [x] 保持移动卡片单一“详情 / 写跟进”主操作，避免低频按钮堆叠。
- [x] 验证移动卡片与 PC 共用原业务事件和权限路径。

### Task 4: Finance transaction validation

**Files:**
- Modify: `frontend/src/views/finance/TransactionListView.vue`

- [x] WAP 使用金额优先卡片，展示时间、类型、对象和状态。
- [x] Pad 竖屏使用双列卡片，横屏使用精简表格。
- [x] 将筛选放入公共 Sheet，并确保筛选控件可触控。
- [x] 明确金额正负、退款和异常状态的视觉区别。

### Task 5: Verification

**Files:**
- Modify only when verification identifies a scoped defect.

- [x] 运行 `npm run typecheck`，预期退出码为 0。
- [x] 运行 `npm run build`，预期退出码为 0。
- [x] 启动 Vite 开发服务器。
- [x] 使用 Playwright 检查 360x800、390x844、820x1180、1180x820 和 1440x900。
- [x] 确认主路由无页面级横向滚动、无遮挡、无控制台错误，并检查代表性截图。

### Task 6: Academic and enrollment interactions

**Files:**
- Modify: `frontend/src/views/enrollments/EnrollmentView.vue`
- Modify: `frontend/src/views/academic/CourseFormView.vue`
- Modify: `frontend/src/views/academic/ScheduleView.vue`

- [x] 报名购买项目和业绩归属在 WAP/Pad 使用可编辑卡片，PC 保留表格。
- [x] 课程定价在紧凑设备使用纵向字段组，避免单行宽表。
- [x] 课表四种视图在紧凑设备使用完整可达的选择器。
- [x] 长表单主操作固定在视口底部并适配安全区域。
- [x] 使用真实学员和课程数据验证课时步进器、折扣与归属编辑状态。

### Task 7: Finance report cards

**Files:**
- Modify: `frontend/src/views/finance/IncomeReportView.vue`

- [x] 支付方式汇总在紧凑设备改为摘要卡片。
- [x] 课程课消汇总在紧凑设备改为摘要卡片。
- [x] 课程待消与学员待消明细在紧凑设备改为风险卡片。
- [x] PC 保留原有对比表格。

### Task 8: Full route audit

**Files:**
- Modify only when the audit identifies a scoped defect.

- [x] 巡检报名、教务、财务、素材、文案、海报、知识库、模板、用户和上传主路由。
- [x] 巡检文案生成、海报生成、AI 生图、学情新建和综合办公页面。
- [x] 在 390px 与 820px 下确认主路由无页面级横向滚动。
