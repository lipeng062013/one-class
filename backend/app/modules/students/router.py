from pathlib import Path

from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import get_current_user, require_roles
from app.core.responses import fail, ok
from app.core.storage import LocalStorage, get_storage
from app.models.student import LearningRecordFile
from app.models.user import User
from app.modules.students import service as svc
from app.modules.students.schemas import (
    LearningRecordCreate,
    LearningRecordUpdate,
    StudentCreate,
    StudentReassign,
    StudentUpdate,
)

router = APIRouter(tags=["students"])

ALLOWED_IMAGE_TYPES = {
    "image/png",
    "image/jpeg",
    "image/jpg",
    "image/webp",
    "image/gif",
}
MAX_FILE_SIZE = 8 * 1024 * 1024


# ── managers ──────────────────────────────────────────────


# 学生模块：运营不可见；仅 admin / teacher
_student_roles = require_roles("admin", "teacher")


@router.get("/students/managers")
def get_managers(
    include_inactive: bool = Query(True),
    db: Session = Depends(get_db),
    _: User = Depends(_student_roles),
):
    return ok(svc.list_managers(db, include_inactive=include_inactive))


# ── students CRUD ─────────────────────────────────────────


@router.get("/students")
def list_students(
    grade: str | None = None,
    name: str | None = None,
    phone: str | None = None,
    status: str | None = None,
    school: str | None = None,
    academic_manager_id: int | None = None,
    q: str | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(_student_roles),
):
    rows = svc.list_students(
        db,
        grade=grade,
        name=name,
        phone=phone,
        status=status,
        school=school,
        academic_manager_id=academic_manager_id,
        q=q,
    )
    return ok([svc.student_to_dict(db, s) for s in rows])


@router.post("/students")
def create_student(
    body: StudentCreate,
    db: Session = Depends(get_db),
    user: User = Depends(_student_roles),
):
    result = svc.create_student(db, user, body.model_dump())
    if isinstance(result, str):
        return fail("STUDENT_CREATE_FAILED", result, status_code=400)
    return ok(svc.student_to_dict(db, result), status_code=201)


@router.post("/students/reassign")
def reassign_students(
    body: StudentReassign,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin")),
):
    if user.role != "admin":
        return fail("FORBIDDEN", "无权限转交", status_code=403)
    result = svc.reassign_students(
        db,
        student_ids=body.student_ids,
        to_manager_id=body.to_manager_id,
        from_manager_id=body.from_manager_id,
    )
    if isinstance(result, str):
        return fail("REASSIGN_FAILED", result, status_code=400)
    return ok(result)


@router.get("/students/{student_id}")
def get_student(
    student_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(_student_roles),
):
    s = svc.get_student(db, student_id)
    if not s:
        return fail("NOT_FOUND", "学生不存在", status_code=404)
    return ok(svc.student_to_dict(db, s))


@router.get("/students/{student_id}/growth-report")
def download_growth_report(
    student_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(_student_roles),
):
    from urllib.parse import quote

    from app.modules.students.report import build_growth_report_pdf

    s = svc.get_student(db, student_id)
    if not s:
        return fail("NOT_FOUND", "学生不存在", status_code=404)
    data, filename = build_growth_report_pdf(db, s)
    encoded = quote(filename)
    return StreamingResponse(
        iter([data]),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{encoded}",
        },
    )


@router.patch("/students/{student_id}")
def patch_student(
    student_id: int,
    body: StudentUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(_student_roles),
):
    s = svc.get_student(db, student_id)
    if not s:
        return fail("NOT_FOUND", "学生不存在", status_code=404)
    result = svc.update_student(db, s, body.model_dump(exclude_unset=True))
    if isinstance(result, str):
        return fail("STUDENT_UPDATE_FAILED", result, status_code=400)
    return ok(svc.student_to_dict(db, result))


@router.delete("/students/{student_id}")
def delete_student(
    student_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin")),
):
    s = svc.get_student(db, student_id)
    if not s:
        return fail("NOT_FOUND", "学生不存在", status_code=404)
    if not svc.can_delete_student(user):
        return fail("FORBIDDEN", "仅负责人可删除学生", status_code=403)
    svc.delete_student(db, s)
    return ok({"deleted": True, "id": student_id})


# ── learning records ──────────────────────────────────────


@router.get("/learning-records")
def list_learning(
    student_id: int | None = None,
    teacher_id: int | None = None,
    mine: bool = False,
    db: Session = Depends(get_db),
    user: User = Depends(_student_roles),
):
    tid = teacher_id
    if mine or (user.role == "teacher" and teacher_id is None and student_id is None):
        # 老师默认看自己的；若带了 student_id 则看该学生全部学情
        if student_id is None:
            tid = user.id
    rows = svc.list_learning_records(db, student_id=student_id, teacher_id=tid)
    return ok([svc.learning_to_dict(db, r) for r in rows])


@router.post("/learning-records")
def create_learning(
    body: LearningRecordCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "teacher")),
):
    if not svc.can_write_learning(user):
        return fail("FORBIDDEN", "无权限写学情", status_code=403)
    result = svc.create_learning_record(db, user, body.model_dump())
    if isinstance(result, str):
        return fail("LEARNING_CREATE_FAILED", result, status_code=400)
    return ok(svc.learning_to_dict(db, result), status_code=201)


@router.get("/learning-records/files/{file_id}/content")
def download_learning_file(
    file_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    storage: LocalStorage = Depends(get_storage),
):
    mf = db.get(LearningRecordFile, file_id)
    if not mf:
        return fail("NOT_FOUND", "文件不存在", status_code=404)
    record = svc.get_learning_record(db, mf.record_id)
    if not record:
        return fail("NOT_FOUND", "学情不存在", status_code=404)
    if user.role not in {"admin", "operator", "teacher"}:
        return fail("FORBIDDEN", "无权限", status_code=403)
    try:
        data = storage.read(mf.file_path)
    except FileNotFoundError:
        return fail("NOT_FOUND", "文件不存在", status_code=404)

    media_type = mf.file_type or "application/octet-stream"
    if not media_type.startswith("image/"):
        suffix = Path(mf.file_path).suffix.lower()
        media_type = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".webp": "image/webp",
            ".gif": "image/gif",
        }.get(suffix, media_type)
    return StreamingResponse(iter([data]), media_type=media_type)


@router.get("/learning-records/{record_id}")
def get_learning(
    record_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(_student_roles),
):
    r = svc.get_learning_record(db, record_id)
    if not r:
        return fail("NOT_FOUND", "学情不存在", status_code=404)
    return ok(svc.learning_to_dict(db, r))


@router.patch("/learning-records/{record_id}")
def patch_learning(
    record_id: int,
    body: LearningRecordUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "teacher")),
):
    r = svc.get_learning_record(db, record_id)
    if not r:
        return fail("NOT_FOUND", "学情不存在", status_code=404)
    result = svc.update_learning_record(db, user, r, body.model_dump(exclude_unset=True))
    if isinstance(result, str):
        code = 403 if "只能" in result else 400
        return fail("LEARNING_UPDATE_FAILED", result, status_code=code)
    return ok(svc.learning_to_dict(db, result))


@router.delete("/learning-records/{record_id}")
def delete_learning(
    record_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "teacher")),
):
    r = svc.get_learning_record(db, record_id)
    if not r:
        return fail("NOT_FOUND", "学情不存在", status_code=404)
    err = svc.delete_learning_record(db, user, r)
    if err:
        return fail("FORBIDDEN", err, status_code=403)
    return ok({"deleted": True, "id": record_id})


@router.post("/learning-records/{record_id}/files")
async def upload_learning_file(
    record_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "teacher")),
    storage: LocalStorage = Depends(get_storage),
):
    r = svc.get_learning_record(db, record_id)
    if not r:
        return fail("NOT_FOUND", "学情不存在", status_code=404)
    if user.role != "admin" and r.teacher_id != user.id:
        return fail("FORBIDDEN", "只能为自己的学情上传图片", status_code=403)

    content_type = file.content_type or "application/octet-stream"
    if content_type not in ALLOWED_IMAGE_TYPES and not content_type.startswith("image/"):
        return fail("INVALID_FILE", "仅支持图片上传", status_code=400)

    data = await file.read()
    if len(data) > MAX_FILE_SIZE:
        return fail("FILE_TOO_LARGE", "单文件不能超过 8MB", status_code=400)
    if not data:
        return fail("EMPTY_FILE", "文件为空", status_code=400)

    mf = svc.add_learning_file(
        db,
        storage,
        r,
        filename=file.filename or "upload.bin",
        content=data,
        content_type=content_type,
    )
    return ok(
        {
            "id": mf.id,
            "file_path": mf.file_path,
            "file_type": mf.file_type,
            "sort_order": mf.sort_order,
        },
        status_code=201,
    )
