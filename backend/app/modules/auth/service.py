from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User


def authenticate(db: Session, username: str, password: str) -> User | None:
    user = (
        db.query(User)
        .filter(User.username == username, User.deleted_at.is_(None))
        .first()
    )
    if not user:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


def issue_token(user: User) -> str:
    return create_access_token(subject=str(user.id), extra={"role": user.role, "username": user.username})


def change_password(user: User, current_password: str, new_password: str) -> str | None:
    """Returns error message or None on success (mutates user.password_hash)."""
    if not verify_password(current_password, user.password_hash):
        return "当前密码不正确"
    user.password_hash = hash_password(new_password)
    return None
