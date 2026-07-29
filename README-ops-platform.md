# 壹号教室运营工具平台 — 运行说明（登录 / 用户）

当前已交付：

- **账号密码登录**、演示种子账号、管理员建号（必填密码）、重置密码、修改密码
- **素材模块**：老师手机上传（图+文+授权）、我的素材；运营/负责人素材列表与状态处理
- **Element Plus** 响应式界面

## 演示账号（开发默认）

| 用户名 | 密码 | 角色 |
|--------|------|------|
| `admin` | `admin123` | 负责人 |
| `ops` | `ops123` | 运营 |
| `teacher1` | `t123` | 老师 |

生产环境请修改密码或通过环境变量覆盖（见 `.env.example`）。

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

浏览器打开 Vite 提示的地址（默认 `http://127.0.0.1:5173`）。开发代理会把 `/api` 转到 `8000`。

## 使用要点

1. **新建运营/老师账号**：负责人登录 → 用户管理 → 新建用户 → **必须填初始密码**（可点「生成」）→ 创建成功后弹窗**只展示一次**账号密码，请复制后告知对方。
2. **忘记密码**：登录页点「忘记密码」查看说明；负责人在用户管理中「重置密码」，新密码同样只展示一次。
3. **自己改密**：顶栏头像菜单 → 修改密码。
4. **老师交素材**：`teacher1` 登录 → 上传页填说明、选授权、选图片 → 提交 →「我的素材」可见。
5. **运营处理**：`ops` 登录 → 工作台/素材 → 查看详情 → 标为可用 / 确认授权。

## 测试

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
pytest -v
```
