from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.timeutil import now as _utcnow

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(128))
    role: Mapped[str] = mapped_column(String(32), index=True)  # admin|operator|teacher|cr|academic_manager
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # JSON array of extra permission codes beyond role defaults (admin grants)
    extra_permissions: Mapped[str] = mapped_column(Text, default="[]")
    # Soft-delete: keep row so material/learning authorship (uploader_id / teacher_id) stays valid
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, default=None, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
