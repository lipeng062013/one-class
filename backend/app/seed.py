import json
import random
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import hash_password
from app.core.timeutil import now as _utcnow
from app.models.knowledge import KnowledgeEntry
from app.models.lead import Lead
from app.models.student import Student
from app.models.template import CopyTemplate, PosterTemplate
from app.models.user import User

SYSTEM_COPY_BODY = (
    "【{{title}}】\n"
    "痛点：{{pain_point}}\n"
    "老师怎么做：{{teacher_action}}\n"
    "下一步：{{next_step}}"
)

SYSTEM_POSTER_LAYOUT = {
    "width": 750,
    "height": 1000,
    "background": "#176b4d",
    "fields": [
        {"key": "title", "x": 40, "y": 80, "font_size": 48, "fill": "#ffffff"},
        {"key": "subtitle", "x": 40, "y": 180, "font_size": 28, "fill": "#e8f2ed"},
        {"key": "footer", "x": 40, "y": 900, "font_size": 24, "fill": "#ffffff"},
    ],
}

SURNAMES = list("赵钱孙李周吴郑王冯陈褚卫蒋沈韩杨朱秦尤许何吕施张孔曹严华金魏陶姜")
GIVEN = [
    "浩然",
    "子轩",
    "雨桐",
    "思远",
    "一诺",
    "诗涵",
    "俊杰",
    "欣怡",
    "明轩",
    "可欣",
    "宇轩",
    "佳怡",
    "博文",
    "雨欣",
    "子墨",
    "梦琪",
    "昊然",
    "语嫣",
    "晨曦",
    "若曦",
]
GRADES = [
    "一年级",
    "二年级",
    "三年级",
    "四年级",
    "五年级",
    "六年级",
    "初一",
    "初二",
    "初三",
]
SCHOOLS = [
    "实验小学",
    "育才小学",
    "中心小学",
    "希望小学",
    "外国语小学",
    "第一中学",
    "第二中学",
    "实验中学",
    "明德中学",
    "博雅学校",
]
SOURCES = ["referral", "dianping", "wechat", "walkin", "other"]
LEAD_STATUSES = ["new", "contacted", "visited", "enrolled", "lost"]
NEEDS = ["数学提高", "英语口语", "语文阅读", "物理补弱", "试听咨询", "假期集训", "一对一"]

def seed_demo_users(db: Session) -> None:
    """Idempotent: create demo users if missing; do not overwrite existing passwords."""
    settings = get_settings()
    demos = [
        (settings.seed_admin_username, settings.seed_admin_password, "负责人", "admin"),
        (settings.seed_ops_username, settings.seed_ops_password, "运营", "operator"),
        # Keep the legacy demo login stable; new accounts should use CR.
        (settings.seed_teacher_username, settings.seed_teacher_password, "老师甲", "teacher"),
    ]
    for username, password, display_name, role in demos:
        exists = db.query(User).filter(User.username == username).first()
        if exists:
            continue
        db.add(
            User(
                username=username,
                password_hash=hash_password(password),
                display_name=display_name,
                role=role,
                is_active=True,
            )
        )
    db.commit()

def seed_extra_teachers(db: Session, count: int = 10) -> None:
    """Ensure at least `count` extra demo teachers (teacher2..).密码与用户名相同。"""
    created = 0
    for i in range(2, count + 2):
        username = f"teacher{i}"
        if db.query(User).filter(User.username == username).first():
            continue
        db.add(
            User(
                username=username,
                password_hash=hash_password(username),
                display_name=f"老师{SURNAMES[i % len(SURNAMES)]}{GIVEN[i % len(GIVEN)][:1]}",
                role="teacher",
                is_active=True,
            )
        )
        created += 1
    if created:
        db.commit()

def seed_extra_crs(db: Session, count: int = 10) -> None:
    """Ensure cr1..crN demo 学管师 accounts (role=cr)。密码与用户名相同。"""
    created = 0
    for i in range(1, count + 1):
        username = f"cr{i}"
        if db.query(User).filter(User.username == username).first():
            continue
        surname = SURNAMES[(i * 3) % len(SURNAMES)]
        given = GIVEN[(i * 5) % len(GIVEN)]
        db.add(
            User(
                username=username,
                password_hash=hash_password(username),
                display_name=f"学管{surname}{given}",
                role="cr",
                is_active=True,
            )
        )
        created += 1
    if created:
        db.commit()

def _active_crs(db: Session) -> list[User]:
    return (
        db.query(User)
        .filter(
            User.role.in_(["cr", "academic_manager"]),
            User.is_active.is_(True),
            User.deleted_at.is_(None),
        )
        .order_by(User.id.asc())
        .all()
    )

def reassign_students_to_crs(db: Session) -> int:
    """把仍挂在老师/空学管上的学员改派到 CR（学管师）账号。"""
    crs = _active_crs(db)
    if not crs:
        return 0
    students = db.query(Student).order_by(Student.id.asc()).all()
    changed = 0
    for i, s in enumerate(students):
        mgr = db.get(User, s.academic_manager_id) if s.academic_manager_id else None
        if (
            mgr
            and mgr.deleted_at is None
            and mgr.is_active
            and mgr.role in {"cr", "academic_manager"}
        ):
            continue
        s.academic_manager_id = crs[i % len(crs)].id
        changed += 1
    if changed:
        db.commit()
    return changed

def cleanup_junk_demo_students(db: Session) -> int:
    """清理明显脏数据学员名：无业务关联则删除，有关联则改成正常演示姓名。"""
    from sqlalchemy import text

    junk_names = {
        "A",
        "a",
        "111",
        "112",
        "123",
        "奥特曼",
        "第阿萨大大",
        "张三",
        "思维英语学生1",
        "小雨",
    }
    students = db.query(Student).order_by(Student.id.asc()).all()
    changed = 0
    rename_i = 0
    for s in students:
        name = (s.name or "").strip()
        bare = name.removeprefix("【待整理】").strip() if name.startswith("【待整理】") else name
        is_junk = (
            bare in junk_names
            or (bare.isdigit() and len(bare) <= 4)
            or len(bare) <= 1
            or name.startswith("【待整理】")
        )
        if not is_junk:
            continue
        linked = False
        for sql in (
            "SELECT 1 FROM enrollment_records WHERE student_id = :id LIMIT 1",
            "SELECT 1 FROM student_course_packages WHERE student_id = :id LIMIT 1",
            "SELECT 1 FROM course_consumptions WHERE student_id = :id LIMIT 1",
            "SELECT 1 FROM finance_orders WHERE student_id = :id LIMIT 1",
            "SELECT 1 FROM learning_records WHERE student_id = :id LIMIT 1",
            "SELECT 1 FROM class_members WHERE student_id = :id LIMIT 1",
        ):
            try:
                if db.execute(text(sql), {"id": s.id}).first():
                    linked = True
                    break
            except Exception:
                continue
        if linked:
            new_name = f"{SURNAMES[rename_i % len(SURNAMES)]}{GIVEN[rename_i % len(GIVEN)]}"
            rename_i += 1
            s.name = new_name
            if s.notes and "[脏数据已标记]" in s.notes:
                s.notes = s.notes.replace("[脏数据已标记]", "").strip()
            changed += 1
            continue
        try:
            db.query(Student).filter(Student.id == s.id).delete(synchronize_session=False)
            changed += 1
        except Exception:
            db.rollback()
            continue
    if changed:
        db.commit()
    return changed

def seed_system_templates(db: Session) -> None:
    has_system_copy = (
        db.query(CopyTemplate)
        .filter(CopyTemplate.is_system.is_(True), CopyTemplate.scene == "xhs_script")
        .first()
    )
    if not has_system_copy:
        db.add(
            CopyTemplate(
                name="系统-小红书脚本",
                scene="xhs_script",
                body=SYSTEM_COPY_BODY,
                is_system=True,
                is_active=True,
                created_by=None,
            )
        )

    has_system_poster = db.query(PosterTemplate).filter(PosterTemplate.is_system.is_(True)).first()
    if not has_system_poster:
        db.add(
            PosterTemplate(
                name="系统-竖版海报",
                scene="xhs_poster",
                layout_json=json.dumps(SYSTEM_POSTER_LAYOUT, ensure_ascii=False),
                preview_path=None,
                is_system=True,
                is_active=True,
            )
        )
    db.commit()

def seed_sample_knowledge(db: Session) -> None:
    # 清理已废弃分类（tone / course / faq 等）
    obsolete = {"tone", "course", "faq", "staff", "process"}
    for old in db.query(KnowledgeEntry).filter(KnowledgeEntry.category.in_(obsolete)).all():
        db.delete(old)

    samples = [
        (
            "script",
            "首次电话开场",
            "您好，我是嘉壹启航的学管老师，看到您关注了我们的课程，方便耽误您两分钟介绍一下适合孩子的方案吗？",
            "开场,电话",
        ),
        (
            "script",
            "试听邀约",
            "这周我们有一次体验课名额，可以让孩子先感受课堂氛围，您看周几晚上更方便？",
            "试听,邀约",
        ),
        (
            "objection",
            "价格贵",
            "理解您的顾虑。我们按课时计费、可灵活调课；先试听再决定，比盲目报班更省心。",
            "价格,异议",
        ),
        (
            "objection",
            "再考虑一下",
            "当然可以。我帮您把试听时间先预留 24 小时，您和家人商量后随时回复我即可。",
            "考虑,异议",
        ),
        (
            "banned",
            "包过",
            "禁止承诺包过、保分、保证录取等绝对化结果表述。",
            "合规",
        ),
        (
            "banned",
            "第一名",
            "禁止使用「全城第一」「必进名校」等无法核验的夸张宣传。",
            "合规",
        ),
    ]
    for category, title, content, tags in samples:
        exists = (
            db.query(KnowledgeEntry)
            .filter(KnowledgeEntry.category == category, KnowledgeEntry.title == title)
            .first()
        )
        if exists:
            # Keep sample scripts in sync with current brand name
            if exists.content != content or exists.tags != tags:
                exists.content = content
                exists.tags = tags
            continue
        db.add(
            KnowledgeEntry(
                category=category,
                title=title,
                content=content,
                tags=tags,
                is_active=True,
            )
        )
    db.commit()

def migrate_brand_name(db: Session, old: str = "壹号教室", new: str = "嘉壹启航") -> None:
    """Replace legacy brand string in stored text (knowledge, copies, posters, etc.)."""
    from sqlalchemy import text

    tables = db.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).fetchall()
    changed = 0
    for (table,) in tables:
        if table.startswith("sqlite_"):
            continue
        cols = db.execute(text(f"PRAGMA table_info({table})")).fetchall()
        for col in cols:
            col_name = col[1]
            # skip pure numeric / blob-ish columns by name heuristic
            if col_name in {"id", "rowid"} or col_name.endswith("_id"):
                continue
            try:
                result = db.execute(
                    text(
                        f"UPDATE {table} SET {col_name} = REPLACE(CAST({col_name} AS TEXT), :old, :new) "
                        f"WHERE CAST({col_name} AS TEXT) LIKE :pat"
                    ),
                    {"old": old, "new": new, "pat": f"%{old}%"},
                )
                changed += result.rowcount or 0
            except Exception:
                continue
    if changed:
        db.commit()

def seed_demo_leads(db: Session, target: int = 20) -> None:
    current = db.query(Lead).count()
    if current >= target:
        return
    need = target - current
    rng = random.Random(42 + current)
    for i in range(need):
        name = f"{rng.choice(SURNAMES)}{rng.choice(GIVEN)}家长"
        db.add(
            Lead(
                student_or_parent_name=name,
                phone=f"139{rng.randint(10000000, 99999999)}",
                source=rng.choice(SOURCES),
                referrer_name=rng.choice(["李同学", "王妈妈", "老学员", None]),
                channel_note=rng.choice(["朋友圈", "地推", "转介绍", ""]),
                need=rng.choice(NEEDS),
                status=rng.choice(LEAD_STATUSES),
                next_follow_at=_utcnow() + timedelta(days=rng.randint(-2, 7)),
                notes=rng.choice(["已加微信", "待回访", "意向一般", ""]),
            )
        )
    db.commit()

def seed_demo_students(db: Session, target: int = 40) -> None:
    current = db.query(Student).count()
    if current >= target:
        return
    managers = _active_crs(db)
    if not managers:
        return
    admin = db.query(User).filter(User.role == "admin").first()
    need = target - current
    rng = random.Random(99 + current)
    statuses = ["active", "active", "active", "paused", "graduated"]
    for i in range(need):
        m = managers[i % len(managers)]
        db.add(
            Student(
                name=f"{rng.choice(SURNAMES)}{rng.choice(GIVEN)}",
                grade=rng.choice(GRADES),
                school=rng.choice(SCHOOLS),
                phone=f"138{rng.randint(10000000, 99999999)}",
                parent_name=f"{rng.choice(SURNAMES)}妈妈",
                academic_manager_id=m.id,
                status=rng.choice(statuses),
                notes=rng.choice(["注意力需加强", "作业习惯好", "家长沟通顺畅", ""]),
                created_by=admin.id if admin else m.id,
            )
        )
    db.commit()

def migrate_user_deleted_at(db: Session) -> None:
    """Add users.deleted_at for soft-delete (existing SQLite DBs won't get it from create_all)."""
    from sqlalchemy import text

    try:
        cols = db.execute(text("PRAGMA table_info(users)")).fetchall()
    except Exception:
        return
    names = {c[1] for c in cols}
    if "deleted_at" in names:
        return
    db.execute(text("ALTER TABLE users ADD COLUMN deleted_at DATETIME"))
    db.commit()

def migrate_enrollment_courses(db: Session) -> None:
    """Add enrollment_records.courses JSON column for existing SQLite DBs."""
    from sqlalchemy import text

    try:
        cols = db.execute(text("PRAGMA table_info(enrollment_records)")).fetchall()
    except Exception:
        return
    if not cols:
        return
    names = {c[1] for c in cols}
    if "courses" in names:
        return
    db.execute(text("ALTER TABLE enrollment_records ADD COLUMN courses TEXT DEFAULT '[]'"))
    db.commit()

def _sqlite_add_column(db: Session, table: str, column: str, ddl: str) -> None:
    """Idempotent ALTER TABLE ADD COLUMN for SQLite."""
    from sqlalchemy import text

    try:
        cols = db.execute(text(f"PRAGMA table_info({table})")).fetchall()
    except Exception:
        return
    if not cols:
        return
    names = {c[1] for c in cols}
    if column in names:
        return
    db.execute(text(f"ALTER TABLE {table} ADD COLUMN {ddl}"))
    db.commit()

def migrate_enrollment_order_pay(db: Session) -> None:
    """报名记录：订单号 + 支付方式（既有库补列）。"""
    _sqlite_add_column(db, "enrollment_records", "order_no", "order_no VARCHAR(32) DEFAULT ''")
    _sqlite_add_column(db, "enrollment_records", "pay_methods", "pay_methods TEXT DEFAULT '[]'")
    _sqlite_add_column(db, "enrollment_records", "pay_other", "pay_other VARCHAR(128) DEFAULT ''")

def migrate_student_linked_courses(db: Session) -> None:
    """学员档案：关联课程快照。"""
    _sqlite_add_column(db, "students", "linked_courses", "linked_courses TEXT DEFAULT '[]'")

def migrate_lead_contact_fields(db: Session) -> None:
    """线索：最近联系信息（既有库补列；协作/动态表由 create_all 新建）。"""
    _sqlite_add_column(db, "leads", "last_contact_at", "last_contact_at DATETIME")
    _sqlite_add_column(db, "leads", "last_contact_by", "last_contact_by INTEGER")
    _sqlite_add_column(db, "leads", "last_contact_method", "last_contact_method VARCHAR(32) DEFAULT ''")

def migrate_class_default_room(db: Session) -> None:
    """班级默认上课教室。"""
    _sqlite_add_column(db, "class_rooms", "default_room", "default_room VARCHAR(128) DEFAULT ''")

def migrate_class_record_salary_hours(db: Session) -> None:
    """点名记录新增计薪课时；历史数据按原授课课时回填。"""
    from sqlalchemy import text

    try:
        cols = db.execute(text("PRAGMA table_info(class_records)")).fetchall()
    except Exception:
        return
    if not cols:
        return
    names = {c[1] for c in cols}
    if "salary_hours" in names:
        return
    db.execute(text("ALTER TABLE class_records ADD COLUMN salary_hours FLOAT DEFAULT 1"))
    db.execute(text("UPDATE class_records SET salary_hours = 1"))
    db.commit()

def migrate_course_package_metadata(db: Session) -> None:
    """课包购买明细与课消分配（兼容既有 SQLite 数据库）。"""
    _sqlite_add_column(
        db,
        "student_course_packages",
        "purchased_hours",
        "purchased_hours FLOAT DEFAULT 0",
    )
    _sqlite_add_column(
        db,
        "student_course_packages",
        "gift_hours",
        "gift_hours FLOAT DEFAULT 0",
    )
    _sqlite_add_column(
        db,
        "student_course_packages",
        "valid_until",
        "valid_until DATE",
    )
    _sqlite_add_column(
        db,
        "course_consumptions",
        "package_allocations",
        "package_allocations TEXT DEFAULT '[]'",
    )
    _sqlite_add_column(
        db,
        "course_consumptions",
        "uncovered_hours",
        "uncovered_hours FLOAT DEFAULT 0",
    )

def migrate_user_extra_permissions(db: Session) -> None:
    """用户额外授权码列表（JSON 数组；既有库补列）。"""
    _sqlite_add_column(db, "users", "extra_permissions", "extra_permissions TEXT DEFAULT '[]'")

def seed_essentials(db: Session) -> None:
    """Always: login accounts, system templates, sample knowledge, brand fix."""
    migrate_user_deleted_at(db)
    migrate_user_extra_permissions(db)
    migrate_enrollment_courses(db)
    migrate_enrollment_order_pay(db)
    migrate_student_linked_courses(db)
    migrate_lead_contact_fields(db)
    migrate_class_default_room(db)
    migrate_class_record_salary_hours(db)
    migrate_course_package_metadata(db)
    seed_demo_users(db)
    seed_system_templates(db)
    seed_sample_knowledge(db)
    migrate_brand_name(db)

def seed_demo_courses(db: Session) -> None:
    """Idempotent sample courses for 教务/报名联调."""
    from app.models.academic import Course

    samples = [
        ("初一物理一对一", "one_to_one", "初一", "物理", 1000),
        ("初一数学一对一", "one_to_one", "初一", "数学", 1000),
        ("高一英语一对一", "one_to_one", "高一", "英语", 2000),
        ("初二英语班课", "group", "初二", "英语", 220),
        ("初二数学班课", "group", "初二", "数学", 240),
        ("新高一物理班课", "group", "高一", "物理", 350),
        ("新高一数学班课", "group", "高一", "数学", 500),
        ("预初数学班课", "group", "预初", "数学", 300),
    ]
    for name, ctype, grade, subject, price in samples:
        exists = db.query(Course).filter(Course.name == name).first()
        if exists:
            continue
        db.add(
            Course(
                name=name,
                course_type=ctype,
                grade=grade,
                subject=subject,
                term="2026暑假",
                billing_mode="hour",
                unit_price=float(price),
                leave_rule="no_deduct",
                absent_rule="no_deduct",
                enabled=True,
            )
        )
    db.commit()

def seed_demo_business(db: Session) -> None:
    """Development/test only: fake teachers/CRs, leads, students for UI 联调."""
    seed_extra_teachers(db, count=10)
    seed_extra_crs(db, count=10)
    seed_demo_leads(db, target=20)
    cleanup_junk_demo_students(db)
    reassign_students_to_crs(db)
    seed_demo_students(db, target=40)
    seed_demo_courses(db)

def seed_all(db: Session) -> None:
    """
    Seed by environment:
    - essentials: every env (accounts + system templates + knowledge)
    - demo business data: only when APP_ENV=development (or SEED_DEMO_DATA=true)
    """
    settings = get_settings()
    seed_essentials(db)
    if settings.should_seed_demo_data:
        seed_demo_business(db)
