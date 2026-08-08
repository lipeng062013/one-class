from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import require_permissions
from app.core.responses import fail, ok
from app.core.storage import Storage, get_storage
from app.models.enrollment import EnrollmentRecord
from app.models.user import User
from app.modules.enrollments import service as svc
from app.modules.enrollments.schemas import EnrollmentCreate

router = APIRouter(prefix="/enrollments", tags=["enrollments"])

_admin = require_permissions("enrollments.manage")

ALLOWED_IMAGE_TYPES = {"image/png", "image/jpeg", "image/jpg", "image/webp"}
MAX_FILE_SIZE = 20 * 1024 * 1024


@router.get("")
def list_enrollments(
    student_id: int | None = None,
    kind: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(_admin),
):
    return ok(
        svc.list_records(
            db,
            student_id=student_id,
            kind=kind,
            page=page,
            page_size=page_size,
            viewer=user,
        )
    )


@router.post("")
def create_enrollment(
    body: EnrollmentCreate,
    db: Session = Depends(get_db),
    user: User = Depends(_admin),
):
    result = svc.create_record(
        db,
        user,
        {
            "student_id": body.student_id,
            "kind": body.kind,
            "handled_at": body.handled_at,
            "amount": body.amount,
            "courses": [c.model_dump() for c in body.courses],
            "attributions": [a.model_dump() for a in body.attributions],
            "pay_methods": list(body.pay_methods),
            "pay_other": body.pay_other,
            "payments": [p.model_dump() for p in body.payments],
            "internal_notes": body.internal_notes,
            "external_notes": body.external_notes,
            "internal_images": body.internal_images,
            "transfer_mode": body.transfer_mode,
            "transfer_out_course_id": body.transfer_out_course_id,
            "transfer_out_items": [t.model_dump() for t in body.transfer_out_items],
            "transfer_to_student_id": body.transfer_to_student_id,
        },
    )
    if isinstance(result, str):
        return fail("ENROLLMENT_CREATE_FAILED", result, status_code=400)
    return ok(svc.record_to_dict(db, result), status_code=201)


@router.post("/note-images")
async def upload_note_image(
    file: UploadFile = File(...),
    storage: Storage = Depends(get_storage),
    _: User = Depends(_admin),
):
    content_type = (file.content_type or "").lower()
    if content_type not in ALLOWED_IMAGE_TYPES:
        return fail("INVALID_FILE", "仅支持 jpg / png / webp", status_code=400)
    data = await file.read()
    if len(data) > MAX_FILE_SIZE:
        return fail("FILE_TOO_LARGE", "单张图片不能超过 20MB", status_code=400)
    if not data:
        return fail("EMPTY_FILE", "文件为空", status_code=400)
    path = svc.save_note_image(storage, data, content_type)
    return ok({"path": path}, status_code=201)


@router.get("/note-images/content")
def read_note_image(
    path: str = Query(..., min_length=1),
    storage: Storage = Depends(get_storage),
    _: User = Depends(_admin),
):
    # 仅允许报名备注目录，防路径穿越
    norm = path.replace("\\", "/").lstrip("/")
    if not norm.startswith("enrollments/notes/") or ".." in norm:
        return fail("INVALID_PATH", "非法路径", status_code=400)
    if not storage.exists(norm):
        return fail("NOT_FOUND", "图片不存在", status_code=404)
    raw = storage.read(norm)
    media = "image/jpeg"
    if norm.endswith(".png"):
        media = "image/png"
    elif norm.endswith(".webp"):
        media = "image/webp"
    return Response(content=raw, media_type=media)


@router.get("/{record_id}")
def get_enrollment(
    record_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(_admin),
):
    row = db.get(EnrollmentRecord, record_id)
    if not row:
        return fail("NOT_FOUND", "记录不存在", status_code=404)
    return ok(svc.record_to_dict(db, row))
