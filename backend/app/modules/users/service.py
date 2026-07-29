from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.user import User

VALID_ROLES = {"admin", "operator", "teacher"}


def list_users(
    db: Session,
    *,
    role: str | None = None,
    is_active: bool | None = None,
    username: str | None = None,
    display_name: str | None = None,
) -> list[User]:
    q = db.query(User)
    if role:
        q = q.filter(User.role == role)
    if is_active is not None:
        q = q.filter(User.is_active.is_(is_active))
    if username:
        q = q.filter(User.username.contains(username))
    if display_name:
        q = q.filter(User.display_name.contains(display_name))
    return q.order_by(User.id.asc()).all()


def create_user(db: Session, *, username: str, display_name: str, role: str, password: str) -> User | str:
    if role not in VALID_ROLES:
        return "角色无效"
    exists = db.query(User).filter(User.username == username).first()
    if exists:
        return "用户名已存在"
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
    if display_name is not None:
        user.display_name = display_name
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


def reset_password(db: Session, user: User, new_password: str) -> None:
    user.password_hash = hash_password(new_password)
    db.add(user)
    db.commit()
