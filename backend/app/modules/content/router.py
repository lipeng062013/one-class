from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import require_permissions
from app.core.responses import ok
from app.models.user import User
from app.modules.content import service
from app.modules.content.schemas import CopyBulkDelete, GenerateCopyRequest, GeneratedCopyUpdate

router = APIRouter(prefix="/copies", tags=["content"])

_ops = require_permissions("copies.use")


@router.post("/generate")
def generate_copy(
    body: GenerateCopyRequest,
    db: Session = Depends(get_db),
    user: User = Depends(_ops),
):
    return ok(service.generate_copy(db, user, body))


@router.get("")
def list_copies(
    q: str | None = None,
    mode: str | None = None,
    platform: str | None = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    _: User = Depends(_ops),
):
    return ok(
        service.list_copies(
            db, q=q, mode=mode, platform=platform, page=page, page_size=page_size
        )
    )


@router.post("/bulk-delete")
def bulk_delete_copies(
    body: CopyBulkDelete,
    db: Session = Depends(get_db),
    _: User = Depends(_ops),
):
    result = service.bulk_delete_copies(db, body.ids)
    return ok(result)


@router.get("/{copy_id}")
def get_copy(
    copy_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(_ops),
):
    copy = service.get_copy(db, copy_id)
    return ok(service.serialize_copy_detail(db, copy))


@router.patch("/{copy_id}")
def patch_copy(
    copy_id: int,
    body: GeneratedCopyUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(_ops),
):
    copy = service.update_copy(db, copy_id, body)
    return ok(service.serialize_copy_detail(db, copy))


@router.delete("/{copy_id}")
def remove_copy(
    copy_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(_ops),
):
    service.delete_copy(db, copy_id)
    return ok({"deleted": True, "id": copy_id})
