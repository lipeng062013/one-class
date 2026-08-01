# 将本仓库的 Git hooks 指向版本库内的 .githooks（含 pre-push TypeScript 检查）
# 用法（仓库根目录）:
#   powershell -ExecutionPolicy Bypass -File scripts/setup/install-git-hooks.ps1

$ErrorActionPreference = "Stop"

$root = git rev-parse --show-toplevel 2>$null
if (-not $root) {
  Write-Error "请在 one-class Git 仓库内执行本脚本"
}

$hooksPath = Join-Path $root ".githooks"
if (-not (Test-Path $hooksPath)) {
  Write-Error "未找到 .githooks 目录: $hooksPath"
}

# pre-push 需可执行；Git for Windows 通过 sh 运行，仍建议去掉 CRLF 问题
$prePush = Join-Path $hooksPath "pre-push"
if (Test-Path $prePush) {
  $content = [System.IO.File]::ReadAllText($prePush) -replace "`r`n", "`n"
  $utf8NoBom = New-Object System.Text.UTF8Encoding $false
  [System.IO.File]::WriteAllText($prePush, $content, $utf8NoBom)
}

git config core.hooksPath .githooks

Write-Host "已设置 core.hooksPath = .githooks"
Write-Host "推送前将自动执行: frontend npm run typecheck"
Write-Host ""
Write-Host "验证: git config core.hooksPath"
git config core.hooksPath
