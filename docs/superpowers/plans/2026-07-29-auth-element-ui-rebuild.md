# Auth + Element Plus Login/Users Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship working password login, admin user create/reset, self change-password, seed demo accounts, and an Element Plus Vue frontend for login/users — so operator/teacher accounts can log in with known passwords.

**Architecture:** Monorepo `backend/` (FastAPI + SQLAlchemy + SQLite) and `frontend/` (Vue 3 + Vite + Pinia + Element Plus). JWT auth; passwords bcrypt-hashed; admin creates users with required password; reset-password and change-password endpoints; seed three demo users on startup.

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy 2, Alembic-ready models, passlib/bcrypt, python-jose, pydantic-settings, pytest; Vue 3, TypeScript, Vite, Vue Router, Pinia, Element Plus, axios

**Spec:** `docs/superpowers/specs/2026-07-29-auth-element-ui-rebuild-design.md`

---

## File map

```text
backend/
  requirements.txt
  requirements-dev.txt
  app/__init__.py
  app/main.py
  app/core/config.py
  app/core/db.py
  app/core/security.py
  app/core/deps.py
  app/core/responses.py
  app/models/__init__.py
  app/models/user.py
  app/modules/auth/router.py
  app/modules/auth/schemas.py
  app/modules/auth/service.py
  app/modules/users/router.py
  app/modules/users/schemas.py
  app/modules/users/service.py
  app/seed.py
  tests/conftest.py
  tests/test_health.py
  tests/test_security.py
  tests/test_auth.py
  tests/test_users.py
frontend/
  package.json
  vite.config.ts
  index.html
  src/main.ts
  src/App.vue
  src/router/index.ts
  src/stores/auth.ts
  src/api/client.ts
  src/api/auth.ts
  src/api/users.ts
  src/views/LoginView.vue
  src/views/users/UserListView.vue
  src/views/DashboardView.vue
  src/layouts/AppLayout.vue
  src/components/ChangePasswordDialog.vue
.env.example
.gitignore  (ensure data/, .env, node_modules, .venv)
```

---

### Task 1: Backend health + config envelope

**Files:**
- Create: `backend/requirements.txt`, `backend/requirements-dev.txt`
- Create: `backend/app/__init__.py`, `backend/app/main.py`
- Create: `backend/app/core/config.py`, `backend/app/core/responses.py`
- Create: `backend/tests/conftest.py`, `backend/tests/test_health.py`
- Create: `.env.example`, update `.gitignore`

- [ ] **Step 1: Write failing health test**

```python
# backend/tests/test_health.py
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health_returns_ok():
    res = client.get("/api/v1/health")
    assert res.status_code == 200
    body = res.json()
    assert body["error"] is None
    assert body["data"]["status"] == "ok"
```

- [ ] **Step 2: Implement minimal app + run pytest until green**

- [ ] **Step 3: Commit** `feat: add backend health endpoint`

---

### Task 2: Security helpers + User model + DB

**Files:**
- Create: `backend/app/core/db.py`, `backend/app/core/security.py`
- Create: `backend/app/models/user.py`, `backend/app/models/__init__.py`
- Create: `backend/tests/test_security.py`

- [ ] **Step 1: Failing tests for hash/verify and JWT**
- [ ] **Step 2: Implement until green**
- [ ] **Step 3: Commit** `feat: add user model and password/jwt helpers`

---

### Task 3: Login, /me, change-password, seed

**Files:**
- Create: auth module, deps, seed
- Create: `backend/tests/test_auth.py`
- Modify: `backend/app/main.py` lifespan seed

Demo seeds: `admin/admin123`, `ops/ops123`, `teacher1/t123`

- [ ] **Step 1: Failing auth tests** (login success/fail, me, change password, inactive reject)
- [ ] **Step 2: Implement until green**
- [ ] **Step 3: Commit** `feat: add login JWT auth and change-password`

---

### Task 4: Users list/create/reset/patch

**Files:**
- Create: users module
- Create: `backend/tests/test_users.py`

- [ ] **Step 1: Failing tests** (admin create with required password; operator forbidden; reset password; list has no hash)
- [ ] **Step 2: Implement until green**
- [ ] **Step 3: Commit** `feat: add admin user create and reset-password APIs`

---

### Task 5: Frontend scaffold + Element Plus + login

**Files:** frontend scaffold as in file map

- [ ] **Step 1: Vite vue-ts + element-plus + router + pinia + axios**
- [ ] **Step 2: LoginView, auth store, route guards, AppLayout shell, Dashboard placeholder**
- [ ] **Step 3: Manual/dev verify login with seed accounts**
- [ ] **Step 4: Commit** `feat: scaffold Element Plus app with login`

---

### Task 6: User management + change password UI

**Files:**
- `UserListView.vue`, `ChangePasswordDialog.vue`, users API

- [ ] **Step 1: Create user dialog with required password + one-time reveal**
- [ ] **Step 2: Reset password dialog one-time reveal**
- [ ] **Step 3: Change password from header menu**
- [ ] **Step 4: Commit** `feat: add user admin and change-password UI`

---

### Task 7: README runbook + final verify

- Create: `README-ops-platform.md` with demo accounts and run commands
- Run full backend pytest
- Commit docs

---

## Spec coverage

| Spec item | Tasks |
|-----------|-------|
| Password login + JWT | 3, 5 |
| Seed demo accounts | 3, 7 |
| Create user required password + one-time UI | 4, 6 |
| Admin reset + login forgot hint | 4, 5, 6 |
| Self change-password | 3, 6 |
| Element Plus | 5, 6 |
| No password in list/me | 3, 4 |
