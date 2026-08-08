"""可重复执行的开发环境演示数据。

生产环境不会调用这里的函数。开发环境启动时，``seed_demo_business`` 会在已有
数据的基础上把每个业务列表补到至少五条，并为这些记录补上必要的关联数据。
所有新增记录都使用“演示”前缀，函数本身只新增不足的数量，不清理或覆盖用户已有数据。
"""

from __future__ import annotations

import base64
import json
import uuid
from datetime import timedelta
from typing import Iterable

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.storage import LocalStorage
from app.core.timeutil import now as _now
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
from app.models.content import GeneratedCopy
from app.models.enrollment import EnrollmentRecord
from app.models.finance import (
    CourseConsumption,
    FinanceOrder,
    FinanceTransaction,
    OrderOperationLog,
    RechargeRecord,
    StudentAccount,
)
from app.models.knowledge import KnowledgeEntry
from app.models.lead import Lead, LeadActivity, LeadCollaborator
from app.models.material import Material, MaterialFile
from app.models.poster import GeneratedPoster
from app.models.student import LearningRecord, LearningRecordFile, Student
from app.models.template import CopyTemplate, PosterTemplate
from app.models.todo import TodoItem
from app.models.user import User


MIN_DEMO_ROWS = 5

# A small valid PNG used for material/learning/poster previews.  The seed also
# creates a larger colourful variant with Pillow when available; this fallback
# keeps seeding usable in minimal test environments.
_FALLBACK_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk"
    "+AAAAAYAAjCB0C8AAAAASUVORK5CYII="
)


def _need(db: Session, model: type, minimum: int = MIN_DEMO_ROWS) -> int:
    return max(0, minimum - int(db.query(model).count()))


def _unique_users(users: Iterable[User | None]) -> list[User]:
    result: list[User] = []
    seen: set[int] = set()
    for user in users:
        if user is None or user.id in seen:
            continue
        seen.add(user.id)
        result.append(user)
    return result


def _active_user(db: Session, role: str, username: str | None = None) -> User | None:
    query = db.query(User).filter(
        User.role == role,
        User.is_active.is_(True),
        User.deleted_at.is_(None),
    )
    if username:
        preferred = query.filter(User.username == username).first()
        if preferred:
            return preferred
    return query.order_by(User.id.asc()).first()


def _demo_image(index: int = 0) -> bytes:
    """Return a deterministic, valid preview image without network calls."""
    try:
        from io import BytesIO

        from PIL import Image, ImageDraw

        palette = (
            (23, 107, 77),
            (36, 99, 235),
            (124, 58, 237),
            (219, 112, 38),
            (13, 148, 136),
        )
        bg = palette[index % len(palette)]
        image = Image.new("RGB", (900, 1200), bg)
        draw = ImageDraw.Draw(image)
        # Geometric shapes are intentionally language-neutral so the fallback
        # font does not fail on machines without a Chinese font installed.
        draw.rounded_rectangle((55, 55, 845, 1145), radius=38, outline=(255, 255, 255), width=5)
        draw.rectangle((95, 220, 805, 245), fill=(255, 255, 255))
        draw.rectangle((95, 285, 625, 310), fill=(225, 245, 238))
        draw.ellipse((610, 430, 780, 600), fill=(255, 255, 255), outline=(225, 245, 238), width=8)
        draw.polygon(((145, 860), (350, 600), (565, 860)), fill=(225, 245, 238))
        draw.polygon(((405, 860), (575, 675), (770, 860)), fill=(190, 225, 214))
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        return buffer.getvalue()
    except Exception:  # pragma: no cover - Pillow is a runtime dependency, fallback is defensive
        return _FALLBACK_PNG


def _save_asset(relative_path: str, index: int = 0) -> None:
    """Save a local preview without ever writing to a configured OSS bucket."""
    try:
        storage = LocalStorage(get_settings().storage_root)
        if not storage.exists(relative_path):
            storage.save(relative_path, _demo_image(index))
    except Exception:
        # A database seed should not make login fail just because a local
        # preview directory is read-only.  The row still remains useful for
        # list/detail testing; the API will report a missing file if opened.
        return


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False)


def _course_snapshot(course: Course, hours: float) -> dict:
    type_label = "一对一" if course.course_type == "one_to_one" else "一对多"
    unit_price = float(course.unit_price or 0)
    return {
        "id": course.id,
        "name": course.name,
        "type": type_label,
        "price_label": f"单价({unit_price:g}元/课时)",
        "price_standard": f"单价({unit_price:g}元/课时)",
        "hours": float(hours),
        "unit_price": unit_price,
        "gift_hours": 0.0,
        "discount_type": "reduce",
        "discount_value": 0.0,
        "discount": 0.0,
        "subtotal": round(unit_price * hours, 2),
    }


def _ensure_templates(db: Session, creator: User | None) -> tuple[list[CopyTemplate], list[PosterTemplate]]:
    """补齐模板列表，保留系统模板和用户自建模板。"""
    copy_rows = db.query(CopyTemplate).order_by(CopyTemplate.id.asc()).all()
    for i in range(_need(db, CopyTemplate)):
        n = len(copy_rows) + i + 1
        db.add(
            CopyTemplate(
                name=f"演示-小红书话术模板{n}",
                scene="xhs_script",
                body=(
                    "【{{title}}】\n"
                    "家长常见痛点：{{pain_point}}\n"
                    "老师处理建议：{{teacher_action}}\n"
                    "咨询下一步：{{next_step}}"
                ),
                is_system=False,
                is_active=True,
                created_by=creator.id if creator else None,
            )
        )

    poster_rows = db.query(PosterTemplate).order_by(PosterTemplate.id.asc()).all()
    for i in range(_need(db, PosterTemplate)):
        n = len(poster_rows) + i + 1
        layout = dict(
            width=900,
            height=1200,
            background=("#176b4d", "#2463eb", "#7c3aed", "#db7026", "#0d9488")[i % 5],
            fields=[
                {"key": "title", "x": 70, "y": 90, "font_size": 52, "fill": "#ffffff"},
                {"key": "subtitle", "x": 70, "y": 180, "font_size": 30, "fill": "#e8f2ed"},
                {"key": "footer", "x": 70, "y": 1080, "font_size": 26, "fill": "#ffffff"},
            ],
        )
        db.add(
            PosterTemplate(
                name=f"演示-竖版海报模板{n}",
                scene="xhs_poster",
                layout_json=_json(layout),
                preview_path=None,
                is_system=False,
                is_active=True,
            )
        )
    db.flush()
    return (
        db.query(CopyTemplate).order_by(CopyTemplate.id.asc()).all(),
        db.query(PosterTemplate).order_by(PosterTemplate.id.asc()).all(),
    )


def _ensure_materials(
    db: Session,
    *,
    uploader: User | None,
) -> list[Material]:
    if uploader is not None:
        rows = db.query(Material).order_by(Material.id.asc()).all()
        for i in range(_need(db, Material)):
            n = len(rows) + i + 1
            db.add(
                Material(
                    uploader_id=uploader.id,
                    title=f"演示教学素材-{n}",
                    grade=("三年级", "四年级", "初一", "初二", "高一")[i % 5],
                    subject=("数学", "英语", "语文", "物理", "化学")[i % 5],
                    pain_point=("基础薄弱", "审题速度慢", "表达不完整", "公式易混淆", "学习计划不稳定")[i % 5],
                    teacher_action=("拆解例题并逐步演示", "用错题复盘强化方法", "先口头表达再落笔", "结合图示讲清概念", "制定一周练习清单")[i % 5],
                    next_step=("预约一次试听", "上传一份错题", "安排家长回访", "完成课后练习", "确认下次上课时间")[i % 5],
                    auth_status="authorized" if i % 3 else "pending",
                    status="new" if i % 2 == 0 else "usable",
                )
            )
        db.flush()

    rows = db.query(Material).order_by(Material.id.asc()).all()
    # Every demo material gets at least one real local preview; if existing
    # data has fewer than five files, add files to existing materials first.
    file_count = int(db.query(MaterialFile).count())
    for i, material in enumerate(rows):
        if file_count >= MIN_DEMO_ROWS:
            break
        has_file = db.query(MaterialFile.id).filter(MaterialFile.material_id == material.id).first()
        if has_file:
            continue
        rel = f"materials/{material.id}/demo-preview-{i + 1}.png"
        _save_asset(rel, i)
        db.add(
            MaterialFile(
                material_id=material.id,
                file_path=rel,
                file_type="image/png",
                sort_order=0,
            )
        )
        file_count += 1
    # A database may have fewer than five materials but one material can hold
    # multiple files; keep the child table at the same minimum as the parent.
    i = 0
    while file_count < MIN_DEMO_ROWS and rows:
        material = rows[i % len(rows)]
        rel = f"materials/{material.id}/demo-preview-extra-{file_count + 1}.png"
        _save_asset(rel, file_count)
        db.add(
            MaterialFile(
                material_id=material.id,
                file_path=rel,
                file_type="image/png",
                sort_order=file_count,
            )
        )
        file_count += 1
        i += 1
    db.flush()
    return rows


def _ensure_generated_content(
    db: Session,
    *,
    materials: list[Material],
    copy_templates: list[CopyTemplate],
    poster_templates: list[PosterTemplate],
    creator: User | None,
) -> None:
    if materials and copy_templates:
        current = db.query(GeneratedCopy).count()
        for i in range(max(0, MIN_DEMO_ROWS - current)):
            n = current + i + 1
            material = materials[i % len(materials)]
            template = copy_templates[i % len(copy_templates)]
            db.add(
                GeneratedCopy(
                    material_id=material.id,
                    template_id=template.id,
                    mode=("template", "template_then_llm", "template", "llm", "template")[i % 5],
                    platform="xhs",
                    title=f"演示文案-{n}｜{material.title}",
                    body=(
                        f"围绕{material.pain_point or '学习目标'}，{material.teacher_action or '给出清晰的练习建议'}。"
                        f"下一步：{material.next_step or '预约试听'}。"
                    ),
                    prompt_snapshot="演示数据：请生成一段家长易读的课程介绍",
                    model_name="demo-local" if i % 2 else None,
                    created_by=creator.id if creator else None,
                )
            )

    if materials and poster_templates:
        current = db.query(GeneratedPoster).count()
        for i in range(max(0, MIN_DEMO_ROWS - current)):
            n = current + i + 1
            material = materials[i % len(materials)]
            template = poster_templates[i % len(poster_templates)]
            rel = f"posters/demo-{uuid.uuid5(uuid.NAMESPACE_URL, f'one-class-poster-{n}').hex}.png"
            _save_asset(rel, i)
            db.add(
                GeneratedPoster(
                    material_id=material.id,
                    template_id=template.id,
                    mode="layout",
                    title=f"演示海报-{n}｜{material.title}",
                    payload_json=_json(
                        {
                            "title": f"学习力提升计划 {n}",
                            "subtitle": material.subject or "精品课程",
                            "footer": "嘉壹启航 · 预约试听",
                        }
                    ),
                    file_path=rel,
                    created_by=creator.id if creator else None,
                )
            )
    db.flush()


def _ensure_lead_support(db: Session, *, admin: User | None, operator: User | None) -> None:
    leads = db.query(Lead).order_by(Lead.id.asc()).all()
    if not leads:
        return

    # Assign otherwise-unowned demo rows so CR/运营 workbenches can exercise
    # ownership filters.  Existing explicit assignments are left untouched.
    owners = _unique_users((admin, operator))
    for i, lead in enumerate(leads):
        if lead.owner_id is None and owners:
            lead.owner_id = owners[i % len(owners)].id

    current = db.query(LeadActivity).count()
    for i, lead in enumerate(leads):
        if current >= MIN_DEMO_ROWS:
            break
        actor = owners[i % len(owners)] if owners else None
        db.add(
            LeadActivity(
                lead_id=lead.id,
                actor_id=actor.id if actor else None,
                kind="follow",
                title="演示跟进记录",
                content="已完成首次沟通，家长希望了解课程安排。",
                contact_method=("phone", "wechat", "visit", "sms", "other")[i % 5],
                meta_json=_json({"demo": True, "next": "安排试听"}),
            )
        )
        current += 1

    current = db.query(LeadCollaborator).count()
    candidates = _unique_users((operator, admin))
    existing_pairs = {
        (int(row.lead_id), int(row.user_id))
        for row in db.query(LeadCollaborator.lead_id, LeadCollaborator.user_id).all()
    }
    for lead in leads:
        for user in candidates:
            if current >= MIN_DEMO_ROWS:
                break
            pair = (lead.id, user.id)
            if lead.owner_id == user.id or pair in existing_pairs:
                continue
            db.add(
                LeadCollaborator(
                    lead_id=lead.id,
                    user_id=user.id,
                    role="collaborator",
                    note="演示协作跟进",
                    joined_by=admin.id if admin else user.id,
                )
            )
            existing_pairs.add(pair)
            current += 1
        if current >= MIN_DEMO_ROWS:
            break
    db.flush()


def _parse_links(raw: str | None) -> list[dict]:
    try:
        value = json.loads(raw or "[]")
    except (TypeError, ValueError, json.JSONDecodeError):
        return []
    return value if isinstance(value, list) else []


def _ensure_student_packages(
    db: Session,
    *,
    students: list[Student],
    courses: list[Course],
) -> list[StudentCoursePackage]:
    if not students or not courses:
        return []

    # Give a handful of existing demo students a course snapshot when they
    # were created by the older seed.  This makes enrollment/class pickers
    # useful without changing non-empty user data.
    for i, student in enumerate(students[: min(10, len(students))]):
        links = _parse_links(getattr(student, "linked_courses", None))
        if links:
            continue
        course = courses[i % len(courses)]
        student.linked_courses = _json([_course_snapshot(course, 10)])

    packages = db.query(StudentCoursePackage).order_by(StudentCoursePackage.id.asc()).all()
    pairs = {(int(p.student_id), int(p.course_id)) for p in packages}
    # Five distinct pairs are enough to make the five demo classes usable.
    i = 0
    while len(packages) < MIN_DEMO_ROWS:
        student = students[i % len(students)]
        course = courses[i % len(courses)]
        pair = (student.id, course.id)
        i += 1
        if pair in pairs:
            if i > len(students) * len(courses) * 2:
                break
            continue
        purchased = 10.0 + float(i % 3)
        gift = 1.0 if i % 4 == 0 else 0.0
        db.add(
            StudentCoursePackage(
                student_id=student.id,
                course_id=course.id,
                enrollment_id=None,
                purchased_hours=purchased,
                gift_hours=gift,
                total_hours=purchased + gift,
                remain_hours=purchased + gift,
                unit_price=float(course.unit_price or 0),
                valid_until=None,
                status="active",
            )
        )
        pairs.add(pair)
        # Keep the profile snapshot in sync for newly linked students.
        links = _parse_links(getattr(student, "linked_courses", None))
        if not any(int(link.get("id", -1)) == course.id for link in links if isinstance(link, dict)):
            links.append(_course_snapshot(course, purchased))
            student.linked_courses = _json(links)
        packages.append(
            StudentCoursePackage(
                student_id=student.id,
                course_id=course.id,
                remain_hours=purchased + gift,
                status="active",
            )
        )
    db.flush()
    return db.query(StudentCoursePackage).order_by(StudentCoursePackage.id.asc()).all()


def _package_for(
    db: Session,
    *,
    student_id: int,
    course_id: int,
) -> StudentCoursePackage | None:
    return (
        db.query(StudentCoursePackage)
        .filter(
            StudentCoursePackage.student_id == student_id,
            StudentCoursePackage.course_id == course_id,
            StudentCoursePackage.status == "active",
        )
        .order_by(StudentCoursePackage.id.asc())
        .first()
    )


def _ensure_academic(
    db: Session,
    *,
    students: list[Student],
    courses: list[Course],
    packages: list[StudentCoursePackage],
    teachers: list[User],
    creator: User | None,
) -> tuple[list[ClassRoom], list[ScheduleLesson], list[ClassRecord]]:
    if not courses or not students:
        return [], [], []

    package_pairs = {(int(p.student_id), int(p.course_id)) for p in packages}
    class_rows = db.query(ClassRoom).order_by(ClassRoom.id.asc()).all()
    for i in range(_need(db, ClassRoom)):
        n = len(class_rows) + i + 1
        course = courses[i % len(courses)]
        eligible = [s for s in students if (s.id, course.id) in package_pairs]
        primary = eligible[0] if eligible else students[i % len(students)]
        mode = "one_to_one" if course.course_type == "one_to_one" else "group"
        db.add(
            ClassRoom(
                name=f"演示{course.name}第{n}班",
                mode=mode,
                course_id=course.id,
                capacity=1 if mode == "one_to_one" else 12,
                over_capacity=True,
                open_count=2 if mode == "group" else 1,
                online_select=False,
                category="演示班级",
                hours_per_session=1.0,
                default_room=("101", "202", "301", "302", "新城203教室")[i % 5],
                primary_student_id=primary.id if mode == "one_to_one" else None,
                status="active",
                remark="用于本地联调的演示班级",
                created_by=creator.id if creator else None,
            )
        )
    db.flush()
    class_rows = db.query(ClassRoom).order_by(ClassRoom.id.asc()).all()

    teacher_ids = [u.id for u in teachers]
    if teacher_ids:
        existing_teacher_pairs = {
            (int(row.class_id), int(row.teacher_id))
            for row in db.query(ClassTeacher.class_id, ClassTeacher.teacher_id).all()
        }
        for i, classroom in enumerate(class_rows):
            class_has_teacher = any(cid == classroom.id for cid, _ in existing_teacher_pairs)
            if not class_has_teacher:
                tid = teacher_ids[i % len(teacher_ids)]
                db.add(ClassTeacher(class_id=classroom.id, teacher_id=tid, is_head=True))
                existing_teacher_pairs.add((classroom.id, tid))
        current = db.query(ClassTeacher).count()
        i = 0
        while current < MIN_DEMO_ROWS and class_rows:
            classroom = class_rows[i % len(class_rows)]
            tid = teacher_ids[(i + 1) % len(teacher_ids)]
            pair = (classroom.id, tid)
            i += 1
            if pair in existing_teacher_pairs:
                if i > len(class_rows) * len(teacher_ids) * 2:
                    break
                continue
            db.add(ClassTeacher(class_id=classroom.id, teacher_id=tid, is_head=False))
            existing_teacher_pairs.add(pair)
            current += 1

    # Build active class members from students who have a matching package.
    package_pairs = {(int(p.student_id), int(p.course_id)) for p in packages}
    existing_member_pairs = {
        (int(row.class_id), int(row.student_id))
        for row in db.query(ClassMember.class_id, ClassMember.student_id).all()
    }
    for classroom in class_rows:
        active_members = [
            row
            for row in db.query(ClassMember).filter(
                ClassMember.class_id == classroom.id,
                ClassMember.status == "active",
            )
        ]
        if active_members or not classroom.course_id:
            continue
        eligible = [s for s in students if (s.id, classroom.course_id) in package_pairs]
        if not eligible:
            continue
        limit = 1 if classroom.mode == "one_to_one" else min(3, len(eligible))
        for student in eligible[:limit]:
            pair = (classroom.id, student.id)
            if pair in existing_member_pairs:
                continue
            package = _package_for(db, student_id=student.id, course_id=classroom.course_id)
            db.add(
                ClassMember(
                    class_id=classroom.id,
                    student_id=student.id,
                    remain_hours=float(package.remain_hours if package else 0),
                    status="active",
                )
            )
            existing_member_pairs.add(pair)
            if classroom.mode == "one_to_one":
                classroom.primary_student_id = student.id
                break

    # If the table is still short, attach additional eligible students to a
    # group class without disturbing existing memberships.
    current_members = db.query(ClassMember).count()
    if current_members < MIN_DEMO_ROWS:
        for classroom in class_rows:
            if classroom.mode != "group" or not classroom.course_id:
                continue
            for student in students:
                if current_members >= MIN_DEMO_ROWS:
                    break
                if (student.id, classroom.course_id) not in package_pairs:
                    continue
                pair = (classroom.id, student.id)
                if pair in existing_member_pairs:
                    continue
                package = _package_for(db, student_id=student.id, course_id=classroom.course_id)
                db.add(
                    ClassMember(
                        class_id=classroom.id,
                        student_id=student.id,
                        remain_hours=float(package.remain_hours if package else 0),
                        status="active",
                    )
                )
                existing_member_pairs.add(pair)
                current_members += 1
            if current_members >= MIN_DEMO_ROWS:
                break
    db.flush()

    # At least five schedule rows, with two today so the dashboard has an
    # immediately useful workbench in a fresh database.
    schedules = db.query(ScheduleLesson).order_by(ScheduleLesson.id.asc()).all()
    current = len(schedules)
    usable_classes = [c for c in class_rows if c.course_id]
    for i in range(max(0, MIN_DEMO_ROWS - current)):
        n = current + i + 1
        classroom = usable_classes[i % len(usable_classes)] if usable_classes else None
        if not classroom:
            break
        day_offset = (i % 5) - 1  # yesterday, today, today, tomorrow, +3
        start = _now().replace(hour=9 + (i % 4) * 2, minute=0, second=0, microsecond=0) + timedelta(days=day_offset)
        end = start + timedelta(hours=float(classroom.hours_per_session or 1))
        class_teacher_rows = db.query(ClassTeacher.teacher_id).filter(ClassTeacher.class_id == classroom.id).all()
        ids = [int(row[0]) for row in class_teacher_rows] or teacher_ids[:1]
        db.add(
            ScheduleLesson(
                class_id=classroom.id,
                course_id=classroom.course_id,
                start_at=start,
                end_at=end,
                room=classroom.default_room or f"{101 + i}",
                status="completed" if day_offset < 0 else "scheduled",
                teacher_ids=_json(ids),
                remark="演示排课：可直接进入点名流程",
                created_by=creator.id if creator else None,
            )
        )
    db.flush()
    schedules = db.query(ScheduleLesson).order_by(ScheduleLesson.id.asc()).all()

    # Add class records for schedules that do not already have a non-void
    # record.  Existing records are never replaced.
    records = db.query(ClassRecord).order_by(ClassRecord.id.asc()).all()
    record_count = len(records)
    for i, schedule in enumerate(schedules):
        if record_count >= MIN_DEMO_ROWS:
            break
        if (
            db.query(ClassRecord.id)
            .filter(ClassRecord.schedule_id == schedule.id, ClassRecord.status != "void")
            .first()
        ):
            continue
        classroom = db.get(ClassRoom, schedule.class_id)
        course = db.get(Course, schedule.course_id) if schedule.course_id else None
        member_rows = (
            db.query(ClassMember)
            .filter(ClassMember.class_id == schedule.class_id, ClassMember.status == "active")
            .order_by(ClassMember.id.asc())
            .all()
        )
        teacher_rows = db.query(ClassTeacher.teacher_id).filter(ClassTeacher.class_id == schedule.class_id).all()
        ids = [int(row[0]) for row in teacher_rows] or teacher_ids[:1]
        hours = float(classroom.hours_per_session if classroom else 1.0)
        amount = float(course.unit_price or 0) * hours * max(1, len(member_rows)) if course else 0.0
        record = ClassRecord(
            class_id=schedule.class_id,
            schedule_id=schedule.id,
            course_id=schedule.course_id,
            roll_at=schedule.start_at,
            class_start=schedule.start_at,
            class_end=schedule.end_at,
            teacher_ids=_json(ids),
            hours=hours,
            salary_hours=hours,
            status="normal",
            content=f"演示课堂：{course.name if course else '常规辅导'}",
            amount=amount,
            present_count=0,
            total_count=len(member_rows),
            created_by=creator.id if creator else None,
        )
        db.add(record)
        db.flush()
        present = 0
        total_amount = 0.0
        for j, member in enumerate(member_rows):
            status = ("present", "late", "leave", "absent")[j % 4]
            consumed = hours if status in {"present", "late"} else 0.0
            row_amount = float(course.unit_price or 0) * consumed if course else 0.0
            db.add(
                ClassAttendance(
                    record_id=record.id,
                    student_id=member.student_id,
                    status=status,
                    hours_consumed=consumed,
                    amount=row_amount,
                )
            )
            if consumed > 0:
                present += 1
                total_amount += row_amount
        record.present_count = present
        record.amount = total_amount
        db.add(
            ClassRecordOperationLog(
                record_id=record.id,
                action="create",
                action_label="创建点名记录",
                detail="演示数据自动生成",
                operator_id=creator.id if creator else None,
            )
        )
        record_count += 1
    db.flush()

    # Child attendance/log tables may be empty in a legacy database even when
    # the parent already has enough rows.  Fill only the missing minimum.
    attendance_count = db.query(ClassAttendance).count()
    if attendance_count < MIN_DEMO_ROWS:
        for record in db.query(ClassRecord).order_by(ClassRecord.id.asc()).all():
            if attendance_count >= MIN_DEMO_ROWS:
                break
            classroom = db.get(ClassRoom, record.class_id)
            members = (
                db.query(ClassMember)
                .filter(ClassMember.class_id == record.class_id, ClassMember.status == "active")
                .all()
            )
            for member in members:
                if attendance_count >= MIN_DEMO_ROWS:
                    break
                exists = db.query(ClassAttendance.id).filter(
                    ClassAttendance.record_id == record.id,
                    ClassAttendance.student_id == member.student_id,
                ).first()
                if exists:
                    continue
                db.add(
                    ClassAttendance(
                        record_id=record.id,
                        student_id=member.student_id,
                        status="present",
                        hours_consumed=float(record.hours or 1),
                        amount=0.0,
                    )
                )
                attendance_count += 1

    log_count = db.query(ClassRecordOperationLog).count()
    if log_count < MIN_DEMO_ROWS:
        for record in db.query(ClassRecord).order_by(ClassRecord.id.asc()).all():
            if log_count >= MIN_DEMO_ROWS:
                break
            db.add(
                ClassRecordOperationLog(
                    record_id=record.id,
                    action="update",
                    action_label="演示记录备注",
                    detail="用于验证点名记录操作日志展示",
                    operator_id=creator.id if creator else None,
                )
            )
            log_count += 1
    db.flush()
    return class_rows, schedules, db.query(ClassRecord).order_by(ClassRecord.id.asc()).all()


def _unique_order_no(db: Session, prefix: str = "DE") -> str:
    while True:
        value = f"{prefix}{_now().strftime('%Y%m%d')}{uuid.uuid4().hex[:8].upper()}"
        if not db.query(FinanceOrder.id).filter(FinanceOrder.order_no == value).first() and not db.query(
            EnrollmentRecord.id
        ).filter(EnrollmentRecord.order_no == value).first():
            return value


def _ensure_finance(
    db: Session,
    *,
    students: list[Student],
    courses: list[Course],
    creator: User | None,
    operator: User | None,
) -> None:
    if not students or not courses:
        return
    owner_id = creator.id if creator else None
    staff_id = operator.id if operator else owner_id

    enrollments = db.query(EnrollmentRecord).order_by(EnrollmentRecord.id.asc()).all()
    for i in range(max(0, MIN_DEMO_ROWS - len(enrollments))):
        n = len(enrollments) + i + 1
        student = students[i % len(students)]
        course = courses[(i + 1) % len(courses)]
        hours = float(6 + i)
        amount = round(float(course.unit_price or 0) * hours, 2)
        order_no = _unique_order_no(db, "DE")
        snapshot = _course_snapshot(course, hours)
        kind = "renew" if i % 3 == 2 else "enroll"
        handled = _now() - timedelta(days=i)
        row = EnrollmentRecord(
            student_id=student.id,
            kind=kind,
            handled_at=handled,
            amount=amount,
            order_no=order_no,
            pay_methods=_json(["微信"] if i % 2 else ["微信", "现金"]),
            pay_other="",
            courses=_json([snapshot]),
            attributions=_json(
                [{"user_id": owner_id, "display_name": creator.display_name if creator else "演示负责人", "amount": amount}]
                if owner_id
                else []
            ),
            internal_notes="演示报名记录：内部备注",
            external_notes="家长已确认试听时间",
            internal_images="[]",
            created_by=owner_id,
        )
        db.add(row)
        db.flush()
        received = amount if i % 3 != 1 else round(amount * 0.6, 2)
        status = "paid" if received >= amount else "partial"
        order = FinanceOrder(
            order_no=order_no,
            student_id=student.id,
            order_type=kind,
            item_summary=course.name,
            courses=_json([snapshot]),
            receivable=amount,
            received=received,
            arrears=max(0.0, amount - received),
            status=status,
            source="演示数据",
            performance_owner_id=owner_id,
            handler_id=staff_id,
            enrollment_id=row.id,
            pay_method="微信、现金" if i % 2 == 0 else "微信",
            handled_at=handled,
            paid_at=handled if received else None,
            created_by=owner_id,
        )
        db.add(order)
        db.flush()
        if received > 0:
            db.add(
                FinanceTransaction(
                    handled_at=handled,
                    item="报名/续费",
                    tx_type="income",
                    status="confirmed" if i % 2 == 0 else "pending",
                    amount=received,
                    pay_method="微信" if i % 2 else "现金",
                    account="演示账户",
                    handler_id=staff_id,
                    order_id=order.id,
                    student_id=student.id,
                    payer_name=student.name,
                    remark="演示收款记录",
                    created_by=owner_id,
                    confirmed_at=handled if i % 2 == 0 else None,
                    confirmed_by=owner_id if i % 2 == 0 else None,
                )
            )
        db.add(
            OrderOperationLog(
                order_id=order.id,
                action="create",
                action_label="创建订单",
                detail="演示数据自动生成",
                operator_id=staff_id,
                operator_name=creator.display_name if creator else "演示负责人",
            )
        )
        enrollments.append(row)

    # If an imported/legacy database already had five enrollments but fewer
    # finance rows, fill the independent lists without touching existing rows.
    orders = db.query(FinanceOrder).order_by(FinanceOrder.id.asc()).all()
    for i in range(max(0, MIN_DEMO_ROWS - len(orders))):
        student = students[(i + 3) % len(students)]
        course = courses[(i + 4) % len(courses)]
        amount = float(course.unit_price or 0) * 4
        order = FinanceOrder(
            order_no=_unique_order_no(db, "DM"),
            student_id=student.id,
            order_type="other",
            item_summary=f"演示杂项-{i + 1}",
            courses=_json([]),
            receivable=amount,
            received=amount,
            arrears=0,
            status="paid",
            source="演示数据",
            performance_owner_id=owner_id,
            handler_id=staff_id,
            pay_method="支付宝",
            handled_at=_now() - timedelta(days=i),
            paid_at=_now() - timedelta(days=i),
            created_by=owner_id,
        )
        db.add(order)
        db.flush()
        db.add(
            FinanceTransaction(
                handled_at=order.handled_at or _now(),
                item="其他收入",
                tx_type="income",
                status="confirmed",
                amount=amount,
                pay_method="支付宝",
                account="演示账户",
                handler_id=staff_id,
                order_id=order.id,
                student_id=student.id,
                payer_name=student.name,
                remark="演示手工订单",
                created_by=owner_id,
                confirmed_at=order.handled_at,
                confirmed_by=owner_id,
            )
        )
        db.add(
            OrderOperationLog(
                order_id=order.id,
                action="create",
                action_label="创建订单",
                detail="演示手工订单",
                operator_id=staff_id,
                operator_name=creator.display_name if creator else "演示负责人",
            )
        )
        orders.append(order)

    tx_count = db.query(FinanceTransaction).count()
    if tx_count < MIN_DEMO_ROWS and orders:
        for i in range(MIN_DEMO_ROWS - tx_count):
            order = orders[i % len(orders)]
            db.add(
                FinanceTransaction(
                    handled_at=_now() - timedelta(hours=i + 1),
                    item="账户充值" if i % 2 else "报名/续费",
                    tx_type="income" if i % 3 else "expense",
                    status="pending" if i % 2 else "confirmed",
                    amount=float(180 + i * 50),
                    pay_method=("微信", "支付宝", "现金")[i % 3],
                    account="演示账户",
                    handler_id=staff_id,
                    order_id=order.id,
                    student_id=students[i % len(students)].id,
                    payer_name=students[i % len(students)].name,
                    remark="演示收支流水",
                    created_by=owner_id,
                    confirmed_at=_now() if i % 2 == 0 else None,
                    confirmed_by=owner_id if i % 2 == 0 else None,
                )
            )
    log_count = db.query(OrderOperationLog).count()
    if log_count < MIN_DEMO_ROWS and orders:
        for i in range(MIN_DEMO_ROWS - log_count):
            order = orders[i % len(orders)]
            db.add(
                OrderOperationLog(
                    order_id=order.id,
                    action="view",
                    action_label="查看订单",
                    detail="演示订单详情浏览记录",
                    operator_id=staff_id,
                    operator_name=creator.display_name if creator else "演示负责人",
                )
            )
    db.flush()

    # 学员账户与充值页数据。
    account_rows = db.query(StudentAccount).order_by(StudentAccount.id.asc()).all()
    account_by_student = {int(row.student_id): row for row in account_rows}
    for i, student in enumerate(students[: min(10, len(students))]):
        if len(account_by_student) >= MIN_DEMO_ROWS and student.id not in account_by_student:
            continue
        if student.id in account_by_student:
            continue
        account = StudentAccount(student_id=student.id, balance=float(300 + i * 120))
        db.add(account)
        db.flush()
        account_by_student[student.id] = account
        if len(account_by_student) >= MIN_DEMO_ROWS:
            break

    recharge_count = db.query(RechargeRecord).count()
    account_students = list(account_by_student.values())
    for i in range(max(0, MIN_DEMO_ROWS - recharge_count)):
        if not account_students:
            break
        account = account_students[i % len(account_students)]
        amount = float(200 + i * 100)
        account.balance = float(account.balance or 0) + amount
        db.add(
            RechargeRecord(
                student_id=account.student_id,
                amount=amount,
                balance_after=account.balance,
                pay_method=("微信", "支付宝", "现金")[i % 3],
                handler_id=staff_id,
                order_id=None,
                status="success",
                remark="演示充值记录",
            )
        )


def _ensure_consumptions(db: Session, *, creator: User | None, students: list[Student]) -> None:
    current = db.query(CourseConsumption).count()
    if current >= MIN_DEMO_ROWS:
        return
    records = db.query(ClassRecord).order_by(ClassRecord.id.asc()).all()
    if not records:
        return
    teacher_id = creator.id if creator else None
    for i in range(MIN_DEMO_ROWS - current):
        record = records[i % len(records)]
        course = db.get(Course, record.course_id) if record.course_id else None
        classroom = db.get(ClassRoom, record.class_id)
        attendance = (
            db.query(ClassAttendance)
            .filter(ClassAttendance.record_id == record.id)
            .order_by(ClassAttendance.id.asc())
            .first()
        )
        student_id = attendance.student_id if attendance else students[i % len(students)].id
        hours = float(attendance.hours_consumed if attendance and attendance.hours_consumed else 1.0)
        amount = float(course.unit_price or 0) * hours if course else 0.0
        package = _package_for(db, student_id=student_id, course_id=course.id) if course else None
        allocations: list[dict] = []
        uncovered = hours
        if package and float(package.remain_hours or 0) > 0:
            allocated = min(float(package.remain_hours), hours)
            package.remain_hours = max(0.0, float(package.remain_hours) - allocated)
            allocations.append(
                {
                    "package_id": package.id,
                    "hours": allocated,
                    "amount": round(amount * allocated / hours, 2) if hours else 0.0,
                }
            )
            uncovered = max(0.0, hours - allocated)
        db.add(
            CourseConsumption(
                student_id=student_id,
                class_id=classroom.id if classroom else None,
                course_id=course.id if course else None,
                record_id=record.id,
                teacher_id=teacher_id,
                consume_type="课时课消",
                source="点名",
                hours=hours,
                amount=amount,
                package_allocations=_json(allocations),
                uncovered_hours=uncovered,
                consumed_at=record.class_start or _now(),
                status="normal",
                created_by=creator.id if creator else None,
            )
        )


def _ensure_learning(
    db: Session,
    *,
    students: list[Student],
    teacher: User | None,
) -> None:
    if not students or teacher is None:
        return
    records = db.query(LearningRecord).order_by(LearningRecord.id.asc()).all()
    for i in range(max(0, MIN_DEMO_ROWS - len(records))):
        student = students[i % len(students)]
        class_date = _now() - timedelta(days=i + 1)
        db.add(
            LearningRecord(
                student_id=student.id,
                teacher_id=teacher.id,
                class_date=class_date,
                class_status=("attended", "late", "leave", "makeup", "absent")[i % 5],
                subject=("数学", "英语", "语文", "物理", "化学")[i % 5],
                learning_summary=(
                    "完成基础题训练，能独立复述解题步骤。",
                    "口语表达积极，需继续积累高频词汇。",
                    "阅读主旨判断准确，细节题需要回看原文。",
                    "掌握核心公式，综合题仍需加强建模。",
                    "复习状态稳定，建议按错题本完成巩固。",
                )[i % 5],
                homework_note="完成课后练习并拍照反馈。",
                notes="演示学情记录",
            )
        )
    db.flush()
    records = db.query(LearningRecord).order_by(LearningRecord.id.asc()).all()
    file_count = db.query(LearningRecordFile).count()
    for i, record in enumerate(records):
        if file_count >= MIN_DEMO_ROWS:
            break
        if db.query(LearningRecordFile.id).filter(LearningRecordFile.record_id == record.id).first():
            continue
        rel = f"learning/{record.id}/demo-note-{i + 1}.png"
        _save_asset(rel, i + 1)
        db.add(
            LearningRecordFile(
                record_id=record.id,
                file_path=rel,
                file_type="image/png",
                sort_order=0,
            )
        )
        file_count += 1
    db.flush()


def _ensure_knowledge(db: Session, updater: User | None) -> None:
    current = db.query(KnowledgeEntry).count()
    samples = (
        ("script", "演示-首次回访", "您好，想跟您确认一下孩子最近的学习目标，方便聊两分钟吗？", "回访,开场"),
        ("script", "演示-试听提醒", "体验课会先做基础测评，再给出适合孩子的练习建议。", "试听,提醒"),
        ("objection", "演示-时间安排", "可以先从每周一节开始，根据孩子的时间再灵活调整。", "时间,异议"),
        ("objection", "演示-效果顾虑", "我们会用阶段目标和学习记录持续复盘，家长能看到具体变化。", "效果,异议"),
        ("banned", "演示-合规表达", "避免使用绝对化承诺，改为说明课程方法和可验证的阶段目标。", "合规"),
    )
    for i in range(max(0, MIN_DEMO_ROWS - current)):
        category, title, content, tags = samples[i % len(samples)]
        db.add(
            KnowledgeEntry(
                category=category,
                title=title,
                content=content,
                tags=tags,
                is_active=True,
                updated_by=updater.id if updater else None,
            )
        )
    db.flush()


def _ensure_todos(db: Session, users: list[User]) -> None:
    """为四类常用演示账号各补五条个人待办。"""
    for user in users:
        current = db.query(TodoItem).filter(TodoItem.user_id == user.id).count()
        for i in range(max(0, MIN_DEMO_ROWS - current)):
            done = (i % 5) == 3
            created = _now() - timedelta(hours=i + 1)
            db.add(
                TodoItem(
                    user_id=user.id,
                    title=("回访重点线索", "整理今日素材", "确认试听课表", "更新学习记录", "核对收款流水")[i % 5],
                    content="演示待办：用于验证工作台和个人待办列表。",
                    is_done=done,
                    created_at=created,
                    completed_at=created if done else None,
                )
            )
    db.flush()


def seed_demo_workspace(db: Session) -> None:
    """补齐所有开发环境业务列表及其关键关联数据。"""
    settings = get_settings()
    admin = _active_user(db, "admin", settings.seed_admin_username)
    operator = _active_user(db, "operator", settings.seed_ops_username)
    teacher = _active_user(db, "teacher", settings.seed_teacher_username)
    manager = _active_user(db, "cr") or _active_user(db, "academic_manager")
    creator = admin or operator or teacher or manager

    copy_templates, poster_templates = _ensure_templates(db, operator or admin)
    materials = _ensure_materials(db, uploader=teacher or operator or admin)
    _ensure_generated_content(
        db,
        materials=materials,
        copy_templates=copy_templates,
        poster_templates=poster_templates,
        creator=operator or admin,
    )
    _ensure_lead_support(db, admin=admin, operator=operator)

    courses = db.query(Course).filter(Course.enabled.is_(True)).order_by(Course.id.asc()).all()
    students = (
        db.query(Student)
        .filter(Student.status.in_(("active", "paused", "graduated")))
        .order_by(Student.id.asc())
        .all()
    )
    packages = _ensure_student_packages(db, students=students, courses=courses)
    teaching_users = _unique_users((admin, teacher, manager))
    _ensure_academic(
        db,
        students=students,
        courses=courses,
        packages=packages,
        teachers=teaching_users,
        creator=creator,
    )
    _ensure_consumptions(db, creator=creator, students=students)
    _ensure_finance(
        db,
        students=students,
        courses=courses,
        creator=admin or creator,
        operator=operator or creator,
    )
    _ensure_learning(db, students=students, teacher=teacher or creator)
    _ensure_knowledge(db, updater=operator or admin)
    _ensure_todos(db, users=_unique_users((admin, operator, teacher, manager)))
    db.commit()


__all__ = ["seed_demo_workspace"]
