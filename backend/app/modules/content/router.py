from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import require_roles
from app.core.responses import ok
from app.models.user import User
from app.modules.content import service
from app.modules.content.schemas import GenerateCopyRequest, GeneratedCopyUpdate

router = APIRouter(prefix="/copies", tags=["content"])

_ops = require_roles("admin", "operator")


@router.post("/generate")
def generate_copy(
    body: GenerateCopyRequest,
    db: Session = Depends(get_db),
    user: User = Depends(_ops),
):
    return ok(service.generate_copy(db, user, body))


@router.get("")
def list_copies(
    db: Session = Depends(get_db),
    _: User = Depends(_ops),
):
    items = service.list_copies(db)
    return ok([service.serialize_copy(c) for c in items])


@router.patch("/{copy_id}")
def patch_copy(
    copy_id: int,
    body: GeneratedCopyUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(_ops),
):
    copy = service.update_copy(db, copy_id, body)
    return ok(service.serialize_copy(copy))
