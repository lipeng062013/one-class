import re
from typing import Any, TYPE_CHECKING

from pydantic import BaseModel, field_validator

if TYPE_CHECKING:
    from app.models.user import User


PHONE_ERROR_MESSAGE = "手机号必须为11位数字且以1开头"
_PHONE_PATTERN = re.compile(r"^1\d{10}$")


def validate_phone_value(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or _PHONE_PATTERN.fullmatch(value) is None:
        raise ValueError(PHONE_ERROR_MESSAGE)
    return value


def can_view_student_phone(user: "User | None") -> bool:
    """仅负责人可查看学员完整手机号；学管/老师等不可见。"""
    return bool(user is not None and getattr(user, "role", None) == "admin")


def phone_for_viewer(phone: str | None, user: "User | None") -> str:
    """按查看者权限返回手机号；无权限时返回空串（前端展示为 —）。"""
    raw = (phone or "").strip()
    if not raw:
        return ""
    if can_view_student_phone(user):
        return raw
    return ""


class PhoneInputModel(BaseModel):
    """Validate phone fields only on create/update request models."""

    @field_validator("phone", mode="before", check_fields=False)
    @classmethod
    def validate_phone(cls, value: Any) -> str | None:
        if value is None or value == "":
            raise ValueError(PHONE_ERROR_MESSAGE)
        return validate_phone_value(value)
