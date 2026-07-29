from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import hash_password
from app.models.user import User


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
