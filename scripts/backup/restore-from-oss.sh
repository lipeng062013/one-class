#!/usr/bin/env bash
# 从 OSS 下载备份包并恢复到 data/（默认先再备份当前 data，防误操作）
# 用法:
#   bash scripts/backup/restore-from-oss.sh oss://bucket/one-class/backups/xxx.tar.gz
#   RESTORE_ENV=1 bash ...   # 同时恢复 env.backup → .env（慎用）
set -euo pipefail

OSS_URI="${1:-}"
if [[ -z "$OSS_URI" ]]; then
  echo "用法: $0 oss://<bucket>/<path/to/backup.tar.gz>"
  exit 1
fi

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

if [[ -z "$OSS_ENDPOINT" || -z "$OSS_ACCESS_KEY_ID" || -z "$OSS_ACCESS_KEY_SECRET" ]]; then
  echo "[restore] 请在 .env 配置 OSS_ENDPOINT / OSS_ACCESS_KEY_ID / OSS_ACCESS_KEY_SECRET"
  exit 2
fi

if ! command -v ossutil >/dev/null 2>&1; then
  echo "[restore] 未找到 ossutil。请先: bash scripts/setup/install-ossutil.sh"
  exit 3
fi

WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
LOCAL_TGZ="$WORK/backup.tar.gz"

echo "[restore] 下载 $OSS_URI ..."
ossutil cp "$OSS_URI" "$LOCAL_TGZ" \
  -e "$OSS_ENDPOINT" \
  -i "$OSS_ACCESS_KEY_ID" \
  -k "$OSS_ACCESS_KEY_SECRET" \
  --force

# 恢复前本地再留一份
if [[ -d "$APP_DIR/data" ]]; then
  SAFETY="$APP_DIR/data.safety-$(date +%Y%m%d-%H%M%S).tar.gz"
  echo "[restore] 当前 data/ 安全副本: $SAFETY"
  tar -czf "$SAFETY" -C "$APP_DIR" data
fi

echo "[restore] 解压到 $APP_DIR ..."
tar -xzf "$LOCAL_TGZ" -C "$APP_DIR"

if [[ "${RESTORE_ENV:-0}" == "1" && -f "$APP_DIR/env.backup" ]]; then
  cp "$APP_DIR/env.backup" "$APP_DIR/.env"
  rm -f "$APP_DIR/env.backup"
  echo "[restore] 已恢复 .env"
elif [[ -f "$APP_DIR/env.backup" ]]; then
  echo "[restore] 包内有 env.backup，未自动覆盖 .env（需要时: RESTORE_ENV=1）"
fi

echo "[restore] 完成。建议执行: cd $APP_DIR && docker compose up -d"
