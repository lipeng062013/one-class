#!/usr/bin/env sh
# 将本仓库的 Git hooks 指向版本库内的 .githooks（含 pre-push TypeScript 检查）
# 用法（仓库根目录）: sh scripts/setup/install-git-hooks.sh

set -e
ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"

if [ ! -d .githooks ]; then
  echo "未找到 .githooks 目录" >&2
  exit 1
fi

# 保证 hook 为 LF，并在 Unix 上可执行
if [ -f .githooks/pre-push ]; then
  # 去掉可能的 CRLF
  if command -v sed >/dev/null 2>&1; then
    sed -i.bak 's/\r$//' .githooks/pre-push 2>/dev/null || true
    rm -f .githooks/pre-push.bak
  fi
  chmod +x .githooks/pre-push
fi

git config core.hooksPath .githooks
echo "已设置 core.hooksPath = .githooks"
echo "推送前将自动执行: frontend npm run typecheck"
git config core.hooksPath
