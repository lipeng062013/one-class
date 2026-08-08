from datetime import timedelta

from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password, verify_password
from app.core.timeutil import now as _utcnow
from app.models.todo import TodoItem
from app.models.user import User

# Marker embedded in admin todo content for dedupe of reset requests
_PWD_RESET_MARKER = "[pwd-reset-request:"
_PWD_RESET_COOLDOWN = timedelta(hours=24)


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
    """Returns error message or None on success (mutates user.password_hash).

    Any authenticated user may change their own password (requires current password).
    Admins reset others via users.reset_password (no current password needed).
    """
    if not verify_password(current_password, user.password_hash):
        return "当前密码不正确"
    if current_password == new_password:
        return "新密码不能与当前密码相同"
    if len(new_password) < 6:
        return "新密码至少 6 位"
    user.password_hash = hash_password(new_password)
    return None


def list_active_admins(db: Session) -> list[User]:
    return (
        db.query(User)
        .filter(
            User.role == "admin",
            User.is_active.is_(True),
            User.deleted_at.is_(None),
        )
        .order_by(User.id.asc())
        .all()
    )


def password_help_payload(db: Session) -> dict:
    """Public help info for the login-page forgot-password dialog."""
    admins = list_active_admins(db)
    return {
        "supports_self_reset": False,
        "method": "admin_reset",
        "title": "如何找回密码",
        "summary": "本系统为机构内部工具，暂不支持短信/邮箱自助找回。请联系负责人在「用户管理」中重置密码。",
        "steps": [
            "确认并记下您的登录用户名",
            "联系下方负责人，说明需要重置密码",
            "负责人在「用户管理」中为您设置新密码并告知您",
            "用新密码登录后，建议立即在右上角「修改密码」改成自己记得的密码",
        ],
        "admins": [{"display_name": a.display_name} for a in admins],
    }


def _marker_for(username: str) -> str:
    return f"{_PWD_RESET_MARKER}{username.strip().lower()}]"


def request_password_reset(
    db: Session,
    *,
    username: str,
    note: str = "",
) -> dict:
    """
    Unauthenticated password-reset request.

    Always returns a generic success payload so callers cannot probe whether a
    username exists. When the account is active, creates (or refreshes) a todo
    for each active admin within a 24h cooldown window.
    """
    username = (username or "").strip()
    note = (note or "").strip()[:200]
    generic = {
        "accepted": True,
        "message": "若该账号存在，负责人已收到重置提醒。请等待对方联系您。",
    }
    if not username:
        return generic

    user = (
        db.query(User)
        .filter(User.username == username, User.deleted_at.is_(None))
        .first()
    )
    if not user or not user.is_active:
        return generic

    admins = list_active_admins(db)
    if not admins:
        return generic

    marker = _marker_for(user.username)
    since = _utcnow() - _PWD_RESET_COOLDOWN
    note_line = f"备注：{note}" if note else "备注：（无）"
    title = f"【密码重置】{user.display_name}（{user.username}）"
    content = (
        f"{marker}\n"
        f"用户 {user.display_name}（登录名 {user.username}）在登录页申请重置密码。\n"
        f"{note_line}\n"
        f"请打开「用户管理」→ 找到该账号 →「重置密码」，将新密码告知对方。"
    )

    created = 0
    for admin in admins:
        existing = (
            db.query(TodoItem)
            .filter(
                TodoItem.user_id == admin.id,
                TodoItem.is_done.is_(False),
                TodoItem.content.contains(marker),
                TodoItem.created_at >= since,
            )
            .first()
        )
        if existing:
            # Refresh content / bump visibility without spamming new rows
            existing.title = title
            existing.content = content
            existing.created_at = _utcnow()
            db.add(existing)
            continue
        db.add(
            TodoItem(
                user_id=admin.id,
                title=title,
                content=content,
                is_done=False,
            )
        )
        created += 1

    db.commit()
    # Do not expose created count to the client (user enumeration risk)
    _ = created
    return generic
