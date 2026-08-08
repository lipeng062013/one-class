from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import require_permissions
from app.core.permissions import (
    catalog_grouped,
    effective_permissions,
    parse_extra_permissions,
    user_permission_payload,
)
from app.core.responses import fail, ok
from app.models.user import User
from app.modules.users.schemas import (
    ResetPasswordRequest,
    UserCreate,
    UserPermissionsUpdate,
    UserUpdate,
)
from app.modules.users.service import (
    create_user,
    delete_user,
    list_users,
    reset_password,
    set_user_permissions,
    update_user,
)

router = APIRouter(prefix="/users", tags=["users"])

_manage = require_permissions("users.manage")


def _public(user: User) -> dict:
    from app.core.permissions import role_default_permissions

    extra = parse_extra_permissions(getattr(user, "extra_permissions", None))
    if user.role == "admin":
        extra = []
    else:
        # 与授权弹窗一致：已并入角色自带的码不再计为「额外」
        defaults = role_default_permissions(user.role)
        extra = [c for c in extra if c not in defaults]
    return {
        "id": user.id,
        "username": user.username,
        "display_name": user.display_name,
        "role": user.role,
        "is_active": user.is_active,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "extra_permissions": extra,
        "permissions": sorted(effective_permissions(user)),
    }


@router.get("/permissions/catalog")
def get_permission_catalog(_: User = Depends(_manage)):
    """Full permission list for grant UI (grouped)."""
    return ok({"groups": catalog_grouped()})


@router.get("")
def get_users(
    role: str | None = None,
    is_active: bool | None = None,
    username: str | None = None,
    display_name: str | None = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    _: User = Depends(_manage),
):
    result = list_users(
        db,
        role=role,
        is_active=is_active,
        username=username,
        display_name=display_name,
        page=page,
        page_size=page_size,
    )
    return ok(
        {
            **result,
            "items": [_public(u) for u in result["items"]],
        }
    )


@router.post("")
def post_user(
    body: UserCreate,
    db: Session = Depends(get_db),
    _: User = Depends(_manage),
):
    result = create_user(
        db,
        username=body.username,
        display_name=body.display_name,
        role=body.role,
        password=body.password,
        extra_permissions=body.extra_permissions,
    )
    if isinstance(result, str):
        return fail("USER_CREATE_FAILED", result, status_code=400)
    return ok(_public(result), status_code=201)


@router.get("/{user_id}/permissions")
def get_user_permissions(
    user_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(_manage),
):
    user = db.get(User, user_id)
    if not user or user.deleted_at is not None:
        return fail("NOT_FOUND", "用户不存在", status_code=404)
    return ok(user_permission_payload(user))


@router.put("/{user_id}/permissions")
def put_user_permissions(
    user_id: int,
    body: UserPermissionsUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(_manage),
):
    user = db.get(User, user_id)
    if not user or user.deleted_at is not None:
        return fail("NOT_FOUND", "用户不存在", status_code=404)
    result = set_user_permissions(db, user, body.extra_permissions)
    if isinstance(result, str):
        return fail("USER_PERMISSIONS_FAILED", result, status_code=400)
    return ok(user_permission_payload(result))


@router.patch("/{user_id}")
def patch_user(
    user_id: int,
    body: UserUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(_manage),
):
    user = db.get(User, user_id)
    if not user or user.deleted_at is not None:
        return fail("NOT_FOUND", "用户不存在", status_code=404)
    result = update_user(
        db,
        user,
        display_name=body.display_name,
        role=body.role,
        is_active=body.is_active,
        extra_permissions=body.extra_permissions,
    )
    if isinstance(result, str):
        return fail("USER_UPDATE_FAILED", result, status_code=400)
    return ok(_public(result))


@router.post("/{user_id}/reset-password")
def post_reset_password(
    user_id: int,
    body: ResetPasswordRequest,
    db: Session = Depends(get_db),
    _: User = Depends(_manage),
):
    user = db.get(User, user_id)
    if not user or user.deleted_at is not None:
        return fail("NOT_FOUND", "用户不存在", status_code=404)
    err = reset_password(db, user, body.new_password)
    if err:
        return fail("USER_RESET_FAILED", err, status_code=400)
    return ok({"reset": True})


@router.delete("/{user_id}")
def remove_user(
    user_id: int,
    db: Session = Depends(get_db),
    actor: User = Depends(_manage),
):
    user = db.get(User, user_id)
    if not user or user.deleted_at is not None:
        return fail("NOT_FOUND", "用户不存在", status_code=404)
    err = delete_user(db, user, actor=actor)
    if err:
        return fail("USER_DELETE_FAILED", err, status_code=400)
    return ok({"deleted": True, "id": user_id})
