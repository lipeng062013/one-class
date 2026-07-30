# 自动部署手册：GitHub → SSH → 阿里云 + OSS 备份

面向小白的逐步说明。设计背景见 [specs/2026-07-30-auto-deploy-oss-ssh-design.md](./superpowers/specs/2026-07-30-auto-deploy-oss-ssh-design.md)。

---

## 0. 先分清几个「名字」

| 你听到的 | 实际含义 | 例子 |
|----------|----------|------|
| **SSH 用户 / Linux 用户** | 登录服务器的系统账号 | 终端提示符 `admin@iZuf6460c...` 里的 **`admin`** |
| **网站 admin** | 浏览器登录运营平台的账号 | `.env` 里 `SEED_ADMIN_USERNAME=admin`，密码 `SEED_ADMIN_PASSWORD` |
| **部署目录** | 服务器上项目代码所在文件夹 | 当前是 **`/opt/one-class`**（你第一次 `git clone` 的位置） |
| **SSH** | 远程登录/自动部署用的通道 | GitHub Actions 靠它连你的机器执行命令 |
| **OSS** | 阿里云对象存储 | 用来存 **备份包**（数据库文件 + 上传图），防止磁盘坏了或误删 |

> 之前说「如果部署目录不是 `/opt/one-class`、用户不是 `admin`」——意思是：  
> **以你服务器上真实情况为准**。若你 clone 到了 `/home/admin/one-class`，或 SSH 用户叫 `root`，只要在 GitHub Secrets 里写成真实值即可，不是必须叫 admin、必须在 /opt。

---

## 1. `.env` 怎么放到服务器（只做一次）

**不要**把真实 `.env` 提交到 GitHub。

### 推荐：本机 scp 上传

在 **本机 PowerShell**（路径按你电脑修改）：

```powershell
scp "D:\one class\.env" admin@8.133.179.238:/opt/one-class/.env
```

- `admin` → 你的 **Linux SSH 用户**  
- `8.133.179.238` → 你的公网 IP  
- `/opt/one-class/.env` → 服务器项目里的环境文件  

上传后 SSH 登录检查：

```bash
cd /opt/one-class
ls -la .env
# 按需编辑（JWT、密码、OSS 等）
nano .env
docker compose up -d
```

### 或者：服务器上 nano 手敲

对照本机 `.env`，在服务器 `nano /opt/one-class/.env` 填写。可用仓库里的 `.env.example` 作模板。

---

## 2. 配置 SSH（自动部署用）

在 **服务器** 上为 GitHub Actions 准备一把**专用**密钥（不要用你日常密码登录的那套思路混用即可；专用更清晰）。

### 2.1 生成部署密钥（在服务器执行）

```bash
ssh-keygen -t ed25519 -C "github-actions-deploy" -f ~/.ssh/github_actions_deploy -N ""
cat ~/.ssh/github_actions_deploy.pub >> ~/.ssh/authorized_keys
chmod 700 ~/.ssh
chmod 600 ~/.ssh/authorized_keys ~/.ssh/github_actions_deploy
```

### 2.2 查看私钥（稍后粘贴到 GitHub）

```bash
cat ~/.ssh/github_actions_deploy
```

复制 **整段**（含 `BEGIN` / `END` 行）。  
**不要**把私钥发到公开聊天或提交进 Git。

### 2.3 确认 docker 权限

```bash
# 当前 Linux 用户需要能跑 docker（你之前已 usermod -aG docker）
docker ps
```

若必须 `sudo docker`，需要把用户加进 docker 组后重新登录。

---

## 3. 配置阿里云 OSS（备份用）

### 3.1 控制台操作

1. 阿里云 → **对象存储 OSS** → 创建 **Bucket**  
2. 地域尽量与轻量一致（如 **华东2 上海**）  
3. 读写权限：**私有**  
4. 创建 **RAM 用户**（推荐）只授该 Bucket 的 `oss:PutObject` / `GetObject` / `ListObjects` 等，拿到 AccessKey ID/Secret  

### 3.2 写入服务器 `.env`

```env
OSS_ENDPOINT=oss-cn-shanghai.aliyuncs.com
OSS_ACCESS_KEY_ID=你的AK
OSS_ACCESS_KEY_SECRET=你的SK
OSS_BUCKET=你的桶名
OSS_PREFIX=one-class/backups/
BACKUP_INCLUDE_ENV=1
```

Endpoint 以控制台「外网 Endpoint」为准（一般不带 `https://`）。

### 3.3 安装 ossutil 并试备份

```bash
cd /opt/one-class
bash scripts/setup/install-ossutil.sh
bash scripts/backup/backup-to-oss.sh
```

成功会打印 `oss://桶名/one-class/backups/one-class-backup-....tar.gz`。

### 3.4 （可选）每天定时备份

```bash
crontab -e
```

加一行（每天 3:15）：

```cron
15 3 * * * DEPLOY_PATH=/opt/one-class /opt/one-class/scripts/backup/backup-to-oss.sh >> /opt/one-class/data/backup.log 2>&1
```

### 3.5 恢复（以后需要时）

```bash
cd /opt/one-class
bash scripts/backup/restore-from-oss.sh oss://你的桶/one-class/backups/某个文件.tar.gz
docker compose up -d
```

---

## 4. 配置 GitHub Secrets

打开：`https://github.com/lipeng062013/one-class` → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

| Name | 值 | 必填 |
|------|-----|------|
| `SSH_HOST` | 公网 IP，如 `8.133.179.238` | 是 |
| `SSH_USER` | Linux 用户，如 `admin` | 是 |
| `SSH_PRIVATE_KEY` | 上面 `cat ~/.ssh/github_actions_deploy` 的**整段私钥** | 是 |
| `SSH_PORT` | 默认 `22`，改过 SSH 端口再填 | 否 |
| `DEPLOY_PATH` | 默认可填 `/opt/one-class`；不填则脚本内默认也是该路径 | 建议填 |

可选 **Variables**（不是 Secret）：

| Name | 值 | 含义 |
|------|-----|------|
| `BACKUP_REQUIRED` | `1` | 备份失败则**中止**部署（OSS 配好后建议开启） |

---

## 5. 推送代码触发自动部署

1. 本机确保改动已提交（含 `scripts/`、`.github/workflows/deploy-server.yml`、Dockerfile 国内源等）  
2. `git push origin master`  
3. GitHub → **Actions** → **Deploy to Server** 查看是否绿色  
4. 浏览器打开 `http://你的IP:8080` 验证  

也可在 Actions 里 **Run workflow** 手动部署；可勾选跳过备份（`skip_backup=1`）。

服务器上等价于执行：

```bash
cd /opt/one-class   # 或你的 DEPLOY_PATH
bash scripts/deploy/remote-deploy.sh
```

---

## 6. 自动部署会动什么、不会动什么

| 会更新 | 不会动 |
|--------|--------|
| Git 代码、Dockerfile | **`.env`** |
| Docker 镜像与容器 | **`data/`**（SQLite、上传文件） |
| （若配置）OSS 上多一个备份包 | 防火墙、系统用户 |

---

## 7. 常见问题

| 现象 | 处理 |
|------|------|
| Actions 报 Permission denied (publickey) | 公钥是否写入 `authorized_keys`；Secret 私钥是否完整 |
| 健康检查失败 | 服务器 `docker compose logs`；防火墙 8080 |
| 备份 exit 2 | `.env` 里 OSS 四项是否齐全 |
| 备份 exit 3 | `bash scripts/setup/install-ossutil.sh` |
| git pull 冲突 | 远程脚本使用 `reset --hard origin/master`，以仓库为准；不要在服务器上长期手改代码 |
| 网站 admin 登不上 | 改的是应用密码，与 SSH 用户无关 |

---

## 8. 业务文件进 OSS（素材 / 海报 / 学情附件）

与「整包备份」共用同一套 `OSS_ENDPOINT` / AK / `OSS_BUCKET`，前缀不同：

| 用途 | 配置 | 前缀示例 |
|------|------|----------|
| 整包备份脚本 | `OSS_PREFIX` | `one-class/backups/` |
| 业务上传 | `OSS_UPLOAD_PREFIX` + `STORAGE_BACKEND=oss` | `one-class/uploads/` |

服务器 `.env` 增加（在已有 OSS 四项之外）：

```env
STORAGE_BACKEND=oss
OSS_UPLOAD_PREFIX=one-class/uploads/
```

然后重新部署后端（`docker compose up -d --build` 或自动部署）。

- 新上传的素材、新生成的海报、学情附件会写入 OSS。  
- 网页预览仍走后端 API（桶保持私有，无需前端直链）。  
- 旧文件若还在磁盘：读取时 **OSS 没有则回退本地**。  
- 设计说明：`docs/superpowers/specs/2026-07-30-oss-object-storage-design.md`

本地开发保持 `STORAGE_BACKEND=local` 即可，不必连 OSS。

---

## 9. 和「数据库分离」的关系

- **现在：** 业务元数据仍在服务器 `data/app.db`；图可在 OSS；靠 **OSS 备份脚本** 保 DB（及可选本地残留 uploads）。  
- **以后：** 迁 PostgreSQL 时，仍可先 `backup-to-oss`，再导入新库。  

见 [ops-backlog.md](./ops-backlog.md) 中 OPS-20 段。
