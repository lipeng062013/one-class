# 壹号教室运营工具平台（V1）设计规格

## 1. 背景与目标

壹号教室已有全年运营指导手册（`one-class-operations-guide.html`），其中「自用工具」规划包括素材上传、AI 草稿、线索与知识库等。本规格定义 **V1 自用运营网站**：给机构内部使用，把「老师交素材 → 运营出文案/海报 → 登记老带新线索」做成可每天使用的系统。

本项目 **不是** 运营手册网页的延续实现，也 **不是** 单文件 HTML 堆叠全部功能。手册 HTML 仅作需求与业务规则参考，继续可独立通过 GitHub Pages 发布。

### V1 目标

- 用 **Vue 3 + TypeScript** 模块化前端、**Python** 模块化后端、**Docker Compose** 部署。
- 前端 UI 框架采用 **Element UI 体系**（Vue 3 使用 **Element Plus**）；页面需做成 **响应式**，适配电脑后台与老师手机端。
- 支持账号密码登录与三角色：负责人、运营、老师。
- 完成主闭环：素材上传、知识库约束、文案（模板 + 可选大模型）、海报（版式模板 + 可选 AI 生图）、老带新/获客记录。
- 密钥与模型配置仅通过环境变量注入，不进入源码与 Git。

### 明确非目标（V1 不做）

- 多机构 SaaS 租户、平台账号托管、自动发布到微信/小红书等。
- 短信登录、微信 OAuth；邮箱/短信自助重置密码（忘记密码 V1 仅管理员重置）。
- 首次登录强制改密（可后续迭代）。
- 复杂审核排期看板、招生数据大盘、评价抓取。
- 把全部功能塞进单个 `.html` 文件。

## 2. 服务对象与使用场景

- **机构范围：** 先服务壹号教室；数据模型单机构，不强制 `org_id`，架构预留以后扩展。
- **负责人（admin）：** 建账号、管知识库与系统模板、查看全部业务。
- **运营（operator）：** 电脑端处理素材、生成文案/海报、跟进线索、维护自定义模板。
- **老师（teacher）：** 手机简版上传素材、查看自己提交的素材状态。

设备策略与响应式：

- 运营/负责人以 **电脑后台** 为主。
- 老师以 **手机上传** 为主（大按钮、少字段）。
- **全站页面做成响应式**：同一套前端在桌面、平板、手机下可用；断点与布局随视口变化，避免仅桌面可用或仅硬编码固定宽度。
- 组件与交互优先使用 **Element Plus**（Element UI 体系）的栅格、表单、表格、对话框、菜单、消息提示等，保证视觉与交互一致。

## 3. V1 功能范围

| 模块 | 包含 | 说明 |
|------|------|------|
| 登录与角色 | 是 | 账号 + 密码；admin / operator / teacher；建号必填初始密码；管理员重置密码；用户可改密（详见 `2026-07-29-auth-element-ui-rebuild-design.md`） |
| 老带新 / 获客记录 | 是 | 来源、介绍人、需求、跟进状态、下次跟进 |
| 分享海报 | 是 | 默认版式模板导出；可选 AI 生图 |
| 小红书文案 / 脚本 | 是 | 推荐模板 + 自定义模板；可选大模型增强 |
| 素材上传 | 是 | 图 + 文；授权与状态字段 |
| 机构知识库 | 是 | 课程、FAQ、语气、禁用词、流程等 |
| 多平台草稿（朋友圈/视频号/点评） | 否 | V2 |
| 审核与排期工作流 | 否 | V2；V1 仅素材授权字段 |
| 咨询回访自动化提醒 | 否 | V2；V1 仅列表「今日待跟进」 |
| 招生数据看板 | 否 | V2 |

## 4. 整体架构

### 4.1 技术选型

| 层 | 选型 |
|----|------|
| 前端 | Vue 3 + TypeScript + Vite + Vue Router + Pinia |
| UI 框架 | **Element UI 体系**（Vue 3 使用 **Element Plus** 组件库与主题） |
| 页面布局 | **响应式**：桌面侧栏后台 + 窄屏/手机自适应；老师端优先触控友好 |
| 后端 | Python FastAPI |
| ORM / 迁移 | SQLAlchemy + Alembic |
| 数据库 | 第一版 SQLite；连接与模型按可迁移 PostgreSQL 编写 |
| 文件 | 本地目录挂载；`Storage` 抽象，以后可换 OSS/MinIO |
| 部署 | Docker Compose（frontend + backend + data volume） |
| 文案大模型 | 后端调用 OpenAI 兼容接口（如中转站 `LLM_BASE_URL`） |
| 图片生成 | 后端调用图片 API（`IMAGE_API_BASE_URL`） |

### 4.2 仓库结构

```text
one-class/
  frontend/
    src/
      views/
      components/
      api/
      stores/
      router/
  backend/
    app/
      modules/
        auth/
        materials/
        knowledge/
        templates/
        content/
        posters/
        leads/
      core/            # 配置、数据库、安全、存储抽象
      integrations/    # LLM、图片 API
  data/                # gitignore：sqlite + uploads
  docker-compose.yml
  .env.example
  one-class-operations-guide.html   # 既有手册，保留
  docs/superpowers/specs/           # 本规格等
```

### 4.3 运行时关系

```text
老师(手机) / 运营(电脑) / 负责人(电脑)
        → Vue 前端
        → REST/JSON → FastAPI
                        → SQLite
                        → 本地文件卷
                        → 可选 LLM / 图片 API
```

### 4.4 关键原则

1. 前后端分离、按业务模块拆分目录与代码，禁止单文件堆砌全部逻辑。
2. AI Key 与密钥 **只存在后端环境变量**，前端永不持有。
3. 模板路径在无 Key 或上游失败时必须仍可用（优雅降级）。
4. 既有运营手册 HTML 不改造成本系统前端。
5. UI 统一使用 Element UI 体系（Element Plus），禁止另起一套无关联的 UI 组件风格。
6. 页面必须响应式：关键业务页在桌面与窄屏均可完成主流程（登录、列表、表单、上传、详情）。

## 4.5 前端 UI 与响应式要求

### UI 框架（Element UI / Element Plus）

- 安装并全局注册 **Element Plus**（Element UI 在 Vue 3 下的官方对应方案）。
- 表单、表格、分页、按钮、上传、抽屉/对话框、导航菜单、消息/确认框等优先用 Element Plus 组件，少写裸 HTML 控件。
- 主题与间距保持统一；图标可使用 Element Plus Icons。

### 响应式页面

| 场景 | 要求 |
|------|------|
| 桌面（≥992px） | 侧栏 + 顶栏后台布局；表格可展示多列 |
| 平板（768–991px） | 侧栏可折叠/抽屉化；表格横向滚动或精简列 |
| 手机（<768px） | 底部或抽屉导航；列表卡片化；大触控目标；老师上传主路径优先 |
| 通用 | 使用 Element Plus 栅格/`el-row`/`el-col` 或 CSS 媒体查询；禁止写死仅适合某一宽度的布局 |

老师端可继续使用 `MobileLayout` 等专用布局，但整体仍属于同一响应式体系，而不是两套互不兼容的站点。

## 5. 角色与权限

| 能力 | admin | operator | teacher |
|------|:-----:|:--------:|:-------:|
| 登录 | ✓ | ✓ | ✓ |
| 管理用户 | ✓ | ✗ | ✗ |
| 上传素材 | ✓ | ✓ | ✓（主场景） |
| 查看素材 | 全部 | 全部 | 仅自己的 |
| 知识库 | 读写 | 只读 | ✗ |
| 系统推荐模板 | 管理 | 只读 / 复制为自定义 | ✗ |
| 自定义模板 | ✓ | ✓ | ✗ |
| 生成文案 / 海报 | ✓ | ✓ | ✗ |
| 线索 CRUD | ✓ | ✓ | ✗ |

知识库默认仅负责人可写，避免语气与禁用词被误改。

## 6. 数据模型

### 6.1 users

- `id`, `username`, `password_hash`, `display_name`
- `role`: `admin` | `operator` | `teacher`
- `is_active`, `created_at`

### 6.2 materials

- `id`, `uploader_id`
- 业务字段：场景说明、年级、科目、家长痛点、老师处理、下一步行动
- `auth_status`: `pending` | `authorized` | `denied` | `anonymized`
- `status`: `new` | `usable` | `used` | `archived`
- `created_at`

### 6.3 material_files

- `id`, `material_id`, `file_path`, `file_type`, `sort_order`

### 6.4 knowledge_entries

- `id`, `category`: `course` | `faq` | `tone` | `banned` | `staff` | `process`
- `title`, `content`, `tags`, `is_active`
- `updated_by`, `updated_at`

### 6.5 copy_templates

- `id`, `name`, `scene`（如 `referral` | `trial` | `progress` | `xhs_script`）
- `body`（支持 `{{变量}}`）
- `is_system`（系统推荐：不可删，可复制）
- `is_active`, `created_by`, `created_at`

### 6.6 poster_templates

- `id`, `name`, `scene`
- `layout_json`（标题/正文/主图/二维码等区域）
- `preview_path`, `is_system`, `is_active`

### 6.7 generated_copies

- `id`, `material_id?`, `template_id?`
- `mode`: `template` | `llm` | `template_then_llm`
- `platform`（V1 默认 `xhs`，字段预留扩展）
- `title`, `body`, `prompt_snapshot`, `model_name`
- `created_by`, `created_at`

### 6.8 generated_posters

- `id`, `material_id?`, `template_id?`
- `mode`: `layout` | `ai_image`
- `title`, `payload_json`, `file_path`
- `created_by`, `created_at`

### 6.9 leads

- `id`, `student_or_parent_name`, `phone?`
- `source`: `referral` | `dianping` | `wechat` | `walkin` | `other`
- `referrer_name?`, `channel_note`, `need`
- `status`: `new` | `contacted` | `visited` | `enrolled` | `lost`
- `next_follow_at?`, `owner_id?`, `notes`
- `created_at`, `updated_at`

密码仅存 hash；AI 密钥不入库。

### 6.10 状态机

- 素材：`new` → `usable` → `used` → `archived`
- 线索：`new` → `contacted` → `visited` → `enrolled` | `lost`
- 未 `authorized` / `anonymized` 的素材：生成时强提示，运营仍可继续（内部工具）

## 7. 页面与主流程

### 7.1 路由

**公共**

- `/login`

**电脑后台**

- `/` 工作台（待处理素材、今日待跟进线索、最近生成）
- `/materials`, `/materials/:id`
- `/copies`, `/copies/new`
- `/posters`, `/posters/new`
- `/leads`
- `/knowledge`
- `/templates/copies`, `/templates/posters`
- `/users`（仅 admin）

**老师手机**

- `/m/upload`, `/m/materials`
- `role=teacher` 登录后默认进入 `/m/upload`；访问后台路由时重定向到手机简版

### 7.2 主流程

1. **老师交素材：** 登录 → 填说明与授权 → 多图上传 → 状态 `new` → 在「我的素材」可见。
2. **生成文案：** 选素材与模板 → 变量由素材 + 知识库填充 → 模式（仅模板 / 模板后润色 / 直接大模型）→ 可编辑 → 一键复制 → 落库；可选将素材标 `used`。
3. **生成海报：** 选版式 → 填标题/主图/二维码等 → 默认导出 PNG；可选 AI 生图 → 下载并落库。
4. **线索：** 新建与筛选 → 更新状态与备注 → 工作台展示今日待跟进（不做短信）。
5. **知识库与模板：** 负责人维护知识库与系统模板；运营复制系统模板为自定义后修改。

### 7.3 导航

- 电脑侧栏：工作台、素材、文案、海报、线索、知识库、模板、用户（admin）
- 老师底栏：上传 | 我的素材

## 8. 后端 API

- 前缀：`/api/v1`
- 认证：登录返回 JWT；`Authorization: Bearer <token>`
- 响应：`{ "data": ..., "error": null }`；错误含 `code` / `message`
- 越权：403

### 8.1 端点分组

**auth / users**

- `POST /auth/login`
- `GET /auth/me`
- `POST /auth/change-password`（当前用户改密）
- `GET|POST|PATCH /users`（admin；`POST` 必填 `password`）
- `POST /users/{id}/reset-password`（admin；忘记密码由负责人重置）

**materials**

- `GET /materials`（老师仅自己）
- `POST /materials`
- `POST /materials/{id}/files`
- `GET /materials/{id}`
- `PATCH /materials/{id}`

**knowledge**

- `GET /knowledge?category=`
- `POST|PATCH|DELETE /knowledge/{id}`（默认 admin）

**templates**

- `GET /templates/copies`, `GET /templates/posters`
- 自定义模板的 `POST|PATCH|DELETE`；系统模板不可删除

**content**

- `POST /copies/generate`（`material_id?`, `template_id?`, `mode`, `platform`, `extra_instruction?`）
- `GET /copies`, `PATCH /copies/{id}`

**posters**

- `POST /posters/generate`（`mode`: `layout` | `ai_image`）
- `GET /posters`
- 文件下载：`GET /files/{id}`（鉴权）

**leads**

- `GET|POST /leads`, `PATCH /leads/{id}`

## 9. 文案、海报与 AI 集成

### 9.1 文案

- **自定义模板：** 运营/负责人可建、改、删（非系统）。
- **推荐模板：** `is_system=true`，预置老带新、试听、课堂进步、小红书脚本等场景；只读，可复制。
- **大模型（可选）：** 后端使用 `LLM_BASE_URL`、`LLM_API_KEY`、`LLM_MODEL`；system 注入知识库摘要、品牌语气与禁用词。
- 禁用词命中：返回命中列表并在编辑区提示，允许人工修改后保存。
- 上游失败：回退已有模板结果并提示，不整单失败。

### 9.2 海报

- **默认：** 版式模板 + 字段渲染，导出可下载位图（PNG）。实现可选 Pillow 或等价方案，以「稳定可控的版式导出」为准。
- **可选：** `IMAGE_API_BASE_URL`、`IMAGE_API_KEY`（及所需模型参数）生成图片后入库下载。
- AI 生图失败时保留/回退版式结果策略与文案一致：不阻断「至少有一张可用图」的路径（若用户选的是纯 AI 模式且失败，则明确错误，可改选版式重试）。

### 9.3 配置（仅变量名，禁止把真实 Key 写入仓库）

```text
DATABASE_URL=
JWT_SECRET=
STORAGE_ROOT=
LLM_BASE_URL=
LLM_API_KEY=
LLM_MODEL=
IMAGE_API_BASE_URL=
IMAGE_API_KEY=
IMAGE_MODEL=
```

真实值只放本地 `.env`（gitignore）。若 Key 曾在聊天中暴露，应在中转站轮换后再写入 `.env`。

### 9.4 安全与限流

- 生成类接口按用户简单限流，降低误触刷量。
- 上传限制类型与大小（仅常见图片等）。
- 文件下载校验登录与资源归属/角色。

## 10. 存储与部署

- 数据库：SQLite 文件位于 data 卷；SQLAlchemy 模型避免 SQLite 专有写法，便于迁 PostgreSQL。
- 文件：`STORAGE_ROOT` 本地目录；`Storage` 接口提供 save / open / url 或 file id。
- `docker compose up` 启动 frontend + backend；挂载 `./data`。
- 生产前端：构建静态资源并由 nginx（或等价）反代 `/api` 到 backend。

## 11. 错误处理（产品层）

| 情况 | 行为 |
|------|------|
| 登录失败 | 账号或密码错误提示 |
| 无权限 | 403 |
| 上传非法 | 字段级错误 |
| 未授权素材生成 | 警告，可继续 |
| 禁用词 | 标出，可编辑保存 |
| LLM / 生图失败 | 提示 + 模板/版式降级（见第 9 节） |
| 存储失败 | 友好错误 + 服务端日志 |

## 12. 测试与验收

### 12.1 自动测试（后端优先）

- 登录与角色隔离、素材可见性、线索状态。
- 纯模板文案生成不依赖外网；LLM / 图片客户端 mock。
- 存储使用临时目录。

### 12.2 手工验收清单

1. 三角色登录与菜单/路由差异。
2. 老师手机上传 → 运营列表可见。
3. 仅模板生成文案并复制。
4. 配置 LLM 后润色成功；无 Key 或错误时回退。
5. 版式海报下载；可选 AI 图。
6. 线索新建与状态变更；工作台待跟进。
7. 知识库只读/读写符合角色。
8. `docker compose` 冷启动后主流程可走通。
9. 仓库中无真实 API Key；`.env.example` 仅变量名。
10. UI 基于 Element Plus；主流程页面在桌面与手机宽度下均可操作（响应式验收）。

## 13. 与现有仓库的关系

- 保留并继续维护 `one-class-operations-guide.html` 及现有 Pages 部署。
- 本平台以 `frontend/`、`backend/` 等新目录加入同一 monorepo（或约定子目录），不覆盖手册。
- 工具站与手册站点可不同端口或不同域名。

## 14. 决策记录（摘要）

| 主题 | 决定 |
|------|------|
| 用户范围 | 先壹号教室，预留扩展 |
| V1 模块 | 素材、文案、海报、线索、知识库、登录角色 |
| 文案 | 自定义 + 推荐模板 + 可选大模型 |
| 海报 | 版式默认 + 可选 AI 生图 |
| 登录 | 账号密码 |
| 前端 | Vue + TS 模块化 |
| UI 框架 | Element UI 体系（Vue 3 使用 Element Plus） |
| 页面 | 响应式（桌面后台 + 手机/窄屏可用） |
| 后端 | Python（FastAPI）模块化 |
| 数据库 | SQLite 起步，可迁 PostgreSQL；不用 MongoDB |
| 文件 | 本地目录起步，可换对象存储 |
| 设备 | 电脑后台 + 老师手机上传 |
| 总体方案 | monorepo 前后端分离 + Docker Compose |

## 15. 后续步骤

1. 用户审阅并批准本规格。
2. 使用 writing-plans 技能编写分任务实现计划。
3. 按计划实现 V1（建议 TDD / 按模块交付）。
