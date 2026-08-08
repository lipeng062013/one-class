from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, validates

from app.core.db import Base
from app.core.phone import validate_phone_value
from app.core.timeutil import now_aware


class Lead(Base):
    __tablename__ = "leads"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    student_or_parent_name: Mapped[str] = mapped_column(String(255), default="")
    phone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    external_code: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    school: Mapped[str] = mapped_column(String(255), default="")
    grade: Mapped[str] = mapped_column(String(64), default="")
    age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    campus: Mapped[str] = mapped_column(String(255), default="")
    imported_creator_name: Mapped[str] = mapped_column(String(128), default="")
    source: Mapped[str] = mapped_column(String(32), default="other")  # referral|dianping|wechat|walkin|other
    referrer_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    channel_note: Mapped[str] = mapped_column(Text, default="")
    need: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(32), default="new")  # new|contacted|visited|enrolled|lost
    next_follow_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # 主跟进人（业绩/主责）；协作人见 LeadCollaborator
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    # 最近一次联系（便于多人协作时一眼看到谁刚沟通过）
    last_contact_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_contact_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    last_contact_method: Mapped[str] = mapped_column(String(32), default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_aware, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=now_aware,
        server_default=func.now(),
        onupdate=now_aware,
    )

    @validates("phone")
    def validate_phone(self, _key: str, value: str | None) -> str | None:
        return validate_phone_value(value)


class LeadCollaborator(Base):
    """线索协作跟进人（多人跟同一资源时登记，避免撞单）。"""

    __tablename__ = "lead_collaborators"
    __table_args__ = (UniqueConstraint("lead_id", "user_id", name="uq_lead_collaborator"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    lead_id: Mapped[int] = mapped_column(ForeignKey("leads.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    # collaborator | assistant
    role: Mapped[str] = mapped_column(String(32), default="collaborator")
    note: Mapped[str] = mapped_column(String(255), default="")
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_aware, server_default=func.now()
    )
    joined_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)


class LeadActivity(Base):
    """线索跟进动态：跟进记录、字段变更、协作变动等。"""

    __tablename__ = "lead_activities"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    lead_id: Mapped[int] = mapped_column(ForeignKey("leads.id"), index=True)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    # create | update | follow | owner | collaborator | system
    kind: Mapped[str] = mapped_column(String(32), default="follow", index=True)
    title: Mapped[str] = mapped_column(String(255), default="")
    content: Mapped[str] = mapped_column(Text, default="")
    # phone | wechat | visit | sms | other | ""
    contact_method: Mapped[str] = mapped_column(String(32), default="")
    # JSON 变更明细等
    meta_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_aware, server_default=func.now(), index=True
    )
