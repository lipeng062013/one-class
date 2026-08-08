import json
from datetime import date, datetime

from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from app.core.pagination import clamp_page, clamp_page_size, page_payload, paginate_query
from app.core.roles import ACADEMIC_MANAGER_ROLES, is_academic_manager_role
from app.core.storage import Storage
from app.core.timeutil import now as _utcnow
from app.core.timeutil import today as business_today
from app.models.student import LearningRecord, LearningRecordFile, Student
from app.models.user import User
from app.modules.students.schemas import CLASS_STATUSES, STUDENT_STATUSES

def _parse_json_list(raw: str | None) -> list:
    if not raw:
        return []
    try:
        data = json.loads(raw)
        return data if isinstance(data, list) else []
    except (TypeError, json.JSONDecodeError):
        return []

def _normalize_courses(raw: list | None) -> list[dict] | str:
    """校验并规范化关联课程。

    建档允许不关联课程（空列表）；报名/续费时再选择并写入课包。
    传入空列表会清空 linked_courses。
    """
    items = raw or []
    if len(items) > 20:
        return "关联课程最多 20 门"
    out: list[dict] = []
    for item in items:
        if not isinstance(item, dict):
            return "课程数据格式不正确"
        name = str(item.get("name") or "").strip()
        if not name:
            return "课程名称不能为空"
        row: dict = {
            "name": name[:128],
            "type": str(item.get("type") or "").strip()[:32],
            "price_label": str(item.get("price_label") or "").strip()[:128],
        }
        cid = item.get("id")
        if cid is not None:
            try:
                row["id"] = int(cid)
            except (TypeError, ValueError):
                pass
        out.append(row)
    return out

def validate_student_status(status: str) -> str | None:
    if status not in STUDENT_STATUSES:
        return "无效的学生状态"
    return None

def validate_class_status(status: str) -> str | None:
    if status not in CLASS_STATUSES:
        return "无效的上课状态"
    return None

def resolve_manager(db: Session, manager_id: int | None) -> User | str | None:
    """学管师：负责人 / CR / academic_manager（可停用便于转交前仍显示；已删除不可再指派）。"""
    if manager_id is None:
        return None
    user = db.get(User, manager_id)
    if not user or user.deleted_at is not None:
        return "学管师不存在"
    if not is_academic_manager_role(user.role):
        return "学管师须为负责人或 CR（班主任，学管师）角色账号"
    return user

def manager_name(db: Session, manager_id: int | None) -> str | None:
    if not manager_id:
        return None
    user = db.get(User, manager_id)
    # Soft-deleted teachers still resolve so historical 学管师名可展示
    return user.display_name if user else None

def latest_learning_at(db: Session, student_id: int) -> datetime | None:
    row = (
        db.query(func.max(LearningRecord.class_date))
        .filter(LearningRecord.student_id == student_id)
        .scalar()
    )
    return row

def student_has_enroll_record(db: Session, student_id: int) -> bool:
    from app.models.enrollment import EnrollmentRecord

    return (
        db.query(EnrollmentRecord.id)
        .filter(
            EnrollmentRecord.student_id == student_id,
            EnrollmentRecord.kind == "enroll",
        )
        .first()
        is not None
    )


def allocation_phase(db: Session, s: Student) -> str:
    """pending_enroll | pending_alloc | allocated | normal"""
    if not s.source_lead_id:
        return "normal"
    if not student_has_enroll_record(db, s.id):
        return "pending_enroll"
    if not s.academic_manager_id:
        return "pending_alloc"
    return "allocated"


def assert_can_assign_manager(db: Session, student: Student) -> str | None:
    """线索转入学员须先完成报名才能分配学管。返回错误或 None。"""
    if not student.source_lead_id:
        return None
    if student_has_enroll_record(db, student.id):
        return None
    return "请先完成报名后再分配学管"


def student_to_dict(db: Session, s: Student) -> dict:
    phase = allocation_phase(db, s)
    has_enroll = student_has_enroll_record(db, s.id)
    return {
        "id": s.id,
        "name": s.name,
        "grade": s.grade or "",
        "school": s.school or "",
        "phone": s.phone,
        "parent_name": s.parent_name,
        "academic_manager_id": s.academic_manager_id,
        "academic_manager_name": manager_name(db, s.academic_manager_id),
        "status": s.status,
        "source_lead_id": s.source_lead_id,
        "notes": s.notes or "",
        "linked_courses": _parse_json_list(getattr(s, "linked_courses", None)),
        "created_by": s.created_by,
        "created_at": s.created_at,
        "updated_at": s.updated_at,
        "latest_learning_at": latest_learning_at(db, s.id),
        "has_enroll": has_enroll,
        "allocation_phase": phase,
        "needs_allocation": phase == "pending_alloc",
    }

def list_students(
    db: Session,
    *,
    grade: str | None = None,
    name: str | None = None,
    phone: str | None = None,
    status: str | None = None,
    school: str | None = None,
    academic_manager_id: int | None = None,
    q: str | None = None,
    page: int | None = None,
    page_size: int | None = None,
    viewer: User | None = None,
) -> dict:
    """Paginated student list. Returns { items, total, page, page_size }.

    学管师（CR）自动限定为 academic_manager_id = 自己，避免搜到他人名下学员。
    """
    from app.core.roles import is_finance_scoped_role

    query = db.query(Student)
    # 学管师：强制仅名下学员（报名搜索、学员列表一致）
    if viewer is not None and is_finance_scoped_role(viewer.role):
        query = query.filter(Student.academic_manager_id == viewer.id)
    elif academic_manager_id is not None:
        if academic_manager_id == 0:
            query = query.filter(Student.academic_manager_id.is_(None))
        else:
            query = query.filter(Student.academic_manager_id == academic_manager_id)
    if grade:
        query = query.filter(Student.grade == grade)
    if name:
        query = query.filter(Student.name.contains(name))
    if phone:
        query = query.filter(Student.phone.contains(phone))
    if status:
        query = query.filter(Student.status == status)
    if school:
        query = query.filter(Student.school.contains(school))
    if q:
        like = f"%{q}%"
        query = query.filter(
            or_(
                Student.name.like(like),
                Student.phone.like(like),
                Student.school.like(like),
                Student.parent_name.like(like),
            )
        )
    query = query.order_by(Student.id.desc())
    p = clamp_page(page)
    ps = clamp_page_size(page_size)
    rows, total = paginate_query(query, page=p, page_size=ps)
    return page_payload(rows, total=total, page=p, page_size=ps)

def get_student(db: Session, student_id: int) -> Student | None:
    return db.get(Student, student_id)

def create_student(db: Session, user: User, data: dict) -> Student | str:
    err = validate_student_status(data.get("status") or "active")
    if err:
        return err
    mgr = resolve_manager(db, data.get("academic_manager_id"))
    if isinstance(mgr, str):
        return mgr

    courses = _normalize_courses(data.get("courses"))
    if isinstance(courses, str):
        return courses

    student = Student(
        name=data["name"].strip(),
        grade=(data.get("grade") or "").strip(),
        school=(data.get("school") or "").strip(),
        phone=(data.get("phone") or None),
        parent_name=(data.get("parent_name") or None),
        academic_manager_id=data.get("academic_manager_id"),
        status=data.get("status") or "active",
        source_lead_id=data.get("source_lead_id"),
        notes=data.get("notes") or "",
        linked_courses=json.dumps(courses, ensure_ascii=False),
        created_by=user.id,
    )
    if not student.name:
        return "姓名不能为空"
    if not student.grade:
        return "年级不能为空"

    db.add(student)
    db.commit()
    db.refresh(student)
    return student

def update_student(db: Session, student: Student, data: dict) -> Student | str:
    if "status" in data and data["status"] is not None:
        err = validate_student_status(data["status"])
        if err:
            return err
    if "academic_manager_id" in data:
        new_mgr = data["academic_manager_id"]
        # 从空设为有值，或变更学管：线索来源须已报名
        if new_mgr is not None and new_mgr != student.academic_manager_id:
            gate = assert_can_assign_manager(db, student)
            if gate:
                return gate
        mgr = resolve_manager(db, data["academic_manager_id"])
        if isinstance(mgr, str):
            return mgr

    courses_in = data.pop("courses", None)
    if courses_in is not None:
        courses = _normalize_courses(courses_in)
        if isinstance(courses, str):
            return courses
        student.linked_courses = json.dumps(courses, ensure_ascii=False)

    for key, value in data.items():
        if key in {"name", "grade", "school"} and value is not None:
            value = str(value).strip()
        if key == "linked_courses":
            continue
        setattr(student, key, value)

    if not student.name:
        return "姓名不能为空"
    if not student.grade:
        return "年级不能为空"

    student.updated_at = _utcnow()
    db.commit()
    db.refresh(student)
    return student

def delete_student(db: Session, student: Student) -> None:
    db.delete(student)
    db.commit()

def bulk_delete_students(db: Session, student_ids: list[int]) -> dict | str:
    ids = list(dict.fromkeys(student_ids))  # preserve order, unique
    if not ids:
        return "请选择要删除的学生"
    students = db.query(Student).filter(Student.id.in_(ids)).all()
    if not students:
        return "未找到要删除的学生"
    found = {s.id for s in students}
    missing = [i for i in ids if i not in found]
    if missing:
        return f"部分学生不存在: {missing}"
    for s in students:
        db.delete(s)
    db.commit()
    return {"deleted_count": len(students), "deleted_ids": sorted(found)}

def reassign_students(
    db: Session,
    *,
    student_ids: list[int],
    to_manager_id: int,
    from_manager_id: int | None = None,
) -> dict | str:
    to_mgr = resolve_manager(db, to_manager_id)
    if isinstance(to_mgr, str):
        return to_mgr
    if to_mgr is None:
        return "请选择目标学管师"
    assert isinstance(to_mgr, User)
    if not to_mgr.is_active:
        return "目标学管师账号已停用，请选择在职老师"

    if from_manager_id is not None:
        from_mgr = resolve_manager(db, from_manager_id)
        if isinstance(from_mgr, str):
            return from_mgr

    students = db.query(Student).filter(Student.id.in_(student_ids)).all()
    if not students:
        return "未找到要转交的学生"
    if len(students) != len(set(student_ids)):
        found = {s.id for s in students}
        missing = [i for i in student_ids if i not in found]
        return f"部分学生不存在: {missing}"

    if from_manager_id is not None:
        wrong = [s.id for s in students if s.academic_manager_id != from_manager_id]
        if wrong:
            return f"学生 {wrong} 不属于所选原学管师，请重新勾选"

    blocked = []
    for s in students:
        gate = assert_can_assign_manager(db, s)
        if gate:
            blocked.append(f"{s.name}#{s.id}")
    if blocked:
        return f"请先完成报名后再分配学管：{', '.join(blocked)}"

    for s in students:
        s.academic_manager_id = to_manager_id
        s.updated_at = _utcnow()

    db.commit()
    return {
        "updated_count": len(students),
        "student_ids": [s.id for s in students],
        "to_manager_id": to_manager_id,
        "to_manager_name": to_mgr.display_name,
    }

def list_managers(db: Session, *, include_inactive: bool = True) -> list[dict]:
    """可选学管师列表（负责人 / CR / academic_manager），附带名下学生数。已删除账号不出现在指派列表。"""
    query = db.query(User).filter(
        User.role.in_(list(ACADEMIC_MANAGER_ROLES)),
        User.deleted_at.is_(None),
    )
    if not include_inactive:
        query = query.filter(User.is_active.is_(True))
    managers = query.order_by(User.id.asc()).all()

    counts = dict(
        db.query(Student.academic_manager_id, func.count(Student.id))
        .filter(Student.academic_manager_id.isnot(None))
        .group_by(Student.academic_manager_id)
        .all()
    )
    return [
        {
            "id": m.id,
            "display_name": m.display_name,
            "username": m.username,
            "is_active": m.is_active,
            "student_count": int(counts.get(m.id, 0)),
        }
        for m in managers
    ]

def learning_to_dict(db: Session, r: LearningRecord) -> dict:
    teacher = db.get(User, r.teacher_id)
    student = db.get(Student, r.student_id)
    return {
        "id": r.id,
        "student_id": r.student_id,
        "student_name": student.name if student else None,
        "teacher_id": r.teacher_id,
        "teacher_name": teacher.display_name if teacher else None,
        "class_date": r.class_date,
        "class_status": r.class_status,
        "subject": r.subject,
        "learning_summary": r.learning_summary or "",
        "homework_note": r.homework_note or "",
        "notes": r.notes or "",
        "created_at": r.created_at,
        "updated_at": r.updated_at,
        "files": [
            {
                "id": f.id,
                "file_path": f.file_path,
                "file_type": f.file_type,
                "sort_order": f.sort_order,
            }
            for f in (r.files or [])
        ],
    }

def list_learning_records(
    db: Session,
    *,
    student_id: int | None = None,
    teacher_id: int | None = None,
    q: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """Paginated learning records: { items, total, page, page_size }."""
    page = clamp_page(page)
    page_size = clamp_page_size(page_size)
    query = db.query(LearningRecord).options(joinedload(LearningRecord.files))
    if student_id is not None:
        query = query.filter(LearningRecord.student_id == student_id)
    if teacher_id is not None:
        query = query.filter(LearningRecord.teacher_id == teacher_id)
    if q and q.strip():
        qq = q.strip()
        # 学生姓名 / 科目 / 摘要 / 填写人
        query = (
            query.outerjoin(Student, Student.id == LearningRecord.student_id)
            .outerjoin(User, User.id == LearningRecord.teacher_id)
            .filter(
                or_(
                    Student.name.contains(qq),
                    LearningRecord.subject.contains(qq),
                    LearningRecord.learning_summary.contains(qq),
                    User.display_name.contains(qq),
                    User.username.contains(qq),
                )
            )
        )
    query = query.order_by(LearningRecord.class_date.desc(), LearningRecord.id.desc())
    rows, total = paginate_query(query, page=page, page_size=page_size)
    items = [learning_to_dict(db, r) for r in rows]
    return page_payload(items, total=total, page=page, page_size=page_size)

def get_learning_record(db: Session, record_id: int) -> LearningRecord | None:
    return (
        db.query(LearningRecord)
        .options(joinedload(LearningRecord.files))
        .filter(LearningRecord.id == record_id)
        .first()
    )

def create_learning_record(db: Session, user: User, data: dict) -> LearningRecord | str:
    student = get_student(db, data["student_id"])
    if not student:
        return "学生不存在"
    err = validate_class_status(data.get("class_status") or "attended")
    if err:
        return err
    summary = (data.get("learning_summary") or "").strip()
    if not summary:
        return "请填写学习情况"

    class_date = data.get("class_date") or _utcnow()
    record = LearningRecord(
        student_id=student.id,
        teacher_id=user.id,
        class_date=class_date,
        class_status=data.get("class_status") or "attended",
        subject=data.get("subject"),
        learning_summary=summary,
        homework_note=data.get("homework_note") or "",
        notes=data.get("notes") or "",
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return get_learning_record(db, record.id) or record

def update_learning_record(
    db: Session, user: User, record: LearningRecord, data: dict
) -> LearningRecord | str:
    from app.core.permissions import has_permission

    # 负责人或拥有学员删除级权限者可改全部；否则仅本人
    if not has_permission(user, "students.delete") and record.teacher_id != user.id:
        return "只能修改自己提交的学情"
    if "class_status" in data and data["class_status"] is not None:
        err = validate_class_status(data["class_status"])
        if err:
            return err
    if "learning_summary" in data and data["learning_summary"] is not None:
        if not str(data["learning_summary"]).strip():
            return "学习情况不能为空"
        data["learning_summary"] = str(data["learning_summary"]).strip()

    for key, value in data.items():
        setattr(record, key, value)
    record.updated_at = _utcnow()
    db.commit()
    return get_learning_record(db, record.id) or record

def delete_learning_record(db: Session, user: User, record: LearningRecord) -> str | None:
    from app.core.permissions import has_permission

    if not has_permission(user, "students.delete") and record.teacher_id != user.id:
        return "只能删除自己提交的学情"
    db.delete(record)
    db.commit()
    return None

def add_learning_file(
    db: Session,
    storage: Storage,
    record: LearningRecord,
    *,
    filename: str,
    content: bytes,
    content_type: str,
) -> LearningRecordFile:
    safe_name = filename.replace("\\", "_").replace("/", "_")
    rel = f"learning/{record.id}/{int(_utcnow().timestamp())}_{safe_name}"
    storage.save(rel, content)
    sort_order = len(record.files or [])
    mf = LearningRecordFile(
        record_id=record.id,
        file_path=rel,
        file_type=content_type,
        sort_order=sort_order,
    )
    db.add(mf)
    db.commit()
    db.refresh(mf)
    return mf

def can_write_learning(user: User) -> bool:
    from app.core.permissions import has_permission

    return has_permission(user, "learning.write")

def can_delete_student(user: User) -> bool:
    from app.core.permissions import has_permission

    return has_permission(user, "students.delete")

def can_reassign(user: User) -> bool:
    from app.core.permissions import has_permission

    return has_permission(user, "students.delete")

# ── 学生详情 Tab：报读课程 / 消费记录 / 学员动态 ──────────────

PACKAGE_STATUS_LABELS = {
    "active": "在读",
    "exhausted": "已耗尽",
    "refunded": "已退费",
    "closed": "已结课",
    "expired": "已过期",
}


def _package_is_available(package) -> bool:
    return package.status == "active" and (
        not package.valid_until or package.valid_until >= business_today()
    )


def _resolve_package_order(db: Session, package) -> tuple[int | None, str]:
    from app.models.enrollment import EnrollmentRecord
    from app.models.finance import FinanceOrder

    order_no = ""
    order_id = None
    if package.enrollment_id:
        en = db.get(EnrollmentRecord, package.enrollment_id)
        if en and getattr(en, "order_no", None):
            order_no = en.order_no or ""
        fo = (
            db.query(FinanceOrder)
            .filter(FinanceOrder.enrollment_id == package.enrollment_id)
            .first()
        )
        if fo:
            order_id = fo.id
            order_no = fo.order_no or order_no
    return order_id, order_no or f"PKG-{package.id}"


def _package_row_dict(db: Session, package) -> dict:
    order_id, order_no = _resolve_package_order(db, package)
    used = float(package.total_hours or 0) - float(package.remain_hours or 0)
    if used < 0:
        used = 0.0
    gift_hours = float(getattr(package, "gift_hours", 0) or 0)
    purchase_hours = float(getattr(package, "purchased_hours", 0) or 0)
    if purchase_hours <= 0 and gift_hours <= 0:
        purchase_hours = float(package.total_hours or 0)
    # refunded/closed 且剩余被清零时，把清零部分记为退转数量近似值
    refund_hours = 0.0
    if package.status in {"refunded", "closed"} and float(package.remain_hours or 0) <= 0:
        # 无法精确拆分退转，展示 0；清零操作会写入 total 差值时由前端看 remain
        refund_hours = 0.0
    package_status = package.status
    if package_status == "active" and package.valid_until and package.valid_until < business_today():
        package_status = "expired"
    return {
        "package_id": package.id,
        "order_id": order_id,
        "order_no": order_no,
        "purchase_hours": purchase_hours,
        "gift_hours": gift_hours,
        "consumed_hours": round(used, 2),
        "refund_hours": round(refund_hours, 2),
        "remain_hours": float(package.remain_hours or 0),
        "valid_until": package.valid_until.isoformat() if package.valid_until else None,
        "priority_consume": bool(getattr(package, "priority_consume", False)),
        "status": package_status,
        "status_label": PACKAGE_STATUS_LABELS.get(package_status, package_status),
        "unit_price": float(package.unit_price or 0),
        "created_at": package.created_at,
        "can_clear_hours": package.status == "active" and float(package.remain_hours or 0) > 0,
    }


def list_student_course_packages(db: Session, student_id: int) -> dict:
    """报读课程：按课程聚合课包 + 订单行。"""
    from app.models.academic import ClassMember, ClassRoom, Course, StudentCoursePackage
    from app.models.finance import CourseConsumption

    student = get_student(db, student_id)
    if not student:
        return {"error": "学生不存在"}

    pkgs = (
        db.query(StudentCoursePackage)
        .filter(StudentCoursePackage.student_id == student_id)
        .order_by(
            StudentCoursePackage.priority_consume.desc(),
            StudentCoursePackage.id.desc(),
        )
        .all()
    )

    total_remain = sum(float(p.remain_hours or 0) for p in pkgs if _package_is_available(p))
    total_bought = sum(float(p.total_hours or 0) for p in pkgs if p.status != "refunded")
    total_remain_all = sum(
        float(p.remain_hours or 0) for p in pkgs if p.status not in {"refunded"}
    )
    total_consumed = total_bought - total_remain_all
    if total_consumed < 0:
        total_consumed = 0.0

    # group by course_id
    by_course: dict[int, list] = {}
    for p in pkgs:
        by_course.setdefault(int(p.course_id), []).append(p)

    courses_out = []
    for course_id, group in by_course.items():
        course = db.get(Course, course_id)
        remain = sum(float(p.remain_hours or 0) for p in group if _package_is_available(p))
        bought = sum(float(p.total_hours or 0) for p in group if p.status != "refunded")
        remain_all = sum(float(p.remain_hours or 0) for p in group if p.status != "refunded")
        consumed = bought - remain_all
        if consumed < 0:
            consumed = 0.0

        # 所在班级
        class_name = "未选班"
        class_id = None
        cls = (
            db.query(ClassRoom)
            .filter(
                ClassRoom.course_id == course_id,
                ClassRoom.primary_student_id == student_id,
                ClassRoom.status == "active",
            )
            .first()
        )
        if not cls:
            m = (
                db.query(ClassMember)
                .join(ClassRoom, ClassRoom.id == ClassMember.class_id)
                .filter(
                    ClassMember.student_id == student_id,
                    ClassMember.status == "active",
                    ClassRoom.course_id == course_id,
                    ClassRoom.status == "active",
                )
                .first()
            )
            if m:
                cls = db.get(ClassRoom, m.class_id)
        if cls:
            class_name = cls.name
            class_id = cls.id

        orders_rows = [_package_row_dict(db, p) for p in group]
        active_pkgs = [p for p in group if p.status == "active"]
        closed_pkgs = [p for p in group if p.status in {"closed", "exhausted", "refunded"}]
        is_closed = bool(group) and not active_pkgs and bool(closed_pkgs)
        # 仅有过期 active 也算不可用
        has_available = any(_package_is_available(p) for p in group)

        type_label = ""
        if course:
            type_label = "一对一" if course.course_type == "one_to_one" else "一对多"

        courses_out.append(
            {
                "course_id": course_id,
                "course_name": course.name if course else f"课程#{course_id}",
                "course_type": course.course_type if course else "",
                "type_label": type_label,
                "remain_hours": round(remain, 2),
                "consumed_hours": round(consumed, 2),
                "total_hours": round(bought, 2),
                "class_id": class_id,
                "class_name": class_name,
                "packages": orders_rows,
                "is_closed": is_closed,
                "has_available": has_available,
                "can_close": any(p.status == "active" for p in group),
                "can_operate": any(p.status == "active" for p in group),
            }
        )

    # linked_courses 无课包时也展示占位
    linked = _parse_json_list(getattr(student, "linked_courses", None))
    existing_ids = {c["course_id"] for c in courses_out if c.get("course_id") is not None}
    for lc in linked:
        cid = lc.get("id")
        if cid and int(cid) in existing_ids:
            continue
        if not lc.get("name"):
            continue
        courses_out.append(
            {
                "course_id": int(cid) if cid else None,
                "course_name": lc.get("name") or "",
                "course_type": "",
                "type_label": lc.get("type") or "",
                "remain_hours": 0,
                "consumed_hours": 0,
                "total_hours": 0,
                "class_id": None,
                "class_name": "未选班",
                "packages": [],
                "from_link_only": True,
                "is_closed": False,
                "has_available": False,
                "can_close": False,
                "can_operate": False,
            }
        )

    overtime_hours = (
        db.query(func.coalesce(func.sum(CourseConsumption.uncovered_hours), 0.0))
        .filter(
            CourseConsumption.student_id == student_id,
            CourseConsumption.status == "normal",
        )
        .scalar()
        or 0.0
    )

    # 有剩余课时的课程排前，已结课靠后
    courses_out.sort(
        key=lambda c: (
            1 if c.get("is_closed") else 0,
            0 if c.get("has_available") else 1,
            -(c.get("remain_hours") or 0),
        )
    )

    return {
        "summary": {
            "remain_hours": round(total_remain, 2),
            "overtime_hours": round(float(overtime_hours), 2),
            "consumed_hours": round(total_consumed, 2),
            "total_hours": round(total_bought, 2),
        },
        "courses": courses_out,
    }


def update_student_package(
    db: Session,
    student_id: int,
    package_id: int,
    *,
    valid_until: date | None = None,
    clear_valid_until: bool = False,
    priority_consume: bool | None = None,
) -> dict | str:
    """更新课包有效期 / 优先消耗。"""
    from app.models.academic import StudentCoursePackage

    student = get_student(db, student_id)
    if not student:
        return "学生不存在"
    pkg = db.get(StudentCoursePackage, package_id)
    if not pkg or pkg.student_id != student_id:
        return "课包不存在"
    if pkg.status in {"refunded"}:
        return "已退费课包不可修改"

    if clear_valid_until:
        pkg.valid_until = None
    elif valid_until is not None:
        pkg.valid_until = valid_until

    if priority_consume is not None:
        pkg.priority_consume = bool(priority_consume)
        # 同一课程仅允许一个优先课包
        if pkg.priority_consume:
            (
                db.query(StudentCoursePackage)
                .filter(
                    StudentCoursePackage.student_id == student_id,
                    StudentCoursePackage.course_id == pkg.course_id,
                    StudentCoursePackage.id != pkg.id,
                    StudentCoursePackage.priority_consume.is_(True),
                )
                .update({"priority_consume": False}, synchronize_session=False)
            )

    pkg.updated_at = _utcnow()
    db.commit()
    db.refresh(pkg)
    return _package_row_dict(db, pkg)


def clear_package_hours(
    db: Session,
    student_id: int,
    package_id: int,
    *,
    remark: str = "",
) -> dict | str:
    """课时清零：将剩余课时置 0 并标记 exhausted。"""
    from app.models.academic import StudentCoursePackage

    student = get_student(db, student_id)
    if not student:
        return "学生不存在"
    pkg = db.get(StudentCoursePackage, package_id)
    if not pkg or pkg.student_id != student_id:
        return "课包不存在"
    if pkg.status != "active":
        return "仅在读课包可清零课时"
    remain = float(pkg.remain_hours or 0)
    if remain <= 0:
        return "剩余课时已为 0"
    pkg.remain_hours = 0.0
    pkg.status = "exhausted"
    pkg.updated_at = _utcnow()
    db.commit()
    db.refresh(pkg)
    row = _package_row_dict(db, pkg)
    row["cleared_hours"] = remain
    row["remark"] = (remark or "").strip()
    return row


def close_student_course(
    db: Session,
    student_id: int,
    course_id: int,
    *,
    clear_remain: bool = False,
) -> dict | str:
    """结课：课程下 active 课包标记 closed，可选清零剩余。"""
    from app.models.academic import Course, StudentCoursePackage

    student = get_student(db, student_id)
    if not student:
        return "学生不存在"
    course = db.get(Course, course_id)
    if not course:
        return "课程不存在"
    pkgs = (
        db.query(StudentCoursePackage)
        .filter(
            StudentCoursePackage.student_id == student_id,
            StudentCoursePackage.course_id == course_id,
            StudentCoursePackage.status == "active",
        )
        .all()
    )
    if not pkgs:
        return "该课程无可结课的在读课包"
    closed = 0
    for pkg in pkgs:
        if clear_remain:
            pkg.remain_hours = 0.0
        pkg.status = "closed"
        pkg.updated_at = _utcnow()
        closed += 1
    db.commit()
    return {
        "student_id": student_id,
        "course_id": course_id,
        "course_name": course.name,
        "closed_count": closed,
        "clear_remain": clear_remain,
    }


def list_student_orders(
    db: Session,
    student_id: int,
    *,
    page: int = 1,
    page_size: int = 20,
    status: str | None = None,
    order_type: str | None = None,
    item_q: str | None = None,
) -> dict:
    """消费记录：学员相关财务订单（分页；summary 按筛选后非作废汇总）。"""
    from app.models.finance import FinanceOrder
    from app.modules.finance.service import order_to_dict

    student = get_student(db, student_id)
    if not student:
        return {"error": "学生不存在"}

    page = clamp_page(page)
    page_size = clamp_page_size(page_size)
    base = db.query(FinanceOrder).filter(FinanceOrder.student_id == student_id)

    statuses = [s.strip() for s in (status or "").split(",") if s.strip()]
    if statuses:
        base = base.filter(FinanceOrder.status.in_(statuses))
    if order_type:
        types = [t.strip() for t in order_type.split(",") if t.strip()]
        if len(types) == 1:
            base = base.filter(FinanceOrder.order_type == types[0])
        elif types:
            base = base.filter(FinanceOrder.order_type.in_(types))
    if item_q and item_q.strip():
        base = base.filter(FinanceOrder.item_summary.contains(item_q.strip()))

    # 汇总：当前筛选条件下非作废
    all_rows = base.all()
    total_recv = sum(float(r.receivable or 0) for r in all_rows if r.status != "void")
    total_paid = sum(float(r.received or 0) for r in all_rows if r.status != "void")
    total_arrears = sum(float(r.arrears or 0) for r in all_rows if r.status != "void")

    q = base.order_by(FinanceOrder.id.desc())
    rows, total = paginate_query(q, page=page, page_size=page_size)
    items = [order_to_dict(db, r) for r in rows]
    return {
        "summary": {
            "order_amount": round(total_recv, 2),
            "received_amount": round(total_paid, 2),
            "arrears_amount": round(total_arrears, 2),
        },
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


def list_student_order_lines(
    db: Session,
    student_id: int,
    *,
    page: int = 1,
    page_size: int = 20,
    order_type: str | None = None,
    item_q: str | None = None,
) -> dict:
    """消费记录 · 订单明细：展开购买项目行。"""
    from app.models.finance import FinanceOrder
    from app.modules.finance.service import ORDER_TYPE_LABELS, _build_line_items

    student = get_student(db, student_id)
    if not student:
        return {"error": "学生不存在"}

    page = clamp_page(page)
    page_size = clamp_page_size(page_size)
    q = (
        db.query(FinanceOrder)
        .filter(FinanceOrder.student_id == student_id, FinanceOrder.status != "void")
        .order_by(FinanceOrder.id.desc())
    )
    if order_type:
        types = [t.strip() for t in order_type.split(",") if t.strip()]
        if len(types) == 1:
            q = q.filter(FinanceOrder.order_type == types[0])
        elif types:
            q = q.filter(FinanceOrder.order_type.in_(types))
    if item_q and item_q.strip():
        q = q.filter(FinanceOrder.item_summary.contains(item_q.strip()))

    orders = q.all()
    lines: list[dict] = []
    for order in orders:
        built = _build_line_items(db, order)
        if not built:
            lines.append(
                {
                    "order_id": order.id,
                    "order_no": order.order_no,
                    "order_type": order.order_type,
                    "order_type_label": ORDER_TYPE_LABELS.get(order.order_type, order.order_type),
                    "item_name": order.item_summary or "—",
                    "quantity_label": "—",
                    "unit_price": 0,
                    "receivable": float(order.receivable or 0),
                    "received": float(order.received or 0),
                    "status": order.status,
                    "created_at": order.created_at,
                }
            )
            continue
        for line in built:
            if item_q and item_q.strip():
                name = str(line.get("name") or "")
                if item_q.strip() not in name and item_q.strip() not in (order.item_summary or ""):
                    continue
            lines.append(
                {
                    "order_id": order.id,
                    "order_no": order.order_no,
                    "order_type": order.order_type,
                    "order_type_label": ORDER_TYPE_LABELS.get(order.order_type, order.order_type),
                    "item_name": line.get("name") or order.item_summary or "—",
                    "quantity_label": line.get("quantity_label") or "—",
                    "unit_price": float(line.get("unit_price") or 0),
                    "price_label": line.get("price_label") or "",
                    "receivable": float(line.get("receivable") or line.get("subtotal") or 0),
                    "received": float(line.get("subtotal") or 0),
                    "gift_qty": line.get("gift_qty") or "—",
                    "class_name": line.get("class_name") or "—",
                    "valid_until": line.get("valid_until") or "—",
                    "status": order.status,
                    "created_at": order.created_at,
                }
            )

    total = len(lines)
    start = (page - 1) * page_size
    page_items = lines[start : start + page_size]
    return {
        "items": page_items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }

def list_student_activity(db: Session, student_id: int, *, limit: int = 50) -> dict:
    """学员动态：报名/续费、学情、跟进人等时间线。"""
    from app.models.enrollment import EnrollmentRecord
    from app.models.finance import FinanceOrder

    student = get_student(db, student_id)
    if not student:
        return {"error": "学生不存在"}

    events: list[dict] = []

    # 报名/续费
    ens = (
        db.query(EnrollmentRecord)
        .filter(EnrollmentRecord.student_id == student_id)
        .order_by(EnrollmentRecord.id.desc())
        .limit(limit)
        .all()
    )
    for en in ens:
        kind_label = "报名" if en.kind == "enroll" else "续费"
        courses = _parse_json_list(getattr(en, "courses", None))
        names = "、".join(c.get("name") or "" for c in courses if c.get("name"))
        order_no = getattr(en, "order_no", None) or ""
        fo = None
        if en.id:
            fo = (
                db.query(FinanceOrder)
                .filter(FinanceOrder.enrollment_id == en.id)
                .first()
            )
        events.append(
            {
                "id": f"enroll-{en.id}",
                "kind": "enroll" if en.kind == "enroll" else "renew",
                "kind_label": "报名/续费",
                "title": f"报名/续费 · {kind_label}",
                "at": en.handled_at or en.created_at,
                "lines": [
                    f'购买项目 "{names}"' if names else "购买项目 —",
                    f"订单号:{order_no or (fo.order_no if fo else '—')}",
                ],
                "order_id": fo.id if fo else None,
                "order_no": order_no or (fo.order_no if fo else ""),
                "meta": {"enrollment_id": en.id, "amount": float(en.amount or 0)},
            }
        )

    # 学情
    learns = (
        db.query(LearningRecord)
        .filter(LearningRecord.student_id == student_id)
        .order_by(LearningRecord.class_date.desc())
        .limit(limit)
        .all()
    )
    for lr in learns:
        teacher = db.get(User, lr.teacher_id)
        tname = (teacher.display_name or teacher.username) if teacher else ""
        st_map = {
            "attended": "已上课",
            "absent": "缺勤",
            "late": "迟到",
            "leave": "请假",
            "makeup": "补课",
        }
        events.append(
            {
                "id": f"learn-{lr.id}",
                "kind": "learning",
                "kind_label": "学情记录",
                "title": "学情记录",
                "at": lr.class_date or lr.created_at,
                "lines": [
                    f"上课状态：{st_map.get(lr.class_status, lr.class_status)}"
                    + (f" · {lr.subject}" if lr.subject else ""),
                    f"填写人：{tname}" if tname else "",
                    (lr.learning_summary or "")[:80],
                ],
                "meta": {"learning_id": lr.id},
            }
        )

    # 建档 / 学管
    if student.created_at:
        creator = db.get(User, student.created_by) if student.created_by else None
        cname = (creator.display_name or creator.username) if creator else ""
        mgr = manager_name(db, student.academic_manager_id)
        events.append(
            {
                "id": f"create-{student.id}",
                "kind": "create",
                "kind_label": "建档",
                "title": "学员建档",
                "at": student.created_at,
                "lines": [
                    f"创建人：{cname}" if cname else "创建学员档案",
                    f"学管师：{mgr}" if mgr else "",
                ],
                "meta": {},
            }
        )
    if student.academic_manager_id:
        mgr = manager_name(db, student.academic_manager_id)
        events.append(
            {
                "id": f"manager-{student.id}-{student.academic_manager_id}",
                "kind": "manager",
                "kind_label": "跟进人变动",
                "title": "跟进人变动",
                "at": student.updated_at or student.created_at,
                "lines": [
                    f"变动后跟进人：{mgr}",
                    f"变动情况：【{mgr}】进行跟进" if mgr else "",
                ],
                "meta": {"manager_id": student.academic_manager_id},
            }
        )

    # 按时间倒序
    def _ts(e: dict):
        at = e.get("at")
        if at is None:
            return datetime.min
        if isinstance(at, datetime):
            return at.replace(tzinfo=None) if at.tzinfo else at
        return datetime.min

    events.sort(key=_ts, reverse=True)
    # 清理空行
    for e in events:
        e["lines"] = [x for x in (e.get("lines") or []) if x]

    return {"items": events[:limit], "total": len(events)}

def list_student_class_records(
    db: Session,
    student_id: int,
    *,
    view: str = "completed",
    start: str | None = None,
    end: str | None = None,
    class_id: int | None = None,
    course_id: int | None = None,
    teacher_id: int | None = None,
    attendance_status: str | None = None,
    record_status: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """学员维度的点名记录和待上课排课。"""
    from datetime import timedelta

    from app.models.academic import (
        ClassAttendance,
        ClassMember,
        ClassRecord,
        ClassRoom,
        ClassTeacher,
        Course,
        ScheduleLesson,
    )
    from app.modules.academic.service import (
        _parse_ids,
        _teacher_names,
        class_record_to_dict,
        schedule_to_dict,
    )

    student = get_student(db, student_id)
    if not student:
        return {"error": "学生不存在"}

    page = clamp_page(page)
    page_size = clamp_page_size(page_size)

    def parse_day(value: str | None, *, day_end: bool = False) -> datetime | None:
        if not value:
            return None
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
        except (TypeError, ValueError):
            try:
                parsed = datetime.strptime(value[:10], "%Y-%m-%d")
            except (TypeError, ValueError):
                return None
        if day_end and len(value) <= 10:
            parsed += timedelta(days=1)
        return parsed

    start_at = parse_day(start)
    end_at = parse_day(end, day_end=True)

    active_class_ids = {
        row[0]
        for row in db.query(ClassMember.class_id)
        .filter(ClassMember.student_id == student_id, ClassMember.status == "active")
        .all()
    }
    active_class_ids.update(
        row[0]
        for row in db.query(ClassRoom.id)
        .filter(ClassRoom.primary_student_id == student_id, ClassRoom.status == "active")
        .all()
    )
    historical_class_ids = {
        row[0]
        for row in db.query(ClassRecord.class_id)
        .join(ClassAttendance, ClassAttendance.record_id == ClassRecord.id)
        .filter(ClassAttendance.student_id == student_id)
        .distinct()
        .all()
    }
    all_class_ids = active_class_ids | historical_class_ids
    class_rows = (
        db.query(ClassRoom)
        .filter(ClassRoom.id.in_(all_class_ids))
        .order_by(ClassRoom.name.asc())
        .all()
        if all_class_ids
        else []
    )
    all_course_ids = {row.course_id for row in class_rows if row.course_id}
    course_rows = (
        db.query(Course).filter(Course.id.in_(all_course_ids)).order_by(Course.name.asc()).all()
        if all_course_ids
        else []
    )
    teacher_option_ids = (
        {
            row[0]
            for row in db.query(ClassTeacher.teacher_id)
            .filter(ClassTeacher.class_id.in_(all_class_ids))
            .all()
        }
        if all_class_ids
        else set()
    )

    def row_teacher_ids(raw: str | None, row_class_id: int) -> list[int]:
        ids = _parse_ids(raw)
        if ids:
            return ids
        return [
            item[0]
            for item in db.query(ClassTeacher.teacher_id)
            .filter(ClassTeacher.class_id == row_class_id)
            .all()
        ]

    items: list[dict] = []
    summary = {"present": 0, "late": 0, "leave": 0, "absent": 0}
    attendance_labels = {
        "present": "到课",
        "late": "迟到",
        "leave": "请假",
        "absent": "缺勤",
    }

    if view == "pending":
        if active_class_ids:
            query = db.query(ScheduleLesson).filter(
                ScheduleLesson.class_id.in_(active_class_ids),
                ScheduleLesson.status == "scheduled",
            )
            if start_at:
                query = query.filter(ScheduleLesson.start_at >= start_at)
            if end_at:
                query = query.filter(ScheduleLesson.start_at < end_at)
            if class_id:
                query = query.filter(ScheduleLesson.class_id == class_id)
            if course_id:
                query = query.filter(ScheduleLesson.course_id == course_id)
            rows = query.order_by(ScheduleLesson.start_at.asc(), ScheduleLesson.id.asc()).all()
        else:
            rows = []
        for row in rows:
            ids = row_teacher_ids(row.teacher_ids, row.class_id)
            teacher_option_ids.update(ids)
            if teacher_id and teacher_id not in ids:
                continue
            data = schedule_to_dict(db, row)
            items.append(
                {
                    "id": row.id,
                    "row_type": "pending",
                    "schedule_id": row.id,
                    "roll_at": None,
                    "class_id": row.class_id,
                    "class_name": data.get("class_name") or "",
                    "course_id": data.get("course_id"),
                    "course_name": data.get("course_name") or "",
                    "class_start": row.start_at,
                    "class_end": row.end_at,
                    "teachers": data.get("teachers") or "",
                    "teacher_ids": ids,
                    "attendance_status": "pending",
                    "attendance_status_label": "待上课",
                    "makeup_status_label": "—",
                    "consumption_type": "—",
                    "hours_consumed": 0,
                    "amount": 0,
                    "content": row.remark or "",
                    "notes": row.room or "",
                    "record_status": row.status,
                    "record_status_label": "待上课",
                }
            )
    else:
        query = (
            db.query(ClassRecord, ClassAttendance)
            .join(ClassAttendance, ClassAttendance.record_id == ClassRecord.id)
            .filter(ClassAttendance.student_id == student_id)
        )
        when = func.coalesce(ClassRecord.class_start, ClassRecord.roll_at)
        if start_at:
            query = query.filter(when >= start_at)
        if end_at:
            query = query.filter(when < end_at)
        if class_id:
            query = query.filter(ClassRecord.class_id == class_id)
        if course_id:
            query = query.filter(ClassRecord.course_id == course_id)
        if attendance_status:
            query = query.filter(ClassAttendance.status == attendance_status)
        if record_status:
            query = query.filter(ClassRecord.status == record_status)
        rows = query.order_by(when.desc(), ClassRecord.id.desc()).all()
        for record, attendance in rows:
            ids = row_teacher_ids(record.teacher_ids, record.class_id)
            teacher_option_ids.update(ids)
            if teacher_id and teacher_id not in ids:
                continue
            summary[attendance.status] = summary.get(attendance.status, 0) + 1
            data = class_record_to_dict(db, record)
            data.update(
                {
                    "row_type": "completed",
                    "attendance_status": attendance.status,
                    "attendance_status_label": attendance_labels.get(
                        attendance.status, attendance.status
                    ),
                    "makeup_status_label": (
                        "待补课" if attendance.status in {"absent", "leave"} else "无需补课"
                    ),
                    "consumption_type": "课时",
                    "hours_consumed": float(attendance.hours_consumed or 0),
                    "amount": float(attendance.amount or 0),
                    "notes": data.get("room") or "",
                    "record_status": record.status,
                    "record_status_label": "正常" if record.status == "normal" else "已撤销",
                }
            )
            items.append(data)

    total = len(items)
    offset = (page - 1) * page_size
    return {
        "items": items[offset : offset + page_size],
        "total": total,
        "page": page,
        "page_size": page_size,
        "summary": summary,
        "filters": {
            "classes": [{"id": row.id, "name": row.name} for row in class_rows],
            "courses": [{"id": row.id, "name": row.name} for row in course_rows],
            "teachers": [
                {"id": value, "name": _teacher_names(db, [value]) or f"老师#{value}"}
                for value in sorted(teacher_option_ids)
            ],
        },
    }
