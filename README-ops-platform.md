# 嘉壹启航运营工具平台 — 运行说明

Vue 3 + **Element Plus** 前端，FastAPI 后端。当前以 **master** 为准。

## 已交付模块

| 模块 | 说明 |
|------|------|
| 登录 / 用户 | 账号密码、演示账号、建号必填密码、管理员重置、改密 |
| 工作台 | 可点统计卡片跳转；展示 AI 接入状态 |
| 素材 | 老师手机上传；运营列表/详情；**图片预览**；跳转生成文案/海报 |
| 文案 | 模板 / 模板+润色 / 大模型；未配置时提示与回退 |
| 海报 | 版式 PNG **预览+下载**；AI 生图需配置 IMAGE_* |
| 线索 | 新建；状态跟进；**日期时间选择器**设下次跟进 |
| 知识库 / 模板 | 分类维护；系统模板 + 自定义 |
| UI | Element Plus；桌面侧栏；**窄屏抽屉菜单** |

## 演示账号

| 用户名 | 密码 | 角色 |
|--------|------|------|
| `admin` | `admin123` | 负责人 |
| `ops` | `ops123` | 运营 |
| `teacher1` | `t123` | 老师 |

## 启动（开发：本机 Python + Node）

```powershell
# 后端
cd backend
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
uvicorn app.main:app --reload --port 8000

# 前端（另开终端）
cd frontend
npm install
npm run dev
```

- 前端：http://127.0.0.1:5173  
- 健康检查：http://127.0.0.1:8000/api/v1/health  
- AI 状态：`GET /api/v1/system/integrations`（登录后）

## 一键启动（Docker Compose，本机 / 服务器同一套）

适合不想分别装 Python、Node 的场景。本机验证通过后，服务器用**同一命令**即可。

### 前置

1. 安装 [Docker Desktop](https://www.docker.com/products/docker-desktop/)（Windows 需开启 WSL2 或 Hyper-V，按安装向导即可）
2. 项目根目录有 `.env`（没有则从示例复制）：

```powershell
cd E:\one-class
Copy-Item .env.example .env
# 按需编辑 .env：JWT_SECRET、LLM_*、IMAGE_* 等
```

### 启动

```powershell
cd E:\one-class
docker compose up --build
```

后台运行：

```powershell
docker compose up -d --build
```

| 入口 | 地址 |
|------|------|
| 网站（前端 + API 反代） | http://127.0.0.1:8080 |
| 后端直连 / 接口文档 | http://127.0.0.1:8000/docs |
| 健康检查 | http://127.0.0.1:8000/api/v1/health |

数据（SQLite、上传文件）在项目 `data/` 目录，容器重启不丢。

### 常用命令

```powershell
docker compose ps
docker compose logs -f
docker compose down          # 停掉容器（保留 data/）
docker compose down --rmi local  # 可选：顺带删本地构建的镜像
```

### 以后放到服务器

1. 服务器安装 Docker（Linux 用 Docker Engine 即可）
2. `git clone` 本仓库，放入服务器自己的 `.env`（**不要**提交真实 Key）
3. 同样执行：`docker compose up -d --build`
4. 访问 `http://服务器IP:8080`；需要再绑域名与 HTTPS 时，在前面加反向代理即可

本机与服务器共用：`docker-compose.yml`、`backend/Dockerfile`、`frontend/Dockerfile`、`frontend/nginx.conf`。

### 自动部署（GitHub push → 阿里云）+ OSS 备份

- **操作手册（小白逐步）：** [docs/ops-auto-deploy.md](docs/ops-auto-deploy.md)
- **待办日志：** [docs/ops-backlog.md](docs/ops-backlog.md)
- **Workflow：** `.github/workflows/deploy-server.yml`（`master` push 经 **SSH** 执行远程部署）
- **脚本：** `scripts/deploy/remote-deploy.sh`、`scripts/backup/backup-to-oss.sh`
- **注意：** Linux 登录用户（如 `admin@服务器`）≠ 网站登录账号 `admin`；`.env` 只放服务器/本机，不进 Git
## 可选 AI：为什么报错、怎么真正用上大模型

### 报错原因（你截图里的 503）

页面提示 `LLM unavailable: LLM not configured` / `503`，**不是前端坏了**，而是：

1. 项目里**没有**可用的 `.env`（或里面的 `LLM_BASE_URL` / `LLM_API_KEY` 为空）  
2. 后端启动时读不到密钥，调用大模型时判定「未配置」  
3. 旧逻辑对「直接大模型」直接返回 **503**（现已改为：回退模板/草稿，并中文说明）

海报 AI 同理，需要 `IMAGE_API_BASE_URL` + `IMAGE_API_KEY`。

### 怎么配置才能用大模型（必须你自己提供 Key）

本系统调用的是 **OpenAI 兼容 HTTP 接口**（官方 OpenAI、很多国内中转站都可以）：

| 用途 | 实际请求 |
|------|----------|
| 文案 | `{LLM_BASE_URL}/v1/chat/completions` |
| 海报 AI 图 | `{IMAGE_API_BASE_URL}/v1/images/generations` |

**步骤：**

1. 复制示例文件：

```powershell
cd "D:\one class"
Copy-Item .env.example .env
```

2. 用记事本编辑 `.env`，填入你的中转站或官方地址与密钥，例如：

```env
LLM_BASE_URL=https://api.openai.com
LLM_API_KEY=sk-你的密钥
LLM_MODEL=gpt-4o-mini

IMAGE_API_BASE_URL=https://api.openai.com
IMAGE_API_KEY=sk-你的密钥
IMAGE_MODEL=dall-e-3
```

aihub 等中转站示例（文案/生图可共用同一主机，模型名以中转站列表为准）：

```env
LLM_BASE_URL=https://aihub.top
LLM_API_KEY=sk-你的密钥
LLM_MODEL=gpt-5.6-sol

IMAGE_API_BASE_URL=https://aihub.top
IMAGE_API_KEY=sk-你的图片密钥
IMAGE_MODEL=gpt-image-2
```

注意：

- `LLM_BASE_URL` / `IMAGE_API_BASE_URL` **不要**写成带 `/v1/...` 的完整路径，只写主机根（代码会自动加路径）  
- 若用国内中转，把主机换成中转文档里的 Base URL；**图片模型名**须是该站支持的 image 模型（如 `gpt-image-2`），不能照搬 `dall-e-3`  
- **不要把真实 Key 提交到 Git**（`.env` 已在 `.gitignore`）

3. **必须重启后端**（改 env 后不重启不会生效）：

```powershell
cd "D:\one class\backend"
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --port 8000
```

4. 打开工作台，看「AI 接入状态」是否变为「已配置」；或登录后请求：  
   `GET /api/v1/system/integrations`

5. 文案选「模板+润色」或「直接大模型」；海报选「AI 生图」。

### 未配置时的行为（已修复，不再硬 503）

| 能力 | 未配置 / 上游失败 |
|------|-------------------|
| 文案「仅模板」 | 始终可用 |
| 文案「模板+润色」 | 回退模板，提示 `llm_error` |
| 文案「直接大模型」 | **回退模板/本地草稿**，提示如何配置（不再 503） |
| 海报「版式导出」 | 始终可用（Pillow） |
| 海报「AI 生图」 | **回退版式 PNG**，提示如何配置（需已选模板） |

我无法替你申请或填写真实 API Key；你把 Key 写入本地 `.env` 并重启后端后即可调用。

## 使用要点

1. 建号：用户管理 → 必填初始密码 → 弹窗只展示一次。  
2. 忘记密码：负责人重置密码。  
3. 老师 `teacher1` 上传素材 → 运营在素材详情预览图 → 生成文案/海报。  
4. 线索列表可直接改状态与下次跟进时间。  
5. 窄屏点左上角菜单打开抽屉导航。

## 测试

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
pytest -v

cd ..\frontend
npm run build
```

## 仓库说明

- 历史 worktree `.worktrees/feat-ops-platform` 已移除；功能在 master。  
- 运营手册 `one-class-operations-guide.html` 仍独立，不在本平台内。  
