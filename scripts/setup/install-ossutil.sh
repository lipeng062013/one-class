#!/usr/bin/env bash
# 在 Ubuntu 服务器安装阿里云 ossutil（优先官方安装脚本）
set -euo pipefail

if command -v ossutil >/dev/null 2>&1; then
  echo "[setup] ossutil 已存在: $(command -v ossutil)"
  ossutil version || ossutil --version || true
  exit 0
fi

echo "[setup] 安装 ossutil ..."
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
cd "$TMP"

# 官方安装方式（若网络失败，文档中有备用链接）
if curl -fsSL https://gosspublic.alicdn.com/ossutil/install.sh -o install.sh; then
  chmod +x install.sh
  sudo bash install.sh || bash install.sh
else
  echo "[setup] 官方 install.sh 下载失败，尝试直接下 linux amd64 二进制"
  # ossutil 2.x 常见包名可能变化；失败时请按 docs/ops-auto-deploy.md 手动装
  curl -fL "https://gosspublic.alicdn.com/ossutil/1.7.19/ossutil-v1.7.19-linux-amd64.zip" -o ossutil.zip
  command -v unzip >/dev/null || sudo apt-get update && sudo apt-get install -y unzip
  unzip -o ossutil.zip
  BIN=$(find . -type f -name 'ossutil*' ! -name '*.zip' | head -n1)
  sudo install -m 755 "$BIN" /usr/local/bin/ossutil
fi

if ! command -v ossutil >/dev/null 2>&1; then
  # 有的安装脚本装到 /usr/local/bin
  export PATH="/usr/local/bin:$PATH"
fi

if command -v ossutil >/dev/null 2>&1; then
  echo "[setup] 安装成功: $(command -v ossutil)"
  ossutil version || ossutil --version || true
else
  echo "[setup] 安装失败，请查看 docs/ops-auto-deploy.md 手动安装"
  exit 1
fi
