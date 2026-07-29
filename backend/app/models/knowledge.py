from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class KnowledgeEntry(Base):
    __tablename__ = "knowledge_entries"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    category: Mapped[str] = mapped_column(String(32), index=True)  # course|faq|tone|banned|staff|process
    title: Mapped[str] = mapped_column(String(255), default="")
    content: Mapped[str] = mapped_column(Text, default="")
    tags: Mapped[str] = mapped_column(String(255), default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
