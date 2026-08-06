from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.core.db import Base
from app.core.phone import validate_phone_value
from app.core.timeutil import now as _utcnow

class Student(Base):
    """在读/在管学生名册（与线索 leads 分表）。"""

    __tablename__ = "students"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), index=True)
    grade: Mapped[str] = mapped_column(String(64), default="", index=True)
    school: Mapped[str] = mapped_column(String(255), default="")
    phone: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    parent_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    # 学管师 / 班主任（users.id，role=cr 或 academic_manager）
    academic_manager_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True, index=True
    )
    status: Mapped[str] = mapped_column(String(32), default="active", index=True)
    # active | paused | graduated | quit
    source_lead_id: Mapped[int | None] = mapped_column(ForeignKey("leads.id"), nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    # JSON 关联课程快照：[{"id":1,"name":"…","type":"…","price_label":"…"}]
    linked_courses: Mapped[str] = mapped_column(Text, default="[]")
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow)

    learning_records: Mapped[list["LearningRecord"]] = relationship(
        "LearningRecord",
        back_populates="student",
        cascade="all, delete-orphan",
        order_by="LearningRecord.class_date.desc()",
    )

    @validates("phone")
    def validate_phone(self, _key: str, value: str | None) -> str | None:
        return validate_phone_value(value)

class LearningRecord(Base):
    """学情档案：一次上课/跟进记录。"""

    __tablename__ = "learning_records"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), index=True)
    teacher_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    class_date: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, index=True)
    class_status: Mapped[str] = mapped_column(String(32), default="attended")
    # attended | absent | late | leave | makeup
    subject: Mapped[str | None] = mapped_column(String(64), nullable=True)
    learning_summary: Mapped[str] = mapped_column(Text, default="")
    homework_note: Mapped[str] = mapped_column(Text, default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow)

    student: Mapped["Student"] = relationship("Student", back_populates="learning_records")
    files: Mapped[list["LearningRecordFile"]] = relationship(
        "LearningRecordFile",
        back_populates="record",
        cascade="all, delete-orphan",
        order_by="LearningRecordFile.sort_order",
    )

class LearningRecordFile(Base):
    __tablename__ = "learning_record_files"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    record_id: Mapped[int] = mapped_column(ForeignKey("learning_records.id"), index=True)
    file_path: Mapped[str] = mapped_column(String(512))
    file_type: Mapped[str] = mapped_column(String(128))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    record: Mapped["LearningRecord"] = relationship("LearningRecord", back_populates="files")
