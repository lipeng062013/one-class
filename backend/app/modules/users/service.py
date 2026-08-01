import secrets
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.lead import Lead
from app.models.student import Student
from app.models.todo import TodoItem
from app.models.user import User

VALID_ROLES = {"admin", "operator", "teacher"}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def list_users(
    db: Session,
    *,
    role: str | None = None,
    is_active: bool | None = None,
    username: str | None = None,
    display_name: str | None = None,
) -> list[User]:
    q = db.query(User).filter(User.deleted_at.is_(None))
    if role:
        q = q.filter(User.role == role)
    if is_active is not None:
        q = q.filter(User.is_active.is_(is_active))
    if username:
        q = q.filter(User.username.contains(username))
    if display_name:
        q = q.filter(User.display_name.contains(display_name))
    return q.order_by(User.id.asc()).all()


def _display_name_taken(
    db: Session,
    display_name: str,
    *,
    exclude_user_id: int | None = None,
) -> bool:
    name = display_name.strip()
    if not name:
        return False
    q = db.query(User).filter(User.display_name == name, User.deleted_at.is_(None))
    if exclude_user_id is not None:
        q = q.filter(User.id != exclude_user_id)
    return q.first() is not None


def create_user(db: Session, *, username: str, display_name: str, role: str, password: str) -> User | str:
    if role not in VALID_ROLES:
        return "角色无效"
    username = username.strip()
    display_name = display_name.strip()
    if not username:
        return "用户名不能为空"
    if not display_name:
        return "显示名不能为空"
    exists = (
        db.query(User)
        .filter(User.username == username, User.deleted_at.is_(None))
        .first()
    )
    if exists:
        return "用户名已存在"
    if _display_name_taken(db, display_name):
        return "显示名已存在，请更换"
    user = User(
        username=username,
        display_name=display_name,
        role=role,
        password_hash=hash_password(password),
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def update_user(
    db: Session,
    user: User,
    *,
    display_name: str | None = None,
    role: str | None = None,
    is_active: bool | None = None,
) -> User | str:
    if user.deleted_at is not None:
        return "用户已删除"
    if display_name is not None:
        name = display_name.strip()
        if not name:
            return "显示名不能为空"
        if _display_name_taken(db, name, exclude_user_id=user.id):
            return "显示名已存在，请更换"
        user.display_name = name
    if role is not None:
        if role not in VALID_ROLES:
            return "角色无效"
        user.role = role
    if is_active is not None:
        user.is_active = is_active
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def reset_password(db: Session, user: User, new_password: str) -> str | None:
    if user.deleted_at is not None:
        return "用户已删除"
    user.password_hash = hash_password(new_password)
    db.add(user)
    db.commit()
    return None


def delete_user(db: Session, user: User, *, actor: User) -> str | None:
    """
    Soft-delete a user account (including 负责人/admin).

    Authorship on materials (uploader_id) and learning records (teacher_id) is kept
    as-is so historical “who wrote this” still resolves via display_name.
    Current operational assignments (学管师 / 线索负责人) are cleared.
    Personal todos are removed. Login is disabled and the username is freed.
    """
    if user.id == actor.id:
        return "不能删除当前登录账号"
    if user.deleted_at is not None:
        return "用户已删除"

    uid = user.id

    # Personal todos go away with the account
    db.query(TodoItem).filter(TodoItem.user_id == uid).delete(synchronize_session=False)

    # Current operational assignments only — not historical authorship
    db.query(Student).filter(Student.academic_manager_id == uid).update(
        {Student.academic_manager_id: None}, synchronize_session=False
    )
    db.query(Lead).filter(Lead.owner_id == uid).update(
        {Lead.owner_id: None}, synchronize_session=False
    )

    # Soft-delete: keep row for material/learning FK + display_name attribution
    original_username = user.username
    user.deleted_at = _utcnow()
    user.is_active = False
    # Free username so a new account can reuse it (e.g. replace default admin)
    suffix = f".del{uid}"
    base = original_username[: max(1, 64 - len(suffix))]
    user.username = f"{base}{suffix}"
    user.password_hash = hash_password(secrets.token_urlsafe(32))
    db.add(user)
    db.commit()
    return None
