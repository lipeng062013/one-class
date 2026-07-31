import json
import random
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import hash_password
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


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def seed_demo_users(db: Session) -> None:
    """Idempotent: create demo users if missing; do not overwrite existing passwords."""
    settings = get_settings()
    demos = [
        (settings.seed_admin_username, settings.seed_admin_password, "负责人", "admin"),
        (settings.seed_ops_username, settings.seed_ops_password, "运营", "operator"),
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
    """Ensure at least `count` extra demo teachers (teacher2..)."""
    created = 0
    for i in range(2, count + 2):
        username = f"teacher{i}"
        if db.query(User).filter(User.username == username).first():
            continue
        db.add(
            User(
                username=username,
                password_hash=hash_password(f"t{i}1234"),
                display_name=f"老师{SURNAMES[i % len(SURNAMES)]}{GIVEN[i % len(GIVEN)][:1]}",
                role="teacher",
                is_active=True,
            )
        )
        created += 1
    if created:
        db.commit()


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
    teachers = db.query(User).filter(User.role == "teacher", User.is_active.is_(True)).all()
    if not teachers:
        return
    admin = db.query(User).filter(User.role == "admin").first()
    need = target - current
    rng = random.Random(99 + current)
    statuses = ["active", "active", "active", "paused", "graduated"]
    for i in range(need):
        t = rng.choice(teachers)
        db.add(
            Student(
                name=f"{rng.choice(SURNAMES)}{rng.choice(GIVEN)}",
                grade=rng.choice(GRADES),
                school=rng.choice(SCHOOLS),
                phone=f"138{rng.randint(10000000, 99999999)}",
                parent_name=f"{rng.choice(SURNAMES)}妈妈",
                academic_manager_id=t.id,
                status=rng.choice(statuses),
                notes=rng.choice(["注意力需加强", "作业习惯好", "家长沟通顺畅", ""]),
                created_by=admin.id if admin else t.id,
            )
        )
    db.commit()


def seed_essentials(db: Session) -> None:
    """Always: login accounts, system templates, sample knowledge, brand fix."""
    seed_demo_users(db)
    seed_system_templates(db)
    seed_sample_knowledge(db)
    migrate_brand_name(db)


def seed_demo_business(db: Session) -> None:
    """Development/test only: fake teachers, leads, students for UI 联调."""
    seed_extra_teachers(db, count=10)
    seed_demo_leads(db, target=20)
    seed_demo_students(db, target=40)


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
