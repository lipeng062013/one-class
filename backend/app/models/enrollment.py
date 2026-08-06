"""报名 / 续费记录。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.timeutil import now as _utcnow

class EnrollmentRecord(Base):
    """学员报名或续费一笔业务记录（负责人侧）。"""

    __tablename__ = "enrollment_records"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), index=True)
    # enroll | renew
    kind: Mapped[str] = mapped_column(String(16), default="enroll", index=True)
    handled_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, index=True)
    # 销售业绩总额（可选）
    amount: Mapped[float] = mapped_column(Float, default=0.0)
    # 业务订单号（报名/续费确认后生成，供财务等模块引用）
    order_no: Mapped[str] = mapped_column(String(32), default="", index=True)
    # JSON 支付方式：["微信","支付宝","POS机刷卡","现金","其他"]
    pay_methods: Mapped[str] = mapped_column(Text, default="[]")
    # 选「其他」时的补充说明
    pay_other: Mapped[str] = mapped_column(String(128), default="")
    # JSON: [{"id":1,"name":"初一物理一对一","type":"一对一","price_label":"…"}]
    courses: Mapped[str] = mapped_column(Text, default="[]")
    # JSON: [{"user_id":1,"display_name":"…","amount":100}]
    attributions: Mapped[str] = mapped_column(Text, default="[]")
    internal_notes: Mapped[str] = mapped_column(Text, default="")
    external_notes: Mapped[str] = mapped_column(Text, default="")
    # JSON: ["enrollments/1/xxx.jpg", ...]
    internal_images: Mapped[str] = mapped_column(Text, default="[]")
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow)
