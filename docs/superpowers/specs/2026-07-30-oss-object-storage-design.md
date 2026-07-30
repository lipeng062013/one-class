# 设计：业务文件统一对象存储（Local / OSS）

**日期：** 2026-07-30  
**状态：** 已确认  
**关联：** [ops-auto-deploy](../../ops-auto-deploy.md) · [ops-backlog](../../ops-backlog.md) · 自动部署/备份 OSS 设计

---

## 1. 目标

- `STORAGE_BACKEND=oss` 时，**素材、海报、学情附件**（凡走 storage 的写入）存入阿里云 OSS。
- 前端预览/下载仍走现有后端 API；桶保持**私有**。
- `STORAGE_BACKEND=local`（默认）行为与现网一致，便于开发与测试。
- 与备份共用 Endpoint/AK/Bucket，前缀分离：`OSS_UPLOAD_PREFIX` vs `OSS_PREFIX`。

## 2. 架构

- `Storage` 协议：`save` / `read` / `open_bytes` / `exists`（可选）。
- `LocalStorage`：现有磁盘实现。
- `OssStorage`：`oss2` 上传/下载；对象键 = `OSS_UPLOAD_PREFIX` + 相对路径。
- **读：** OSS 优先；若配置了本地回退根且 OSS 无对象，则读本地（过渡旧数据）。
- **写：** 仅写入当前 backend（oss 时不双写本地）。

数据库 `file_path` 仍存相对路径（如 `materials/1/0_a.jpg`），不含桶名。

## 3. 配置

| 变量 | 说明 |
|------|------|
| `STORAGE_BACKEND` | `local` \| `oss` |
| `STORAGE_ROOT` | local 根目录 |
| `OSS_ENDPOINT` / `OSS_ACCESS_KEY_ID` / `OSS_ACCESS_KEY_SECRET` / `OSS_BUCKET` | 与备份共用 |
| `OSS_UPLOAD_PREFIX` | 业务前缀，默认 `one-class/uploads/` |
| `OSS_PREFIX` | 备份前缀（脚本用，应用可不读） |

`STORAGE_BACKEND=oss` 时缺少必填项 → 清晰错误。

## 4. 范围

**做：** storage 抽象、oss2、config、类型注解、测试、文档。  
**不做：** 前端直传、CDN、历史批量迁移脚本、数据库分离。

## 5. 成功标准

- local 下现有 pytest 通过。
- OssStorage 可用 mock/单元测试验证 key 与读写逻辑。
- 未配置 OSS 却启用 oss 时失败信息明确。
