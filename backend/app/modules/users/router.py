from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import require_roles
from app.core.responses import fail, ok
from app.models.user import User
from app.modules.users.schemas import ResetPasswordRequest, UserCreate, UserPublic, UserUpdate
from app.modules.users.service import create_user, delete_user, list_users, reset_password, update_user

router = APIRouter(prefix="/users", tags=["users"])


def _public(user: User) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "display_name": user.display_name,
        "role": user.role,
        "is_active": user.is_active,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


@router.get("")
def get_users(
    role: str | None = None,
    is_active: bool | None = None,
    username: str | None = None,
    display_name: str | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin")),
):
    users = list_users(
        db,
        role=role,
        is_active=is_active,
        username=username,
        display_name=display_name,
    )
    return ok([_public(u) for u in users])


@router.post("")
def post_user(
    body: UserCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin")),
):
    result = create_user(
        db,
        username=body.username,
        display_name=body.display_name,
        role=body.role,
        password=body.password,
    )
    if isinstance(result, str):
        return fail("USER_CREATE_FAILED", result, status_code=400)
    return ok(_public(result), status_code=201)


@router.patch("/{user_id}")
def patch_user(
    user_id: int,
    body: UserUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin")),
):
    user = db.get(User, user_id)
    if not user:
        return fail("NOT_FOUND", "用户不存在", status_code=404)
    result = update_user(
        db,
        user,
        display_name=body.display_name,
        role=body.role,
        is_active=body.is_active,
    )
    if isinstance(result, str):
        return fail("USER_UPDATE_FAILED", result, status_code=400)
    return ok(_public(result))


@router.post("/{user_id}/reset-password")
def post_reset_password(
    user_id: int,
    body: ResetPasswordRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin")),
):
    user = db.get(User, user_id)
    if not user:
        return fail("NOT_FOUND", "用户不存在", status_code=404)
    reset_password(db, user, body.new_password)
    return ok({"reset": True})


@router.delete("/{user_id}")
def remove_user(
    user_id: int,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles("admin")),
):
    user = db.get(User, user_id)
    if not user:
        return fail("NOT_FOUND", "用户不存在", status_code=404)
    err = delete_user(db, user, actor=actor)
    if err:
        return fail("USER_DELETE_FAILED", err, status_code=400)
    return ok({"deleted": True, "id": user_id})
