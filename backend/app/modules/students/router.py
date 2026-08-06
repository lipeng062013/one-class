from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.responses import Response, StreamingResponse
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import get_current_user, require_permissions
from app.core.image_thumb import DEFAULT_THUMB_EDGE, read_image_variant
from app.core.responses import fail, ok
from app.core.storage import Storage, get_storage
from app.models.student import LearningRecordFile
from app.models.user import User
from app.modules.students import service as svc
from app.modules.students.schemas import (
    LearningRecordCreate,
    LearningRecordUpdate,
    StudentBulkDelete,
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


_student_roles = require_permissions("students.read", "students.write")
_student_manage_roles = require_permissions("students.write")


def _student_payload(db: Session, student, user: User) -> dict:
    payload = svc.student_to_dict(db, student)
    if user.role == "teacher":
        payload["phone"] = None
    return payload


@router.get("/students/managers")
def get_managers(
    include_inactive: bool = Query(True),
    db: Session = Depends(get_db),
    user: User = Depends(_student_roles),
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
    page: int = Query(1, ge=1, description="页码，从 1 开始"),
    page_size: int = Query(20, ge=1, le=100, description="每页条数，最大 100"),
    db: Session = Depends(get_db),
    user: User = Depends(_student_roles),
):
    result = svc.list_students(
        db,
        grade=grade,
        name=name,
        phone=None if user.role == "teacher" else phone,
        status=status,
        school=school,
        academic_manager_id=academic_manager_id,
        q=q,
        page=page,
        page_size=page_size,
        viewer=user,
    )
    return ok(
        {
            "items": [_student_payload(db, s, user) for s in result["items"]],
            "total": result["total"],
            "page": result["page"],
            "page_size": result["page_size"],
        }
    )


@router.post("/students")
def create_student(
    body: StudentCreate,
    db: Session = Depends(get_db),
    user: User = Depends(_student_manage_roles),
):
    payload = body.model_dump()
    # courses 为嵌套模型，已 model_dump 成 dict 列表
    result = svc.create_student(db, user, payload)
    if isinstance(result, str):
        return fail("STUDENT_CREATE_FAILED", result, status_code=400)
    return ok(svc.student_to_dict(db, result), status_code=201)


@router.post("/students/reassign")
def reassign_students(
    body: StudentReassign,
    db: Session = Depends(get_db),
    user: User = Depends(require_permissions("students.delete")),
):
    if not svc.can_reassign(user):
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


@router.post("/students/bulk-delete")
def bulk_delete_students(
    body: StudentBulkDelete,
    db: Session = Depends(get_db),
    user: User = Depends(require_permissions("students.delete")),
):
    if not svc.can_delete_student(user):
        return fail("FORBIDDEN", "仅负责人可删除学生", status_code=403)
    result = svc.bulk_delete_students(db, body.student_ids)
    if isinstance(result, str):
        return fail("BULK_DELETE_FAILED", result, status_code=400)
    return ok(result)


@router.get("/students/{student_id}")
def get_student(
    student_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(_student_roles),
):
    from app.core.roles import is_finance_scoped_role

    s = svc.get_student(db, student_id)
    if not s:
        return fail("NOT_FOUND", "学生不存在", status_code=404)
    # 学管师不可查看他人名下学员详情（报名深链等）
    if is_finance_scoped_role(user.role) and s.academic_manager_id != user.id:
        return fail("NOT_FOUND", "学生不存在", status_code=404)
    return ok(_student_payload(db, s, user))


@router.get("/students/{student_id}/course-packages")
def student_course_packages(
    student_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(_student_roles),
):
    """报读课程（课包聚合）。"""
    result = svc.list_student_course_packages(db, student_id)
    if result.get("error"):
        return fail("NOT_FOUND", result["error"], status_code=404)
    return ok(result)


@router.get("/students/{student_id}/orders")
def student_orders(
    student_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(_student_roles),
):
    """消费记录（财务订单，分页）。"""
    result = svc.list_student_orders(db, student_id, page=page, page_size=page_size)
    if result.get("error"):
        return fail("NOT_FOUND", result["error"], status_code=404)
    return ok(result)


@router.get("/students/{student_id}/activity")
def student_activity(
    student_id: int,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(_student_roles),
):
    """学员动态时间线。"""
    result = svc.list_student_activity(db, student_id, limit=limit)
    if result.get("error"):
        return fail("NOT_FOUND", result["error"], status_code=404)
    return ok(result)


@router.get("/students/{student_id}/class-records")
def student_class_records(
    student_id: int,
    view: str = Query("completed", pattern="^(completed|pending)$"),
    start: str | None = None,
    end: str | None = None,
    class_id: int | None = None,
    course_id: int | None = None,
    teacher_id: int | None = None,
    attendance_status: str | None = None,
    record_status: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(_student_roles),
):
    """学员详情中的已上课 / 待上课记录。"""
    result = svc.list_student_class_records(
        db,
        student_id,
        view=view,
        start=start,
        end=end,
        class_id=class_id,
        course_id=course_id,
        teacher_id=teacher_id,
        attendance_status=attendance_status,
        record_status=record_status,
        page=page,
        page_size=page_size,
    )
    if result.get("error"):
        return fail("NOT_FOUND", result["error"], status_code=404)
    return ok(result)


@router.get("/students/{student_id}/growth-report")
def download_growth_report(
    student_id: int,
    date_from: str | None = None,
    date_to: str | None = None,
    record_ids: str | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(_student_roles),
):
    """生成学情 PDF。

    - record_ids: 逗号分隔的学情记录 id，优先；只导出这些记录
    - date_from / date_to: 按上课日期区间过滤（无 record_ids 时生效）
    - 都不传：全部学情
    PDF 正文不展示区间文案。
    """
    from datetime import datetime
    from urllib.parse import quote

    from app.modules.students.report import GrowthReportFontError, build_growth_report_pdf

    s = svc.get_student(db, student_id)
    if not s:
        return fail("NOT_FOUND", "学生不存在", status_code=404)

    def _parse_dt(raw: str | None, *, end_of_day: bool = False) -> datetime | None:
        if not raw or not str(raw).strip():
            return None
        text = str(raw).strip().replace("Z", "+00:00")
        try:
            if len(text) == 10 and text[4] == "-" and text[7] == "-":
                dt = datetime.strptime(text, "%Y-%m-%d")
                if end_of_day:
                    return dt.replace(hour=23, minute=59, second=59, microsecond=999999)
                return dt
            return datetime.fromisoformat(text).replace(tzinfo=None)
        except ValueError:
            return None

    parsed_ids: list[int] = []
    if record_ids and str(record_ids).strip():
        for part in str(record_ids).replace(" ", "").split(","):
            if not part:
                continue
            try:
                parsed_ids.append(int(part))
            except ValueError:
                return fail("INVALID_RECORD_IDS", "record_ids 须为逗号分隔的数字 id", status_code=400)
        if not parsed_ids:
            return fail("INVALID_RECORD_IDS", "请至少选择一条学情记录", status_code=400)

    df = _parse_dt(date_from)
    dt = _parse_dt(date_to, end_of_day=True)
    if not parsed_ids:
        if date_from and df is None:
            return fail("INVALID_DATE", "date_from 格式无效，请用 YYYY-MM-DD", status_code=400)
        if date_to and dt is None:
            return fail("INVALID_DATE", "date_to 格式无效，请用 YYYY-MM-DD", status_code=400)
        if df is not None and dt is not None and df > dt:
            return fail("INVALID_DATE", "开始日期不能晚于结束日期", status_code=400)

    try:
        data, filename = build_growth_report_pdf(
            db,
            s,
            date_from=None if parsed_ids else df,
            date_to=None if parsed_ids else dt,
            record_ids=parsed_ids or None,
        )
    except GrowthReportFontError as e:
        return fail("GROWTH_REPORT_FONT_MISSING", str(e), status_code=500)
    except Exception as e:
        return fail("GROWTH_REPORT_FAILED", f"生成学情报告失败：{e}", status_code=500)
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
    _: User = Depends(_student_manage_roles),
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
    user: User = Depends(require_permissions("students.delete")),
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
    q: str | None = None,
    mine: bool | None = Query(
        None,
        description="True=仅自己填写；False=全部；默认：老师=自己，负责人=全部",
    ),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(_student_roles),
):
    tid = teacher_id
    # 显式 mine / 角色默认；带 student_id 时看该生全部学情（不强制填写人）
    want_mine = mine
    if want_mine is None:
        want_mine = (
            user.role == "teacher"
            and student_id is None
            and teacher_id is None
        )
    if want_mine and student_id is None:
        tid = user.id
    return ok(
        svc.list_learning_records(
            db,
            student_id=student_id,
            teacher_id=tid,
            q=q,
            page=page,
            page_size=page_size,
        )
    )


@router.post("/learning-records")
def create_learning(
    body: LearningRecordCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permissions("learning.write")),
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
    storage: Storage = Depends(get_storage),
    thumb: bool = Query(False, description="返回列表/网格用缩略图"),
    w: int | None = Query(None, ge=64, le=1280, description="缩略图最长边，默认 640"),
):
    mf = db.get(LearningRecordFile, file_id)
    if not mf:
        return fail("NOT_FOUND", "文件不存在", status_code=404)
    record = svc.get_learning_record(db, mf.record_id)
    if not record:
        return fail("NOT_FOUND", "学情不存在", status_code=404)
    if user.role not in {"admin", "operator", "teacher", "cr", "academic_manager"}:
        return fail("FORBIDDEN", "无权限", status_code=403)
    try:
        data, media_type = read_image_variant(
            storage,
            mf.file_path,
            thumb=thumb,
            max_edge=w or DEFAULT_THUMB_EDGE,
            original_media_type=mf.file_type or None,
        )
    except FileNotFoundError:
        return fail("NOT_FOUND", "文件不存在", status_code=404)

    headers = {"Cache-Control": "private, max-age=86400"} if thumb else {}
    return Response(content=data, media_type=media_type, headers=headers)


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
    user: User = Depends(require_permissions("learning.write")),
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
    user: User = Depends(require_permissions("learning.write")),
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
    user: User = Depends(require_permissions("learning.write")),
    storage: Storage = Depends(get_storage),
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
