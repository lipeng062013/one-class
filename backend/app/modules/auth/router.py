from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import get_current_user
from app.core.permissions import effective_permissions, parse_extra_permissions
from app.core.responses import fail, ok
from app.models.user import User
from app.modules.auth.schemas import ChangePasswordRequest, LoginRequest, UserOut
from app.modules.auth.service import authenticate, change_password, issue_token

router = APIRouter(prefix="/auth", tags=["auth"])


def _user_out(user: User) -> dict:
    extra = parse_extra_permissions(getattr(user, "extra_permissions", None))
    return {
        "id": user.id,
        "username": user.username,
        "display_name": user.display_name,
        "role": user.role,
        "is_active": user.is_active,
        "permissions": sorted(effective_permissions(user)),
        "extra_permissions": [] if user.role == "admin" else extra,
    }


@router.post("/login")
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = authenticate(db, body.username, body.password)
    if not user:
        return fail("AUTH_FAILED", "账号或密码错误", status_code=401)
    if not user.is_active:
        return fail("USER_DISABLED", "账号已停用，请联系负责人", status_code=403)
    token = issue_token(user)
    return ok(
        {
            "access_token": token,
            "token_type": "bearer",
            "user": _user_out(user),
        }
    )


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return ok(_user_out(user))


@router.post("/change-password")
def change_password_endpoint(
    body: ChangePasswordRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    err = change_password(user, body.current_password, body.new_password)
    if err:
        return fail("BAD_PASSWORD", err, status_code=400)
    db.add(user)
    db.commit()
    return ok({"changed": True})
