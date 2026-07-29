from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.db import Base, SessionLocal, engine, ensure_data_dir
from app.core.responses import ok
from app.models import Material, MaterialFile, User  # noqa: F401 — register models
from app.modules.auth.router import router as auth_router
from app.modules.materials.router import router as materials_router
from app.modules.users.router import router as users_router
from app.seed import seed_demo_users


@asynccontextmanager
async def lifespan(_app: FastAPI):
    ensure_data_dir()
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_demo_users(db)
    finally:
        db.close()
    yield


app = FastAPI(title="One Class Ops Platform", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/api/v1")
app.include_router(users_router, prefix="/api/v1")
app.include_router(materials_router, prefix="/api/v1")


@app.get("/api/v1/health")
def health():
    return ok({"status": "ok"})
