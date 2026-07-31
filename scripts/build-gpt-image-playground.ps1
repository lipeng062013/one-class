# Build CookSleep GPT Image Playground and copy into frontend/public for embedding.
# Usage (from repo root):  powershell -File scripts/build-gpt-image-playground.ps1

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$src = Join-Path $root "tools\gpt_image_playground"
$dest = Join-Path $root "frontend\public\gpt-image-playground"

if (-not (Test-Path $src)) {
  Write-Host "Cloning CookSleep/gpt_image_playground ..."
  New-Item -ItemType Directory -Force -Path (Join-Path $root "tools") | Out-Null
  git clone --depth 1 https://github.com/CookSleep/gpt_image_playground.git $src
}

Push-Location $src
try {
  if (-not (Test-Path "node_modules")) {
    npm install --no-fund --no-audit
  }
  npm run build
} finally {
  Pop-Location
}

if (Test-Path $dest) {
  Remove-Item -Recurse -Force $dest
}
Copy-Item -Recurse (Join-Path $src "dist") $dest
Write-Host "OK: embedded playground -> $dest"
Write-Host "Open the app menu: GPT 生图  (/ai-image)"
