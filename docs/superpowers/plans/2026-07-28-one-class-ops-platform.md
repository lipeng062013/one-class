# 壹号教室运营工具平台 V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a modular Vue 3 + TypeScript frontend and FastAPI Python backend so 壹号教室 staff can log in, upload materials, generate Xiaohongshu copy and posters (template-first, optional LLM/image APIs), manage knowledge, and track referral leads—deployable with Docker Compose.

**Architecture:** Monorepo with `frontend/` and `backend/`. Backend exposes versioned REST under `/api/v1` with JWT auth and role checks. SQLite via SQLAlchemy + Alembic; files via a `Storage` interface backed by a local directory. LLM and image keys live only in env vars; template generation works without them. Existing `one-class-operations-guide.html` stays untouched.

**Tech Stack:** Vue 3, Vite, TypeScript, Vue Router, Pinia, FastAPI, SQLAlchemy 2, Alembic, Pydantic Settings, python-jose, passlib/bcrypt, Pillow, httpx, pytest, Docker Compose

**Spec:** `docs/superpowers/specs/2026-07-28-one-class-ops-platform-design.md`

---

## File map (create unless noted)

```text
backend/
  pyproject.toml                 # or requirements.txt + requirements-dev.txt
  alembic.ini
  alembic/env.py
  alembic/versions/0001_initial.py
  app/main.py
  app/core/config.py
  app/core/db.py
  app/core/security.py
  app/core/deps.py
  app/core/responses.py
  app/core/storage.py
  app/models/__init__.py
  app/models/user.py
  app/models/material.py
  app/models/knowledge.py
  app/models/template.py
  app/models/content.py
  app/models/poster.py
  app/models/lead.py
  app/modules/auth/router.py
  app/modules/auth/schemas.py
  app/modules/auth/service.py
  app/modules/users/router.py
  app/modules/materials/router.py
  app/modules/materials/schemas.py
  app/modules/materials/service.py
  app/modules/knowledge/router.py
  app/modules/templates/router.py
  app/modules/content/router.py
  app/modules/content/service.py
  app/modules/posters/router.py
  app/modules/posters/service.py
  app/modules/leads/router.py
  app/modules/dashboard/router.py
  app/integrations/llm.py
  app/integrations/image_api.py
  app/seed.py
  tests/conftest.py
  tests/test_health.py
  tests/test_auth.py
  tests/test_materials.py
  tests/test_knowledge.py
  tests/test_content.py
  tests/test_posters.py
  tests/test_leads.py
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
  src/api/materials.ts
  src/api/copies.ts
  src/api/posters.ts
  src/api/leads.ts
  src/api/knowledge.ts
  src/api/templates.ts
  src/api/users.ts
  src/views/LoginView.vue
  src/views/DashboardView.vue
  src/views/materials/MaterialListView.vue
  src/views/materials/MaterialDetailView.vue
  src/views/copies/CopyListView.vue
  src/views/copies/CopyGenerateView.vue
  src/views/posters/PosterListView.vue
  src/views/posters/PosterGenerateView.vue
  src/views/leads/LeadListView.vue
  src/views/knowledge/KnowledgeView.vue
  src/views/templates/TemplateViews.vue
  src/views/users/UserListView.vue
  src/views/mobile/MobileUploadView.vue
  src/views/mobile/MobileMaterialsView.vue
  src/layouts/AppLayout.vue
  src/layouts/MobileLayout.vue
  Dockerfile
backend/Dockerfile
docker-compose.yml
.env.example
```

---

### Task 1: Backend skeleton, config, health endpoint

**Files:**
- Create: `backend/requirements.txt`
- Create: `backend/requirements-dev.txt`
- Create: `backend/app/__init__.py`
- Create: `backend/app/main.py`
- Create: `backend/app/core/config.py`
- Create: `backend/app/core/responses.py`
- Create: `backend/tests/conftest.py`
- Create: `backend/tests/test_health.py`
- Create: `.env.example`

- [ ] **Step 1: Write the failing health test**

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

- [ ] **Step 2: Run test and confirm it fails**

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install fastapi uvicorn pydantic-settings sqlalchemy alembic python-jose passlib bcrypt httpx pillow python-multipart pytest
pip freeze > requirements.txt
pip install pytest httpx
# keep requirements-dev.txt with pytest
pytest tests/test_health.py -v
```

Expected: FAIL (module/app missing or route missing)

- [ ] **Step 3: Implement minimal app**

```python
# backend/app/core/config.py
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "one-class-ops"
    database_url: str = "sqlite:///./data/app.db"
    jwt_secret: str = "dev-change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 12
    storage_root: str = "./data/uploads"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model: str = "gpt-4o-mini"
    image_api_base_url: str = ""
    image_api_key: str = ""
    image_model: str = ""
    seed_admin_username: str = "admin"
    seed_admin_password: str = "admin123"


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

```python
# backend/app/core/responses.py
from typing import Any, Generic, Optional, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ErrorBody(BaseModel):
    code: str
    message: str


class ApiResponse(BaseModel, Generic[T]):
    data: Optional[T] = None
    error: Optional[ErrorBody] = None


def ok(data: Any) -> dict:
    return {"data": data, "error": None}


def err(code: str, message: str) -> dict:
    return {"data": None, "error": {"code": code, "message": message}}
```

```python
# backend/app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.responses import ok

settings = get_settings()
app = FastAPI(title=settings.app_name)

origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/v1/health")
def health():
    return ok({"status": "ok"})
```

```text
# .env.example
DATABASE_URL=sqlite:///./data/app.db
JWT_SECRET=change-me-in-production
STORAGE_ROOT=./data/uploads
CORS_ORIGINS=http://localhost:5173
LLM_BASE_URL=
LLM_API_KEY=
LLM_MODEL=gpt-4o-mini
IMAGE_API_BASE_URL=
IMAGE_API_KEY=
IMAGE_MODEL=
SEED_ADMIN_USERNAME=admin
SEED_ADMIN_PASSWORD=admin123
```

Map env names in Settings with `Field(validation_alias=...)` or use lowercase env with pydantic-settings default (DATABASE_URL works if field is `database_url` with case-insensitive env). Prefer:

```python
model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)
```

- [ ] **Step 4: Run test and confirm it passes**

```powershell
cd backend
pytest tests/test_health.py -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```powershell
git add backend .env.example
git commit -m "chore: scaffold backend health API"
```

---

### Task 2: Database session, User model, security helpers

**Files:**
- Create: `backend/app/core/db.py`
- Create: `backend/app/core/security.py`
- Create: `backend/app/models/__init__.py`
- Create: `backend/app/models/user.py`
- Create: `backend/tests/test_security.py`

- [ ] **Step 1: Write failing security tests**

```python
# backend/tests/test_security.py
from app.core.security import hash_password, verify_password, create_access_token, decode_token


def test_password_hash_roundtrip():
    h = hash_password("secret123")
    assert h != "secret123"
    assert verify_password("secret123", h)
    assert not verify_password("wrong", h)


def test_jwt_roundtrip():
    token = create_access_token(subject="1", extra={"role": "admin"})
    payload = decode_token(token)
    assert payload["sub"] == "1"
    assert payload["role"] == "admin"
```

- [ ] **Step 2: Run tests — expect FAIL**

```powershell
pytest tests/test_security.py -v
```

- [ ] **Step 3: Implement db + security + User model**

```python
# backend/app/core/db.py
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings

settings = get_settings()
connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from app import models  # noqa: F401
    Base.metadata.create_all(bind=engine)
```

```python
# backend/app/core/security.py
from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import get_settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
settings = get_settings()


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(subject: str, extra: dict[str, Any] | None = None) -> str:
    payload: dict[str, Any] = {"sub": subject}
    if extra:
        payload.update(extra)
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    payload["exp"] = expire
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:
        raise ValueError("invalid token") from exc
```

```python
# backend/app/models/user.py
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(128), default="")
    role: Mapped[str] = mapped_column(String(32), index=True)  # admin|operator|teacher
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

```python
# backend/app/models/__init__.py
from app.models.user import User

__all__ = ["User"]
```

- [ ] **Step 4: Run tests — expect PASS**

```powershell
pytest tests/test_security.py -v
```

- [ ] **Step 5: Commit**

```powershell
git add backend
git commit -m "feat: add db base, user model, and password/jwt helpers"
```

---

### Task 3: Auth login, /me, role deps, seed admin

**Files:**
- Create: `backend/app/core/deps.py`
- Create: `backend/app/modules/auth/schemas.py`
- Create: `backend/app/modules/auth/service.py`
- Create: `backend/app/modules/auth/router.py`
- Create: `backend/app/modules/users/router.py`
- Create: `backend/app/seed.py`
- Create: `backend/tests/test_auth.py`
- Modify: `backend/app/main.py`
- Modify: `backend/tests/conftest.py`

- [ ] **Step 1: Write auth tests**

```python
# backend/tests/conftest.py
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Isolate test DB before app imports engine if possible — override in fixture
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["JWT_SECRET"] = "test-secret"
os.environ["STORAGE_ROOT"] = str(Path(__file__).resolve().parent / "_uploads")

from app.core.db import Base, get_db
from app.core.security import hash_password
from app.main import app
from app.models.user import User


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_ROOT", str(tmp_path / "uploads"))
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    db = TestingSession()
    db.add(
        User(
            username="admin",
            password_hash=hash_password("admin123"),
            display_name="负责人",
            role="admin",
        )
    )
    db.add(
        User(
            username="ops",
            password_hash=hash_password("ops123"),
            display_name="运营",
            role="operator",
        )
    )
    db.add(
        User(
            username="teacher1",
            password_hash=hash_password("t123"),
            display_name="老师甲",
            role="teacher",
        )
    )
    db.commit()
    db.close()

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)


def auth_header(client: TestClient, username: str, password: str) -> dict:
    res = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert res.status_code == 200, res.text
    token = res.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}
```

```python
# backend/tests/test_auth.py
from tests.conftest import auth_header


def test_login_success(client):
    res = client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin123"})
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["access_token"]
    assert data["user"]["role"] == "admin"


def test_login_failure(client):
    res = client.post("/api/v1/auth/login", json={"username": "admin", "password": "bad"})
    assert res.status_code == 401


def test_me_requires_auth(client):
    assert client.get("/api/v1/auth/me").status_code == 401


def test_me_returns_user(client):
    headers = auth_header(client, "ops", "ops123")
    res = client.get("/api/v1/auth/me", headers=headers)
    assert res.status_code == 200
    assert res.json()["data"]["username"] == "ops"


def test_teacher_cannot_list_users(client):
    headers = auth_header(client, "teacher1", "t123")
    res = client.get("/api/v1/users", headers=headers)
    assert res.status_code == 403


def test_admin_can_list_users(client):
    headers = auth_header(client, "admin", "admin123")
    res = client.get("/api/v1/users", headers=headers)
    assert res.status_code == 200
    assert len(res.json()["data"]) >= 3
```

- [ ] **Step 2: Run tests — expect FAIL**

```powershell
pytest tests/test_auth.py -v
```

- [ ] **Step 3: Implement auth module, deps, users list, wire main + lifespan seed**

```python
# backend/app/core/deps.py
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import decode_token
from app.models.user import User

bearer = HTTPBearer(auto_error=False)


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    if creds is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        payload = decode_token(creds.credentials)
        user_id = int(payload["sub"])
    except (ValueError, KeyError, TypeError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    user = db.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User inactive")
    return user


def require_roles(*roles: str):
    def _inner(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
        return user

    return _inner
```

```python
# backend/app/modules/auth/schemas.py
from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


class UserOut(BaseModel):
    id: int
    username: str
    display_name: str
    role: str
    is_active: bool

    model_config = {"from_attributes": True}


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut
```

```python
# backend/app/modules/auth/router.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import get_current_user
from app.core.responses import ok
from app.core.security import create_access_token, verify_password
from app.models.user import User
from app.modules.auth.schemas import LoginRequest, LoginResponse, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login")
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == body.username).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Bad credentials")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Inactive")
    token = create_access_token(str(user.id), {"role": user.role})
    return ok(LoginResponse(access_token=token, user=UserOut.model_validate(user)).model_dump())


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return ok(UserOut.model_validate(user).model_dump())
```

```python
# backend/app/modules/users/router.py
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import require_roles
from app.core.responses import ok
from app.core.security import hash_password
from app.models.user import User
from app.modules.auth.schemas import UserOut

router = APIRouter(prefix="/users", tags=["users"])


class UserCreate(BaseModel):
    username: str
    password: str = Field(min_length=6)
    display_name: str = ""
    role: str  # admin|operator|teacher


@router.get("")
def list_users(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin")),
):
    users = db.query(User).order_by(User.id).all()
    return ok([UserOut.model_validate(u).model_dump() for u in users])


@router.post("")
def create_user(
    body: UserCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin")),
):
    if body.role not in {"admin", "operator", "teacher"}:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Invalid role")
    user = User(
        username=body.username,
        password_hash=hash_password(body.password),
        display_name=body.display_name or body.username,
        role=body.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return ok(UserOut.model_validate(user).model_dump())
```

Wire routers in `main.py` under `prefix="/api/v1"`. On startup call `init_db()` and seed admin if missing (`app/seed.py`).

- [ ] **Step 4: Run auth tests — PASS**

```powershell
pytest tests/test_auth.py tests/test_health.py -v
```

- [ ] **Step 5: Commit**

```powershell
git add backend
git commit -m "feat: add login, JWT auth, and admin user APIs"
```

---

### Task 4: Local storage + materials CRUD and upload

**Files:**
- Create: `backend/app/core/storage.py`
- Create: `backend/app/models/material.py`
- Create: `backend/app/modules/materials/schemas.py`
- Create: `backend/app/modules/materials/service.py`
- Create: `backend/app/modules/materials/router.py`
- Create: `backend/tests/test_materials.py`
- Modify: `backend/app/models/__init__.py`, `backend/app/main.py`

- [ ] **Step 1: Write materials tests**

```python
# backend/tests/test_materials.py
from io import BytesIO

from tests.conftest import auth_header


def test_teacher_creates_material_and_uploads(client):
    h = auth_header(client, "teacher1", "t123")
    res = client.post(
        "/api/v1/materials",
        headers=h,
        json={
            "title": "课堂进步",
            "grade": "四年级",
            "subject": "数学",
            "pain_point": "应用题慢",
            "teacher_action": "拆步骤示范",
            "next_step": "预约试听",
            "auth_status": "authorized",
        },
    )
    assert res.status_code == 200
    mid = res.json()["data"]["id"]
    files = {"file": ("a.png", BytesIO(b"\x89PNG\r\n\x1a\nfake"), "image/png")}
    up = client.post(f"/api/v1/materials/{mid}/files", headers=h, files=files)
    assert up.status_code == 200
    assert up.json()["data"]["file_type"].startswith("image/")


def test_teacher_only_sees_own_materials(client):
    h_t = auth_header(client, "teacher1", "t123")
    client.post(
        "/api/v1/materials",
        headers=h_t,
        json={"title": "only-mine", "auth_status": "pending"},
    )
    h_ops = auth_header(client, "ops", "ops123")
    # ops creates another
    client.post(
        "/api/v1/materials",
        headers=h_ops,
        json={"title": "ops-mat", "auth_status": "pending"},
    )
    listed = client.get("/api/v1/materials", headers=h_t)
    assert listed.status_code == 200
    titles = [m["title"] for m in listed.json()["data"]]
    assert "only-mine" in titles
    assert "ops-mat" not in titles


def test_ops_can_patch_status(client):
    h_t = auth_header(client, "teacher1", "t123")
    mid = client.post(
        "/api/v1/materials",
        headers=h_t,
        json={"title": "x", "auth_status": "pending"},
    ).json()["data"]["id"]
    h_ops = auth_header(client, "ops", "ops123")
    res = client.patch(
        f"/api/v1/materials/{mid}",
        headers=h_ops,
        json={"status": "usable", "auth_status": "authorized"},
    )
    assert res.status_code == 200
    assert res.json()["data"]["status"] == "usable"
```

- [ ] **Step 2: Run — FAIL**

```powershell
pytest tests/test_materials.py -v
```

- [ ] **Step 3: Implement Storage, Material models, router**

`LocalStorage.save(relative_path, bytes) -> path`, `open`, ensure root exists.

Models:

```python
# material fields per spec: title, grade, subject, pain_point, teacher_action, next_step,
# auth_status, status, uploader_id, created_at
# material_files: material_id, file_path, file_type, sort_order
```

Rules:

- `POST /materials`: any authenticated role; set `uploader_id=current.id`, default `status=new`
- `GET /materials`: teacher filter `uploader_id == me`; admin/operator all
- `POST /materials/{id}/files`: teacher only own; ops/admin any; store under `materials/{id}/`
- `PATCH`: only admin/operator for status/auth; teacher may not patch others

Wire router; register models.

- [ ] **Step 4: PASS tests**

```powershell
pytest tests/test_materials.py -v
```

- [ ] **Step 5: Commit**

```powershell
git add backend
git commit -m "feat: add materials CRUD and local file upload"
```

---

### Task 5: Knowledge base module

**Files:**
- Create: `backend/app/models/knowledge.py`
- Create: `backend/app/modules/knowledge/router.py` (+ schemas inline or separate)
- Create: `backend/tests/test_knowledge.py`

- [ ] **Step 1: Tests**

```python
def test_admin_can_create_knowledge(client):
    h = auth_header(client, "admin", "admin123")
    res = client.post(
        "/api/v1/knowledge",
        headers=h,
        json={"category": "banned", "title": "包过", "content": "禁止承诺包过", "tags": "合规"},
    )
    assert res.status_code == 200


def test_operator_read_only_knowledge(client):
    h_admin = auth_header(client, "admin", "admin123")
    client.post(
        "/api/v1/knowledge",
        headers=h_admin,
        json={"category": "tone", "title": "语气", "content": "温暖专业", "tags": ""},
    )
    h_ops = auth_header(client, "ops", "ops123")
    assert client.get("/api/v1/knowledge", headers=h_ops).status_code == 200
    assert client.post(
        "/api/v1/knowledge",
        headers=h_ops,
        json={"category": "faq", "title": "x", "content": "y"},
    ).status_code == 403


def test_teacher_cannot_read_knowledge(client):
    h = auth_header(client, "teacher1", "t123")
    assert client.get("/api/v1/knowledge", headers=h).status_code == 403
```

- [ ] **Step 2: FAIL then implement**

- Model `KnowledgeEntry` per spec
- `GET` admin+operator; `POST/PATCH/DELETE` admin only
- Categories: `course|faq|tone|banned|staff|process`

- [ ] **Step 3: PASS + commit**

```powershell
pytest tests/test_knowledge.py -v
git add backend
git commit -m "feat: add institution knowledge base APIs"
```

---

### Task 6: Copy & poster templates

**Files:**
- Create: `backend/app/models/template.py`
- Create: `backend/app/modules/templates/router.py`
- Create: `backend/tests/test_templates.py`
- Modify: `backend/app/seed.py` to insert system templates

- [ ] **Step 1: Tests**

```python
def test_list_includes_system_copy_template_after_seed(client):
    # seed system template in conftest or endpoint bootstrap
    h = auth_header(client, "ops", "ops123")
    res = client.get("/api/v1/templates/copies", headers=h)
    assert res.status_code == 200


def test_cannot_delete_system_template(client):
    h = auth_header(client, "admin", "admin123")
    # create system via seed id=1 or flag
    ...


def test_ops_can_create_custom_copy_template(client):
    h = auth_header(client, "ops", "ops123")
    res = client.post(
        "/api/v1/templates/copies",
        headers=h,
        json={
            "name": "我的老带新",
            "scene": "referral",
            "body": "欢迎{{referrer}}推荐，孩子{{grade}}在学{{subject}}。",
        },
    )
    assert res.status_code == 200
    assert res.json()["data"]["is_system"] is False
```

- [ ] **Step 2: Implement**

Models `CopyTemplate`, `PosterTemplate` with `is_system`, `layout_json` for posters (JSON text).

Endpoints:

- `GET/POST /templates/copies`, `PATCH/DELETE /templates/copies/{id}`
- `GET/POST /templates/posters`, `PATCH/DELETE /templates/posters/{id}`
- Delete/PATCH system: 400 if `is_system` and attempting delete; ops can copy by POST custom with body cloned

Seed at least:

1. Copy system: scene `xhs_script`, body with `{{title}} {{pain_point}} {{teacher_action}} {{next_step}}`
2. Poster system: `layout_json` with title/subtitle/footer regions (simple absolute boxes for Pillow)

- [ ] **Step 3: PASS + commit**

```powershell
pytest tests/test_templates.py -v
git commit -m "feat: add copy and poster template APIs"
```

---

### Task 7: Copy generation (template + optional LLM)

**Files:**
- Create: `backend/app/models/content.py`
- Create: `backend/app/integrations/llm.py`
- Create: `backend/app/modules/content/service.py`
- Create: `backend/app/modules/content/router.py`
- Create: `backend/tests/test_content.py`

- [ ] **Step 1: Tests**

```python
def test_generate_copy_template_only(client):
    h = auth_header(client, "ops", "ops123")
    # create material + custom template with {{pain_point}}
    ...
    res = client.post(
        "/api/v1/copies/generate",
        headers=h,
        json={"material_id": mid, "template_id": tid, "mode": "template", "platform": "xhs"},
    )
    assert res.status_code == 200
    body = res.json()["data"]["body"]
    assert "应用题" in body or material pain point appears
    assert res.json()["data"]["mode"] == "template"


def test_generate_with_llm_mock(client, monkeypatch):
    def fake_chat(messages, **kwargs):
        return "【润色】测试文案"

    monkeypatch.setattr("app.integrations.llm.chat_completion", fake_chat)
    ...
    res = client.post(..., json={..., "mode": "template_then_llm"})
    assert "润色" in res.json()["data"]["body"]


def test_banned_words_reported(client):
    # admin adds banned "包过"; template produces it; response includes hits
    ...
```

- [ ] **Step 2: Implement service**

`render_template(body, context: dict) -> str` replace `{{key}}`.

Context from material fields + selected knowledge snippets (tone + course titles).

`find_banned(text, banned_list) -> list[str]`.

`llm.chat_completion`: if no `llm_api_key` or `llm_base_url`, raise `LlmUnavailable`; content service catches and for `template_then_llm` returns template result with warning field `llm_error`.

httpx POST `{base}/v1/chat/completions` OpenAI-compatible.

Persist `GeneratedCopy`.

Teacher forbidden (403).

- [ ] **Step 3: PASS + commit**

```powershell
pytest tests/test_content.py -v
git commit -m "feat: generate xhs copy from templates and optional LLM"
```

---

### Task 8: Poster generation (layout PNG + optional image API)

**Files:**
- Create: `backend/app/models/poster.py`
- Create: `backend/app/integrations/image_api.py`
- Create: `backend/app/modules/posters/service.py`
- Create: `backend/app/modules/posters/router.py`
- Create: `backend/tests/test_posters.py`

- [ ] **Step 1: Tests**

```python
def test_generate_layout_poster_png(client):
    h = auth_header(client, "ops", "ops123")
    # ensure system poster template exists
    res = client.post(
        "/api/v1/posters/generate",
        headers=h,
        json={
            "template_id": 1,
            "mode": "layout",
            "title": "壹号教室试听",
            "payload": {"subtitle": "嘉定新城", "footer": "扫码预约"},
        },
    )
    assert res.status_code == 200
    assert res.json()["data"]["file_path"]
    file_id = res.json()["data"]["id"]
    dl = client.get(f"/api/v1/files/posters/{file_id}", headers=h)
    assert dl.status_code == 200
    assert dl.headers["content-type"].startswith("image/")


def test_ai_image_fallback_or_mock(client, monkeypatch):
    monkeypatch.setattr(
        "app.integrations.image_api.generate_image",
        lambda **kw: b"\x89PNG\r\n\x1a\n" + b"0" * 64,
    )
    ...
```

- [ ] **Step 2: Implement**

Pillow: create RGB image from `layout_json` width/height, draw title strings, optional paste material image if path provided.

`image_api.generate_image(prompt) -> bytes`; empty config raises.

Save via Storage; `GeneratedPoster` row.

`GET /api/v1/files/posters/{id}` streams file with auth.

- [ ] **Step 3: PASS + commit**

```powershell
pytest tests/test_posters.py -v
git commit -m "feat: generate layout posters and optional AI images"
```

---

### Task 9: Leads + dashboard summary

**Files:**
- Create: `backend/app/models/lead.py`
- Create: `backend/app/modules/leads/router.py`
- Create: `backend/app/modules/dashboard/router.py`
- Create: `backend/tests/test_leads.py`

- [ ] **Step 1: Tests**

```python
def test_create_and_update_lead(client):
    h = auth_header(client, "ops", "ops123")
    res = client.post(
        "/api/v1/leads",
        headers=h,
        json={
            "student_or_parent_name": "张妈妈",
            "source": "referral",
            "referrer_name": "李同学",
            "need": "四年级数学",
            "status": "new",
        },
    )
    assert res.status_code == 200
    lid = res.json()["data"]["id"]
    patch = client.patch(
        f"/api/v1/leads/{lid}",
        headers=h,
        json={"status": "contacted", "notes": "已电话"},
    )
    assert patch.json()["data"]["status"] == "contacted"


def test_teacher_forbidden_leads(client):
    h = auth_header(client, "teacher1", "t123")
    assert client.get("/api/v1/leads", headers=h).status_code == 403


def test_dashboard_counts(client):
    h = auth_header(client, "admin", "admin123")
    res = client.get("/api/v1/dashboard/summary", headers=h)
    assert res.status_code == 200
    assert "materials_new" in res.json()["data"]
    assert "leads_follow_today" in res.json()["data"]
```

- [ ] **Step 2: Implement Lead model + routers; dashboard aggregates**

- [ ] **Step 3: PASS full backend suite + commit**

```powershell
pytest -v
git commit -m "feat: add leads and dashboard summary APIs"
```

---

### Task 10: Frontend scaffold + API client + auth

**Files:**
- Create: entire `frontend/` via Vite template then replace files listed in file map for auth

- [ ] **Step 1: Scaffold**

```powershell
cd "D:\one class"
npm create vite@latest frontend -- --template vue-ts
cd frontend
npm install
npm install vue-router@4 pinia axios
```

- [ ] **Step 2: Implement API client and auth store**

```typescript
// src/api/client.ts
import axios from 'axios'

const client = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api/v1',
})

client.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

export default client
```

```typescript
// src/stores/auth.ts — login, logout, user, loadMe
// src/router/index.ts — routes + beforeEach:
//   - no token -> /login
//   - teacher -> allow only /m/* and /login
//   - admin/operator -> desktop routes; /users admin only
```

```vue
<!-- LoginView.vue: username/password form calling store.login -->
```

- [ ] **Step 3: Manual check**

```powershell
cd backend
uvicorn app.main:app --reload --port 8000
# other terminal
cd frontend
npm run dev
```

Login as admin/admin123 (after seed). Expect redirect to dashboard shell.

- [ ] **Step 4: Commit**

```powershell
git add frontend
git commit -m "feat: scaffold vue app with login and route guards"
```

---

### Task 11: Teacher mobile upload + my materials

**Files:**
- Create: `frontend/src/views/mobile/MobileUploadView.vue`
- Create: `frontend/src/views/mobile/MobileMaterialsView.vue`
- Create: `frontend/src/layouts/MobileLayout.vue`
- Create: `frontend/src/api/materials.ts`

- [ ] **Step 1: Implement large-tap upload form** (title, grade, subject, pain_point, teacher_action, next_step, auth_status, multi file input)

- [ ] **Step 2: List own materials with status badges**

- [ ] **Step 3: Verify with teacher1 account on narrow viewport**

- [ ] **Step 4: Commit**

```powershell
git commit -m "feat: add teacher mobile material upload views"
```

---

### Task 12: Desktop materials, copies, posters, leads, knowledge, users

**Files:**
- Create remaining views under `frontend/src/views/**`
- Create `AppLayout.vue` sidebar per spec

- [ ] **Step 1: Materials list/detail** — filter status; patch usable; link to generate copy/poster

- [ ] **Step 2: Copy generate wizard** — select material, template, mode; show body + banned hits; copy-to-clipboard; save list

- [ ] **Step 3: Poster generate wizard** — layout default; optional ai_image; download link

- [ ] **Step 4: Leads table** — create/edit status; highlight `next_follow_at` today

- [ ] **Step 5: Knowledge** — admin edit; operator read-only UI

- [ ] **Step 6: Templates management** — list system + custom; clone system

- [ ] **Step 7: Users** — admin create user form

- [ ] **Step 8: Dashboard** — call `/dashboard/summary`

- [ ] **Step 9: Commit**

```powershell
git commit -m "feat: add desktop ops views for full v1 loop"
```

---

### Task 13: Docker Compose + production wiring

**Files:**
- Create: `backend/Dockerfile`
- Create: `frontend/Dockerfile`
- Create: `frontend/nginx.conf`
- Create: `docker-compose.yml`
- Modify: `.env.example` if needed

- [ ] **Step 1: Backend Dockerfile**

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY alembic.ini . 
COPY alembic ./alembic
ENV PYTHONPATH=/app
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 2: Frontend multi-stage build + nginx proxy `/api` → `backend:8000`**

- [ ] **Step 3: docker-compose.yml**

```yaml
services:
  backend:
    build: ./backend
    env_file: .env
    volumes:
      - ./data:/app/data
    ports:
      - "8000:8000"
  frontend:
    build: ./frontend
    ports:
      - "8080:80"
    depends_on:
      - backend
```

- [ ] **Step 4: Verify**

```powershell
docker compose up --build
# open http://localhost:8080 — login — smoke main flows
```

- [ ] **Step 5: Commit**

```powershell
git add docker-compose.yml backend/Dockerfile frontend/Dockerfile frontend/nginx.conf .env.example
git commit -m "chore: add docker compose deployment for ops platform"
```

---

### Task 14: Seed data script + README runbook

**Files:**
- Create: `backend/app/seed.py` (complete): admin user, sample knowledge banned/tone, 2 system copy templates, 1 poster template
- Create: `README-ops-platform.md` (or section in root README) — how to run dev, docker, env vars, default accounts **without real API keys**
- Ensure startup calls seed idempotently

- [ ] **Step 1: Implement idempotent seed**

- [ ] **Step 2: Document**

Default dev accounts: `admin` / `admin123` (change in production).

- [ ] **Step 3: Final test**

```powershell
cd backend
pytest -v
```

- [ ] **Step 4: Commit**

```powershell
git commit -m "chore: add seed data and ops platform runbook"
```

---

## Spec coverage checklist (self-review)

| Spec area | Tasks |
|-----------|-------|
| Vue+TS modular frontend | 10–12 |
| Python FastAPI modular backend | 1–9 |
| Docker | 13 |
| Auth + roles | 3, 10 |
| Materials upload | 4, 11 |
| Knowledge | 5, 12 |
| Templates + copy gen | 6–7, 12 |
| Posters layout + AI | 8, 12 |
| Leads + dashboard | 9, 12 |
| SQLite + portable ORM | 2 |
| Local storage abstraction | 4 |
| Secrets only in env | 1, 13, 14 |
| Teacher mobile / ops desktop | 10–12 |
| LLM/image graceful degrade | 7–8 |
| Handbook HTML untouched | all tasks avoid modifying it |

**Placeholder scan:** No TBD implementation steps; AI endpoints use env var names only.

**Type consistency:** Roles `admin|operator|teacher`; material status `new|usable|used|archived`; auth_status `pending|authorized|denied|anonymized`; copy modes `template|llm|template_then_llm`; poster modes `layout|ai_image`; API envelope `{data, error}`.

---

## Execution handoff

Plan complete and saved to `docs/superpowers/plans/2026-07-28-one-class-ops-platform.md`.

**Two execution options:**

1. **Subagent-Driven (recommended)** — fresh subagent per task, review between tasks  
2. **Inline Execution** — execute tasks in this session with executing-plans and checkpoints  

**Which approach?**
