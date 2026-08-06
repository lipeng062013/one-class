import secrets
from datetime import datetime

from sqlalchemy.orm import Session

from app.core.pagination import clamp_page, clamp_page_size, page_payload, paginate_query
from app.core.permissions import (
    dump_extra_permissions,
    role_default_permissions,
    validate_permission_codes,
)
from app.core.security import hash_password
from app.core.timeutil import now as _utcnow
from app.models.lead import Lead, LeadCollaborator
from app.models.student import Student
from app.models.todo import TodoItem
from app.models.user import User

VALID_ROLES = {"admin", "operator", "teacher", "cr", "academic_manager"}

def list_users(
    db: Session,
    *,
    role: str | None = None,
    is_active: bool | None = None,
    username: str | None = None,
    display_name: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """分页用户列表；返回 page_payload 结构。"""
    q = db.query(User).filter(User.deleted_at.is_(None))
    if role:
        q = q.filter(User.role == role)
    if is_active is not None:
        q = q.filter(User.is_active.is_(is_active))
    if username:
        q = q.filter(User.username.contains(username))
    if display_name:
        q = q.filter(User.display_name.contains(display_name))
    q = q.order_by(User.id.asc())
    p = clamp_page(page)
    ps = clamp_page_size(page_size)
    rows, total = paginate_query(q, page=p, page_size=ps)
    return page_payload(rows, total=total, page=p, page_size=ps)

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

def _normalize_extra_for_role(role: str, codes: list[str] | None) -> tuple[str, str | None]:
    """Store only extras beyond role defaults. Admin always stores []."""
    if role == "admin" or codes is None:
        return "[]", None
    cleaned, err = validate_permission_codes(codes)
    if err:
        return "[]", err
    defaults = role_default_permissions(role)
    extras = [c for c in cleaned if c not in defaults]
    return dump_extra_permissions(extras), None

def create_user(
    db: Session,
    *,
    username: str,
    display_name: str,
    role: str,
    password: str,
    extra_permissions: list[str] | None = None,
) -> User | str:
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
    extra_json, extra_err = _normalize_extra_for_role(role, extra_permissions if extra_permissions is not None else [])
    if extra_err:
        return extra_err
    user = User(
        username=username,
        display_name=display_name,
        role=role,
        password_hash=hash_password(password),
        is_active=True,
        extra_permissions=extra_json,
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
    extra_permissions: list[str] | None = None,
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
        # Drop extras that are now covered by the new role defaults
        extra_json, extra_err = _normalize_extra_for_role(
            role,
            None if extra_permissions is None else extra_permissions,
        )
        if extra_permissions is None:
            # Re-normalize existing extras against new role
            from app.core.permissions import parse_extra_permissions

            extra_json, extra_err = _normalize_extra_for_role(
                role, parse_extra_permissions(user.extra_permissions)
            )
        if extra_err:
            return extra_err
        user.extra_permissions = extra_json
    elif extra_permissions is not None:
        extra_json, extra_err = _normalize_extra_for_role(user.role, extra_permissions)
        if extra_err:
            return extra_err
        user.extra_permissions = extra_json
    if is_active is not None:
        user.is_active = is_active
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

def set_user_permissions(db: Session, user: User, extra_permissions: list[str]) -> User | str:
    """Replace extra grants for a non-admin user."""
    if user.deleted_at is not None:
        return "用户已删除"
    if user.role == "admin":
        user.extra_permissions = "[]"
        db.add(user)
        db.commit()
        db.refresh(user)
        return user
    extra_json, extra_err = _normalize_extra_for_role(user.role, extra_permissions)
    if extra_err:
        return extra_err
    user.extra_permissions = extra_json
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
    db.query(Lead).filter(Lead.last_contact_by == uid).update(
        {Lead.last_contact_by: None}, synchronize_session=False
    )
    db.query(LeadCollaborator).filter(LeadCollaborator.user_id == uid).delete(
        synchronize_session=False
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
