# 壹号教室运营工具平台 — 运行说明

Vue 3 + **Element Plus** 前端，FastAPI 后端。当前 `master` 为统一入口；历史实现曾在 `.worktrees/feat-ops-platform` 分支，业务 API 已合入本仓库并用 Element Plus 重做页面。

## 已交付模块

| 模块 | 说明 |
|------|------|
| 登录 / 用户 | 账号密码、演示账号、建号必填密码、管理员重置、改密 |
| 工作台 | 待处理素材、今日线索、文案数量、快捷入口 |
| 素材 | 老师手机上传；运营列表/详情/状态与授权 |
| 文案 | 模板生成、可选 LLM 润色、列表复制 |
| 海报 | 版式 PNG 导出、可选 AI 生图、下载 |
| 线索 | 新建/状态跟进、今日跟进高亮 |
| 知识库 | 分类条目；admin 可写，operator 只读 |
| 模板 | 文案模板 / 海报模板管理 |
| UI | 全站 **Element Plus**，桌面侧栏 + 老师端底栏，响应式 |

运营手册 `one-class-operations-guide.html` 仍独立发布，不在本平台内。

## 演示账号（开发默认）

| 用户名 | 密码 | 角色 |
|--------|------|------|
| `admin` | `admin123` | 负责人 |
| `ops` | `ops123` | 运营 |
| `teacher1` | `t123` | 老师 |

生产请修改密码或用环境变量覆盖（见 `.env.example`）。

## 启动后端

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
uvicorn app.main:app --reload --port 8000
```

健康检查：`http://127.0.0.1:8000/api/v1/health`

## 启动前端

```powershell
cd frontend
npm install
npm run dev
```

浏览器打开 Vite 地址（默认 `http://127.0.0.1:5173`）。开发代理会把 `/api` 转到 `8000`。

## 使用要点

1. **建号**：负责人 → 用户管理 → 新建 → **必填初始密码** → 弹窗只展示一次，请复制告知对方。  
2. **忘记密码**：登录页说明；负责人「重置密码」，新密码只展示一次。  
3. **改密**：顶栏头像 → 修改密码。  
4. **老师交素材**：`teacher1` → 上传 → 我的素材。  
5. **运营闭环**：`ops` → 素材标可用 → 生成文案/海报 → 登记线索 → 维护知识库（只读）/ 自定义模板。

## 主要路由

**电脑后台（admin / operator）**

- `/` 工作台  
- `/materials`、`/materials/:id`  
- `/copies`、`/copies/generate`  
- `/posters`、`/posters/generate`  
- `/leads`、`/knowledge`、`/templates`  
- `/users`（仅 admin）

**老师手机**

- `/m/upload`、`/m/materials`

## 测试

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
pytest -v
```

```powershell
cd frontend
npm run build
```

## 目录说明

```text
backend/     FastAPI API、模型、种子数据
frontend/    Vue3 + Element Plus
docs/        设计规格与实现计划
.worktrees/  历史 worktree（可忽略；功能已合入 master）
```

## 与旧分支的关系

- `feat/ops-platform` worktree：早期无 Element 的完整业务实现，**请以 master 为准**。  
- 重复占位页（如老师端空壳 `MobileHomeView`）已删除，统一走 `MobileUploadView` / `MobileMaterialsView`。  
