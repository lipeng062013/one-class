from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.timeutil import now_aware


class GeneratedPoster(Base):
    __tablename__ = "generated_posters"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    material_id: Mapped[int | None] = mapped_column(ForeignKey("materials.id"), nullable=True, index=True)
    template_id: Mapped[int | None] = mapped_column(
        ForeignKey("poster_templates.id"), nullable=True, index=True
    )
    mode: Mapped[str] = mapped_column(String(32), default="layout")  # layout | ai_image
    title: Mapped[str] = mapped_column(String(255), default="")
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    file_path: Mapped[str] = mapped_column(String(512), default="")
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_aware, server_default=func.now()
    )
