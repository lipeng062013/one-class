from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Lead(Base):
    __tablename__ = "leads"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    student_or_parent_name: Mapped[str] = mapped_column(String(255), default="")
    phone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source: Mapped[str] = mapped_column(String(32), default="other")  # referral|dianping|wechat|walkin|other
    referrer_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    channel_note: Mapped[str] = mapped_column(Text, default="")
    need: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(32), default="new")  # new|contacted|visited|enrolled|lost
    next_follow_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
