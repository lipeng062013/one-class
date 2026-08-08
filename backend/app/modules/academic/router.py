from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import require_permissions
from app.core.responses import fail, ok
from app.models.user import User
from app.modules.academic import service as svc
from app.modules.academic.schemas import (
    ClassAttendanceUpdate,
    ClassCreate,
    ClassRecordCreate,
    ClassRecordUpdate,
    ClassStudentsAdd,
    ClassUpdate,
    CourseCreate,
    CourseUpdate,
    ScheduleBatchCreate,
    ScheduleBatchDelete,
    ScheduleBatchUpdate,
    ScheduleConflictQuery,
    ScheduleCreate,
    ScheduleUpdate,
)

router = APIRouter(prefix="/academic", tags=["academic"])

_staff = require_permissions("academic.read", "academic.write")
# 业务页筛选项/报名选课目录：教务读写、报名权、财务只读均可（运营有 finance.read 但无 academic.read）
_catalog = require_permissions(
    "academic.read",
    "academic.write",
    "enrollments.manage",
    "finance.read",
)
# 点名/课消写操作：仅 academic.write（老师默认只有 academic.read，无需点名）
_write = require_permissions("academic.write")
_admin = require_permissions("academic.courses_admin")


# ── 课程 ──────────────────────────────────────────────


@router.get("/courses")
def list_courses(
    q: Optional[str] = None,
    course_type: Optional[str] = None,
    enabled: Optional[bool] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(_catalog),
):
    return ok(
        svc.list_courses(
            db, q=q, course_type=course_type, enabled=enabled, page=page, page_size=page_size
        )
    )


@router.get("/courses/{course_id}")
def get_course(
    course_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(_catalog),
):
    from app.models.academic import Course

    row = db.get(Course, course_id)
    if not row:
        return fail("NOT_FOUND", "课程不存在", status_code=404)
    return ok(svc.course_to_dict(db, row))


@router.get("/courses/{course_id}/eligible-students")
def list_course_eligible_students(
    course_id: int,
    q: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(_staff),
):
    result = svc.list_course_eligible_students(
        db, course_id, q=q, page=page, page_size=page_size, viewer=user
    )
    if result is None:
        return fail("NOT_FOUND", "课程不存在", status_code=404)
    return ok(result)


@router.post("/courses")
def create_course(
    body: CourseCreate,
    db: Session = Depends(get_db),
    user: User = Depends(_admin),
):
    result = svc.create_course(db, user, body.model_dump())
    if isinstance(result, str):
        return fail("COURSE_CREATE_FAILED", result, status_code=400)
    return ok(svc.course_to_dict(db, result), status_code=201)


@router.patch("/courses/{course_id}")
def update_course(
    course_id: int,
    body: CourseUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(_admin),
):
    result = svc.update_course(db, course_id, body.model_dump(exclude_unset=True))
    if isinstance(result, str):
        return fail("COURSE_UPDATE_FAILED", result, status_code=400)
    return ok(svc.course_to_dict(db, result))


@router.delete("/courses/{course_id}")
def delete_course(
    course_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(_admin),
):
    err = svc.delete_course(db, course_id)
    if err:
        return fail("COURSE_DELETE_FAILED", err, status_code=400)
    return ok({"ok": True})


# ── 班级 ──────────────────────────────────────────────


@router.get("/classes")
def list_classes(
    mode: Optional[str] = None,
    q: Optional[str] = None,
    course_id: Optional[int] = None,
    teacher_id: Optional[int] = None,
    only_mine: bool = False,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(_catalog),
):
    return ok(
        svc.list_classes(
            db,
            mode=mode,
            q=q,
            course_id=course_id,
            teacher_id=teacher_id,
            only_mine=only_mine,
            user=user,
            page=page,
            page_size=page_size,
        )
    )


@router.post("/classes")
def create_class(
    body: ClassCreate,
    db: Session = Depends(get_db),
    user: User = Depends(_write),
):
    """建班：负责人 / 学管师（academic.write）可操作。"""
    result = svc.create_class(db, user, body.model_dump())
    if isinstance(result, str):
        return fail("CLASS_CREATE_FAILED", result, status_code=400)
    return ok(svc.class_to_dict(db, result, viewer=user), status_code=201)


@router.get("/classes/{class_id}")
def get_class(
    class_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(_staff),
):
    from app.models.academic import ClassRoom

    row = db.get(ClassRoom, class_id)
    if not row:
        return fail("NOT_FOUND", "班级不存在", status_code=404)
    return ok(svc.class_to_dict(db, row, viewer=user))


@router.patch("/classes/{class_id}")
def update_class(
    class_id: int,
    body: ClassUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(_write),
):
    result = svc.update_class(db, class_id, body.model_dump(exclude_unset=True))
    if isinstance(result, str):
        return fail("CLASS_UPDATE_FAILED", result, status_code=400)
    return ok(svc.class_to_dict(db, result, viewer=user))


@router.post("/classes/{class_id}/students")
def add_class_students(
    class_id: int,
    body: ClassStudentsAdd,
    db: Session = Depends(get_db),
    user: User = Depends(_write),
):
    result = svc.add_class_students(db, class_id, body.student_ids)
    if isinstance(result, str):
        return fail("CLASS_STUDENT_ADD_FAILED", result, status_code=400)
    return ok(svc.class_to_dict(db, result, viewer=user))


@router.delete("/classes/{class_id}/students/{student_id}")
def remove_class_student(
    class_id: int,
    student_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(_write),
):
    result = svc.remove_class_student(db, class_id, student_id)
    if isinstance(result, str):
        return fail("CLASS_STUDENT_REMOVE_FAILED", result, status_code=400)
    return ok(svc.class_to_dict(db, result, viewer=user))


@router.delete("/classes/{class_id}")
def delete_class(
    class_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(_write),
):
    err = svc.delete_class(db, class_id)
    if err:
        return fail("CLASS_DELETE_FAILED", err, status_code=400)
    return ok({"ok": True})


# ── 排课 ──────────────────────────────────────────────


@router.get("/schedules")
def list_schedules(
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    class_id: Optional[int] = None,
    course_id: Optional[int] = None,
    teacher_id: Optional[int] = None,
    room: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    user: User = Depends(_staff),
):
    # 老师默认有 academic.read：仅可看自己所带课次
    effective_teacher_id = user.id if user.role == "teacher" else teacher_id
    return ok(
        svc.list_schedules(
            db,
            start=start,
            end=end,
            class_id=class_id,
            course_id=course_id,
            teacher_id=effective_teacher_id,
            room=room,
            page=page,
            page_size=page_size,
        )
    )


@router.get("/rooms")
def list_rooms(
    db: Session = Depends(get_db),
    _: User = Depends(_staff),
):
    return ok({"items": svc.list_rooms(db)})


@router.post("/schedules/conflicts")
def check_schedule_conflicts(
    body: ScheduleConflictQuery,
    db: Session = Depends(get_db),
    _: User = Depends(_write),
):
    return ok(
        svc.find_conflicts(
            db,
            start_at=body.start_at,
            end_at=body.end_at,
            teacher_ids=body.teacher_ids,
            room=body.room,
            exclude_id=body.exclude_id,
        )
    )


@router.post("/schedules/availability")
def schedule_availability(
    body: ScheduleConflictQuery,
    db: Session = Depends(get_db),
    _: User = Depends(_write),
):
    """新建排课：返回老师/教室空闲与冲突状态。"""
    return ok(
        svc.availability_for_resources(
            db,
            start_at=body.start_at,
            end_at=body.end_at,
            exclude_id=body.exclude_id,
        )
    )


@router.post("/schedules")
def create_schedule(
    body: ScheduleCreate,
    db: Session = Depends(get_db),
    user: User = Depends(_write),
):
    result = svc.create_schedule(db, user, body.model_dump())
    if isinstance(result, str):
        return fail("SCHEDULE_CREATE_FAILED", result, status_code=400)
    return ok(svc.schedule_to_dict(db, result), status_code=201)


@router.post("/schedules/batch")
def create_schedules_batch(
    body: ScheduleBatchCreate,
    db: Session = Depends(get_db),
    user: User = Depends(_write),
):
    result = svc.create_schedules_batch(db, user, body.model_dump())
    if isinstance(result, str):
        return fail("SCHEDULE_BATCH_FAILED", result, status_code=400)
    return ok(result, status_code=201)


@router.post("/schedules/batch-update")
def update_schedules_batch(
    body: ScheduleBatchUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(_write),
):
    """批量修改课次（换老师/教室/时间/内容）；与课表同源，修改即同步。"""
    result = svc.update_schedules_batch(db, body.model_dump())
    if isinstance(result, str):
        return fail("SCHEDULE_BATCH_UPDATE_FAILED", result, status_code=400)
    return ok(result)


@router.post("/schedules/batch-delete")
def delete_schedules_batch(
    body: ScheduleBatchDelete,
    db: Session = Depends(get_db),
    _: User = Depends(_write),
):
    result = svc.delete_schedules_batch(db, body.model_dump())
    if isinstance(result, str):
        return fail("SCHEDULE_BATCH_DELETE_FAILED", result, status_code=400)
    return ok(result)


@router.get("/schedules/{lesson_id}")
def get_schedule(
    lesson_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(_staff),
):
    """课次详情（侧栏：课次信息 + 上课学员）。"""
    from app.models.academic import ScheduleLesson

    row = db.get(ScheduleLesson, lesson_id)
    if not row or row.status == "cancelled":
        return fail("NOT_FOUND", "课次不存在", status_code=404)
    if not svc.user_can_view_schedule(db, user, row):
        return fail("FORBIDDEN", "只能查看自己所带的课次", status_code=403)
    detail = svc.get_schedule_detail(db, lesson_id, viewer=user)
    if not detail:
        return fail("NOT_FOUND", "课次不存在", status_code=404)
    return ok(detail)


@router.patch("/schedules/{lesson_id}")
def update_schedule(
    lesson_id: int,
    body: ScheduleUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(_write),
):
    result = svc.update_schedule(db, lesson_id, body.model_dump(exclude_unset=True))
    if isinstance(result, str):
        return fail("SCHEDULE_UPDATE_FAILED", result, status_code=400)
    return ok(svc.schedule_to_dict(db, result))


@router.delete("/schedules/{lesson_id}")
def delete_schedule(
    lesson_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(_write),
):
    err = svc.delete_schedule(db, lesson_id)
    if err:
        return fail("SCHEDULE_DELETE_FAILED", err, status_code=400)
    return ok({"ok": True})


# ── 上课记录 / 点名 ────────────────────────────────────


@router.get("/class-records/roll-options")
def get_roll_call_options(
    target_date: Optional[date] = Query(None, alias="date", description="锚点日期，默认今天"),
    start: Optional[date] = Query(None, description="开始日期（含）"),
    end: Optional[date] = Query(None, description="结束日期（含）"),
    db: Session = Depends(get_db),
    user: User = Depends(_write),
):
    return ok(
        svc.get_roll_call_options(
            db,
            user,
            target_date=target_date,
            start=start,
            end=end,
        )
    )


@router.get("/class-records")
def list_class_records(
    class_id: Optional[int] = None,
    course_id: Optional[int] = None,
    teacher_id: Optional[int] = None,
    status: Optional[str] = None,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    class_start: Optional[datetime] = None,
    class_end: Optional[datetime] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(_staff),
):
    return ok(
        svc.list_class_records(
            db,
            class_id=class_id,
            course_id=course_id,
            teacher_id=teacher_id,
            status=status,
            start=start,
            end=end,
            class_start=class_start,
            class_end=class_end,
            page=page,
            page_size=page_size,
        )
    )


@router.get("/class-records/timeout")
def list_timeout_class_records(
    class_id: Optional[int] = None,
    course_id: Optional[int] = None,
    teacher_id: Optional[int] = None,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(_staff),
):
    return ok(
        svc.list_timeout_class_records(
            db,
            class_id=class_id,
            course_id=course_id,
            teacher_id=teacher_id,
            start=start,
            end=end,
            page=page,
            page_size=page_size,
        )
    )


@router.get("/class-records/makeup")
def list_makeup_class_records(
    q: Optional[str] = None,
    class_id: Optional[int] = None,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(_staff),
):
    return ok(
        svc.list_makeup_class_records(
            db,
            q=q,
            class_id=class_id,
            start=start,
            end=end,
            page=page,
            page_size=page_size,
        )
    )


@router.get("/class-records/{record_id}")
def get_class_record(
    record_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(_staff),
):
    result = svc.get_class_record_detail(db, record_id, viewer=user)
    if result is None:
        return fail("NOT_FOUND", "上课记录不存在", status_code=404)
    return ok(result)


@router.get("/class-records/{record_id}/logs")
def list_class_record_logs(
    record_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(_staff),
):
    result = svc.list_class_record_logs(db, record_id)
    if result is None:
        return fail("NOT_FOUND", "上课记录不存在", status_code=404)
    return ok({"items": result})


@router.post("/class-records")
def create_class_record(
    body: ClassRecordCreate,
    db: Session = Depends(get_db),
    user: User = Depends(_write),
):
    result = svc.create_class_record(
        db,
        user,
        {
            **body.model_dump(),
            "attendances": [a.model_dump() for a in body.attendances],
        },
    )
    if isinstance(result, str):
        return fail("CLASS_RECORD_CREATE_FAILED", result, status_code=400)
    return ok(svc.class_record_to_dict(db, result), status_code=201)


@router.patch("/class-records/{record_id}")
def update_class_record(
    record_id: int,
    body: ClassRecordUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(_write),
):
    result = svc.update_class_record(
        db,
        user,
        record_id,
        body.model_dump(exclude_unset=True),
    )
    if isinstance(result, str):
        return fail("CLASS_RECORD_UPDATE_FAILED", result, status_code=400)
    return ok(svc.get_class_record_detail(db, result.id, viewer=user))


@router.patch("/class-records/{record_id}/attendances/{student_id}")
def update_class_attendance(
    record_id: int,
    student_id: int,
    body: ClassAttendanceUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(_write),
):
    result = svc.update_class_attendance(db, user, record_id, student_id, body.status)
    if isinstance(result, str):
        return fail("CLASS_ATTENDANCE_UPDATE_FAILED", result, status_code=400)
    return ok(svc.get_class_record_detail(db, result.id, viewer=user))


@router.delete("/class-records/{record_id}/attendances/{student_id}")
def remove_class_attendance(
    record_id: int,
    student_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(_write),
):
    result = svc.remove_class_attendance(db, user, record_id, student_id)
    if isinstance(result, str):
        return fail("CLASS_ATTENDANCE_REMOVE_FAILED", result, status_code=400)
    return ok(svc.get_class_record_detail(db, result.id, viewer=user))


@router.post("/class-records/{record_id}/void")
def void_class_record(
    record_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(_write),
):
    result = svc.void_class_record(db, user, record_id)
    if isinstance(result, str):
        return fail("CLASS_RECORD_VOID_FAILED", result, status_code=400)
    return ok(svc.class_record_to_dict(db, result))


# ── 老师管理（基于 users.role=teacher） ────────────────


@router.get("/teachers")
def list_teachers(
    q: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(_catalog),
):
    return ok(svc.list_teachers_manage(db, q=q, page=page, page_size=page_size))
