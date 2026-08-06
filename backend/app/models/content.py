from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.timeutil import now_aware


class GeneratedCopy(Base):
    __tablename__ = "generated_copies"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    material_id: Mapped[int | None] = mapped_column(ForeignKey("materials.id"), nullable=True, index=True)
    template_id: Mapped[int | None] = mapped_column(ForeignKey("copy_templates.id"), nullable=True, index=True)
    mode: Mapped[str] = mapped_column(String(32), default="template")  # template|llm|template_then_llm
    platform: Mapped[str] = mapped_column(String(32), default="xhs")
    title: Mapped[str] = mapped_column(String(255), default="")
    body: Mapped[str] = mapped_column(Text, default="")
    prompt_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_aware, server_default=func.now()
    )
