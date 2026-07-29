import json

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import hash_password
from app.models.knowledge import KnowledgeEntry
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
    if not db.query(KnowledgeEntry).filter(KnowledgeEntry.category == "tone").first():
        db.add(
            KnowledgeEntry(
                category="tone",
                title="品牌语气",
                content="温暖专业、真诚不夸张；面向家长口语化，强调陪伴与可执行的小步骤。",
                tags="品牌,语气",
                is_active=True,
            )
        )
    if not db.query(KnowledgeEntry).filter(
        KnowledgeEntry.category == "banned",
        KnowledgeEntry.title == "包过",
    ).first():
        db.add(
            KnowledgeEntry(
                category="banned",
                title="包过",
                content="禁止承诺包过、保分、保证录取等绝对化结果表述。",
                tags="合规",
                is_active=True,
            )
        )
    db.commit()


def seed_all(db: Session) -> None:
    seed_demo_users(db)
    seed_system_templates(db)
    seed_sample_knowledge(db)
