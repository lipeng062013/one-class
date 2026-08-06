from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import require_permissions
from app.core.responses import ok
from app.models.knowledge import KnowledgeEntry
from app.models.user import User
from app.modules.knowledge.schemas import KnowledgeCreate, KnowledgeOut, KnowledgeUpdate

router = APIRouter(prefix="/knowledge", tags=["knowledge"])

# 成长中心：沟通话术 / 异议处理 / 禁用词（已移除 course / tone 等旧分类）
CATEGORIES = {"script", "objection", "banned"}


def _serialize(entry: KnowledgeEntry) -> dict:
    return KnowledgeOut.model_validate(entry).model_dump()


def _validate_category(category: str) -> None:
    if category not in CATEGORIES:
        raise HTTPException(status_code=400, detail="Invalid category")


@router.get("")
def list_knowledge(
    category: str | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_permissions("knowledge.read")),
):
    q = db.query(KnowledgeEntry).order_by(KnowledgeEntry.id.desc())
    if category is not None:
        _validate_category(category)
        q = q.filter(KnowledgeEntry.category == category)
    entries = q.all()
    return ok([_serialize(e) for e in entries])


@router.post("")
def create_knowledge(
    body: KnowledgeCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permissions("knowledge.write")),
):
    _validate_category(body.category)
    entry = KnowledgeEntry(
        category=body.category,
        title=body.title or "",
        content=body.content or "",
        tags=body.tags or "",
        is_active=body.is_active,
        updated_by=user.id,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return ok(_serialize(entry))


@router.patch("/{entry_id}")
def patch_knowledge(
    entry_id: int,
    body: KnowledgeUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permissions("knowledge.write")),
):
    entry = db.get(KnowledgeEntry, entry_id)
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge entry not found")

    data = body.model_dump(exclude_unset=True)
    if "category" in data and data["category"] is not None:
        _validate_category(data["category"])

    for key, value in data.items():
        if value is not None or key in {"title", "content", "tags", "is_active"}:
            setattr(entry, key, value)

    entry.updated_by = user.id
    db.commit()
    db.refresh(entry)
    return ok(_serialize(entry))


@router.delete("/{entry_id}")
def delete_knowledge(
    entry_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_permissions("knowledge.write")),
):
    entry = db.get(KnowledgeEntry, entry_id)
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge entry not found")
    db.delete(entry)
    db.commit()
    return ok({"id": entry_id})
