from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class CopyTemplate(Base):
    __tablename__ = "copy_templates"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), default="")
    scene: Mapped[str] = mapped_column(String(64), default="", index=True)
    body: Mapped[str] = mapped_column(Text, default="")
    is_system: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PosterTemplate(Base):
    __tablename__ = "poster_templates"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), default="")
    scene: Mapped[str] = mapped_column(String(64), default="", index=True)
    layout_json: Mapped[str] = mapped_column(Text, default="{}")
    preview_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
