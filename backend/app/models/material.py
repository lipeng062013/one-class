from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.core.timeutil import now as _utcnow

class Material(Base):
    __tablename__ = "materials"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    uploader_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    grade: Mapped[str | None] = mapped_column(String(64), nullable=True)
    subject: Mapped[str | None] = mapped_column(String(64), nullable=True)
    pain_point: Mapped[str | None] = mapped_column(Text, nullable=True)
    teacher_action: Mapped[str | None] = mapped_column(Text, nullable=True)
    next_step: Mapped[str | None] = mapped_column(Text, nullable=True)
    auth_status: Mapped[str] = mapped_column(String(32), default="pending")
    # pending | authorized | denied | anonymized
    status: Mapped[str] = mapped_column(String(32), default="new", index=True)
    # new | usable | used | archived
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    files: Mapped[list["MaterialFile"]] = relationship(
        "MaterialFile",
        back_populates="material",
        cascade="all, delete-orphan",
        order_by="MaterialFile.sort_order",
    )

class MaterialFile(Base):
    __tablename__ = "material_files"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    material_id: Mapped[int] = mapped_column(ForeignKey("materials.id"), index=True)
    file_path: Mapped[str] = mapped_column(String(512))
    file_type: Mapped[str] = mapped_column(String(128))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    material: Mapped["Material"] = relationship("Material", back_populates="files")
