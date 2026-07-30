# OSS 业务对象存储 Implementation Plan

> **For agentic workers:** Execute task-by-task. Checkbox tracking optional in short session.

**Goal:** 支持 `STORAGE_BACKEND=local|oss`，素材/海报/学情附件经统一 Storage 接口读写；OSS 私有桶 + 后端代理。

**Architecture:** Protocol + LocalStorage + OssStorage；读 OSS 优先、本地回退；写仅当前 backend。

**Tech Stack:** Python 3.11, FastAPI, oss2, pytest

---

### Task 1: Config + requirements
### Task 2: storage.py 实现 + 单元测试
### Task 3: 业务代码类型改为 Storage 协议
### Task 4: 文档与 .env.example
### Task 5: 跑通 pytest
