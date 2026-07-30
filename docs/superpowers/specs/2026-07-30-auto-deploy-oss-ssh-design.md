# 设计：GitHub 自动部署 + SSH + OSS 备份

**日期：** 2026-07-30  
**状态：** 已落地（见 `.github/workflows/deploy-server.yml` 与 `scripts/`）  
**关联：** [ops-backlog](../../ops-backlog.md) · [操作手册](../../ops-auto-deploy.md)

---

## 1. 目标

1. `master` 分支 push（或手动 Run workflow）后，自动更新阿里云轻量上的 Docker 业务。
2. 从第一天起接入 **SSH**（部署通道）与 **OSS**（数据备份），避免日后返工。
3. **不**把真实 `.env` 与 `data/` 放进 Git；服务器本地保留，部署不覆盖。

---

## 2. 名词澄清（避免混淆）

| 名称 | 是什么 | 不是什么 |
|------|--------|----------|
| **Linux 用户 `admin`** | 阿里云轻量系统登录用户（终端里 `admin@iZuf...`） | 不是网站里的「负责人」账号 |
| **应用账号 `admin`** | `.env` 里 `SEED_ADMIN_USERNAME`，登录网页用 | 不能用来 SSH 登录服务器 |
| **`/opt/one-class`** | 当前服务器上的项目目录（首次 `git clone` 的位置） | 不是强制；可改，但 Secrets 里 `DEPLOY_PATH` 要一致 |
| **SSH** | 远程登录/自动部署通道 | 不是对象存储 |
| **OSS** | 阿里云对象存储，存备份包（及日后可选的上传文件） | 不是用来 SSH 的 |

若服务器用户或目录不同：以 **实际 SSH 登录名** 和 **`pwd` 看到的项目路径** 为准，写入 GitHub Secrets。

---

## 3. 架构

```text
开发者 git push master
        │
        ▼
GitHub Actions (deploy-server.yml)
        │  Secrets: SSH_HOST / SSH_USER / SSH_PRIVATE_KEY [/ SSH_PORT / DEPLOY_PATH]
        ▼
SSH ──────────────────────────► 阿里云 Ubuntu
                                  │
                                  ├─ 1) scripts/backup/backup-to-oss.sh
                                  │      data/ (+ 可选 .env) → tar.gz → OSS
                                  ├─ 2) git pull origin master
                                  ├─ 3) docker compose up -d --build
                                  └─ 4) curl 本机健康检查 :8080 / :8000
```

### 职责划分

| 组件 | 职责 |
|------|------|
| GitHub Actions | 触发、SSH 执行远程脚本、展示日志 |
| SSH | 唯一自动化运维入口（部署、可扩展为远程诊断） |
| 服务器 `remote-deploy.sh` | 备份 → 拉代码 → 构建启动 → 健康检查 |
| OSS | 部署前/定时备份；恢复演练；**暂不**改业务上传路径（`STORAGE_ROOT` 仍本地，接口预留） |
| 服务器 `.env` | 运行时密钥 + OSS 凭证；只存在于服务器（及本机开发副本） |

---

## 4. 安全约定

- 部署用 **专用 SSH 密钥**（仅 `deploy` 用途），私钥只进 GitHub Secrets，不进仓库。
- OSS AccessKey 只写在服务器 `.env`（权限尽量「单桶读写」）。
- 备份含业务数据；OSS 桶建议 **私有**，不开公共读。
- 自动部署 **禁止** `docker compose down -v` 或删除 `data/`。

---

## 5. 分阶段（一次设计、分步启用）

| 阶段 | 内容 | 何时 |
|------|------|------|
| **S1（本次）** | Actions + SSH 自动部署；OSS 备份脚本与 `.env` 配置项；操作文档 | 立即 |
| **S2** | 服务器 crontab 每日备份到 OSS | 配好 OSS 后 |
| **S3** | 业务上传改走 OSS（`STORAGE_ROOT` / 存储抽象） | 素材量大或多机时 |
| **S4** | 数据库分离（Postgres 等）+ 迁移拷贝 | backlog OPS-20+ |

S3/S4 不阻塞 S1；但配置项与脚本目录一次到位，减少以后拆改。

---

## 6. 成功标准

- [ ] push `master` 后 Actions 变绿，公网 `:8080` 为新版本  
- [ ] 部署过程不删除、不重置 `data/` 与 `.env`  
- [ ] 配置 OSS 后，执行备份脚本能在桶中看到带时间戳的包  
- [ ] 文档能让小白分清：系统用户 / 应用 admin / 路径 / SSH / OSS  
