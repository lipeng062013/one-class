#!/usr/bin/env bash
# 将 data/（及可选 .env）打包上传到阿里云 OSS
# 依赖：ossutil（见 scripts/setup/install-ossutil.sh）
# 配置：项目根目录 .env 中的 OSS_* 变量
set -euo pipefail

APP_DIR="${DEPLOY_PATH:-$(cd "$(dirname "$0")/../.." && pwd)}"
cd "$APP_DIR"

load_env() {
  local key="$1"
  local line
  if [[ -f "$APP_DIR/.env" ]]; then
    line=$(grep -E "^${key}=" "$APP_DIR/.env" | tail -n1 || true)
    if [[ -n "${line}" ]]; then
      echo "${line#*=}" | sed 's/\r$//' | sed 's/^["'\'']//;s/["'\'']$//'
    fi
  fi
}

OSS_ENDPOINT="${OSS_ENDPOINT:-$(load_env OSS_ENDPOINT)}"
OSS_ACCESS_KEY_ID="${OSS_ACCESS_KEY_ID:-$(load_env OSS_ACCESS_KEY_ID)}"
OSS_ACCESS_KEY_SECRET="${OSS_ACCESS_KEY_SECRET:-$(load_env OSS_ACCESS_KEY_SECRET)}"
OSS_BUCKET="${OSS_BUCKET:-$(load_env OSS_BUCKET)}"
OSS_PREFIX="${OSS_PREFIX:-$(load_env OSS_PREFIX)}"
OSS_PREFIX="${OSS_PREFIX:-one-class/backups/}"
# 是否把 .env 打进包（含密钥，桶必须私有）
BACKUP_INCLUDE_ENV="${BACKUP_INCLUDE_ENV:-$(load_env BACKUP_INCLUDE_ENV)}"
BACKUP_INCLUDE_ENV="${BACKUP_INCLUDE_ENV:-1}"

if [[ -z "$OSS_ENDPOINT" || -z "$OSS_ACCESS_KEY_ID" || -z "$OSS_ACCESS_KEY_SECRET" || -z "$OSS_BUCKET" ]]; then
  echo "[backup] OSS 未配置完整（需要 OSS_ENDPOINT / OSS_ACCESS_KEY_ID / OSS_ACCESS_KEY_SECRET / OSS_BUCKET）"
  echo "[backup] 请编辑 $APP_DIR/.env 后重试。参见 docs/ops-auto-deploy.md"
  exit 2
fi

if ! command -v ossutil >/dev/null 2>&1; then
  echo "[backup] 未找到 ossutil。请先执行: bash scripts/setup/install-ossutil.sh"
  exit 3
fi

STAMP=$(date +%Y%m%d-%H%M%S)
HOST_TAG=$(hostname -s 2>/dev/null || echo host)
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT

ARCHIVE="one-class-backup-${HOST_TAG}-${STAMP}.tar.gz"
ARCHIVE_PATH="$WORK/$ARCHIVE"
STAGE="$WORK/stage"
mkdir -p "$STAGE"

echo "[backup] 打包 data/ ..."
if [[ ! -d "$APP_DIR/data" ]]; then
  mkdir -p "$APP_DIR/data"
  echo "[backup] 已创建空 data/"
fi
cp -a "$APP_DIR/data" "$STAGE/data"

if [[ "$BACKUP_INCLUDE_ENV" == "1" && -f "$APP_DIR/.env" ]]; then
  cp "$APP_DIR/.env" "$STAGE/env.backup"
  echo "[backup] 已包含 .env → env.backup（请确保 OSS 桶为私有）"
fi

tar -czf "$ARCHIVE_PATH" -C "$STAGE" .
SIZE=$(du -h "$ARCHIVE_PATH" | awk '{print $1}')
echo "[backup] 包大小: $SIZE → oss://$OSS_BUCKET/${OSS_PREFIX}${ARCHIVE}"

export OSS_ACCESS_KEY_ID
export OSS_ACCESS_KEY_SECRET

ossutil cp "$ARCHIVE_PATH" "oss://${OSS_BUCKET}/${OSS_PREFIX}${ARCHIVE}" \
  -e "$OSS_ENDPOINT" \
  -i "$OSS_ACCESS_KEY_ID" \
  -k "$OSS_ACCESS_KEY_SECRET" \
  --force

echo "[backup] 上传成功: oss://${OSS_BUCKET}/${OSS_PREFIX}${ARCHIVE}"
echo "[backup] 恢复示例: bash scripts/backup/restore-from-oss.sh oss://${OSS_BUCKET}/${OSS_PREFIX}${ARCHIVE}"
