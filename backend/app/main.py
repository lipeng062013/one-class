from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.db import Base, SessionLocal, engine, ensure_data_dir
from app.core.responses import ok
from app.models import (  # noqa: F401 — register models
    CopyTemplate,
    GeneratedCopy,
    GeneratedPoster,
    KnowledgeEntry,
    Lead,
    LearningRecord,
    LearningRecordFile,
    Material,
    MaterialFile,
    PosterTemplate,
    Student,
    TodoItem,
    User,
)
from app.modules.auth.router import router as auth_router
from app.modules.content.router import router as content_router
from app.modules.dashboard.router import router as dashboard_router
from app.modules.knowledge.router import router as knowledge_router
from app.modules.leads.router import router as leads_router
from app.modules.materials.router import router as materials_router
from app.modules.posters.router import router as posters_router
from app.modules.students.router import router as students_router
from app.modules.image_playground.router import (
    config_router as image_playground_config_router,
    proxy_router as image_playground_proxy_router,
)
from app.modules.system.router import router as system_router
from app.modules.templates.router import router as templates_router
from app.modules.todos.router import router as todos_router
from app.modules.users.router import router as users_router
from app.seed import seed_all


@asynccontextmanager
async def lifespan(_app: FastAPI):
    ensure_data_dir()
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_all(db)
    finally:
        db.close()
    yield


app = FastAPI(title="嘉壹启航运营工具平台", lifespan=lifespan)

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
app.include_router(knowledge_router, prefix="/api/v1")
app.include_router(templates_router, prefix="/api/v1")
app.include_router(content_router, prefix="/api/v1")
app.include_router(posters_router, prefix="/api/v1")
app.include_router(leads_router, prefix="/api/v1")
app.include_router(students_router, prefix="/api/v1")
app.include_router(todos_router, prefix="/api/v1")
app.include_router(dashboard_router, prefix="/api/v1")
app.include_router(system_router, prefix="/api/v1")
# Config under /api/v1; proxy at /image-api/v1 (must not sit under /api/v1 — see router docstring)
app.include_router(image_playground_config_router, prefix="/api/v1")
app.include_router(image_playground_proxy_router)


@app.get("/api/v1/health")
def health():
    return ok({"status": "ok"})
