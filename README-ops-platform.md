# 壹号教室运营工具平台 — 运行说明

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

## 启动

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

## 可选 AI（第 3 项）

在项目根或 `backend` 工作目录的 `.env` 中配置（参考 `.env.example`，**不要提交真实 Key**）：

```env
LLM_BASE_URL=https://your-openai-compatible-host
LLM_API_KEY=sk-...
LLM_MODEL=gpt-4o-mini

IMAGE_API_BASE_URL=https://your-openai-compatible-host
IMAGE_API_KEY=sk-...
IMAGE_MODEL=dall-e-3
```

行为约定：

| 能力 | 未配置 / 上游失败 |
|------|-------------------|
| 文案「仅模板」 | 始终可用 |
| 文案「模板+润色」 | 回退模板正文，并返回 `llm_error` |
| 文案「直接大模型」 | 接口 503；前端会提示改模式 |
| 海报「版式导出」 | 始终可用（Pillow） |
| 海报「AI 生图」 | 前端拦截提示；需 IMAGE_* |

改完 `.env` 后**重启后端**。工作台与生成页会显示是否已配置（不暴露密钥）。

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
