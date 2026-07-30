#!/usr/bin/env bash
# 在服务器上执行：备份(可选) → pull → compose 构建启动 → 健康检查
# 由 GitHub Actions 经 SSH 调用，也可手动：bash scripts/deploy/remote-deploy.sh
set -euo pipefail

APP_DIR="${DEPLOY_PATH:-/opt/one-class}"
BRANCH="${DEPLOY_BRANCH:-master}"
SKIP_BACKUP="${SKIP_BACKUP:-0}"
HEALTH_URL="${HEALTH_URL:-http://127.0.0.1:8080/api/v1/health}"
HEALTH_RETRIES="${HEALTH_RETRIES:-30}"
HEALTH_SLEEP="${HEALTH_SLEEP:-2}"

log() { echo "[deploy $(date '+%Y-%m-%d %H:%M:%S')] $*"; }

if [[ ! -d "$APP_DIR" ]]; then
  log "ERROR: 目录不存在: $APP_DIR"
  log "请确认 GitHub Secret DEPLOY_PATH 与服务器上项目路径一致。"
  exit 1
fi

cd "$APP_DIR"
log "工作目录: $APP_DIR (user=$(id -un))"

# ---- 1. 部署前备份到 OSS（失败默认不阻断；设 BACKUP_REQUIRED=1 则失败即退出）----
if [[ "$SKIP_BACKUP" != "1" && -x "$APP_DIR/scripts/backup/backup-to-oss.sh" ]]; then
  log "部署前备份 → OSS ..."
  if bash "$APP_DIR/scripts/backup/backup-to-oss.sh"; then
    log "备份完成"
  else
    if [[ "${BACKUP_REQUIRED:-0}" == "1" ]]; then
      log "ERROR: 备份失败且 BACKUP_REQUIRED=1，中止部署"
      exit 1
    fi
    log "WARN: 备份失败或未配置 OSS，继续部署（生产建议配好 OSS 并设 BACKUP_REQUIRED=1）"
  fi
elif [[ "$SKIP_BACKUP" == "1" ]]; then
  log "已跳过备份 (SKIP_BACKUP=1)"
else
  log "未找到可执行备份脚本，跳过备份"
fi

# ---- 2. 更新代码（不触碰 .env / data/）----
log "git fetch + reset 到 origin/$BRANCH ..."
git fetch origin "$BRANCH"
# 用 reset 保证与远端一致；本地未提交的服务器改动会被丢掉（应以仓库为准）
git checkout "$BRANCH"
git reset --hard "origin/$BRANCH"

# ---- 3. 构建并启动 ----
if [[ ! -f .env ]]; then
  log "ERROR: 缺少 $APP_DIR/.env"
  log "请先把本机 .env 拷到服务器（scp 或 nano），不要把真实密钥提交到 Git。"
  exit 1
fi

log "docker compose up -d --build ..."
docker compose up -d --build

# ---- 4. 健康检查 ----
log "等待健康检查: $HEALTH_URL"
ok=0
for i in $(seq 1 "$HEALTH_RETRIES"); do
  if curl -fsS "$HEALTH_URL" >/dev/null 2>&1; then
    ok=1
    break
  fi
  sleep "$HEALTH_SLEEP"
done

if [[ "$ok" != "1" ]]; then
  log "ERROR: 健康检查失败"
  docker compose ps || true
  docker compose logs --tail=80 || true
  exit 1
fi

log "部署成功"
docker compose ps
curl -fsS "$HEALTH_URL" || true
echo
