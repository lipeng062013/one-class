import json
from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import get_current_user, require_permissions
from app.core.responses import ok
from app.core.timeutil import day_end, day_start, today as business_today
from app.models.academic import ClassMember, ClassRecord, ClassRoom, Course, ScheduleLesson
from app.models.content import GeneratedCopy
from app.models.enrollment import EnrollmentRecord
from app.models.lead import Lead, LeadCollaborator
from app.models.material import Material
from app.models.student import Student
from app.models.user import User

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary")
def dashboard_summary(
    db: Session = Depends(get_db),
    _: User = Depends(require_permissions("dashboard.read")),
):
    materials_new = db.query(func.count(Material.id)).filter(Material.status == "new").scalar() or 0

    today = business_today()
    range_start = day_start(today)
    range_end = day_end(today)

    # Prefer next_follow_at on today; also count status==new as follow-ups
    leads_follow_today = (
        db.query(func.count(Lead.id))
        .filter(
            or_(
                and_(Lead.next_follow_at >= range_start, Lead.next_follow_at <= range_end),
                Lead.status == "new",
            )
        )
        .scalar()
        or 0
    )

    recent_copies = db.query(func.count(GeneratedCopy.id)).scalar() or 0

    return ok(
        {
            "materials_new": materials_new,
            "leads_follow_today": leads_follow_today,
            "recent_copies": recent_copies,
        }
    )


@router.get("/today-todos")
def today_todos(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Role-aware workbench items for today's follow-ups, courses and roll call.

    课表待办：学管师/负责人完成点名后自动 is_done=True（撤销点名后恢复未完成）。
    """
    today = business_today()
    start = day_start(today)
    end = day_end(today)
    # 线索 next_follow_at 可能带时区信息，按业务日墙钟比较
    lead_start = start
    lead_end = end
    rows: list[dict] = []
    next_id = -1

    def add(
        title: str,
        content: str,
        path: str,
        *,
        is_done: bool = False,
        source: str | None = None,
        ref_id: int | None = None,
    ) -> None:
        nonlocal next_id
        rows.append(
            {
                "id": next_id,
                "user_id": user.id,
                "title": title,
                "content": content,
                "is_done": is_done,
                "created_at": None,
                "completed_at": None,
                "kind": "system",
                "path": path,
                "source": source,
                "ref_id": ref_id,
            }
        )
        next_id -= 1

    if user.role in {"admin", "operator", "cr", "academic_manager"}:
        lead_query = db.query(Lead).filter(
            or_(
                and_(Lead.next_follow_at >= lead_start, Lead.next_follow_at <= lead_end),
                Lead.status == "new",
            )
        )
        if user.role != "admin":
            lead_query = lead_query.filter(
                or_(
                    Lead.owner_id == user.id,
                    Lead.id.in_(
                        db.query(LeadCollaborator.lead_id).filter(
                            LeadCollaborator.user_id == user.id
                        )
                    ),
                )
            )
        leads = lead_query.order_by(Lead.id.asc()).all()
        for lead in leads:
            add(
                "线索今日跟进",
                lead.student_or_parent_name,
                f"/leads/{lead.id}",
                source="lead",
                ref_id=lead.id,
            )

    # 负责人：报名成功且尚未分配学管的线索转入学员
    if user.role == "admin":
        enrolled_ids = {
            row[0]
            for row in db.query(EnrollmentRecord.student_id)
            .filter(EnrollmentRecord.kind == "enroll")
            .distinct()
            .all()
        }
        if enrolled_ids:
            pending = (
                db.query(Student)
                .filter(
                    Student.source_lead_id.isnot(None),
                    Student.academic_manager_id.is_(None),
                    Student.id.in_(enrolled_ids),
                )
                .order_by(Student.id.desc())
                .limit(50)
                .all()
            )
            for stu in pending:
                add(
                    "报名成功待调配",
                    f"{stu.name} · 请分配学管",
                    f"/students/{stu.id}",
                    source="student_allocation",
                    ref_id=stu.id,
                )

    if user.role in {"admin", "cr", "academic_manager", "teacher"}:
        schedules = (
            db.query(ScheduleLesson, ClassRoom, Course)
            .join(ClassRoom, ClassRoom.id == ScheduleLesson.class_id, isouter=True)
            .join(Course, Course.id == ScheduleLesson.course_id, isouter=True)
            .filter(
                ScheduleLesson.start_at >= start,
                ScheduleLesson.start_at <= end,
                ScheduleLesson.status != "cancelled",
            )
            .order_by(ScheduleLesson.start_at.asc())
            .all()
        )
        managed_class_ids: set[int] | None = None
        if user.role in {"cr", "academic_manager"}:
            managed_class_ids = {
                row[0]
                for row in db.query(ClassMember.class_id)
                .join(Student, Student.id == ClassMember.student_id)
                .filter(
                    Student.academic_manager_id == user.id,
                    ClassMember.status == "active",
                )
                .distinct()
                .all()
            }

        # 批量查今日课表已有效点名记录，避免 N+1
        lesson_ids = [lesson.id for lesson, _, _ in schedules]
        rolled_map: dict[int, int] = {}
        if lesson_ids:
            for schedule_id, record_id in (
                db.query(ClassRecord.schedule_id, ClassRecord.id)
                .filter(
                    ClassRecord.schedule_id.in_(lesson_ids),
                    ClassRecord.status != "void",
                )
                .all()
            ):
                if schedule_id is not None and schedule_id not in rolled_map:
                    rolled_map[int(schedule_id)] = int(record_id)

        for lesson, classroom, course in schedules:
            if managed_class_ids is not None and lesson.class_id not in managed_class_ids:
                continue
            if user.role == "teacher":
                try:
                    teacher_ids = [int(x) for x in json.loads(lesson.teacher_ids or "[]")]
                except (TypeError, ValueError, json.JSONDecodeError):
                    teacher_ids = []
                if user.id not in teacher_ids:
                    continue

            label = course.name if course else (classroom.name if classroom else "今日课程")
            time_label = ""
            if lesson.start_at and lesson.end_at:
                time_label = (
                    f"{lesson.start_at.strftime('%H:%M')}-{lesson.end_at.strftime('%H:%M')}"
                )
            elif lesson.start_at:
                time_label = lesson.start_at.strftime("%H:%M")
            content_parts = [p for p in (time_label, label) if p]
            if lesson.room:
                content_parts.append(lesson.room)
            content = " · ".join(content_parts) if content_parts else label

            record_id = rolled_map.get(lesson.id)
            is_done = record_id is not None
            # 课表 status=completed 也视为已点名（兼容历史）
            if not is_done and lesson.status == "completed":
                is_done = True

            if is_done:
                content = f"{content} · 已点名" if content else "已点名"

            # 学管/负责人主操作是点名；老师看课表；点名后可进上课记录
            if user.role in {"admin", "cr", "academic_manager"}:
                title = "班级点名"
                if record_id:
                    path = f"/academic/class-records/{record_id}"
                else:
                    path = "/academic/class-records"
            else:
                title = "今日课程"
                if record_id:
                    path = f"/academic/class-records/{record_id}"
                else:
                    path = "/academic/schedule"

            add(
                title,
                content,
                path,
                is_done=is_done,
                source="schedule",
                ref_id=lesson.id,
            )
    return ok(rows)
