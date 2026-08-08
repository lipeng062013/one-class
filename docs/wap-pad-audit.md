# 嘉壹启航 WAP / Pad 页面与弹层审查报告

版本：v1.0 · 2026-08-08  
测试地址：`http://localhost:5173`（Vite 代理后端实际为 `127.0.0.1:8000`）  
测试账号：使用用户提供的本地账号登录；报告不记录密码。

## 1. 审查范围与结论

本轮以已登录状态检查了项目中可访问的全部正式业务路由，并按三种触控设备尺寸分别截图：

| 模式 | 视口 | 页面记录 |
|---|---:|---:|
| 手机 WAP | 390 × 844 | 41 |
| Pad 竖屏 | 834 × 1112 | 41 |
| Pad 横屏 | 1180 × 820 | 41 |

共 41 个页面、123 条尺寸记录。页面级横向溢出检查结果为 0；`body`、`content`、`doc`、`main` 的 `scrollWidth - clientWidth` 均为 0。页面截图、弹窗截图和审查 JSON 全部保存在 [docs/wap-pad-screenshots](/E:/one-class/docs/wap-pad-screenshots) 中：原有弹窗/弹层审查截图 192 张，最终三种视口页面截图 123 张（WAP/Pad 交付合计 315 张 PNG，另附 1 张 PC 回归截图）。

主要结论：

- 业务信息和 PC 端色调保持一致，但移动端不能继续采用“PC 表格缩小版”。当前已将高频列表改成卡片/摘要，将课表改成按日期分组的 agenda。
- 手机采用顶栏返回 + 底部主导航；Pad 竖屏保留触控卡片，Pad 横屏使用左侧图标轨和右侧 Sheet/双栏空间。
- 所有详情、编辑、生成、上传页面都有安全返回目标；直接打开深层链接时也不会出现空白返回按钮。
- 筛选使用底部/右侧 Sheet，长表单使用全屏或高占比面板，短确认保留 Dialog；弹层底部操作不会再被底部导航遮挡。
- 最终三种模式无未命名图标按钮；学情图片上传控件已补齐实际触发节点的无障碍名称。

## 2. 页面与功能清单

下表截图顺序固定为：手机、Pad 竖屏、Pad 横屏。手机截图文件名中 `home` 是列表/工作区页面前缀，详情/编辑页使用路由片段直接命名。

表格中的 `audit-*` 文件保留了逐页审查记录；完成美化后的最终版本统一放在 [final-2026-08-08](/E:/one-class/docs/wap-pad-screenshots/final-2026-08-08) 目录，避免把基线截图和最终截图混淆。

| 模块 | 路由 | 页面功能 | 手机 | Pad 竖屏 | Pad 横屏 |
|---|---|---|---|---|---|
| 工作台 | `/` | 今日概览、待办、快捷入口、最近业务 | [截图](/E:/one-class/docs/wap-pad-screenshots/audit-phone-home.png) | [截图](/E:/one-class/docs/wap-pad-screenshots/audit-pad-portrait-home.png) | [截图](/E:/one-class/docs/wap-pad-screenshots/audit-pad-landscape-home.png) |
| 素材 | `/upload` | 上传图片、填写场景/年级/科目、授权状态 | [截图](/E:/one-class/docs/wap-pad-screenshots/audit-phone-homeupload.png) | [截图](/E:/one-class/docs/wap-pad-screenshots/audit-pad-portrait-upload.png) | [截图](/E:/one-class/docs/wap-pad-screenshots/audit-pad-landscape-upload.png) |
| 素材 | `/materials` | 素材列表、搜索/筛选、展开摘要、批量操作 | [截图](/E:/one-class/docs/wap-pad-screenshots/audit-phone-homematerials.png) | [截图](/E:/one-class/docs/wap-pad-screenshots/audit-pad-portrait-materials.png) | [截图](/E:/one-class/docs/wap-pad-screenshots/audit-pad-landscape-materials.png) |
| 素材 | `/materials/5` | 素材详情、预览、授权/标签、生成文案 | [截图](/E:/one-class/docs/wap-pad-screenshots/audit-phone-materials-5.png) | [截图](/E:/one-class/docs/wap-pad-screenshots/audit-pad-portrait-materials-5.png) | [截图](/E:/one-class/docs/wap-pad-screenshots/audit-pad-landscape-materials-5.png) |
| 文案 | `/copies` | 文案列表、选择/删除、进入生成 | [截图](/E:/one-class/docs/wap-pad-screenshots/audit-phone-homecopies.png) | [截图](/E:/one-class/docs/wap-pad-screenshots/audit-pad-portrait-copies.png) | [截图](/E:/one-class/docs/wap-pad-screenshots/audit-pad-landscape-copies.png) |
| 文案 | `/copies/generate` | 选择素材/模板、生成、对照和保存 | [截图](/E:/one-class/docs/wap-pad-screenshots/audit-phone-homecopies-generate.png) | [截图](/E:/one-class/docs/wap-pad-screenshots/audit-pad-portrait-copies-generate.png) | [截图](/E:/one-class/docs/wap-pad-screenshots/audit-pad-landscape-copies-generate.png) |
| 文案 | `/copies/5` | 文案详情、复制全文、编辑、版本查看 | [截图](/E:/one-class/docs/wap-pad-screenshots/audit-phone-copies-5.png) | [截图](/E:/one-class/docs/wap-pad-screenshots/audit-pad-portrait-copies-5.png) | [截图](/E:/one-class/docs/wap-pad-screenshots/audit-pad-landscape-copies-5.png) |
| 海报 | `/posters` | 海报列表、预览、下载、删除 | [截图](/E:/one-class/docs/wap-pad-screenshots/audit-phone-homeposters.png) | [截图](/E:/one-class/docs/wap-pad-screenshots/audit-pad-portrait-posters.png) | [截图](/E:/one-class/docs/wap-pad-screenshots/audit-pad-landscape-posters.png) |
| 海报 | `/posters/generate` | 模板/文案选择、实时预览、生成 | [截图](/E:/one-class/docs/wap-pad-screenshots/audit-phone-homeposters-generate.png) | [截图](/E:/one-class/docs/wap-pad-screenshots/audit-pad-portrait-posters-generate.png) | [截图](/E:/one-class/docs/wap-pad-screenshots/audit-pad-landscape-posters-generate.png) |
| AI | `/ai-image` | GPT 生图、提示词、参考图、结果预览 | [截图](/E:/one-class/docs/wap-pad-screenshots/audit-phone-homeai-image.png) | [截图](/E:/one-class/docs/wap-pad-screenshots/audit-pad-portrait-ai-image.png) | [截图](/E:/one-class/docs/wap-pad-screenshots/audit-pad-landscape-ai-image.png) |
| 线索 | `/leads` | 搜索/筛选、导入、新建、跟进、协作 | [截图](/E:/one-class/docs/wap-pad-screenshots/audit-phone-homeleads.png) | [截图](/E:/one-class/docs/wap-pad-screenshots/audit-pad-portrait-leads.png) | [截图](/E:/one-class/docs/wap-pad-screenshots/audit-pad-landscape-leads.png) |
| 线索 | `/leads/30` | 线索资料、跟进时间线、编辑、协作人 | [截图](/E:/one-class/docs/wap-pad-screenshots/audit-phone-leads-30.png) | [截图](/E:/one-class/docs/wap-pad-screenshots/audit-pad-portrait-leads-30.png) | [截图](/E:/one-class/docs/wap-pad-screenshots/audit-pad-landscape-leads-30.png) |
| 学员 | `/students` | 学员列表、搜索/筛选、选择和批量管理 | [截图](/E:/one-class/docs/wap-pad-screenshots/audit-phone-homestudents.png) | [截图](/E:/one-class/docs/wap-pad-screenshots/audit-pad-portrait-students.png) | [截图](/E:/one-class/docs/wap-pad-screenshots/audit-pad-landscape-students.png) |
| 学员 | `/students/40` | 学生档案、课程/课消/上课记录、学情时间线 | [截图](/E:/one-class/docs/wap-pad-screenshots/audit-phone-students-40.png) | [截图](/E:/one-class/docs/wap-pad-screenshots/audit-pad-portrait-students-40.png) | [截图](/E:/one-class/docs/wap-pad-screenshots/audit-pad-landscape-students-40.png) |
| 报名 | `/enrollments` | 选择学员、建档、报名/续费、购买课时、建单 | [截图](/E:/one-class/docs/wap-pad-screenshots/audit-phone-homeenrollments.png) | [截图](/E:/one-class/docs/wap-pad-screenshots/audit-pad-portrait-enrollments.png) | [截图](/E:/one-class/docs/wap-pad-screenshots/audit-pad-landscape-enrollments.png) |
| 报名 | `/enrollments/records` | 报名/续费记录筛选、订单入口 | [截图](/E:/one-class/docs/wap-pad-screenshots/audit-phone-homeenrollments-records.png) | [截图](/E:/one-class/docs/wap-pad-screenshots/audit-pad-portrait-enrollments-records.png) | [截图](/E:/one-class/docs/wap-pad-screenshots/audit-pad-landscape-enrollments-records.png) |
| 学情 | `/learning` | 我的学情/全部学情、状态筛选、展开摘要 | [截图](/E:/one-class/docs/wap-pad-screenshots/audit-phone-homelearning.png) | [截图](/E:/one-class/docs/wap-pad-screenshots/audit-pad-portrait-learning.png) | [截图](/E:/one-class/docs/wap-pad-screenshots/audit-pad-landscape-learning.png) |
| 学情 | `/learning/new` | 选择学生、上课状态、学情内容、图片上传 | [截图](/E:/one-class/docs/wap-pad-screenshots/audit-phone-homelearning-new.png) | [截图](/E:/one-class/docs/wap-pad-screenshots/audit-pad-portrait-learning-new.png) | [截图](/E:/one-class/docs/wap-pad-screenshots/audit-pad-landscape-learning-new.png) |
| 教务 | `/academic/classes` | 班课/一对一、筛选、批量结业/删除、新建 | [截图](/E:/one-class/docs/wap-pad-screenshots/audit-phone-homeacademic-classes.png) | [截图](/E:/one-class/docs/wap-pad-screenshots/audit-pad-portrait-academic-classes.png) | [截图](/E:/one-class/docs/wap-pad-screenshots/audit-pad-landscape-academic-classes.png) |
| 教务 | `/academic/classes/5` | 班级信息、课程、老师、学员、排课、点名 | [截图](/E:/one-class/docs/wap-pad-screenshots/audit-phone-academic-classes-5.png) | [截图](/E:/one-class/docs/wap-pad-screenshots/audit-pad-portrait-academic-classes-5.png) | [截图](/E:/one-class/docs/wap-pad-screenshots/audit-pad-landscape-academic-classes-5.png) |
| 教务 | `/academic/schedule` | 日/周/月课表、筛选、排课、详情、点名、编辑/删除 | [截图](/E:/one-class/docs/wap-pad-screenshots/audit-phone-homeacademic-schedule.png) | [截图](/E:/one-class/docs/wap-pad-screenshots/audit-pad-portrait-academic-schedule.png) | [截图](/E:/one-class/docs/wap-pad-screenshots/audit-pad-landscape-academic-schedule.png) |
| 教务 | `/academic/class-records` | 点名记录、超时/缺课补课、导出、点名 | [截图](/E:/one-class/docs/wap-pad-screenshots/audit-phone-homeacademic-class-records.png) | [截图](/E:/one-class/docs/wap-pad-screenshots/audit-pad-portrait-academic-class-records.png) | [截图](/E:/one-class/docs/wap-pad-screenshots/audit-pad-landscape-academic-class-records.png) |
| 教务 | `/academic/class-records/6` | 点名详情、到课统计、编辑、撤销 | [截图](/E:/one-class/docs/wap-pad-screenshots/audit-phone-academic-class-records-6.png) | [截图](/E:/one-class/docs/wap-pad-screenshots/audit-pad-portrait-academic-class-records-6.png) | [截图](/E:/one-class/docs/wap-pad-screenshots/audit-pad-landscape-academic-class-records-6.png) |
| 教务 | `/academic/courses` | 课程列表、筛选、新建/编辑/删除 | [截图](/E:/one-class/docs/wap-pad-screenshots/audit-phone-homeacademic-courses.png) | [截图](/E:/one-class/docs/wap-pad-screenshots/audit-pad-portrait-academic-courses.png) | [截图](/E:/one-class/docs/wap-pad-screenshots/audit-pad-landscape-academic-courses.png) |
| 教务 | `/academic/courses/new` | 课程基础信息、收费、扣课规则、颜色 | [截图](/E:/one-class/docs/wap-pad-screenshots/audit-phone-homeacademic-courses-new.png) | [截图](/E:/one-class/docs/wap-pad-screenshots/audit-pad-portrait-academic-courses-new.png) | [截图](/E:/one-class/docs/wap-pad-screenshots/audit-pad-landscape-academic-courses-new.png) |
| 教务 | `/academic/courses/8/edit` | 编辑课程配置并保存 | [截图](/E:/one-class/docs/wap-pad-screenshots/audit-phone-academic-courses-8-edit.png) | [截图](/E:/one-class/docs/wap-pad-screenshots/audit-pad-portrait-academic-courses-8-edit.png) | [截图](/E:/one-class/docs/wap-pad-screenshots/audit-pad-landscape-academic-courses-8-edit.png) |
| 教务 | `/academic/teachers` | 老师、角色、在职状态、带班概览 | [截图](/E:/one-class/docs/wap-pad-screenshots/audit-phone-homeacademic-teachers.png) | [截图](/E:/one-class/docs/wap-pad-screenshots/audit-pad-portrait-academic-teachers.png) | [截图](/E:/one-class/docs/wap-pad-screenshots/audit-pad-landscape-academic-teachers.png) |
| 财务 | `/finance/orders` | 订单类型入口、订单列表、筛选 | [截图](/E:/one-class/docs/wap-pad-screenshots/audit-phone-homefinance-orders.png) | [截图](/E:/one-class/docs/wap-pad-screenshots/audit-pad-portrait-finance-orders.png) | [截图](/E:/one-class/docs/wap-pad-screenshots/audit-pad-landscape-finance-orders.png) |
| 财务 | `/finance/orders/5` | 订单详情、支付/课时信息、操作日志 | [截图](/E:/one-class/docs/wap-pad-screenshots/audit-phone-finance-orders-5.png) | [截图](/E:/one-class/docs/wap-pad-screenshots/audit-pad-portrait-finance-orders-5.png) | [截图](/E:/one-class/docs/wap-pad-screenshots/audit-pad-landscape-finance-orders-5.png) |
| 财务 | `/finance/transactions` | 收支明细、确认/作废、筛选和汇总 | [截图](/E:/one-class/docs/wap-pad-screenshots/audit-phone-homefinance-transactions.png) | [截图](/E:/one-class/docs/wap-pad-screenshots/audit-pad-portrait-finance-transactions.png) | [截图](/E:/one-class/docs/wap-pad-screenshots/audit-pad-landscape-finance-transactions.png) |
| 财务 | `/finance/consumption` | 课消记录、金额汇总、详情 | [截图](/E:/one-class/docs/wap-pad-screenshots/audit-phone-homefinance-consumption.png) | [截图](/E:/one-class/docs/wap-pad-screenshots/audit-pad-portrait-finance-consumption.png) | [截图](/E:/one-class/docs/wap-pad-screenshots/audit-pad-landscape-finance-consumption.png) |
| 财务 | `/finance/recharge` | 充值记录、余额、账户充值 | [截图](/E:/one-class/docs/wap-pad-screenshots/audit-phone-homefinance-recharge.png) | [截图](/E:/one-class/docs/wap-pad-screenshots/audit-pad-portrait-finance-recharge.png) | [截图](/E:/one-class/docs/wap-pad-screenshots/audit-pad-landscape-finance-recharge.png) |
| 财务 | `/finance/income-report` | 日期范围、确认收入/课时/待消报表 | [截图](/E:/one-class/docs/wap-pad-screenshots/audit-phone-homefinance-income-report.png) | [截图](/E:/one-class/docs/wap-pad-screenshots/audit-pad-portrait-finance-income-report.png) | [截图](/E:/one-class/docs/wap-pad-screenshots/audit-pad-landscape-finance-income-report.png) |
| 知识库 | `/knowledge/scripts` | 沟通话术 CRUD、启用状态 | [截图](/E:/one-class/docs/wap-pad-screenshots/audit-phone-homeknowledge-scripts.png) | [截图](/E:/one-class/docs/wap-pad-screenshots/audit-pad-portrait-knowledge-scripts.png) | [截图](/E:/one-class/docs/wap-pad-screenshots/audit-pad-landscape-knowledge-scripts.png) |
| 知识库 | `/knowledge/objections` | 异议处理 CRUD、启用状态 | [截图](/E:/one-class/docs/wap-pad-screenshots/audit-phone-homeknowledge-objections.png) | [截图](/E:/one-class/docs/wap-pad-screenshots/audit-pad-portrait-knowledge-objections.png) | [截图](/E:/one-class/docs/wap-pad-screenshots/audit-pad-landscape-knowledge-objections.png) |
| 知识库 | `/knowledge/banned` | 禁用词 CRUD、启用状态 | [截图](/E:/one-class/docs/wap-pad-screenshots/audit-phone-homeknowledge-banned.png) | [截图](/E:/one-class/docs/wap-pad-screenshots/audit-pad-portrait-knowledge-banned.png) | [截图](/E:/one-class/docs/wap-pad-screenshots/audit-pad-landscape-knowledge-banned.png) |
| 模板 | `/templates` | 文案/海报模板 Tab、启用、编辑、新建 | [截图](/E:/one-class/docs/wap-pad-screenshots/audit-phone-hometemplates.png) | [截图](/E:/one-class/docs/wap-pad-screenshots/audit-pad-portrait-templates.png) | [截图](/E:/one-class/docs/wap-pad-screenshots/audit-pad-landscape-templates.png) |
| 模板 | `/templates/copies/1` | 文案模板详情、复制、编辑、使用模板 | [截图](/E:/one-class/docs/wap-pad-screenshots/audit-phone-templates-copies-1.png) | [截图](/E:/one-class/docs/wap-pad-screenshots/audit-pad-portrait-templates-copies-1.png) | [截图](/E:/one-class/docs/wap-pad-screenshots/audit-pad-landscape-templates-copies-1.png) |
| 模板 | `/templates/posters/1` | 海报模板详情、复制、编辑、生成海报 | [截图](/E:/one-class/docs/wap-pad-screenshots/audit-phone-templates-posters-1.png) | [截图](/E:/one-class/docs/wap-pad-screenshots/audit-pad-portrait-templates-posters-1.png) | [截图](/E:/one-class/docs/wap-pad-screenshots/audit-pad-landscape-templates-posters-1.png) |
| 办公 | `/office` | 综合办公表、打开 WPS | [截图](/E:/one-class/docs/wap-pad-screenshots/audit-phone-homeoffice.png) | [截图](/E:/one-class/docs/wap-pad-screenshots/audit-pad-portrait-office.png) | [截图](/E:/one-class/docs/wap-pad-screenshots/audit-pad-landscape-office.png) |
| 管理 | `/users` | 用户列表、角色/状态、创建、重置密码、权限 | [截图](/E:/one-class/docs/wap-pad-screenshots/audit-phone-homeusers.png) | [截图](/E:/one-class/docs/wap-pad-screenshots/audit-pad-portrait-users.png) | [截图](/E:/one-class/docs/wap-pad-screenshots/audit-pad-landscape-users.png) |

登录页另有 [手机登录截图](/E:/one-class/docs/wap-pad-screenshots/audit-phone-login.png)、[Pad 竖屏登录截图](/E:/one-class/docs/wap-pad-screenshots/audit-pad-portrait-834-login.png) 和 [Pad 横屏登录截图](/E:/one-class/docs/wap-pad-screenshots/audit-pad-landscape-1180-login.png)。

## 3. 布局与功能合理性分析

### 3.1 导航和返回

原始问题是移动端详情页没有稳定的顶部返回，用户只能依赖系统返回或重新打开抽屉。现在 App 顶栏统一承担“返回 + 标题 + 用户入口”：

- 详情、编辑、生成、上传页显示明确的“返回上一页”。
- 只有浏览历史确实属于当前父级时才 `router.back()`；否则使用父级路径 `router.replace()`，避免从新标签页/深链返回到无关站点。
- `/students/40`、`/upload`、`/copies/generate` 已实测分别返回 `/students`、`/materials`、`/copies`。
- 移动导航抽屉增加“关闭导航”按钮，避免打开后只能点遮罩。
- 生成文案/生成海报页面在移动端不再重复渲染第二个页面头。

这套逻辑符合 WAP/Pad 的用户预期，也不会改变 PC 端的历史行为。

### 3.2 列表和详情

手机端列表使用“一张卡片 = 一个业务对象”的结构：身份/状态在首行，最关键的 2–3 个字段在摘要，更多信息通过展开或详情页查看。这样避免了 PC 表格在 390px 宽度下出现横向拖动。Pad 竖屏可以使用两列卡片，Pad 横屏则优先利用横向空间显示列表和详情。

### 3.3 表单、Dialog 和 Sheet

- 短确认、短编辑（重置密码、状态调整）适合 Dialog。
- 搜索筛选、添加学员、编辑学生、编写学情等连续操作适合 Sheet，底部固定操作区更容易触控。
- 长表单（上传素材、报名续费、课程编辑、生成内容）使用独立页面或接近全屏的面板，避免在小 Dialog 内滚动两层。
- Pad 横屏的 Sheet 改为右侧面板；手机和 Pad 竖屏仍从底部上滑。这样横屏可以一边看列表，一边填写表单。
- Dialog/Sheet 打开时主内容层级提升到弹层下方、底部导航上方，修复了新建线索等弹层底部按钮被导航遮挡的问题。

### 3.4 课表和表格

原来的七列时间网格在手机上信息密度过高、文字过小、容易横向拖动。现在 WAP/Pad 使用日期分组 agenda：日期标题、课次数、时间、班级/老师/教室和“详情/点名/编辑/删除”操作都在卡片内；日/周/月、筛选、前后周期切换仍保留。PC 继续使用时间轴网格，因而没有牺牲桌面端的排课效率。

财务、报名、点名等数据在移动端采用汇总数字 + 记录卡片，金额、状态和危险操作仍保持清晰的颜色与文字，不将关键字段隐藏在横向表格中。

## 4. 不适合 WAP/Pad 的部分与已完成改造

| 原问题 | 影响 | 当前处理 |
|---|---|---|
| PC 时间课表直接压缩到手机 | 文字拥挤、横向滚动、点课次困难 | 改成按日期分组 agenda；保留日/周/月与课次操作 |
| Pad 横屏仍使用底部 Sheet | 遮挡内容、无法利用横向空间 | `AppSheet` 在 Pad 横屏自动切换为右侧 Sheet |
| 详情页缺少顶部返回 | 深链和从列表进入后的回退不一致 | AppLayout 统一安全返回目标和父级 fallback |
| 弹窗 footer 被底部 Tab/导航盖住 | 保存/取消不可见或不可点 | 弹层打开时提升 `.main` 层级，footer 固定在可视区域 |
| 移动端重复显示生成页头 | 首屏浪费高度，视觉层级重复 | 由 App 顶栏统一提供标题和返回 |
| 列表保留过多 PC 列 | 需要缩放或横向拖动 | 卡片摘要、展开区、详情分层；PC 表格仅保留桌面 |
| 过滤条件直接平铺 | 占用首屏，修改一次就触发请求 | 使用 draft/apply/reset 的 Filter Sheet |
| 图标按钮无可读名称 | 读屏/键盘无法理解操作 | 统一补 `aria-label`、`title` 或可见文字；最终审计为 0 |
| 导航抽屉没有显式关闭入口 | 触控路径不完整 | 增加“关闭导航”按钮和 Escape/遮罩关闭 |

## 5. 弹窗、弹层、抽屉和 Popover 清单

项目中弹层由 `el-dialog`、`AppSheet`、`MobileFilterSheet`、导航 `el-drawer` 和课表 `el-popover` 组成。下列截图覆盖了实际可触发的主要状态；动态标题（例如“新建/编辑话术”“手工建单·报名/续费”）共用同一组件，只随业务标题变化。

### 5.1 导航、筛选和工作台 Sheet

| 类型 | 用途 | 截图 |
|---|---|---|
| 导航抽屉 | 手机打开模块导航、退出导航 | [打开前](/E:/one-class/docs/wap-pad-screenshots/baseline-nav-drawer-phone-390.png) · [增加关闭按钮后](/E:/one-class/docs/wap-pad-screenshots/baseline-nav-drawer-phone-390-after.png) |
| 学员筛选 | 姓名、状态、年级、学管师、电话、学校 | [手机](/E:/one-class/docs/wap-pad-screenshots/baseline-students-filter-phone-390.png) · [Pad 横屏](/E:/one-class/docs/wap-pad-screenshots/baseline-students-filter-pad-landscape-1180.png) |
| 线索筛选 | 来源、状态、负责人、时间范围 | [手机](/E:/one-class/docs/wap-pad-screenshots/sheet-lead-filter-phone-390.png) |
| 工作台新增待办 | 新建待办、类型、截止时间 | [手机](/E:/one-class/docs/wap-pad-screenshots/sheet-dashboard-todo-phone-390.png) · [Pad 横屏](/E:/one-class/docs/wap-pad-screenshots/sheet-dashboard-todo-pad-landscape-1180-after.png) |
| 工作台快捷入口配置 | 自定义入口、排序/启用 | [手机](/E:/one-class/docs/wap-pad-screenshots/dialog-dashboard-custom-phone-390.png) |

同一 `MobileFilterSheet` 还用于素材、文案、模板、知识库、学情、班级、上课记录、课程、老师、报名、订单、收支、课消、充值、收入报表和用户列表；各页面的字段在 Sheet 内按业务显示，布局规则统一为“条件 → 重置/查看结果”。

### 5.2 线索、学员、学情和报名

| 弹层 | 业务功能 | 截图 |
|---|---|---|
| 新建线索 | 姓名、电话、来源、需求、下次跟进、备注 | [手机](/E:/one-class/docs/wap-pad-screenshots/dialog-lead-create-phone-390.png) · [Pad 竖屏](/E:/one-class/docs/wap-pad-screenshots/dialog-lead-create-pad-portrait-834.png) · [Pad 横屏](/E:/one-class/docs/wap-pad-screenshots/dialog-lead-create-pad-landscape-1180.png) |
| 编辑线索 | 修改基础资料和负责人 | [截图](/E:/one-class/docs/wap-pad-screenshots/dialog-lead-edit-phone-390.png) |
| 写跟进 | 跟进内容、状态、下次联系时间 | [截图](/E:/one-class/docs/wap-pad-screenshots/dialog-lead-follow-phone-390.png) |
| 添加协作人 | 多人协作登记 | [截图](/E:/one-class/docs/wap-pad-screenshots/dialog-lead-collaborator-phone-390.png) |
| 导入线索 | Excel 导入、字段预览、错误提示 | [截图](/E:/one-class/docs/wap-pad-screenshots/dialog-lead-import-phone-390.png) |
| 编辑学生 Sheet | 学生档案和家长联系方式 | [手机](/E:/one-class/docs/wap-pad-screenshots/sheet-student-edit-phone-390.png) · [Pad 横屏](/E:/one-class/docs/wap-pad-screenshots/sheet-student-edit-pad-landscape-1180-after.png) |
| 编写学情 Sheet | 学习情况、作业、备注、图片 | [手机](/E:/one-class/docs/wap-pad-screenshots/sheet-student-learning-phone-390.png) · [Pad 横屏](/E:/one-class/docs/wap-pad-screenshots/sheet-student-learning-pad-landscape-1180-after.png) |
| 学情报告 Sheet | 生成/查看阶段报告 | [截图](/E:/one-class/docs/wap-pad-screenshots/sheet-student-report-phone-390.png) |
| 报名新建学生 Sheet | 快速建档并回填报名流程 | [手机](/E:/one-class/docs/wap-pad-screenshots/sheet-enrollment-new-student-phone-390.png) · [Pad 横屏](/E:/one-class/docs/wap-pad-screenshots/sheet-enrollment-new-student-pad-landscape-1180.png) |

### 5.3 教务、课表和点名

| 弹层 | 业务功能 | 截图 |
|---|---|---|
| 新建班级 Sheet | 班级类型、课程、老师、课时 | [手机](/E:/one-class/docs/wap-pad-screenshots/sheet-class-create-phone-390.png) · [Pad 横屏](/E:/one-class/docs/wap-pad-screenshots/sheet-class-create-pad-landscape-1180.png) |
| 编辑班级 Sheet | 修改班级信息 | [截图](/E:/one-class/docs/wap-pad-screenshots/sheet-class-edit-phone-390.png) |
| 批量排课 Sheet | 周期、日期、老师、教室 | [截图](/E:/one-class/docs/wap-pad-screenshots/sheet-class-schedule-batch-phone-390.png) |
| 添加学员 Dialog | 向班级添加在读学员 | [截图](/E:/one-class/docs/wap-pad-screenshots/dialog-class-add-student-phone-390.png) |
| 课堂点名 Dialog | 选择课次并提交到课状态 | [截图](/E:/one-class/docs/wap-pad-screenshots/dialog-class-roll-phone-390.png) |
| 点名详情 Dialog | 查看本次点名汇总 | [截图](/E:/one-class/docs/wap-pad-screenshots/dialog-class-attendance-detail-phone-390.png) |
| 修改课次/到课状态 Dialog | 修正时间、出勤状态 | [课次](/E:/one-class/docs/wap-pad-screenshots/dialog-class-record-edit-phone-390.png) · [到课状态](/E:/one-class/docs/wap-pad-screenshots/dialog-class-record-attendance-phone-390.png) |
| 新建排课 Sheet | 课程、老师、时间、重复规则 | [手机](/E:/one-class/docs/wap-pad-screenshots/sheet-schedule-create-phone-390.png) · [Pad 横屏](/E:/one-class/docs/wap-pad-screenshots/sheet-schedule-create-pad-landscape-1180.png) |
| 课次详情 Sheet | 查看课次并进入点名/编辑 | [截图](/E:/one-class/docs/wap-pad-screenshots/sheet-schedule-lesson-detail-phone-390.png) |
| 修改课表时间 Dialog | 修改某个课次时间 | [截图](/E:/one-class/docs/wap-pad-screenshots/dialog-schedule-time-edit-phone-390.png) |
| 添加临时学员 Dialog | 临时加入当前课次 | [截图](/E:/one-class/docs/wap-pad-screenshots/dialog-schedule-add-temp-student-phone-390.png) |
| 点名/补课 Dialog | 从上课记录发起点名、缺课补课 | [截图](/E:/one-class/docs/wap-pad-screenshots/dialog-roll-phone-390.png) |

课表中的日期选择器、前后周期箭头和课次快捷菜单是 `el-popover`/日期控件，不会遮住主导航；对应整体状态见 [手机课表截图](/E:/one-class/docs/wap-pad-screenshots/after-schedule-phone-390.png) 和 [Pad 横屏课表截图](/E:/one-class/docs/wap-pad-screenshots/audit-pad-landscape-academic-schedule.png)。

### 5.4 财务、内容和管理

| 弹层 | 业务功能 | 截图 |
|---|---|---|
| 账户充值 Dialog | 学员账户充值、支付方式、经办人 | [手机](/E:/one-class/docs/wap-pad-screenshots/dialog-recharge-phone-390.png) · [Pad 竖屏](/E:/one-class/docs/wap-pad-screenshots/dialog-recharge-pad-portrait-834.png) |
| 手工建单 Dialog | 报名、续费、转课、退课、其他建单 | [截图](/E:/one-class/docs/wap-pad-screenshots/dialog-order-manual-phone-390.png) |
| 操作日志 Dialog | 查看订单操作轨迹 | [截图](/E:/one-class/docs/wap-pad-screenshots/dialog-order-logs-phone-390.png) |
| 课消详情 Dialog | 查看课消关联课次和金额 | [截图](/E:/one-class/docs/wap-pad-screenshots/dialog-consumption-detail-phone-390.png) |
| 素材上传 Dialog | 相册/文件选择、元数据、授权 | [截图](/E:/one-class/docs/wap-pad-screenshots/dialog-material-upload-phone-390.png) |
| 海报上传 Dialog | 上传成品海报、标题/模板信息 | [截图](/E:/one-class/docs/wap-pad-screenshots/dialog-poster-upload-phone-390.png) |
| 知识库新建/编辑 Dialog | 话术、异议、禁用词 | [截图](/E:/one-class/docs/wap-pad-screenshots/dialog-knowledge-create-phone-390.png) |
| 文案模板 Dialog | 新建/编辑文案模板 | [截图](/E:/one-class/docs/wap-pad-screenshots/dialog-template-copy-create-phone-390.png) |
| 海报模板 Dialog | 新建/编辑海报模板；与文案模板共用表单骨架 | 同构截图见 [模板表单](/E:/one-class/docs/wap-pad-screenshots/dialog-template-copy-create-phone-390.png) |
| 用户新建 Dialog | 账号、角色、状态 | [手机](/E:/one-class/docs/wap-pad-screenshots/dialog-user-create-phone-390.png) · [Pad 竖屏](/E:/one-class/docs/wap-pad-screenshots/dialog-user-create-pad-portrait-834.png) |
| 重置密码 Dialog | 为用户生成/设置新密码 | [截图](/E:/one-class/docs/wap-pad-screenshots/dialog-user-reset-phone-390.png) |
| 权限 Dialog | 按模块选择权限并保存 | [截图](/E:/one-class/docs/wap-pad-screenshots/dialog-user-permissions-phone-390.png) |

### 5.5 账户入口

| 弹层 | 业务功能 | 截图 |
|---|---|---|
| 忘记密码 Dialog | 手机号/验证码/新密码流程 | [截图](/E:/one-class/docs/wap-pad-screenshots/dialog-forgot-password-phone-390.png) |
| 修改密码 Dialog | 已登录用户修改密码 | [截图](/E:/one-class/docs/wap-pad-screenshots/dialog-change-password-phone-390.png) |

## 6. 视觉规范与美化结果

### 6.1 色调

保留 PC 的“米金 + 深棕”品牌识别，同时降低移动端大面积渐变和阴影：

| Token | 当前用途 |
|---|---|
| `--oc-page-mobile` / `#F7F4EE` | WAP/Pad 页面背景 |
| `--oc-card` / `#FFFCF7` | 卡片、Sheet、表单容器 |
| `--oc-ink` / `#292524` | 主文字 |
| `--oc-muted` / `#78716C` | 辅助文字 |
| `--oc-primary` / `#A16207` | 主按钮、选中态、课表强调色 |
| `--oc-success` / `#16A34A` | 正常/已完成 |
| `--oc-warning` / `#D97706` | 待跟进/提醒 |
| `--oc-danger` / `#DC2626` | 删除、撤销、异常 |

统一使用 4px 间距基线，常用 8/12/16/24px；触控目标最小 44px；手机顶栏约 56px、底部 Tab 64px + safe-area；Pad 横屏左侧 rail 76px。状态同时显示文字和颜色，不依赖颜色单独传达含义。

### 6.2 导航和组件风格

- 手机底部主导航固定为“工作台、线索、学员、财务、更多”，选中态使用主金色短条和文字加粗。
- Pad 横屏使用深棕图标轨，当前模块显示金色背景和左侧指示条。
- 卡片采用浅米白背景、细边框、14px 圆角，减少厚重阴影。
- Sheet footer 统一右对齐、按钮间距统一，键盘/安全区不会遮住主操作。
- 表格类数据优先采用“摘要指标 + 记录卡片 + 详情”，复杂字段才在 Pad 横屏双栏或 PC 表格呈现。

## 7. 已修改的主要文件与行为

- [AppLayout.vue](/E:/one-class/frontend/src/layouts/AppLayout.vue)：统一返回目标、历史判断、移动抽屉关闭、重复页头隐藏和弹层层级。
- [AppSheet.vue](/E:/one-class/frontend/src/components/AppSheet.vue)：手机/Pad 竖屏底部 Sheet，Pad 横屏右侧 Sheet。
- [AppRail.vue](/E:/one-class/frontend/src/components/AppRail.vue) 与 [AppTabBar.vue](/E:/one-class/frontend/src/components/AppTabBar.vue)：Pad rail、手机底部导航、当前态和无障碍名称。
- [useBreakpoint.ts](/E:/one-class/frontend/src/composables/useBreakpoint.ts)：明确 `phone`、`pad-portrait`、`pad-landscape`、`desktop` 模式。
- [ScheduleView.vue](/E:/one-class/frontend/src/views/academic/ScheduleView.vue)：WAP/Pad agenda 课表，保留日/周/月和完整课次操作。
- [StudentDetailView.vue](/E:/one-class/frontend/src/views/students/StudentDetailView.vue)、[StudentListView.vue](/E:/one-class/frontend/src/views/students/StudentListView.vue)、[TodayTodos.vue](/E:/one-class/frontend/src/components/TodayTodos.vue)：横屏 Sheet 方向和宽度适配。
- [LearningNewView.vue](/E:/one-class/frontend/src/views/learning/LearningNewView.vue)：图片上传实际触发节点补齐 `aria-label/title`。
- [style.css](/E:/one-class/frontend/src/style.css)：移动端 token、safe-area、弹层 footer、visually-hidden 和触控样式。

## 8. 验证结果

已完成并通过：

- `frontend/npm run typecheck`
- `frontend/npm run build`
- `python -m pytest -q backend/tests/test_leads.py backend/tests/test_lead_excel_import.py`：18 passed
- `backend/python -m pytest -q`：145 passed
- 41 路由 × 3 尺寸：123 条布局记录，横向溢出 0
- 返回逻辑：学生详情、上传、生成文案三条深链均回到正确父级
- Pad 横屏：学生筛选、编辑学生、排课和工作台待办均显示右侧 Sheet
- 弹层层级：新建线索 footer 按钮可见、可点击，底部导航不再覆盖
- 无障碍：手机、Pad 竖屏、Pad 横屏各 41 路由，未命名交互控件 0；记录见 [audit-unnamed-buttons-final.json](/E:/one-class/docs/wap-pad-screenshots/audit-unnamed-buttons-final.json)

原有用户修改和业务接口未做破坏性回退；没有创建分支、提交或推送。旧 `/m/*` 入口继续作为兼容重定向，正式业务仍使用同一套路由和 API。

## 9. 最终复核与自评分

最终暖色 Hero 版本页面截图与机器审查结果见 [redesign-v2/final](/E:/one-class/docs/wap-pad-screenshots/redesign-v2/final)，其中包含手机 390×844、Pad 竖屏 834×1112、Pad 横屏 1180×820 三套 41 页截图，以及 [all-routes-audit.json](/E:/one-class/docs/wap-pad-screenshots/redesign-v2/final/all-routes-audit.json)。三种视口共 123 条记录，均为横向溢出 0、未命名交互控件 0。新版 Dialog、Sheet 和 Pad 右侧 Sheet 代表状态见 [dialogs](/E:/one-class/docs/wap-pad-screenshots/redesign-v2/final/dialogs)。

本版根据最终视觉复核撤销了黑色 WAP/Pad 顶栏、底栏、Rail 和弹层标题，改为与 PC Hero 同源的暖白到浅金背景、深棕文字和克制金色操作。中间工作区继续使用中性浅灰，避免整页变成单一米黄色。

PC 回归基准另见 [pc-regression-students-1440.png](/E:/one-class/docs/wap-pad-screenshots/pc-regression-students-1440.png)，用于确认 1200px 以上仍保留原有 PC 表格与深色侧栏风格。

我对本轮交付的自评分为 **94 / 100**，不能诚实地给满分：

| 维度 | 得分 | 结论 |
|---|---:|---|
| PC 色调与移动视觉一致性 | 19 / 20 | 导航、Hero、弹层头尾改为 PC 同源暖色；内容区保留中性灰，避免黑金压迫和全页泛黄 |
| WAP/Pad 响应式布局 | 20 / 20 | 手机卡片/底部导航、Pad 竖屏卡片、Pad 横屏 Rail + 双栏/右侧 Sheet 均已验证 |
| 深层详情页 | 19 / 20 | 学员、线索、订单、素材、文案和模板详情已按触控层级重排，身份摘要统一为浅暖 Hero |
| Dialog / Sheet / Drawer | 18 / 20 | 统一暖色头尾、footer、安全区、层级和关闭逻辑；仍需真实设备软键盘回归 |
| 功能、返回、触控与可访问性 | 18 / 20 | 返回 fallback、电话操作、课表 agenda、底部操作栏和 aria 名称已验证；外部服务无法在本地完全验收 |

没有写成 100 分的原因是：WPS/AI 等外部服务、极端长文本、系统软键盘遮挡，以及真实 iOS/Android 安全区差异仍需要上线设备抽测。本地三视口与演示数据范围已完成，但这些边界不能用桌面浏览器截图替代。
