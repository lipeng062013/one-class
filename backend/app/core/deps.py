from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import decode_token
from app.models.user import User

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if creds is None or not creds.credentials:
        raise HTTPException(status_code=401, detail="未登录")
    try:
        payload = decode_token(creds.credentials)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="登录已失效") from exc
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="登录已失效")
    user = db.get(User, int(user_id))
    if not user or not user.is_active or user.deleted_at is not None:
        raise HTTPException(status_code=401, detail="账号不可用")
    return user


def require_roles(*roles: str):
    def _dep(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=403, detail="无权限")
        return user

    return _dep
