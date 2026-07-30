from datetime import datetime, timezone

from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from app.core.storage import Storage
from app.models.student import LearningRecord, LearningRecordFile, Student
from app.models.user import User
from app.modules.students.schemas import CLASS_STATUSES, STUDENT_STATUSES


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def validate_student_status(status: str) -> str | None:
    if status not in STUDENT_STATUSES:
        return "无效的学生状态"
    return None


def validate_class_status(status: str) -> str | None:
    if status not in CLASS_STATUSES:
        return "无效的上课状态"
    return None


def resolve_manager(db: Session, manager_id: int | None) -> User | str | None:
    """学管师必须是 teacher 角色（可停用，便于转交前仍显示）。"""
    if manager_id is None:
        return None
    user = db.get(User, manager_id)
    if not user:
        return "学管师不存在"
    if user.role != "teacher":
        return "学管师须为老师角色账号"
    return user


def manager_name(db: Session, manager_id: int | None) -> str | None:
    if not manager_id:
        return None
    user = db.get(User, manager_id)
    return user.display_name if user else None


def latest_learning_at(db: Session, student_id: int) -> datetime | None:
    row = (
        db.query(func.max(LearningRecord.class_date))
        .filter(LearningRecord.student_id == student_id)
        .scalar()
    )
    return row


def student_to_dict(db: Session, s: Student) -> dict:
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
        "created_by": s.created_by,
        "created_at": s.created_at,
        "updated_at": s.updated_at,
        "latest_learning_at": latest_learning_at(db, s.id),
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
) -> list[Student]:
    query = db.query(Student)
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
    if academic_manager_id is not None:
        if academic_manager_id == 0:
            query = query.filter(Student.academic_manager_id.is_(None))
        else:
            query = query.filter(Student.academic_manager_id == academic_manager_id)
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
    return query.order_by(Student.id.desc()).all()


def get_student(db: Session, student_id: int) -> Student | None:
    return db.get(Student, student_id)


def create_student(db: Session, user: User, data: dict) -> Student | str:
    err = validate_student_status(data.get("status") or "active")
    if err:
        return err
    mgr = resolve_manager(db, data.get("academic_manager_id"))
    if isinstance(mgr, str):
        return mgr

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
        mgr = resolve_manager(db, data["academic_manager_id"])
        if isinstance(mgr, str):
            return mgr

    for key, value in data.items():
        if key in {"name", "grade", "school"} and value is not None:
            value = str(value).strip()
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
    """可选学管师列表（老师账号），附带名下学生数。"""
    query = db.query(User).filter(User.role == "teacher")
    if not include_inactive:
        query = query.filter(User.is_active.is_(True))
    teachers = query.order_by(User.id.asc()).all()

    counts = dict(
        db.query(Student.academic_manager_id, func.count(Student.id))
        .filter(Student.academic_manager_id.isnot(None))
        .group_by(Student.academic_manager_id)
        .all()
    )
    return [
        {
            "id": t.id,
            "display_name": t.display_name,
            "username": t.username,
            "is_active": t.is_active,
            "student_count": int(counts.get(t.id, 0)),
        }
        for t in teachers
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
) -> list[LearningRecord]:
    query = db.query(LearningRecord).options(joinedload(LearningRecord.files))
    if student_id is not None:
        query = query.filter(LearningRecord.student_id == student_id)
    if teacher_id is not None:
        query = query.filter(LearningRecord.teacher_id == teacher_id)
    return query.order_by(LearningRecord.class_date.desc(), LearningRecord.id.desc()).all()


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
    if user.role != "admin" and record.teacher_id != user.id:
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
    if user.role != "admin" and record.teacher_id != user.id:
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
    return user.role in {"admin", "teacher"}


def can_delete_student(user: User) -> bool:
    return user.role == "admin"


def can_reassign(user: User) -> bool:
    return user.role == "admin"
