# 壹号教室 GitHub Pages 部署设计

## 目标

将现有单文件运营指导网页部署到 GitHub Pages，使仓库出现 `github-pages` Deployment，并获得可直接分享给朋友的公开网址。后续每次推送 `master` 分支时自动重新部署。

## 当前状态

- GitHub 仓库：`lipeng062013/one-class`
- 默认分支：`master`
- 当前仓库可见性：私有
- 页面源文件：`one-class-operations-guide.html`
- GitHub Pages 尚未启用

## 采用方案

使用 GitHub Actions 官方 Pages 工作流部署，不改变现有网页文件名。工作流在运行时创建临时站点目录，将 `one-class-operations-guide.html` 复制为站点入口 `index.html`，然后使用 GitHub 官方 Actions 上传并部署静态产物。

部署流程：

1. 推送代码到 `master`，或在 Actions 页面手动触发工作流。
2. 检出仓库代码。
3. 创建临时站点目录并复制网页为 `index.html`。
4. 使用 `actions/upload-pages-artifact` 上传静态站点。
5. 使用 `actions/deploy-pages` 发布到 `github-pages` 环境。
6. GitHub 返回公开 Pages URL，并在 Deployments 页面保留部署记录。

## 仓库可见性策略

优先尝试为当前私有仓库启用 GitHub Pages。如果 GitHub 明确返回当前账号方案不支持私有仓库 Pages，则将 `one-class` 改为公开仓库后重试。用户已明确授权此降级处理。

Pages 网站用于公开分享，不承诺仓库源码保持私密。仓库公开后，网页源码、测试和设计文档均可被任何人查看，但不会包含本地文件、GitHub 密码或访问令牌。

## 权限与安全

工作流只申请以下最低权限：

- `contents: read`：读取仓库内容
- `pages: write`：创建 Pages 部署
- `id-token: write`：完成 GitHub Pages 身份验证

部署环境固定为 `github-pages`。工作流不保存业务数据，不包含 GitHub Token，不上传 `.git`、测试截图或本地临时文件。

## 文件变更

- 新增 `.github/workflows/deploy-pages.yml`
- 新增针对 Pages 工作流结构和入口文件的自动化测试
- 保留 `one-class-operations-guide.html` 作为可直接发送的单文件网页

## 错误处理

- Pages 未启用：通过 GitHub API 设置构建类型为 `workflow`
- 私有仓库方案受限：按授权将仓库改为公开后重试
- 工作流失败：读取 Actions 日志，修正后重新推送或手动触发
- 网站暂未可访问：等待 Pages CDN 发布完成，并重复检查 HTTP 状态

## 验收标准

- 仓库中存在启用状态的 Pages 工作流
- Actions 工作流成功完成
- Deployments 页面出现 `github-pages` 环境和成功部署
- GitHub API 返回 Pages 公开 URL
- 公开 URL 返回成功 HTTP 状态并显示“壹号教室全年运营与宣传执行方案”
- 本地测试通过，工作区干净，本地 `master` 与 `origin/master` 一致
