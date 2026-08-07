# WAP / Pad Responsive Optimization Design

## Goal

在保留现有 PC 功能和业务逻辑的前提下，为 WAP 与 Pad 提供完整、可触控、无非预期横向滚动的操作体验，并建立可复用的响应式组件规范。

## Device Strategy

- WAP：视口宽度不超过 767px，使用单列、卡片列表、底部 Sheet 和固定操作栏。
- Pad：768px 至 991px。竖屏优先卡片或双列卡片，横屏优先精简表格或双栏详情。
- PC：992px 及以上，保留现有桌面布局。
- 992px 至 1279px 的复杂表格进入窄桌面模式，隐藏低优先级列，避免横向拖动。

## Interaction Rules

1. 普通业务列表在紧凑设备上转换为卡片，不把横向滚动作为默认方案。
2. 对比型表格仅保留核心列，并固定首列或操作入口。
3. 报表提供摘要与明细入口，只有明细模式允许明确提示的横向滚动。
4. 复杂筛选在 WAP/Pad 竖屏进入底部 Sheet，显示已选数量并提供重置与确认。
5. 弹窗在 WAP 使用全屏或底部 Sheet，Pad 使用受控宽度弹窗或侧边 Drawer。
6. 触控目标最小 44 x 44px，关键功能不依赖 hover。
7. 固定底部操作栏适配安全区域和软键盘，页面返回时恢复筛选与滚动状态。

## Shared Architecture

- 扩展 `useBreakpoint`，提供 mobile、pad、compact、pad portrait、pad landscape 和 narrow desktop 状态。
- 在全局样式中统一紧凑页面间距、触控尺寸、安全区域和 Element Plus 控件行为。
- 提供 `MobileFilterSheet`、`MobileActionBar` 和通用移动信息卡片结构。
- 业务页面继续复用当前 API、权限和状态管理，仅按断点切换展示与操作容器。

## Delivery Batches

### Batch 1: Foundation and Representative Lists

- 公共断点、触控样式和安全区。
- 学生列表：复杂资料型列表代表。
- 线索列表：筛选、批量操作和状态变更代表。
- 财务流水：金额与日期型表格代表。

### Batch 2: Academic and Enrollment

- 报名、班级、课程、教师、课表与课堂记录。

### Batch 3: Finance and Content

- 订单、充值、消费、收入报表、素材、文案、海报与知识库。

### Batch 4: Detail and Creation Flows

- 详情页、长表单、上传、生成流程与异常状态。

## Acceptance Criteria

- 360、375、390、430、768、820、1024 和 1180px 宽度下无非预期页面横向滚动。
- WAP 与 Pad 可以完成 PC 的核心业务操作，权限行为一致。
- 表格核心信息无需左右拖动即可查看和操作。
- 弹窗、菜单、固定操作栏和软键盘不互相遮挡。
- 横竖屏切换后数据、筛选、选择和弹窗状态保持正确。
- TypeScript 检查与生产构建通过，并对关键视口执行浏览器截图检查。

