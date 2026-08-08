"""教务业务：课程、班级、排课、点名扣课。"""

from __future__ import annotations

import json
from datetime import date, datetime, time, timedelta

from sqlalchemy import case, or_
from sqlalchemy.orm import Session

from app.core.pagination import clamp_page, clamp_page_size, page_payload, paginate_query
from app.core.phone import phone_for_viewer
from app.core.roles import ROLE_DISPLAY_LABEL, TEACHING_STAFF_ROLES, is_teaching_staff
from app.core.timeutil import now as _utcnow
from app.core.timeutil import today as business_today
from app.models.academic import (
    ClassAttendance,
    ClassMember,
    ClassRecord,
    ClassRecordOperationLog,
    ClassRoom,
    ClassTeacher,
    Course,
    ScheduleLesson,
    StudentCoursePackage,
)
from app.models.finance import CourseConsumption
from app.models.student import Student
from app.models.user import User

# 默认教室清单（可与历史排课合并）
DEFAULT_ROOMS = [
    "小学部4教",
    "小学部6教",
    "小学部7教",
    "小学部10教",
    "新城203教室",
    "301",
    "302",
]

def _parse_ids(raw: str | None) -> list[int]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
        if not isinstance(data, list):
            return []
        out: list[int] = []
        for x in data:
            try:
                out.append(int(x))
            except (TypeError, ValueError):
                continue
        return out
    except (TypeError, json.JSONDecodeError):
        return []

def _parse_json_list(raw: str | None) -> list[dict]:
    if not raw:
        return []
    try:
        value = json.loads(raw)
    except (TypeError, ValueError):
        return []
    return value if isinstance(value, list) else []

def _student_linked_to_course(db: Session, student: Student, course_id: int) -> bool:
    package = (
        db.query(StudentCoursePackage.id)
        .filter(
            StudentCoursePackage.student_id == student.id,
            StudentCoursePackage.course_id == course_id,
            StudentCoursePackage.status != "refunded",
        )
        .first()
    )
    if package:
        return True
    for link in _parse_json_list(student.linked_courses):
        try:
            if int(link.get("id")) == course_id:
                return True
        except (TypeError, ValueError):
            continue
    return False

def _teacher_names(db: Session, ids: list[int]) -> str:
    if not ids:
        return ""
    users = db.query(User).filter(User.id.in_(ids)).all()
    by_id = {u.id: (u.display_name or u.username) for u in users}
    return "、".join(by_id[i] for i in ids if i in by_id)

def _course_type_label(t: str) -> str:
    return "一对一" if t == "one_to_one" else "一对多"

def course_to_dict(db: Session, row: Course) -> dict:
    pkg_students = (
        db.query(StudentCoursePackage.student_id)
        .filter(
            StudentCoursePackage.course_id == row.id,
            StudentCoursePackage.status == "active",
            StudentCoursePackage.remain_hours > 0,
        )
        .distinct()
        .count()
    )
    class_students = (
        db.query(ClassMember.student_id)
        .join(ClassRoom, ClassRoom.id == ClassMember.class_id)
        .filter(
            ClassRoom.course_id == row.id,
            ClassRoom.status == "active",
            ClassMember.status == "active",
        )
        .distinct()
        .count()
    )
    student_count = max(pkg_students, class_students)
    price_label = (
        f"单价({int(row.unit_price) if row.unit_price == int(row.unit_price) else row.unit_price}元/课时)"
        if row.billing_mode == "hour"
        else f"{row.unit_price}元"
    )
    return {
        "id": row.id,
        "name": row.name,
        "course_type": row.course_type,
        "type_label": _course_type_label(row.course_type),
        "grade": row.grade or "",
        "subject": row.subject or "",
        "term": row.term or "",
        "billing_mode": row.billing_mode,
        "billing_label": "按课时" if row.billing_mode == "hour" else row.billing_mode,
        "unit_price": float(row.unit_price or 0),
        "price_label": price_label,
        "leave_rule": row.leave_rule,
        "absent_rule": row.absent_rule,
        "color": row.color or "#a16207",
        "enabled": bool(row.enabled),
        "student_count": student_count,
        "remark": row.remark or "",
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }

def list_courses(
    db: Session,
    *,
    q: str | None = None,
    course_type: str | None = None,
    enabled: bool | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    page = clamp_page(page)
    page_size = clamp_page_size(page_size)
    query = db.query(Course)
    if q:
        query = query.filter(Course.name.contains(q.strip()))
    if course_type in {"group", "one_to_one"}:
        query = query.filter(Course.course_type == course_type)
    if enabled is not None:
        query = query.filter(Course.enabled.is_(enabled))
    query = query.order_by(Course.id.desc())
    rows, total = paginate_query(query, page=page, page_size=page_size)
    return page_payload(
        [course_to_dict(db, r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
    )

def list_course_eligible_students(
    db: Session,
    course_id: int,
    *,
    q: str | None = None,
    page: int = 1,
    page_size: int = 20,
    viewer: User | None = None,
) -> dict | None:
    course = db.get(Course, course_id)
    if not course:
        return None
    page = clamp_page(page)
    page_size = clamp_page_size(page_size)
    query = db.query(Student).filter(Student.status.in_(("active", "paused")))
    if q:
        qq = q.strip()
        # 非负责人不可按完整手机号检索（避免旁路获取号码）
        if viewer is not None and viewer.role != "admin":
            query = query.filter(Student.name.contains(qq))
        else:
            query = query.filter(or_(Student.name.contains(qq), Student.phone.contains(qq)))
    candidates = query.order_by(Student.id.desc()).all()
    eligible = [s for s in candidates if _student_linked_to_course(db, s, course_id)]
    start = (page - 1) * page_size
    items = []
    for student in eligible[start : start + page_size]:
        packages = (
            db.query(StudentCoursePackage)
            .filter(
                StudentCoursePackage.student_id == student.id,
                StudentCoursePackage.course_id == course_id,
                StudentCoursePackage.status != "refunded",
            )
            .all()
        )
        remain = sum(
            float(pkg.remain_hours or 0)
            for pkg in packages
            if pkg.status == "active"
            and (not pkg.valid_until or pkg.valid_until >= business_today())
        )
        items.append(
            {
                "id": student.id,
                "name": student.name,
                "grade": student.grade or "",
                "school": student.school or "",
                "phone": phone_for_viewer(student.phone, viewer),
                "status": student.status,
                "course_id": course_id,
                "has_package": bool(packages),
                "remain_hours": round(remain, 2),
                "grade_matched": not course.grade or not student.grade or course.grade == student.grade,
            }
        )
    return page_payload(items, total=len(eligible), page=page, page_size=page_size)

def create_course(db: Session, user: User, data: dict) -> Course | str:
    name = (data.get("name") or "").strip()
    if not name:
        return "请填写课程名称"
    course_type = data.get("course_type") or "group"
    if course_type not in {"group", "one_to_one"}:
        return "课程类型无效"
    row = Course(
        name=name,
        course_type=course_type,
        grade=(data.get("grade") or "").strip(),
        subject=(data.get("subject") or "").strip(),
        term=(data.get("term") or "").strip(),
        billing_mode=data.get("billing_mode") or "hour",
        unit_price=float(data.get("unit_price") or 0),
        leave_rule=data.get("leave_rule") or "no_deduct",
        absent_rule=data.get("absent_rule") or "no_deduct",
        color=data.get("color") or "#a16207",
        enabled=bool(data.get("enabled", True)),
        remark=(data.get("remark") or "").strip(),
        created_by=user.id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row

def update_course(db: Session, course_id: int, data: dict) -> Course | str:
    row = db.get(Course, course_id)
    if not row:
        return "课程不存在"
    for key in (
        "name",
        "course_type",
        "grade",
        "subject",
        "term",
        "billing_mode",
        "leave_rule",
        "absent_rule",
        "color",
        "remark",
    ):
        if key in data and data[key] is not None:
            val = data[key]
            if isinstance(val, str):
                val = val.strip()
            setattr(row, key, val)
    if "unit_price" in data and data["unit_price"] is not None:
        row.unit_price = float(data["unit_price"])
    if "enabled" in data and data["enabled"] is not None:
        row.enabled = bool(data["enabled"])
    if row.course_type not in {"group", "one_to_one"}:
        return "课程类型无效"
    row.updated_at = _utcnow()
    db.commit()
    db.refresh(row)
    return row

def delete_course(db: Session, course_id: int) -> str | None:
    row = db.get(Course, course_id)
    if not row:
        return "课程不存在"
    used = db.query(ClassRoom).filter(ClassRoom.course_id == course_id).count()
    if used:
        return "课程已关联班级，无法删除（可改为停用）"
    pkg = db.query(StudentCoursePackage).filter(StudentCoursePackage.course_id == course_id).count()
    if pkg:
        return "课程已有购课记录，无法删除（可改为停用）"
    db.delete(row)
    db.commit()
    return None

def _sync_class_teachers(
    db: Session,
    class_id: int,
    teacher_ids: list[int],
    head_teacher_id: int | None,
) -> str | None:
    ids = []
    for tid in teacher_ids:
        try:
            ids.append(int(tid))
        except (TypeError, ValueError):
            continue
    ids = list(dict.fromkeys(ids))
    for tid in ids:
        u = db.get(User, tid)
        if not u or u.deleted_at is not None or not u.is_active or not is_teaching_staff(u.role):
            return f"老师 {tid} 不存在"
    db.query(ClassTeacher).filter(ClassTeacher.class_id == class_id).delete()
    head = head_teacher_id if head_teacher_id in ids else (ids[0] if ids else None)
    for tid in ids:
        db.add(
            ClassTeacher(
                class_id=class_id,
                teacher_id=tid,
                is_head=(tid == head),
            )
        )
    return None

def _sync_class_members(db: Session, class_id: int, student_ids: list[int]) -> str | None:
    cls = db.get(ClassRoom, class_id)
    if not cls or not cls.course_id:
        return "班级未关联课程"
    ids = []
    for sid in student_ids:
        try:
            ids.append(int(sid))
        except (TypeError, ValueError):
            continue
    ids = list(dict.fromkeys(ids))
    if cls.mode == "one_to_one" and len(ids) > 1:
        return "一对一班级只能有 1 名学员"
    if cls.capacity is not None and not cls.over_capacity and len(ids) > cls.capacity:
        return f"班级容量为 {cls.capacity} 人，不能超额添加学员"
    for sid in ids:
        s = db.get(Student, sid)
        if not s:
            return f"学员 {sid} 不存在"
        if s.status not in {"active", "paused"}:
            return f"学员「{s.name}」当前状态不可入班"
        if not _student_linked_to_course(db, s, cls.course_id):
            course = db.get(Course, cls.course_id)
            return f"学员「{s.name}」未关联课程「{course.name if course else cls.course_id}」"
    existing = {
        m.student_id: m
        for m in db.query(ClassMember).filter(ClassMember.class_id == class_id).all()
    }
    keep = set(ids)
    for sid, m in existing.items():
        if sid not in keep:
            m.status = "left"
    for sid in ids:
        if sid in existing:
            existing[sid].status = "active"
        else:
            db.add(ClassMember(class_id=class_id, student_id=sid, status="active"))
    return None

def class_to_dict(db: Session, row: ClassRoom, viewer: User | None = None) -> dict:
    course = db.get(Course, row.course_id) if row.course_id else None
    teachers = (
        db.query(ClassTeacher, User)
        .join(User, User.id == ClassTeacher.teacher_id)
        .filter(ClassTeacher.class_id == row.id)
        .all()
    )
    teacher_parts = []
    teacher_ids = []
    for ct, u in teachers:
        teacher_ids.append(u.id)
        label = u.display_name or u.username
        if ct.is_head:
            label = f"{label}（班主任）"
        teacher_parts.append(label)

    members = (
        db.query(ClassMember)
        .filter(ClassMember.class_id == row.id, ClassMember.status == "active")
        .all()
    )
    member_count = len(members)
    student_ids = [m.student_id for m in members]
    primary = db.get(Student, row.primary_student_id) if row.primary_student_id else None
    if not primary and row.mode == "one_to_one" and student_ids:
        primary = db.get(Student, student_ids[0])

    scheduled_n = (
        db.query(ScheduleLesson)
        .filter(ScheduleLesson.class_id == row.id, ScheduleLesson.status != "cancelled")
        .count()
    )
    done_n = (
        db.query(ClassRecord)
        .filter(ClassRecord.class_id == row.id, ClassRecord.status == "normal")
        .count()
    )
    hours_sum = (
        db.query(ClassRecord)
        .filter(ClassRecord.class_id == row.id, ClassRecord.status == "normal")
        .all()
    )
    taught_hours = sum(float(r.hours or 0) for r in hours_sum)

    remain = 0.0
    if primary and row.course_id:
        pkgs = (
            db.query(StudentCoursePackage)
            .filter(
                StudentCoursePackage.student_id == primary.id,
                StudentCoursePackage.course_id == row.course_id,
                StudentCoursePackage.status == "active",
                or_(StudentCoursePackage.valid_until.is_(None), StudentCoursePackage.valid_until >= business_today()),
            )
            .all()
        )
        remain = sum(float(p.remain_hours or 0) for p in pkgs)

    cap = row.capacity
    capacity_label = f"{member_count}/{cap if cap is not None else '未设置'}"

    member_rows: list[dict] = []
    if student_ids:
        students = db.query(Student).filter(Student.id.in_(student_ids)).all()
        by_id = {s.id: s for s in students}
        for sid in student_ids:
            s = by_id.get(sid)
            if not s:
                continue
            s_remain = 0.0
            consume_label = ""
            if row.course_id:
                pkgs = (
                    db.query(StudentCoursePackage)
                    .filter(
                        StudentCoursePackage.student_id == sid,
                        StudentCoursePackage.course_id == row.course_id,
                        StudentCoursePackage.status == "active",
                        or_(StudentCoursePackage.valid_until.is_(None), StudentCoursePackage.valid_until >= business_today()),
                    )
                    .all()
                )
                s_remain = sum(float(p.remain_hours or 0) for p in pkgs)
                if course:
                    consume_label = f"课程【{course.name}】"
            member_rows.append(
                {
                    "id": s.id,
                    "name": s.name,
                    "phone": phone_for_viewer(s.phone, viewer),
                    "gender": "",
                    "remain_hours": s_remain,
                    "consume_label": consume_label or "—",
                }
            )

    status_map = {"active": "在读", "graduated": "结业", "archived": "已归档"}
    return {
        "id": row.id,
        "name": row.name,
        "mode": row.mode,
        "mode_label": "一对一" if row.mode == "one_to_one" else "班课",
        "course_id": row.course_id,
        "course_name": course.name if course else "",
        "course_type": course.course_type if course else "",
        "course_type_label": (
            "一对一" if course and course.course_type == "one_to_one" else "一对多" if course else ""
        ),
        "teachers": "、".join(teacher_parts) if teacher_parts else "待分配",
        "teacher_ids": teacher_ids,
        "student_ids": student_ids,
        "members": member_rows,
        "member_count": member_count,
        "capacity": cap,
        "capacity_label": (
            f"{member_count}/{cap if cap is not None else '未设置'}"
            + ("(可超额)" if cap is not None and row.over_capacity else "")
        ),
        "over_capacity": bool(row.over_capacity),
        "open_count": row.open_count,
        "category": row.category or "",
        "hours_per_session": float(row.hours_per_session or 1),
        "default_room": getattr(row, "default_room", None) or "",
        "primary_student_id": primary.id if primary else None,
        "student_name": primary.name if primary else None,
        "phone": phone_for_viewer(primary.phone if primary else None, viewer) or None,
        "scheduled_label": f"{done_n}/{scheduled_n}",
        "done_sessions": done_n,
        "scheduled_sessions": scheduled_n,
        "taught_hours": taught_hours,
        "remain_hours": remain,
        "status": row.status,
        "status_label": status_map.get(row.status, row.status),
        "remark": row.remark or "",
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }

def list_classes(
    db: Session,
    *,
    mode: str | None = None,
    q: str | None = None,
    course_id: int | None = None,
    teacher_id: int | None = None,
    only_mine: bool = False,
    user: User | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    page = clamp_page(page)
    page_size = clamp_page_size(page_size)
    query = db.query(ClassRoom).filter(ClassRoom.status != "archived")
    if mode in {"group", "one_to_one"}:
        query = query.filter(ClassRoom.mode == mode)
    if q:
        qq = q.strip()
        from sqlalchemy import or_

        # 班课/一对一均可按班级名搜索；同时支持按在班学员姓名（负责人可手机号）
        if user is not None and user.role != "admin":
            stu_filter = Student.name.contains(qq)
        else:
            stu_filter = (Student.name.contains(qq)) | (Student.phone.contains(qq))
        stu_ids = [r[0] for r in db.query(Student.id).filter(stu_filter).all()]
        member_class_ids: list[int] = []
        if stu_ids:
            member_class_ids = [
                r[0]
                for r in db.query(ClassMember.class_id)
                .filter(ClassMember.student_id.in_(stu_ids), ClassMember.status == "active")
                .distinct()
                .all()
            ]
        conds = [ClassRoom.name.contains(qq)]
        if stu_ids:
            conds.append(ClassRoom.primary_student_id.in_(stu_ids))
        if member_class_ids:
            conds.append(ClassRoom.id.in_(member_class_ids))
        query = query.filter(or_(*conds))
    if course_id:
        query = query.filter(ClassRoom.course_id == course_id)
    if only_mine and user:
        teacher_id = user.id
    if teacher_id:
        class_ids = [
            r[0]
            for r in db.query(ClassTeacher.class_id)
            .filter(ClassTeacher.teacher_id == teacher_id)
            .all()
        ]
        if not class_ids:
            return page_payload([], total=0, page=page, page_size=page_size)
        query = query.filter(ClassRoom.id.in_(class_ids))
    # Keep graduated classes visible, but put them after classes still in progress.
    # Apply this before pagination so the ordering is consistent across pages.
    query = query.order_by(
        case((ClassRoom.status == "graduated", 1), else_=0),
        ClassRoom.id.desc(),
    )
    rows, total = paginate_query(query, page=page, page_size=page_size)
    return page_payload(
        [class_to_dict(db, r, viewer=user) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
    )

def create_class(db: Session, user: User, data: dict) -> ClassRoom | str:
    name = (data.get("name") or "").strip()
    if not name:
        return "请填写班级名称"
    mode = data.get("mode") or "group"
    if mode not in {"group", "one_to_one"}:
        return "班级类型无效"
    course_id = data.get("course_id")
    if course_id:
        course = db.get(Course, int(course_id))
        if not course:
            return "关联课程不存在"
        if not course.enabled:
            return "关联课程已停用"
        if course.course_type != mode:
            return "班级类型须与关联课程类型一致"
    else:
        return "请选择关联课程"

    primary_student_id = data.get("primary_student_id")
    student_ids: list[int] = []
    if mode == "one_to_one":
        if not primary_student_id:
            return "一对一班级请选择学员"
        primary_student_id = int(primary_student_id)
        student_ids = [primary_student_id]
    else:
        primary_student_id = None

    row = ClassRoom(
        name=name,
        mode=mode,
        course_id=int(course_id),
        capacity=data.get("capacity"),
        over_capacity=bool(data.get("over_capacity", True)),
        open_count=data.get("open_count"),
        online_select=False,
        category=(data.get("category") or "").strip(),
        hours_per_session=float(data.get("hours_per_session") or 1),
        default_room=(data.get("default_room") or "").strip(),
        primary_student_id=primary_student_id,
        status="active",
        remark=(data.get("remark") or "").strip(),
        created_by=user.id,
    )
    db.add(row)
    db.flush()

    err = _sync_class_teachers(
        db, row.id, list(data.get("teacher_ids") or []), data.get("head_teacher_id")
    )
    if err:
        db.rollback()
        return err
    if student_ids:
        err = _sync_class_members(db, row.id, student_ids)
        if err:
            db.rollback()
            return err

    db.commit()
    db.refresh(row)
    return row

def update_class(db: Session, class_id: int, data: dict) -> ClassRoom | str:
    row = db.get(ClassRoom, class_id)
    if not row:
        return "班级不存在"
    if "name" in data and data["name"] is not None:
        row.name = str(data["name"]).strip()
    course_changed = False
    if "course_id" in data and data["course_id"] is not None:
        course = db.get(Course, int(data["course_id"]))
        if not course:
            return "关联课程不存在"
        if not course.enabled:
            return "关联课程已停用"
        if course.course_type != row.mode:
            return "班级类型须与关联课程类型一致"
        course_changed = row.course_id != int(data["course_id"])
        row.course_id = int(data["course_id"])
    for key in ("capacity", "open_count", "primary_student_id"):
        if key in data:
            row.__setattr__(key, data[key])
    if "over_capacity" in data and data["over_capacity"] is not None:
        row.over_capacity = bool(data["over_capacity"])
    if "category" in data and data["category"] is not None:
        row.category = str(data["category"]).strip()
    if "hours_per_session" in data and data["hours_per_session"] is not None:
        row.hours_per_session = float(data["hours_per_session"])
    if "default_room" in data and data["default_room"] is not None:
        row.default_room = str(data["default_room"]).strip()
    if "status" in data and data["status"]:
        row.status = str(data["status"])
    if "remark" in data and data["remark"] is not None:
        row.remark = str(data["remark"]).strip()

    if "teacher_ids" in data and data["teacher_ids"] is not None:
        err = _sync_class_teachers(
            db, row.id, list(data["teacher_ids"]), data.get("head_teacher_id")
        )
        if err:
            db.rollback()
            return err
    if "student_ids" in data and data["student_ids"] is not None:
        next_student_ids = list(data["student_ids"])
        if row.mode == "one_to_one":
            primary = data.get("primary_student_id")
            if primary:
                next_student_ids = [int(primary)]
            elif next_student_ids:
                row.primary_student_id = int(next_student_ids[0])
        err = _sync_class_members(db, row.id, next_student_ids)
        if err:
            db.rollback()
            return err
    elif course_changed or "capacity" in data or "over_capacity" in data:
        current_ids = [
            member.student_id
            for member in db.query(ClassMember)
            .filter(ClassMember.class_id == row.id, ClassMember.status == "active")
            .all()
        ]
        err = _sync_class_members(db, row.id, current_ids)
        if err:
            db.rollback()
            return err

    row.updated_at = _utcnow()
    db.commit()
    db.refresh(row)
    return row

def add_class_students(
    db: Session, class_id: int, student_ids: list[int]
) -> ClassRoom | str:
    row = db.get(ClassRoom, class_id)
    if not row:
        return "班级不存在"
    if not row.course_id:
        return "班级未关联课程"

    ids = list(dict.fromkeys(int(sid) for sid in student_ids))
    if not ids:
        return "请选择学员"

    active_ids = {
        member.student_id
        for member in db.query(ClassMember)
        .filter(ClassMember.class_id == class_id, ClassMember.status == "active")
        .all()
    }
    duplicate_ids = [sid for sid in ids if sid in active_ids]
    if duplicate_ids:
        student = db.get(Student, duplicate_ids[0])
        return f"学员「{student.name if student else duplicate_ids[0]}」已经在班，不用重复添加"

    next_ids = active_ids | set(ids)
    if row.mode == "one_to_one" and len(next_ids) > 1:
        return "一对一班级只能有 1 名学员"
    if row.capacity is not None and not row.over_capacity and len(next_ids) > row.capacity:
        return f"班级容量为 {row.capacity} 人，不能超额添加学员"

    new_ids = ids
    course = db.get(Course, row.course_id)
    for sid in new_ids:
        student = db.get(Student, sid)
        if not student:
            return f"学员 {sid} 不存在"
        if student.status not in {"active", "paused"}:
            return f"学员「{student.name}」当前状态不可入班"
        if not _student_linked_to_course(db, student, row.course_id):
            return f"学员「{student.name}」未关联课程「{course.name if course else row.course_id}」"

    existing = {
        member.student_id: member
        for member in db.query(ClassMember)
        .filter(ClassMember.class_id == class_id, ClassMember.student_id.in_(new_ids))
        .all()
    }
    for sid in new_ids:
        if sid in existing:
            existing[sid].status = "active"
        else:
            db.add(ClassMember(class_id=class_id, student_id=sid, status="active"))

    if row.mode == "one_to_one" and next_ids:
        row.primary_student_id = next(iter(next_ids))
    row.updated_at = _utcnow()
    db.commit()
    db.refresh(row)
    return row

def remove_class_student(db: Session, class_id: int, student_id: int) -> ClassRoom | str:
    row = db.get(ClassRoom, class_id)
    if not row:
        return "班级不存在"

    memberships = (
        db.query(ClassMember)
        .filter(
            ClassMember.class_id == class_id,
            ClassMember.student_id == student_id,
            ClassMember.status == "active",
        )
        .all()
    )
    if not memberships:
        return "学员不在本班"
    for membership in memberships:
        membership.status = "left"

    if row.primary_student_id == student_id:
        row.primary_student_id = None
    row.updated_at = _utcnow()
    db.commit()
    db.refresh(row)
    return row

def delete_class(db: Session, class_id: int) -> str | None:
    row = db.get(ClassRoom, class_id)
    if not row:
        return "班级不存在"
    records = db.query(ClassRecord).filter(ClassRecord.class_id == class_id).count()
    if records:
        row.status = "archived"
        row.updated_at = _utcnow()
        db.commit()
        return None
    db.query(ClassTeacher).filter(ClassTeacher.class_id == class_id).delete()
    db.query(ClassMember).filter(ClassMember.class_id == class_id).delete()
    db.query(ScheduleLesson).filter(ScheduleLesson.class_id == class_id).delete()
    db.delete(row)
    db.commit()
    return None

def schedule_to_dict(db: Session, row: ScheduleLesson) -> dict:
    cls = db.get(ClassRoom, row.class_id)
    course = db.get(Course, row.course_id) if row.course_id else None
    if not course and cls and cls.course_id:
        course = db.get(Course, cls.course_id)
    t_ids = _parse_ids(row.teacher_ids)
    if not t_ids and cls:
        t_ids = [
            r.teacher_id
            for r in db.query(ClassTeacher).filter(ClassTeacher.class_id == cls.id).all()
        ]
    members = []
    if cls:
        members = (
            db.query(Student)
            .join(ClassMember, ClassMember.student_id == Student.id)
            .filter(ClassMember.class_id == cls.id, ClassMember.status == "active")
            .all()
        )
    member_count = len(members)
    cap = cls.capacity if cls else None
    over = bool(cls.over_capacity) if cls else True
    cap_txt = f"{member_count}/{cap if cap is not None else '未设置'}"
    if cap is not None and over:
        cap_txt += "(可超额)"
    # 授课课时：班级单次课次（默认 1），与墙钟上课时长无关
    session_hours = float(cls.hours_per_session or 1) if cls else 1.0
    return {
        "id": row.id,
        "class_id": row.class_id,
        "class_name": cls.name if cls else "",
        "course_id": course.id if course else None,
        "course_name": course.name if course else "",
        "course_color": (course.color if course else None) or "#a16207",
        "start_at": row.start_at,
        "end_at": row.end_at,
        "room": row.room or "",
        "status": row.status,
        "teacher_ids": t_ids,
        "teachers": _teacher_names(db, t_ids),
        "capacity": cap,
        "capacity_label": cap_txt,
        "over_capacity": over,
        "students": "、".join(s.name for s in members[:20]),
        "member_count": member_count,
        "hours": session_hours,
        "hours_per_session": session_hours,
        "can_roll_call": _schedule_can_roll_call(row),
        "remark": row.remark or "",
        "created_at": row.created_at,
    }

def get_schedule_detail(
    db: Session, lesson_id: int, viewer: User | None = None
) -> dict | None:
    """课次详情：排课信息 + 班级学员明细（姓名/手机/课耗/剩余/实扣）。"""
    row = db.get(ScheduleLesson, lesson_id)
    if not row or row.status == "cancelled":
        return None
    base = schedule_to_dict(db, row)
    cls = db.get(ClassRoom, row.class_id)
    course = db.get(Course, row.course_id) if row.course_id else None
    if not course and cls and cls.course_id:
        course = db.get(Course, cls.course_id)

    record = (
        db.query(ClassRecord)
        .filter(
            ClassRecord.schedule_id == row.id,
            ClassRecord.status == "normal",
        )
        .order_by(ClassRecord.id.desc())
        .first()
    )
    attendance_by_student = {}
    if record:
        attendance_by_student = {
            attendance.student_id: attendance
            for attendance in db.query(ClassAttendance)
            .filter(ClassAttendance.record_id == record.id)
            .all()
        }

    # 授课课时按班级单次课次计（机构常 2 小时墙钟 = 1 课时），不按排课起止时长推算
    hours = float(cls.hours_per_session or 1) if cls else 1.0

    members: list[dict] = []
    if cls:
        member_rows = (
            db.query(ClassMember)
            .filter(ClassMember.class_id == cls.id, ClassMember.status == "active")
            .all()
        )
        sids = [m.student_id for m in member_rows]
        students = db.query(Student).filter(Student.id.in_(sids)).all() if sids else []
        by_id = {s.id: s for s in students}
        course_id = course.id if course else None
        for mid in sids:
            s = by_id.get(mid)
            if not s:
                continue
            attendance = attendance_by_student.get(mid)
            s_remain = 0.0
            consume_label = "—"
            if course_id:
                pkgs = (
                    db.query(StudentCoursePackage)
                    .filter(
                        StudentCoursePackage.student_id == mid,
                        StudentCoursePackage.course_id == course_id,
                        StudentCoursePackage.status == "active",
                        or_(StudentCoursePackage.valid_until.is_(None), StudentCoursePackage.valid_until >= business_today()),
                    )
                    .all()
                )
                s_remain = sum(float(p.remain_hours or 0) for p in pkgs)
                if course:
                    consume_label = f"课程【{course.name}】"
            # 无课包时回落班级维度剩余课时
            cm = next((m for m in member_rows if m.student_id == mid), None)
            if s_remain <= 0 and cm and float(cm.remain_hours or 0) > 0:
                s_remain = float(cm.remain_hours or 0)
            members.append(
                {
                    "id": s.id,
                    "name": s.name,
                    "phone": phone_for_viewer(s.phone, viewer),
                    "remain_hours": s_remain,
                    "consume_label": consume_label,
                    "deducted_hours": (
                        float(attendance.hours_consumed or 0)
                        if attendance is not None
                        else None
                    ),
                }
            )

    base.update(
        {
            "hours": hours,
            "hours_per_session": float(cls.hours_per_session or hours) if cls else hours,
            "open_count": cls.open_count if cls else None,
            "open_count_label": (
                str(cls.open_count) if cls and cls.open_count is not None else "未设置"
            ),
            "capacity_value": cls.capacity if cls else None,
            "capacity_text": (
                str(cls.capacity)
                if cls and cls.capacity is not None
                else "未设置"
            ),
            "members": members,
            "status_label": {
                "scheduled": "未上课",
                "completed": "已上课",
                "cancelled": "已取消",
            }.get(row.status, row.status),
        }
    )
    return base

def _class_teacher_ids(db: Session, class_id: int) -> list[int]:
    return [
        r.teacher_id
        for r in db.query(ClassTeacher).filter(ClassTeacher.class_id == class_id).all()
    ]

def _lesson_has_teacher(db: Session, row: ScheduleLesson, teacher_id: int) -> bool:
    """排课 teacher_ids 优先；未指定时回退班级任课老师。"""
    t_ids = _parse_ids(row.teacher_ids)
    if t_ids:
        return teacher_id in t_ids
    return teacher_id in _class_teacher_ids(db, row.class_id)

def user_can_view_schedule(db: Session, user: User, row: ScheduleLesson) -> bool:
    """老师仅可查看自己所带课次；其他角色看全部。"""
    if user.role != "teacher":
        return True
    return _lesson_has_teacher(db, row, user.id)

def _time_overlap(a_start: datetime, a_end: datetime, b_start: datetime, b_end: datetime) -> bool:
    return a_start < b_end and b_start < a_end

def list_schedules(
    db: Session,
    *,
    start: datetime | None = None,
    end: datetime | None = None,
    class_id: int | None = None,
    course_id: int | None = None,
    teacher_id: int | None = None,
    room: str | None = None,
    page: int = 1,
    page_size: int = 100,
) -> dict:
    page = clamp_page(page)
    # 课表周视图可能一次加载较多节次
    page_size = max(1, min(int(page_size or 100), 500))
    query = db.query(ScheduleLesson).filter(ScheduleLesson.status != "cancelled")
    if start:
        query = query.filter(ScheduleLesson.end_at >= start)
    if end:
        query = query.filter(ScheduleLesson.start_at <= end)
    if class_id:
        query = query.filter(ScheduleLesson.class_id == class_id)
    if course_id:
        query = query.filter(ScheduleLesson.course_id == course_id)
    if room:
        query = query.filter(ScheduleLesson.room == room.strip())
    query = query.order_by(ScheduleLesson.start_at.asc())
    rows = query.all()
    if teacher_id:
        # 优先匹配排课上的老师；无则回退班级任课老师
        class_ids = {
            r[0]
            for r in db.query(ClassTeacher.class_id)
            .filter(ClassTeacher.teacher_id == teacher_id)
            .all()
        }
        filtered: list[ScheduleLesson] = []
        for r in rows:
            t_ids = _parse_ids(r.teacher_ids)
            if teacher_id in t_ids or (not t_ids and r.class_id in class_ids):
                filtered.append(r)
        rows = filtered
    total = len(rows)
    offset = (page - 1) * page_size
    page_rows = rows[offset : offset + page_size]
    return page_payload(
        [schedule_to_dict(db, r) for r in page_rows],
        total=total,
        page=page,
        page_size=page_size,
    )

def get_roll_call_options(
    db: Session,
    user: User,
    *,
    target_date: date | None = None,
    start: date | None = None,
    end: date | None = None,
) -> dict:
    """Return roll-call classes/schedules visible to the current user.

    - 默认：当天
    - 传 start/end：闭区间日期范围（用于周课表点名）
    - 仅传 target_date：单日
    """
    today = business_today()
    if start is not None or end is not None:
        range_start = start or end or today
        range_end = end or start or today
        if range_end < range_start:
            range_start, range_end = range_end, range_start
        # 防止一次拉过大范围
        if (range_end - range_start).days > 31:
            range_end = range_start + timedelta(days=31)
        anchor = target_date or today
        if anchor < range_start or anchor > range_end:
            anchor = range_start
    else:
        anchor = target_date or today
        range_start = anchor
        range_end = anchor

    schedules_page = list_schedules(
        db,
        start=datetime.combine(range_start, time.min),
        end=datetime.combine(range_end, time.max),
        page=1,
        page_size=500,
    )
    schedules = [
        item
        for item in schedules_page["items"]
        if item["status"] in {"scheduled", "completed"}
    ]
    if user.role in {"teacher", "cr", "academic_manager"}:
        managed_class_ids = {
            row[0]
            for row in (
                db.query(ClassMember.class_id)
                .join(Student, Student.id == ClassMember.student_id)
                .filter(
                    ClassMember.status == "active",
                    Student.academic_manager_id == user.id,
                )
                .distinct()
                .all()
            )
        }
        schedules = [
            item for item in schedules if int(item["class_id"]) in managed_class_ids
        ]
    class_ids = {int(item["class_id"]) for item in schedules}
    if not class_ids:
        return {
            "date": anchor.isoformat(),
            "start": range_start.isoformat(),
            "end": range_end.isoformat(),
            "classes": [],
            "schedules": [],
        }

    rows = (
        db.query(ClassRoom)
        .filter(ClassRoom.id.in_(class_ids), ClassRoom.status != "archived")
        .order_by(ClassRoom.name.asc(), ClassRoom.id.asc())
        .all()
    )
    return {
        "date": anchor.isoformat(),
        "start": range_start.isoformat(),
        "end": range_end.isoformat(),
        "classes": [class_to_dict(db, row) for row in rows],
        "schedules": schedules,
    }

def list_rooms(db: Session) -> list[dict]:
    """合并默认教室与历史排课教室。"""
    used = (
        db.query(ScheduleLesson.room)
        .filter(ScheduleLesson.room != "", ScheduleLesson.status != "cancelled")
        .distinct()
        .all()
    )
    names: list[str] = []
    seen: set[str] = set()
    for name in DEFAULT_ROOMS + [r[0] for r in used if r[0]]:
        n = (name or "").strip()
        if n and n not in seen:
            seen.add(n)
            names.append(n)
    return [{"name": n} for n in names]

def find_conflicts(
    db: Session,
    *,
    start_at: datetime,
    end_at: datetime,
    teacher_ids: list[int] | None = None,
    room: str | None = None,
    exclude_id: int | None = None,
) -> dict:
    """检测老师/教室时段冲突，返回冲突详情与空闲状态。"""
    if end_at <= start_at:
        return {"ok": False, "error": "结束时间须晚于开始时间", "teachers": [], "rooms": []}

    query = db.query(ScheduleLesson).filter(
        ScheduleLesson.status != "cancelled",
        ScheduleLesson.start_at < end_at,
        ScheduleLesson.end_at > start_at,
    )
    if exclude_id:
        query = query.filter(ScheduleLesson.id != exclude_id)
    overlapping = query.all()

    teacher_ids = list(teacher_ids or [])
    teacher_results = []
    for tid in teacher_ids:
        hits = [r for r in overlapping if _lesson_has_teacher(db, r, tid)]
        teacher_results.append(
            {
                "id": tid,
                "name": _teacher_names(db, [tid]) or str(tid),
                "busy": len(hits) > 0,
                "status": "冲突" if hits else "空闲",
                "conflicts": [
                    {
                        "id": h.id,
                        "class_name": (db.get(ClassRoom, h.class_id).name if db.get(ClassRoom, h.class_id) else ""),
                        "start_at": h.start_at,
                        "end_at": h.end_at,
                        "room": h.room or "",
                    }
                    for h in hits[:5]
                ],
            }
        )

    room_name = (room or "").strip()
    room_results = []
    if room_name and room_name != "不指定":
        hits = [r for r in overlapping if (r.room or "").strip() == room_name]
        room_results.append(
            {
                "name": room_name,
                "busy": len(hits) > 0,
                "status": "冲突" if hits else "空闲",
                "conflicts": [
                    {
                        "id": h.id,
                        "class_name": (db.get(ClassRoom, h.class_id).name if db.get(ClassRoom, h.class_id) else ""),
                        "start_at": h.start_at,
                        "end_at": h.end_at,
                        "teachers": _teacher_names(db, _parse_ids(h.teacher_ids)),
                    }
                    for h in hits[:5]
                ],
            }
        )

    any_busy = any(t["busy"] for t in teacher_results) or any(r["busy"] for r in room_results)
    return {
        "ok": True,
        "has_conflict": any_busy,
        "teachers": teacher_results,
        "rooms": room_results,
    }

def availability_for_resources(
    db: Session,
    *,
    start_at: datetime,
    end_at: datetime,
    exclude_id: int | None = None,
) -> dict:
    """为新建排课下拉提供全部老师/教室的冲突状态（含负责人）。"""
    teachers = (
        db.query(User)
        .filter(
            User.role.in_(list(TEACHING_STAFF_ROLES)),
            User.is_active.is_(True),
            User.deleted_at.is_(None),
        )
        .order_by(User.id.asc())
        .all()
    )
    t_ids = [u.id for u in teachers]
    rooms = list_rooms(db)
    conf = find_conflicts(
        db,
        start_at=start_at,
        end_at=end_at,
        teacher_ids=t_ids,
        room="",
        exclude_id=exclude_id,
    )
    teacher_map = {t["id"]: t for t in conf.get("teachers", [])}
    teacher_items = []
    for u in teachers:
        info = teacher_map.get(u.id) or {}
        teacher_items.append(
            {
                "id": u.id,
                "name": u.display_name or u.username,
                "username": u.username,
                "phone": getattr(u, "phone", None) or "-",
                "busy": bool(info.get("busy")),
                "status": info.get("status") or "空闲",
                "conflicts": info.get("conflicts") or [],
            }
        )

    # 逐教室检测
    room_items = []
    for r in rooms:
        rc = find_conflicts(
            db,
            start_at=start_at,
            end_at=end_at,
            teacher_ids=[],
            room=r["name"],
            exclude_id=exclude_id,
        )
        ri = (rc.get("rooms") or [{}])[0] if rc.get("rooms") else {}
        room_items.append(
            {
                "name": r["name"],
                "busy": bool(ri.get("busy")),
                "status": ri.get("status") or "空闲",
                "conflicts": ri.get("conflicts") or [],
            }
        )
    room_items.append({"name": "不指定", "busy": False, "status": "空闲", "conflicts": []})

    return {"teachers": teacher_items, "rooms": room_items}

def _parse_date(s: str) -> date | None:
    try:
        return datetime.strptime(s.strip()[:10], "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None

def _parse_hm(s: str) -> time | None:
    raw = (s or "").strip()
    for fmt in ("%H:%M", "%H:%M:%S"):
        try:
            return datetime.strptime(raw, fmt).time()
        except ValueError:
            continue
    return None

def _iter_schedule_dates(
    *,
    start_date: date,
    repeat_mode: str,
    end_mode: str,
    end_date: date | None,
    session_count: int | None,
    weekdays: list[int] | None = None,
) -> list[date]:
    """按规则生成上课日期列表（最多 200 节）。"""
    out: list[date] = []
    cur = start_date
    selected_weekdays = sorted({v for v in (weekdays or []) if 1 <= v <= 7})

    if repeat_mode in {"weekly", "biweekly"} and selected_weekdays:
        def matches_selected_weekday(value: date) -> bool:
            if value.isoweekday() not in selected_weekdays:
                return False
            if repeat_mode == "weekly":
                return True
            return ((value - start_date).days // 7) % 2 == 0

        if end_mode == "by_count":
            target = max(1, min(int(session_count or 1), 200))
            guard = 0
            while len(out) < target and guard < 2800:
                if matches_selected_weekday(cur):
                    out.append(cur)
                cur = cur + timedelta(days=1)
                guard += 1
            return out

        if not end_date:
            end_date = start_date
        if end_date < start_date:
            return []
        while cur <= end_date and len(out) < 200:
            if matches_selected_weekday(cur):
                out.append(cur)
            cur = cur + timedelta(days=1)
        return out

    step = {
        "daily": 1,
        "alternate": 2,
        "weekly": 7,
        "biweekly": 14,
    }.get(repeat_mode, 7)

    max_n = 200
    if end_mode == "by_count":
        n = max(1, min(int(session_count or 1), max_n))
        for _ in range(n):
            out.append(cur)
            cur = cur + timedelta(days=step)
        return out

    # by_date
    if not end_date:
        end_date = start_date
    if end_date < start_date:
        return []
    guard = 0
    while cur <= end_date and guard < max_n:
        out.append(cur)
        cur = cur + timedelta(days=step)
        guard += 1
    return out

def _make_lesson_row(
    *,
    user: User,
    cls: ClassRoom,
    start_at: datetime,
    end_at: datetime,
    room: str,
    teacher_ids: list[int],
    remark: str,
) -> ScheduleLesson:
    return ScheduleLesson(
        class_id=cls.id,
        course_id=cls.course_id,
        start_at=start_at,
        end_at=end_at,
        room=room,
        status="scheduled",
        teacher_ids=json.dumps(teacher_ids, ensure_ascii=False),
        remark=remark,
        created_by=user.id,
    )

def create_schedule(db: Session, user: User, data: dict) -> ScheduleLesson | str:
    class_id = int(data["class_id"])
    cls = db.get(ClassRoom, class_id)
    if not cls or cls.status != "active":
        return "班级不存在或当前不可排课"
    start_at = data.get("start_at")
    end_at = data.get("end_at")
    if not start_at or not end_at:
        return "请填写上课时间"
    if end_at <= start_at:
        return "结束时间须晚于开始时间"
    teacher_ids = list(data.get("teacher_ids") or [])
    if not teacher_ids:
        teacher_ids = [
            r.teacher_id
            for r in db.query(ClassTeacher).filter(ClassTeacher.class_id == class_id).all()
        ]
    for teacher_id in teacher_ids:
        teacher = db.get(User, int(teacher_id))
        if not teacher or not teacher.is_active or not is_teaching_staff(teacher.role):
            return f"老师 {teacher_id} 不存在或已停用"
    room = (data.get("room") or "").strip()
    if room == "不指定":
        room = ""
    # 未指定教室时回退班级默认教室（与老师回退班级任课一致）
    if not room:
        room = (getattr(cls, "default_room", None) or "").strip()
        if room == "不指定":
            room = ""
    # 默认冲突校验（强制创建可跳过）
    if not data.get("force"):
        conf = find_conflicts(
            db,
            start_at=start_at,
            end_at=end_at,
            teacher_ids=teacher_ids,
            room=room,
        )
        if conf.get("has_conflict"):
            parts = []
            for t in conf.get("teachers") or []:
                if t.get("busy"):
                    parts.append(f"老师「{t['name']}」时段冲突")
            for r in conf.get("rooms") or []:
                if r.get("busy"):
                    parts.append(f"教室「{r['name']}」时段冲突")
            return "；".join(parts) or "存在排课冲突"

    row = _make_lesson_row(
        user=user,
        cls=cls,
        start_at=start_at,
        end_at=end_at,
        room=room,
        teacher_ids=teacher_ids,
        remark=(data.get("remark") or "").strip(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row

def create_schedules_batch(db: Session, user: User, data: dict) -> dict | str:
    """规则排课：按重复规则批量生成课次。"""
    class_id = int(data["class_id"])
    cls = db.get(ClassRoom, class_id)
    if not cls or cls.status != "active":
        return "班级不存在或当前不可排课"

    start_d = _parse_date(str(data.get("start_date") or ""))
    st = _parse_hm(str(data.get("start_time") or ""))
    et = _parse_hm(str(data.get("end_time") or ""))
    if not start_d or not st or not et:
        return "请填写开始日期与上课时间"
    if et <= st:
        return "结束时间须晚于开始时间"

    repeat_mode = str(data.get("repeat_mode") or "weekly")
    try:
        weekdays = sorted({int(v) for v in (data.get("weekdays") or [])})
    except (TypeError, ValueError):
        return "每周上课日格式不正确"
    if any(v < 1 or v > 7 for v in weekdays):
        return "每周上课日须为周一至周日"
    end_mode = str(data.get("end_mode") or "by_date")
    end_d = _parse_date(str(data.get("end_date") or "")) if data.get("end_date") else None
    session_count = data.get("session_count")
    if end_mode == "by_date" and not end_d:
        return "请选择结束日期"
    if end_mode == "by_count" and not session_count:
        return "请填写排课次数"

    teacher_ids = list(data.get("teacher_ids") or [])
    if not teacher_ids:
        teacher_ids = [
            r.teacher_id
            for r in db.query(ClassTeacher).filter(ClassTeacher.class_id == class_id).all()
        ]
    for teacher_id in teacher_ids:
        teacher = db.get(User, int(teacher_id))
        if not teacher or not teacher.is_active or not is_teaching_staff(teacher.role):
            return f"老师 {teacher_id} 不存在或已停用"
    room = (data.get("room") or "").strip()
    if room == "不指定":
        room = ""
    # 未指定教室时回退班级默认教室
    if not room:
        room = (getattr(cls, "default_room", None) or "").strip()
        if room == "不指定":
            room = ""
    remark = (data.get("remark") or "").strip()
    on_conflict = str(data.get("on_conflict") or "skip")

    dates = _iter_schedule_dates(
        start_date=start_d,
        repeat_mode=repeat_mode,
        end_mode=end_mode,
        end_date=end_d,
        session_count=int(session_count) if session_count else None,
        weekdays=weekdays,
    )
    if not dates:
        return "未生成任何课次，请检查日期规则"

    created: list[ScheduleLesson] = []
    skipped: list[dict] = []
    for d in dates:
        start_at = datetime.combine(d, st)
        end_at = datetime.combine(d, et)
        conf = find_conflicts(
            db,
            start_at=start_at,
            end_at=end_at,
            teacher_ids=teacher_ids,
            room=room,
        )
        if conf.get("has_conflict") and on_conflict != "force":
            if on_conflict == "fail":
                db.rollback()
                reason_parts = []
                for t in conf.get("teachers") or []:
                    if t.get("busy"):
                        reason_parts.append(f"老师「{t['name']}」")
                for r in conf.get("rooms") or []:
                    if r.get("busy"):
                        reason_parts.append(f"教室「{r['name']}」")
                return f"{d.isoformat()} 时段冲突：{'、'.join(reason_parts) or '资源占用'}"
            skipped.append(
                {
                    "date": d.isoformat(),
                    "start_at": start_at,
                    "end_at": end_at,
                    "reason": "时段冲突",
                }
            )
            continue

        row = _make_lesson_row(
            user=user,
            cls=cls,
            start_at=start_at,
            end_at=end_at,
            room=room,
            teacher_ids=teacher_ids,
            remark=remark,
        )
        db.add(row)
        db.flush()
        created.append(row)

    db.commit()
    for r in created:
        db.refresh(r)
    return {
        "created_count": len(created),
        "skipped_count": len(skipped),
        "items": [schedule_to_dict(db, r) for r in created],
        "skipped": skipped,
    }

def update_schedule(db: Session, lesson_id: int, data: dict) -> ScheduleLesson | str:
    row = db.get(ScheduleLesson, lesson_id)
    if not row:
        return "排课不存在"
    if row.status == "completed":
        return "已上课的排课不可改期，请先撤销点名"
    if "start_at" in data and data["start_at"] is not None:
        row.start_at = data["start_at"]
    if "end_at" in data and data["end_at"] is not None:
        row.end_at = data["end_at"]
    if row.end_at <= row.start_at:
        return "结束时间须晚于开始时间"
    if "room" in data and data["room"] is not None:
        room = str(data["room"]).strip()
        row.room = "" if room == "不指定" else room
    if "teacher_ids" in data and data["teacher_ids"] is not None:
        for teacher_id in data["teacher_ids"]:
            teacher = db.get(User, int(teacher_id))
            if not teacher or not teacher.is_active or not is_teaching_staff(teacher.role):
                return f"老师 {teacher_id} 不存在或已停用"
        row.teacher_ids = json.dumps(list(data["teacher_ids"]), ensure_ascii=False)
    if "status" in data and data["status"]:
        row.status = str(data["status"])
    if "remark" in data and data["remark"] is not None:
        row.remark = str(data["remark"]).strip()

    if not data.get("force"):
        conf = find_conflicts(
            db,
            start_at=row.start_at,
            end_at=row.end_at,
            teacher_ids=_parse_ids(row.teacher_ids),
            room=row.room or "",
            exclude_id=row.id,
        )
        if conf.get("has_conflict"):
            parts = []
            for t in conf.get("teachers") or []:
                if t.get("busy"):
                    parts.append(f"老师「{t['name']}」时段冲突")
            for r in conf.get("rooms") or []:
                if r.get("busy"):
                    parts.append(f"教室「{r['name']}」时段冲突")
            db.rollback()
            return "；".join(parts) or "存在排课冲突"

    db.commit()
    db.refresh(row)
    return row

def delete_schedule(db: Session, lesson_id: int) -> str | None:
    row = db.get(ScheduleLesson, lesson_id)
    if not row:
        return "排课不存在"
    used = db.query(ClassRecord).filter(ClassRecord.schedule_id == lesson_id).count()
    if used:
        row.status = "cancelled"
        db.commit()
        return None
    db.delete(row)
    db.commit()
    return None

def update_schedules_batch(db: Session, data: dict) -> dict | str:
    """批量修改课次字段；成功写入后课表视图自动可见（同源数据）。"""
    raw_ids = data.get("ids") or []
    try:
        ids = [int(x) for x in raw_ids]
    except (TypeError, ValueError):
        return "课次 ID 无效"
    if not ids:
        return "请选择要修改的课次"
    if len(ids) > 200:
        return "单次最多修改 200 节"

    update_teachers = bool(data.get("update_teachers"))
    update_room = bool(data.get("update_room"))
    update_remark = bool(data.get("update_remark"))
    update_time = bool(data.get("update_time"))
    if not any((update_teachers, update_room, update_remark, update_time)):
        return "请至少勾选一项要修改的内容"

    st = _parse_hm(str(data.get("start_time") or "")) if update_time else None
    et = _parse_hm(str(data.get("end_time") or "")) if update_time else None
    if update_time:
        if not st or not et:
            return "请填写上课开始与结束时间"
        if et <= st:
            return "结束时间须晚于开始时间"

    teacher_ids: list[int] = []
    if update_teachers:
        try:
            teacher_ids = [int(x) for x in (data.get("teacher_ids") or [])]
        except (TypeError, ValueError):
            return "老师 ID 无效"
        if not teacher_ids:
            return "请选择上课老师"
        for teacher_id in teacher_ids:
            teacher = db.get(User, int(teacher_id))
            if not teacher or not teacher.is_active or not is_teaching_staff(teacher.role):
                return f"老师 {teacher_id} 不存在或已停用"

    room_val: str | None = None
    if update_room:
        room_val = str(data.get("room") or "").strip()
        if room_val == "不指定":
            room_val = ""

    remark_val: str | None = None
    if update_remark:
        remark_val = str(data.get("remark") or "").strip()

    force = bool(data.get("force"))
    updated: list[ScheduleLesson] = []
    failed: list[dict] = []
    skipped: list[dict] = []

    # 去重并保持顺序
    seen: set[int] = set()
    ordered_ids: list[int] = []
    for lid in ids:
        if lid in seen:
            continue
        seen.add(lid)
        ordered_ids.append(lid)

    for lid in ordered_ids:
        row = db.get(ScheduleLesson, lid)
        if not row or row.status == "cancelled":
            skipped.append({"id": lid, "reason": "课次不存在或已取消"})
            continue
        if row.status == "completed":
            skipped.append({"id": lid, "reason": "已上课不可修改，请先撤销点名"})
            continue

        patch: dict = {"force": force}
        if update_teachers:
            patch["teacher_ids"] = teacher_ids
        if update_room:
            patch["room"] = room_val
        if update_remark:
            patch["remark"] = remark_val
        if update_time and st and et:
            d = row.start_at.date() if row.start_at else None
            if not d:
                failed.append({"id": lid, "reason": "课次缺少上课日期"})
                continue
            patch["start_at"] = datetime.combine(d, st)
            patch["end_at"] = datetime.combine(d, et)

        result = update_schedule(db, lid, patch)
        if isinstance(result, str):
            failed.append({"id": lid, "reason": result})
            continue
        updated.append(result)

    return {
        "updated_count": len(updated),
        "failed_count": len(failed),
        "skipped_count": len(skipped),
        "items": [schedule_to_dict(db, r) for r in updated],
        "failed": failed,
        "skipped": skipped,
    }

def delete_schedules_batch(db: Session, data: dict) -> dict | str:
    """批量删除课次；有点名记录的改为取消状态。"""
    raw_ids = data.get("ids") or []
    try:
        ids = [int(x) for x in raw_ids]
    except (TypeError, ValueError):
        return "课次 ID 无效"
    if not ids:
        return "请选择要删除的课次"
    if len(ids) > 200:
        return "单次最多删除 200 节"

    deleted = 0
    cancelled = 0
    failed: list[dict] = []
    seen: set[int] = set()
    for lid in ids:
        if lid in seen:
            continue
        seen.add(lid)
        row = db.get(ScheduleLesson, lid)
        if not row:
            failed.append({"id": lid, "reason": "排课不存在"})
            continue
        if row.status == "completed":
            failed.append({"id": lid, "reason": "已上课不可删除，请先撤销点名"})
            continue
        used = db.query(ClassRecord).filter(ClassRecord.schedule_id == lid).count()
        if used:
            row.status = "cancelled"
            cancelled += 1
        else:
            db.delete(row)
            deleted += 1
    db.commit()
    return {
        "deleted_count": deleted,
        "cancelled_count": cancelled,
        "failed_count": len(failed),
        "failed": failed,
    }

def _consume_package(
    db: Session,
    *,
    student_id: int,
    course_id: int | None,
    hours: float,
    unit_price: float,
) -> tuple[float, list[dict], float]:
    """按到期日/FIFO 扣减课包，返回金额、课包分配和不足课时。"""
    if hours <= 0 or not course_id:
        return 0.0, [], max(0.0, hours)
    pkgs = (
        db.query(StudentCoursePackage)
        .filter(
            StudentCoursePackage.student_id == student_id,
            StudentCoursePackage.course_id == course_id,
            StudentCoursePackage.status == "active",
            StudentCoursePackage.remain_hours > 0,
            or_(
                StudentCoursePackage.valid_until.is_(None),
                StudentCoursePackage.valid_until >= business_today(),
            ),
        )
        .order_by(
            StudentCoursePackage.priority_consume.desc(),
            StudentCoursePackage.valid_until.is_(None).asc(),
            StudentCoursePackage.valid_until.asc(),
            StudentCoursePackage.id.asc(),
        )
        .all()
    )
    left = hours
    amount = 0.0
    allocations: list[dict] = []
    for pkg in pkgs:
        if left <= 0:
            break
        take = min(float(pkg.remain_hours), left)
        price = float(pkg.unit_price or unit_price or 0)
        allocation_amount = round(take * price, 2)
        amount += allocation_amount
        allocations.append(
            {
                "package_id": pkg.id,
                "hours": round(take, 4),
                "amount": allocation_amount,
            }
        )
        pkg.remain_hours = float(pkg.remain_hours) - take
        if pkg.remain_hours <= 1e-9:
            pkg.remain_hours = 0
            pkg.status = "exhausted"
        pkg.updated_at = _utcnow()
        left -= take
    uncovered = max(0.0, left)
    # 余额不足时保留欠课时，并按课程单价估算课消金额。
    if left > 0 and unit_price > 0:
        amount += left * unit_price
    return round(amount, 2), allocations, round(uncovered, 4)

def class_record_to_dict(db: Session, row: ClassRecord) -> dict:
    cls = db.get(ClassRoom, row.class_id)
    course = db.get(Course, row.course_id) if row.course_id else None
    schedule = db.get(ScheduleLesson, row.schedule_id) if row.schedule_id else None
    t_ids = _parse_ids(row.teacher_ids)
    creator = db.get(User, row.created_by) if row.created_by else None
    return {
        "id": row.id,
        "class_id": row.class_id,
        "class_name": cls.name if cls else "",
        "schedule_id": row.schedule_id,
        "course_id": row.course_id,
        "course_name": course.name if course else "",
        "roll_at": row.roll_at,
        "class_start": row.class_start,
        "class_end": row.class_end,
        "room": schedule.room if schedule else (cls.default_room if cls else ""),
        "teachers": _teacher_names(db, t_ids),
        "teacher_ids": t_ids,
        "hours": float(row.hours or 0),
        "salary_hours": float(row.salary_hours if row.salary_hours is not None else row.hours or 0),
        "status": row.status,
        "status_label": "正常" if row.status == "normal" else "已撤销",
        "content": row.content or "",
        "amount": float(row.amount or 0),
        "attendance": f"{row.present_count}/{row.total_count}",
        "present_count": row.present_count,
        "total_count": row.total_count,
        "created_by": row.created_by,
        "creator_name": creator.display_name if creator else "",
        "created_at": row.created_at,
    }

def get_class_record_detail(
    db: Session, record_id: int, viewer: User | None = None
) -> dict | None:
    row = db.get(ClassRecord, record_id)
    if not row:
        return None
    result = class_record_to_dict(db, row)
    attendance_rows = (
        db.query(ClassAttendance)
        .filter(ClassAttendance.record_id == record_id)
        .order_by(ClassAttendance.id.asc())
        .all()
    )
    consumptions = (
        db.query(CourseConsumption)
        .filter(
            CourseConsumption.record_id == record_id,
            CourseConsumption.status != "void",
        )
        .all()
    )
    consumption_by_student = {c.student_id: c for c in consumptions}
    status_labels = {
        "present": "出勤",
        "absent": "缺勤",
        "leave": "请假",
        "late": "迟到",
    }
    items = []
    for attendance in attendance_rows:
        student = db.get(Student, attendance.student_id)
        consumption = consumption_by_student.get(attendance.student_id)
        items.append(
            {
                "student_id": attendance.student_id,
                "student_name": student.name if student else f"学员#{attendance.student_id}",
                "phone": phone_for_viewer(student.phone if student else None, viewer),
                "status": attendance.status,
                "status_label": status_labels.get(attendance.status, attendance.status),
                "hours_consumed": float(attendance.hours_consumed or 0),
                "uncovered_hours": float(
                    getattr(consumption, "uncovered_hours", 0) or 0
                ),
                "amount": float(attendance.amount or 0),
            }
        )
    result["attendances"] = items
    result["uncovered_hours"] = round(
        sum(float(item["uncovered_hours"]) for item in items), 4
    )
    return result

def _add_class_record_log(
    db: Session,
    row: ClassRecord,
    user: User,
    *,
    action: str,
    action_label: str,
    detail: str,
) -> None:
    db.add(
        ClassRecordOperationLog(
            record_id=row.id,
            action=action,
            action_label=action_label,
            detail=detail,
            operator_id=user.id,
        )
    )

def list_class_record_logs(db: Session, record_id: int) -> list[dict] | None:
    if not db.get(ClassRecord, record_id):
        return None
    rows = (
        db.query(ClassRecordOperationLog)
        .filter(ClassRecordOperationLog.record_id == record_id)
        .order_by(ClassRecordOperationLog.created_at.desc(), ClassRecordOperationLog.id.desc())
        .all()
    )
    result = []
    for row in rows:
        operator = db.get(User, row.operator_id) if row.operator_id else None
        result.append(
            {
                "id": row.id,
                "action": row.action,
                "action_label": row.action_label,
                "detail": row.detail,
                "operator_id": row.operator_id,
                "operator_name": operator.display_name if operator else "",
                "created_at": row.created_at,
            }
        )
    return result

def list_class_records(
    db: Session,
    *,
    class_id: int | None = None,
    course_id: int | None = None,
    teacher_id: int | None = None,
    status: str | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
    class_start: datetime | None = None,
    class_end: datetime | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    page = clamp_page(page)
    page_size = clamp_page_size(page_size)
    query = db.query(ClassRecord)
    if class_id:
        query = query.filter(ClassRecord.class_id == class_id)
    if course_id:
        query = query.filter(ClassRecord.course_id == course_id)
    if status:
        query = query.filter(ClassRecord.status == status)
    if start:
        query = query.filter(ClassRecord.roll_at >= start)
    if end:
        query = query.filter(ClassRecord.roll_at <= end)
    if class_start:
        query = query.filter(ClassRecord.class_start >= class_start)
    if class_end:
        query = query.filter(ClassRecord.class_start <= class_end)
    if teacher_id:
        class_ids = [
            r[0]
            for r in db.query(ClassTeacher.class_id)
            .filter(ClassTeacher.teacher_id == teacher_id)
            .all()
        ]
        if class_ids:
            query = query.filter(ClassRecord.class_id.in_(class_ids))
        else:
            return page_payload([], total=0, page=page, page_size=page_size)
    query = query.order_by(ClassRecord.roll_at.desc(), ClassRecord.id.desc())
    rows, total = paginate_query(query, page=page, page_size=page_size)
    return page_payload(
        [class_record_to_dict(db, r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
    )

def list_timeout_class_records(
    db: Session,
    *,
    class_id: int | None = None,
    course_id: int | None = None,
    teacher_id: int | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """已到结束时间但尚未点名的排课。"""
    page = clamp_page(page)
    page_size = clamp_page_size(page_size)
    now = _utcnow()
    query = db.query(ScheduleLesson).filter(
        ScheduleLesson.status == "scheduled",
        ScheduleLesson.end_at <= now,
    )
    if class_id:
        query = query.filter(ScheduleLesson.class_id == class_id)
    if course_id:
        query = query.filter(ScheduleLesson.course_id == course_id)
    if start:
        query = query.filter(ScheduleLesson.start_at >= start)
    if end:
        query = query.filter(ScheduleLesson.start_at <= end)
    query = query.order_by(ScheduleLesson.start_at.desc(), ScheduleLesson.id.desc())
    rows = query.all()
    if teacher_id:
        class_ids = {
            r[0]
            for r in db.query(ClassTeacher.class_id)
            .filter(ClassTeacher.teacher_id == teacher_id)
            .all()
        }
        rows = [
            r
            for r in rows
            if teacher_id in _parse_ids(r.teacher_ids)
            or (not _parse_ids(r.teacher_ids) and r.class_id in class_ids)
        ]
    total = len(rows)
    offset = (page - 1) * page_size
    return page_payload(
        [schedule_to_dict(db, r) for r in rows[offset : offset + page_size]],
        total=total,
        page=page,
        page_size=page_size,
    )

def list_makeup_class_records(
    db: Session,
    *,
    q: str | None = None,
    class_id: int | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """缺勤/请假后待补课的学员明细；本期只做记录与筛选，不含请假申请流。"""
    page = clamp_page(page)
    page_size = clamp_page_size(page_size)
    query = (
        db.query(ClassAttendance, ClassRecord, Student)
        .join(ClassRecord, ClassRecord.id == ClassAttendance.record_id)
        .join(Student, Student.id == ClassAttendance.student_id)
        .filter(
            ClassRecord.status == "normal",
            ClassAttendance.status.in_(("absent", "leave")),
        )
    )
    if q:
        qq = q.strip()
        query = query.filter(or_(Student.name.contains(qq), Student.phone.contains(qq)))
    if class_id:
        query = query.filter(ClassRecord.class_id == class_id)
    if start:
        query = query.filter(ClassRecord.class_start >= start)
    if end:
        query = query.filter(ClassRecord.class_start <= end)
    query = query.order_by(ClassRecord.class_start.desc(), ClassAttendance.id.desc())
    total = query.count()
    rows = query.offset((page - 1) * page_size).limit(page_size).all()
    status_labels = {"absent": "未到", "leave": "请假"}
    items: list[dict] = []
    for attendance, record, student in rows:
        cls = db.get(ClassRoom, record.class_id)
        course = db.get(Course, record.course_id) if record.course_id else None
        items.append(
            {
                "id": attendance.id,
                "record_id": record.id,
                "student_id": student.id,
                "student_name": student.name,
                "phone": student.phone or "",
                "class_id": record.class_id,
                "class_name": cls.name if cls else "",
                "course_id": record.course_id,
                "course_name": course.name if course else "",
                "class_start": record.class_start,
                "class_end": record.class_end,
                "teachers": _teacher_names(db, _parse_ids(record.teacher_ids)),
                "absence_status": attendance.status,
                "absence_status_label": status_labels.get(attendance.status, attendance.status),
                "consume_label": f"课程【{course.name}】" if course else "—",
                "expected_hours": float(record.hours or 0),
                "actual_hours": float(attendance.hours_consumed or 0),
                "amount": float(attendance.amount or 0),
                "makeup_status": "pending",
                "makeup_status_label": "待补课",
                "content": record.content or "",
            }
        )
    return page_payload(items, total=total, page=page, page_size=page_size)

def _attendance_consume_hours(status: str, session_hours: float) -> float:
    """点名扣课时：出勤/迟到扣课；请假/缺勤一律不扣。"""
    if status in {"present", "late"}:
        return float(session_hours or 0)
    return 0.0


def _lesson_day(value: datetime | date | None) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    return value


def _assert_roll_call_day_allowed(class_start: datetime | date | None) -> str | None:
    """仅允许当天及过去的课次点名；未指定上课时间视为当天（未排课直接点名）。"""
    lesson_day = _lesson_day(class_start)
    if lesson_day is None:
        return None
    if lesson_day > business_today():
        return "不能对未来课程点名，仅可点当天及过去的课次"
    return None


def _schedule_can_roll_call(row: ScheduleLesson) -> bool:
    if row.status != "scheduled":
        return False
    return _assert_roll_call_day_allowed(row.start_at) is None


def create_class_record(db: Session, user: User, data: dict) -> ClassRecord | str:
    class_id = int(data["class_id"])
    cls = db.get(ClassRoom, class_id)
    if not cls or cls.status != "active":
        return "班级不存在或当前不可上课"
    course = db.get(Course, cls.course_id) if cls.course_id else None
    # 授课课时默认取班级单次课次（通常为 1），与排课墙钟时长无关；计薪课时另计
    if data.get("hours") is not None:
        hours = float(data["hours"])
    else:
        hours = float(cls.hours_per_session or 1)
    if hours <= 0:
        return "授课课时须大于 0"

    schedule_id = data.get("schedule_id")
    schedule = db.get(ScheduleLesson, int(schedule_id)) if schedule_id else None
    if schedule_id and not schedule:
        return "排课不存在"
    if schedule and schedule.class_id != class_id:
        return "排课不属于所选班级"
    if schedule and schedule.status == "cancelled":
        return "已取消的排课不能点名"
    if schedule:
        existing_record = (
            db.query(ClassRecord)
            .filter(
                ClassRecord.schedule_id == schedule.id,
                ClassRecord.status == "normal",
            )
            .first()
        )
        if existing_record:
            return "该排课已经点名，请勿重复提交"

    teacher_ids = list(data.get("teacher_ids") or [])
    if not teacher_ids:
        if schedule:
            teacher_ids = _parse_ids(schedule.teacher_ids)
        if not teacher_ids:
            teacher_ids = [
                r.teacher_id
                for r in db.query(ClassTeacher).filter(ClassTeacher.class_id == class_id).all()
            ]
    for teacher_id in teacher_ids:
        teacher = db.get(User, int(teacher_id))
        if not teacher or not teacher.is_active or not is_teaching_staff(teacher.role):
            return f"老师 {teacher_id} 不存在或已停用"

    members = (
        db.query(ClassMember)
        .filter(ClassMember.class_id == class_id, ClassMember.status == "active")
        .all()
    )
    if not members:
        return "班级暂无学员，无法点名"

    attendance_input = data.get("attendances") or []
    attendance_ids = [int(a["student_id"]) for a in attendance_input]
    if len(attendance_ids) != len(set(attendance_ids)):
        return "点名名单中存在重复学员"
    member_ids = {m.student_id for m in members}
    if set(attendance_ids) != member_ids:
        return "请为班级全部在读学员提交点名状态"
    att_in = {
        int(a["student_id"]): a.get("status") or "present" for a in attendance_input
    }

    unit_price = float(course.unit_price or 0) if course else 0.0

    class_start = data.get("class_start") or (schedule.start_at if schedule else None)
    class_end = data.get("class_end") or (schedule.end_at if schedule else None)
    time_err = _assert_roll_call_day_allowed(class_start)
    if time_err:
        return time_err

    record = ClassRecord(
        class_id=class_id,
        schedule_id=schedule.id if schedule else None,
        course_id=cls.course_id,
        roll_at=_utcnow(),
        class_start=class_start,
        class_end=class_end,
        teacher_ids=json.dumps(teacher_ids, ensure_ascii=False),
        hours=hours,
        salary_hours=(
            float(data["salary_hours"])
            if data.get("salary_hours") is not None
            else 1.0
        ),
        status="normal",
        content=(data.get("content") or "").strip(),
        amount=0,
        present_count=0,
        total_count=len(members),
        created_by=user.id,
    )
    db.add(record)
    db.flush()

    total_amount = 0.0
    present = 0
    for m in members:
        st = att_in.get(m.student_id, "present")
        if st not in {"present", "absent", "leave", "late"}:
            st = "present"
        if st in {"present", "late"}:
            present += 1
        consume_hours = _attendance_consume_hours(st, hours)

        amt = 0.0
        if consume_hours > 0:
            amt, allocations, uncovered = _consume_package(
                db,
                student_id=m.student_id,
                course_id=cls.course_id,
                hours=consume_hours,
                unit_price=unit_price,
            )
            total_amount += amt
            db.add(
                CourseConsumption(
                    student_id=m.student_id,
                    class_id=class_id,
                    course_id=cls.course_id,
                    record_id=record.id,
                    teacher_id=teacher_ids[0] if teacher_ids else None,
                    consume_type="课时课消",
                    source="点名",
                    hours=consume_hours,
                    amount=amt,
                    package_allocations=json.dumps(allocations, ensure_ascii=False),
                    uncovered_hours=uncovered,
                    consumed_at=class_start or _utcnow(),
                    status="normal",
                    created_by=user.id,
                )
            )
            # 同步班级成员剩余
            if cls.course_id:
                pkgs = (
                    db.query(StudentCoursePackage)
                    .filter(
                        StudentCoursePackage.student_id == m.student_id,
                        StudentCoursePackage.course_id == cls.course_id,
                        StudentCoursePackage.status == "active",
                        or_(StudentCoursePackage.valid_until.is_(None), StudentCoursePackage.valid_until >= business_today()),
                    )
                    .all()
                )
                m.remain_hours = sum(float(p.remain_hours or 0) for p in pkgs)

        db.add(
            ClassAttendance(
                record_id=record.id,
                student_id=m.student_id,
                status=st,
                hours_consumed=consume_hours,
                amount=amt,
            )
        )

    record.present_count = present
    record.amount = round(total_amount, 2)
    if schedule:
        schedule.status = "completed"

    _add_class_record_log(
        db,
        record,
        user,
        action="create",
        action_label="完成点名",
        detail=f"创建上课记录，共 {record.total_count} 名学员，实到 {record.present_count} 人",
    )

    db.commit()
    db.refresh(record)
    return record

def _restore_package(
    db: Session,
    *,
    student_id: int,
    course_id: int | None,
    hours: float,
) -> None:
    """撤销点名时回滚课包课时。"""
    if hours <= 0 or not course_id:
        return
    pkgs = (
        db.query(StudentCoursePackage)
        .filter(
            StudentCoursePackage.student_id == student_id,
            StudentCoursePackage.course_id == course_id,
            StudentCoursePackage.status.in_(("active", "exhausted")),
        )
        .order_by(StudentCoursePackage.id.desc())
        .all()
    )
    left = float(hours)
    for pkg in pkgs:
        if left <= 0:
            break
        # 优先回填到仍有「已消耗空间」的课包，否则加到最近一包
        room = max(0.0, float(pkg.total_hours or 0) - float(pkg.remain_hours or 0))
        take = min(room, left) if room > 0 else left
        if take <= 0:
            continue
        pkg.remain_hours = float(pkg.remain_hours or 0) + take
        if pkg.remain_hours > 0:
            pkg.status = "active"
        pkg.updated_at = _utcnow()
        left -= take
    if left > 0 and pkgs:
        # 兜底：全部加回最近一包（允许略超 total，避免课时丢失）
        pkgs[0].remain_hours = float(pkgs[0].remain_hours or 0) + left
        pkgs[0].status = "active"
        pkgs[0].updated_at = _utcnow()

def _restore_consumption(db: Session, consumption: CourseConsumption) -> None:
    allocations = _parse_json_list(getattr(consumption, "package_allocations", None))
    restored = False
    for allocation in allocations:
        try:
            package_id = int(allocation.get("package_id"))
            hours = float(allocation.get("hours") or 0)
        except (TypeError, ValueError):
            continue
        if hours <= 0:
            continue
        package = db.get(StudentCoursePackage, package_id)
        if not package or package.student_id != consumption.student_id:
            continue
        package.remain_hours = min(
            float(package.total_hours or 0),
            float(package.remain_hours or 0) + hours,
        )
        if package.status == "exhausted" and package.remain_hours > 0:
            package.status = "active"
        package.updated_at = _utcnow()
        restored = True
    if not restored and float(getattr(consumption, "uncovered_hours", 0) or 0) <= 0:
        _restore_package(
            db,
            student_id=consumption.student_id,
            course_id=consumption.course_id,
            hours=float(consumption.hours or 0),
        )

def _sync_member_remain_hours(
    db: Session,
    *,
    class_id: int,
    course_id: int | None,
    student_ids: set[int],
) -> None:
    if not course_id or not student_ids:
        return
    members = (
        db.query(ClassMember)
        .filter(
            ClassMember.class_id == class_id,
            ClassMember.student_id.in_(student_ids),
            ClassMember.status == "active",
        )
        .all()
    )
    for member in members:
        packages = (
            db.query(StudentCoursePackage)
            .filter(
                StudentCoursePackage.student_id == member.student_id,
                StudentCoursePackage.course_id == course_id,
                StudentCoursePackage.status == "active",
                or_(
                    StudentCoursePackage.valid_until.is_(None),
                    StudentCoursePackage.valid_until >= business_today(),
                ),
            )
            .all()
        )
        member.remain_hours = sum(float(pkg.remain_hours or 0) for pkg in packages)

def _recalculate_class_record(db: Session, row: ClassRecord) -> None:
    """回滚当前课消，再按最新课时和出勤状态重新计算。"""
    old_consumptions = (
        db.query(CourseConsumption)
        .filter(CourseConsumption.record_id == row.id, CourseConsumption.status != "void")
        .all()
    )
    affected_students = {int(c.student_id) for c in old_consumptions}
    for consumption in old_consumptions:
        _restore_consumption(db, consumption)
        consumption.status = "void"

    attendance_rows = (
        db.query(ClassAttendance)
        .filter(ClassAttendance.record_id == row.id)
        .order_by(ClassAttendance.id.asc())
        .all()
    )
    affected_students.update(int(a.student_id) for a in attendance_rows)
    course = db.get(Course, row.course_id) if row.course_id else None
    unit_price = float(course.unit_price or 0) if course else 0.0
    teacher_ids = _parse_ids(row.teacher_ids)
    session_hours = float(row.hours or 0)

    total_amount = 0.0
    present_count = 0
    for attendance in attendance_rows:
        if attendance.status in {"present", "late"}:
            present_count += 1
        consume_hours = _attendance_consume_hours(attendance.status, session_hours)

        amount = 0.0
        if consume_hours > 0:
            amount, allocations, uncovered = _consume_package(
                db,
                student_id=attendance.student_id,
                course_id=row.course_id,
                hours=consume_hours,
                unit_price=unit_price,
            )
            db.add(
                CourseConsumption(
                    student_id=attendance.student_id,
                    class_id=row.class_id,
                    course_id=row.course_id,
                    record_id=row.id,
                    teacher_id=teacher_ids[0] if teacher_ids else None,
                    consume_type="课时课消",
                    source="点名修改",
                    hours=consume_hours,
                    amount=amount,
                    package_allocations=json.dumps(allocations, ensure_ascii=False),
                    uncovered_hours=uncovered,
                    consumed_at=row.class_start or _utcnow(),
                    status="normal",
                    created_by=row.created_by,
                )
            )
        attendance.hours_consumed = consume_hours
        attendance.amount = amount
        total_amount += amount

    row.present_count = present_count
    row.total_count = len(attendance_rows)
    row.amount = round(total_amount, 2)
    _sync_member_remain_hours(
        db,
        class_id=row.class_id,
        course_id=row.course_id,
        student_ids=affected_students,
    )

def update_class_record(
    db: Session,
    user: User,
    record_id: int,
    data: dict,
) -> ClassRecord | str:
    row = db.get(ClassRecord, record_id)
    if not row:
        return "上课记录不存在"
    if row.status == "void":
        return "已撤销的记录不能修改"

    class_start = data.get("class_start", row.class_start)
    class_end = data.get("class_end", row.class_end)
    if class_start and class_end and class_end <= class_start:
        return "下课时间须晚于上课时间"

    changes: list[str] = []
    recalculate = False
    if "class_start" in data and class_start != row.class_start:
        changes.append("上课时间")
        row.class_start = class_start
    if "class_end" in data and class_end != row.class_end:
        if "上课时间" not in changes:
            changes.append("上课时间")
        row.class_end = class_end
    if "hours" in data and data["hours"] is not None:
        hours = float(data["hours"])
        if hours <= 0:
            return "授课课时须大于 0"
        if abs(hours - float(row.hours or 0)) > 1e-6:
            changes.append(f"授课课时改为 {hours:g}")
            row.hours = hours
            recalculate = True
    if "salary_hours" in data and data["salary_hours"] is not None:
        salary_hours = float(data["salary_hours"])
        if salary_hours <= 0:
            return "计薪课时须大于 0"
        current_salary_hours = float(
            row.salary_hours if row.salary_hours is not None else row.hours or 0
        )
        if abs(salary_hours - current_salary_hours) > 1e-6:
            changes.append(f"计薪课时改为 {salary_hours:g}")
            row.salary_hours = salary_hours
    if "teacher_ids" in data and data["teacher_ids"] is not None:
        teacher_ids = [int(value) for value in data["teacher_ids"]]
        for teacher_id in teacher_ids:
            teacher = db.get(User, teacher_id)
            if not teacher or not teacher.is_active or not is_teaching_staff(teacher.role):
                return f"老师 {teacher_id} 不存在或已停用"
        if teacher_ids != _parse_ids(row.teacher_ids):
            row.teacher_ids = json.dumps(teacher_ids, ensure_ascii=False)
            changes.append("上课老师")
    if "content" in data and data["content"] is not None:
        content = str(data["content"]).strip()
        if content != (row.content or ""):
            row.content = content
            changes.append("上课内容")
    if "room" in data and data["room"] is not None:
        room = str(data["room"]).strip()
        schedule = db.get(ScheduleLesson, row.schedule_id) if row.schedule_id else None
        if schedule:
            if room != (schedule.room or ""):
                schedule.room = room
                changes.append("上课教室")
        elif room:
            return "未关联排课的记录不能单独修改教室"

    if not changes:
        return row
    if recalculate:
        _recalculate_class_record(db, row)
    elif "上课时间" in changes:
        for consumption in db.query(CourseConsumption).filter(
            CourseConsumption.record_id == row.id,
            CourseConsumption.status != "void",
        ):
            consumption.consumed_at = row.class_start or consumption.consumed_at

    _add_class_record_log(
        db,
        row,
        user,
        action="update",
        action_label="编辑课次",
        detail="、".join(changes),
    )
    db.commit()
    db.refresh(row)
    return row

def update_class_attendance(
    db: Session,
    user: User,
    record_id: int,
    student_id: int,
    status: str,
) -> ClassRecord | str:
    row = db.get(ClassRecord, record_id)
    if not row:
        return "上课记录不存在"
    if row.status == "void":
        return "已撤销的记录不能修改"
    attendance = (
        db.query(ClassAttendance)
        .filter(
            ClassAttendance.record_id == record_id,
            ClassAttendance.student_id == student_id,
        )
        .first()
    )
    if not attendance:
        return "点名名单中不存在该学员"
    if status not in {"present", "absent", "leave", "late"}:
        return "到课状态无效"
    if attendance.status == status:
        return "到课状态没有变化"
    labels = {"present": "出勤", "absent": "缺勤", "leave": "请假", "late": "迟到"}
    old_label = labels.get(attendance.status, attendance.status)
    student = db.get(Student, student_id)
    attendance.status = status
    _recalculate_class_record(db, row)
    _add_class_record_log(
        db,
        row,
        user,
        action="attendance_update",
        action_label="修改点名",
        detail=f"{student.name if student else f'学员#{student_id}'}：{old_label}改为{labels[status]}",
    )
    db.commit()
    db.refresh(row)
    return row

def remove_class_attendance(
    db: Session,
    user: User,
    record_id: int,
    student_id: int,
) -> ClassRecord | str:
    row = db.get(ClassRecord, record_id)
    if not row:
        return "上课记录不存在"
    if row.status == "void":
        return "已撤销的记录不能修改"
    attendance = (
        db.query(ClassAttendance)
        .filter(
            ClassAttendance.record_id == record_id,
            ClassAttendance.student_id == student_id,
        )
        .first()
    )
    if not attendance:
        return "点名名单中不存在该学员"
    if row.total_count <= 1:
        return "点名记录至少保留一名学员"
    student = db.get(Student, student_id)
    db.delete(attendance)
    db.flush()
    _recalculate_class_record(db, row)
    _add_class_record_log(
        db,
        row,
        user,
        action="attendance_remove",
        action_label="移出名单",
        detail=f"移出 {student.name if student else f'学员#{student_id}'}",
    )
    db.commit()
    db.refresh(row)
    return row

def void_class_record(db: Session, user: User, record_id: int) -> ClassRecord | str:
    row = db.get(ClassRecord, record_id)
    if not row:
        return "上课记录不存在"
    if row.status == "void":
        return "记录已撤销"
    row.status = "void"

    consumptions = (
        db.query(CourseConsumption)
        .filter(CourseConsumption.record_id == record_id, CourseConsumption.status != "void")
        .all()
    )
    for c in consumptions:
        _restore_consumption(db, c)
        c.status = "void"
        # 同步班级成员剩余课时
        if c.class_id and c.course_id:
            m = (
                db.query(ClassMember)
                .filter(
                    ClassMember.class_id == c.class_id,
                    ClassMember.student_id == c.student_id,
                    ClassMember.status == "active",
                )
                .first()
            )
            if m:
                pkgs = (
                    db.query(StudentCoursePackage)
                    .filter(
                        StudentCoursePackage.student_id == c.student_id,
                        StudentCoursePackage.course_id == c.course_id,
                        StudentCoursePackage.status == "active",
                        or_(StudentCoursePackage.valid_until.is_(None), StudentCoursePackage.valid_until >= business_today()),
                    )
                    .all()
                )
                m.remain_hours = sum(float(p.remain_hours or 0) for p in pkgs)

    # 关联排课恢复为待上
    if row.schedule_id:
        sch = db.get(ScheduleLesson, row.schedule_id)
        if sch and sch.status == "completed":
            other = (
                db.query(ClassRecord)
                .filter(
                    ClassRecord.schedule_id == row.schedule_id,
                    ClassRecord.id != row.id,
                    ClassRecord.status == "normal",
                )
                .count()
            )
            if not other:
                sch.status = "scheduled"

    _add_class_record_log(
        db,
        row,
        user,
        action="void",
        action_label="撤销点名",
        detail="撤销上课记录并回滚课时",
    )

    db.commit()
    db.refresh(row)
    return row

def list_teachers_manage(db: Session, *, q: str | None = None, page: int = 1, page_size: int = 50) -> dict:
    """老师下拉/管理列表：含负责人（可授课）。"""
    page = clamp_page(page)
    page_size = clamp_page_size(page_size)
    query = db.query(User).filter(
        User.role.in_(list(TEACHING_STAFF_ROLES)),
        User.is_active.is_(True),
        User.deleted_at.is_(None),
    )
    if q:
        qq = q.strip()
        query = query.filter((User.display_name.contains(qq)) | (User.username.contains(qq)))
    query = query.order_by(User.id.asc())
    rows, total = paginate_query(query, page=page, page_size=page_size)
    items = []
    for u in rows:
        class_count = (
            db.query(ClassTeacher)
            .join(ClassRoom, ClassRoom.id == ClassTeacher.class_id)
            .filter(ClassTeacher.teacher_id == u.id, ClassRoom.status == "active")
            .count()
        )
        items.append(
            {
                "id": u.id,
                "name": u.display_name or u.username,
                "username": u.username,
                "role": ROLE_DISPLAY_LABEL.get(u.role, u.role),
                "role_code": u.role,
                "subject": "",
                "phone": "-",
                "class_count": class_count,
                "status": "在职" if u.is_active else "离职",
                "is_active": u.is_active,
            }
        )
    return page_payload(items, total=total, page=page, page_size=page_size)

def grant_course_package(
    db: Session,
    *,
    student_id: int,
    course_id: int,
    hours: float,
    unit_price: float,
    purchased_hours: float | None = None,
    gift_hours: float = 0.0,
    valid_until: date | None = None,
    enrollment_id: int | None = None,
) -> StudentCoursePackage:
    """报名/续费写入课包。"""
    pkg = StudentCoursePackage(
        student_id=student_id,
        course_id=course_id,
        enrollment_id=enrollment_id,
        purchased_hours=(hours - gift_hours if purchased_hours is None else purchased_hours),
        gift_hours=gift_hours,
        total_hours=hours,
        remain_hours=hours,
        unit_price=unit_price,
        valid_until=valid_until,
        status="active",
    )
    db.add(pkg)
    db.flush()
    return pkg

def ensure_one_to_one_class(
    db: Session,
    *,
    student: Student,
    course: Course,
    user: User,
) -> ClassRoom | None:
    """一对一报课后自动建班（若不存在）。"""
    if course.course_type != "one_to_one":
        return None
    existing = (
        db.query(ClassRoom)
        .filter(
            ClassRoom.mode == "one_to_one",
            ClassRoom.course_id == course.id,
            ClassRoom.primary_student_id == student.id,
            ClassRoom.status == "active",
        )
        .first()
    )
    if existing:
        return existing
    name = f"{course.name}_{student.name}"
    row = ClassRoom(
        name=name,
        mode="one_to_one",
        course_id=course.id,
        capacity=1,
        over_capacity=False,
        online_select=False,
        hours_per_session=1.0,
        primary_student_id=student.id,
        status="active",
        created_by=user.id,
    )
    db.add(row)
    db.flush()
    db.add(ClassMember(class_id=row.id, student_id=student.id, status="active"))
    return row
