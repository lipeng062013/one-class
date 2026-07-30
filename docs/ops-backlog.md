# 嘉壹启航 · 运维待办日志

> 记录上线后待办，避免遗忘。完成一项把状态改为 ✅ 并在变更记录写一笔。  
> **最后更新：** 2026-07-30

---

## 当前优先级

| 优先级 | 主题 | 状态 |
|--------|------|------|
| **P0** | GitHub push → 阿里云自动部署（SSH + OSS） | 🟡 代码已落地，待你配置 Secrets/OSS 并验证 |
| **P1** | 数据库分离、迁移与拷贝 | ⬜ 暂缓（自动部署验证后再做） |
| **P1** | 生产安全加固 | ⬜ 待做 |
| **P2** | 域名 HTTPS、AI 配置、业务文件直传 OSS | ⬜ 待做 |

---

## 1. 已完成

| ID | 事项 | 完成日 | 备注 |
|----|------|--------|------|
| OPS-00 | 购买阿里云轻量 2核2G（上海，Ubuntu 24.04） | 2026-07-30 | 公网约 `8.133.179.238` |
| OPS-01 | 防火墙放行 8080 | 2026-07-30 | 应用类型：自定义 / TCP |
| OPS-02 | 安装 Docker + Compose（apt：docker.io） | 2026-07-30 | get.docker.com 国内不通 |
| OPS-03 | 配置 2G Swap | 2026-07-30 | `/swapfile` |
| OPS-04 | 配置 Docker 镜像加速 | 2026-07-30 | daocloud / 1ms.run |
| OPS-05 | 首次 `docker compose` 部署跑通 | 2026-07-30 | 路径 `/opt/one-class`；入口 `:8080` |
| OPS-06 | 后端 pip / 前端 npm 国内源 | 2026-07-30 | 服务器 Dockerfile 已改；本机同步后需 push |

---

## 2. 进行中 / 待你操作

| ID | 事项 | 状态 | 说明 |
|----|------|------|------|
| **OPS-10** | 自动化部署（GitHub Actions + **SSH**） | 🟡 | 仓库已加 `deploy-server.yml` + `scripts/deploy/`；需配 Secrets 并 push 验证。手册：`docs/ops-auto-deploy.md` |
| **OPS-12** | **OSS 备份**（部署前 + 可选定时） | 🟡 | 脚本 `scripts/backup/*`、`.env` 中 `OSS_*`；桶私有。业务上传仍本地，直传 OSS 为 S3 阶段 |
| OPS-11 | 本机 push 含 Dockerfile 国内源，与服务器对齐 | 🟡 | 随首次自动部署 `git reset --hard` 对齐 |
| OPS-13 | 分清 Linux 用户 `admin` vs 网站账号 `admin` | ✅ | 见 `docs/ops-auto-deploy.md` §0 |
| OPS-14 | 服务器放入真实 `.env`（scp/nano，不进 Git） | ⬜ | 含 JWT、密码、OSS 凭证 |

---

## 3. 暂缓：数据库分离 / 迁移拷贝（P1，自动部署后再做）

| ID | 事项 | 状态 | 说明 |
|----|------|------|------|
| OPS-20 | 明确「分离」目标 | ⬜ | 例：SQLite → PostgreSQL；或 data 卷与代码目录分离；或本机/服务器数据互拷 |
| OPS-21 | 设计迁移方案（Alembic / 导出导入） | ⬜ | 设计规格里已写 SQLAlchemy + Alembic，当前多为 `create_all` |
| OPS-22 | 上传文件（uploads）与 DB 一并迁移策略 | ⬜ | `data/` 含 `app.db` + `uploads/` |
| OPS-23 | 本机 → 服务器 / 服务器 → 本机 拷贝流程文档 | ⬜ | 避免覆盖生产数据 |
| OPS-24 | docker-compose 可选 Postgres 服务 | ⬜ | 视 OPS-20 结论 |

---

## 4. 生产安全（建议自动部署前后尽快做）

| ID | 事项 | 状态 | 说明 |
|----|------|------|------|
| OPS-30 | 修改演示账号密码 | ⬜ | 勿长期使用 `admin123` 等 |
| OPS-31 | 更换 `JWT_SECRET` | ⬜ | `openssl rand -hex 32` |
| OPS-32 | 确认 8000 不对公网开放 | ⬜ | 仅 22 + 8080（日后 80/443） |
| OPS-33 | SSH 强密码或密钥登录 | ⬜ | 阿里云密钥对 |
| OPS-34 | `.env` 永不进 Git | ⬜ | 已在 `.gitignore`；服务器本地维护 |

---

## 5. 体验与运维增强（P2）

| ID | 事项 | 状态 | 说明 |
|----|------|------|------|
| OPS-40 | 配置 `LLM_*` / `IMAGE_*` | ⬜ | 需要 AI 文案/海报时 |
| OPS-41 | `data/` + `.env` 定期备份到 OSS | 🟡 | 脚本已有；配好 OSS 后加 crontab（见手册 §3.4） |
| OPS-41b | 业务文件存 OSS（素材/海报/学情，后端代理） | 🟡 | 代码已支持 `STORAGE_BACKEND=oss`；服务器配好后改为 oss 并重建 |
| OPS-42 | 域名解析到服务器 | ⬜ | |
| OPS-43 | HTTPS（80/443 + 证书） | ⬜ | |
| OPS-44 | 入口改为 80 免端口 | ⬜ | 依赖域名或直接改映射 |
| OPS-45 | 续费提醒 | ⬜ | 轻量到期约 2027-07-30 |
| OPS-46 | 资源吃紧时升配 2核4G | ⬜ | 按实际负载 |

---

## 6. 服务器速查

| 项 | 值 |
|----|-----|
| 地域 | 华东2（上海） |
| 系统 | Ubuntu 24.04 |
| 规格 | 2 vCPU / 2 GiB / 40 GiB |
| 项目目录 | `/opt/one-class` |
| 访问 | `http://<公网IP>:8080` |
| 数据 | `/opt/one-class/data/`（SQLite + uploads） |
| 环境变量 | `/opt/one-class/.env`（勿提交） |
| 常用命令 | `cd /opt/one-class && docker compose ps` / `logs` / `up -d --build` |

---

## 7. 变更记录

| 日期 | 内容 |
|------|------|
| 2026-07-30 | 初建日志：记录首发上线完成项；P0=自动部署；P1=库分离/迁移；安全与备份等列入待办 |
| 2026-07-30 | 落地自动部署：SSH Actions + OSS 备份脚本/手册；明确 Linux admin ≠ 网站 admin；DEPLOY_PATH 可配置 |
