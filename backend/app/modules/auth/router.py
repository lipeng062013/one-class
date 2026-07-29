from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import get_current_user
from app.core.responses import fail, ok
from app.models.user import User
from app.modules.auth.schemas import ChangePasswordRequest, LoginRequest, UserOut
from app.modules.auth.service import authenticate, change_password, issue_token

router = APIRouter(prefix="/auth", tags=["auth"])


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
            "user": UserOut.model_validate(user).model_dump(),
        }
    )


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return ok(UserOut.model_validate(user).model_dump())


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
