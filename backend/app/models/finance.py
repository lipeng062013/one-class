"""财务域：订单、收支、课消、账户充值。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.timeutil import now as _utcnow

class FinanceOrder(Base):
    """财务订单（报名/续费/转课/退课/充值等）。"""

    __tablename__ = "finance_orders"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    order_no: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), index=True)
    # enroll | renew | transfer | drop | recharge | refund | other
    order_type: Mapped[str] = mapped_column(String(32), default="enroll", index=True)
    item_summary: Mapped[str] = mapped_column(Text, default="")
    # JSON courses snapshot
    courses: Mapped[str] = mapped_column(Text, default="[]")
    receivable: Mapped[float] = mapped_column(Float, default=0.0)
    received: Mapped[float] = mapped_column(Float, default=0.0)
    arrears: Mapped[float] = mapped_column(Float, default=0.0)
    # paid | partial | unpaid | void
    status: Mapped[str] = mapped_column(String(32), default="paid", index=True)
    source: Mapped[str] = mapped_column(String(64), default="机构创建")
    performance_owner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    handler_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    enrollment_id: Mapped[int | None] = mapped_column(
        ForeignKey("enrollment_records.id"), nullable=True, index=True
    )
    pay_method: Mapped[str] = mapped_column(String(64), default="")
    handled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

class FinanceTransaction(Base):
    """收支明细。"""

    __tablename__ = "finance_transactions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    handled_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, index=True)
    # 报名/续费 | 账户充值 | 退费 | …
    item: Mapped[str] = mapped_column(String(64), default="报名/续费")
    # income | expense
    tx_type: Mapped[str] = mapped_column(String(16), default="income", index=True)
    # pending | confirmed | void
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    amount: Mapped[float] = mapped_column(Float, default=0.0)
    pay_method: Mapped[str] = mapped_column(String(64), default="")
    account: Mapped[str] = mapped_column(String(64), default="")
    handler_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    order_id: Mapped[int | None] = mapped_column(ForeignKey("finance_orders.id"), nullable=True, index=True)
    student_id: Mapped[int | None] = mapped_column(ForeignKey("students.id"), nullable=True, index=True)
    payer_name: Mapped[str] = mapped_column(String(128), default="")
    voucher: Mapped[str] = mapped_column(String(128), default="")
    flow_no: Mapped[str] = mapped_column(String(128), default="")
    remark: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    confirmed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)

class CourseConsumption(Base):
    """课消记录（点名产生）。"""

    __tablename__ = "course_consumptions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), index=True)
    class_id: Mapped[int | None] = mapped_column(ForeignKey("class_rooms.id"), nullable=True, index=True)
    course_id: Mapped[int | None] = mapped_column(ForeignKey("courses.id"), nullable=True, index=True)
    record_id: Mapped[int | None] = mapped_column(ForeignKey("class_records.id"), nullable=True, index=True)
    teacher_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    # hour_consume | …
    consume_type: Mapped[str] = mapped_column(String(32), default="课时课消")
    # roll_call | manual
    source: Mapped[str] = mapped_column(String(32), default="点名")
    hours: Mapped[float] = mapped_column(Float, default=0.0)
    amount: Mapped[float] = mapped_column(Float, default=0.0)
    # JSON: [{"package_id": 1, "hours": 1.0, "amount": 200.0}]
    package_allocations: Mapped[str] = mapped_column(Text, default="[]")
    # 课包余额不足时仍保留的欠课时，供续费与课时处理追踪。
    uncovered_hours: Mapped[float] = mapped_column(Float, default=0.0)
    consumed_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, index=True)
    # normal | void
    status: Mapped[str] = mapped_column(String(32), default="normal", index=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

class StudentAccount(Base):
    """学员账户余额。"""

    __tablename__ = "student_accounts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), unique=True, index=True)
    balance: Mapped[float] = mapped_column(Float, default=0.0)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow)

class RechargeRecord(Base):
    """账户充值记录。"""

    __tablename__ = "recharge_records"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), index=True)
    amount: Mapped[float] = mapped_column(Float, default=0.0)
    balance_after: Mapped[float] = mapped_column(Float, default=0.0)
    pay_method: Mapped[str] = mapped_column(String(64), default="微信")
    handler_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    order_id: Mapped[int | None] = mapped_column(ForeignKey("finance_orders.id"), nullable=True)
    # success | void
    status: Mapped[str] = mapped_column(String(32), default="success")
    remark: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, index=True)

class OrderOperationLog(Base):
    """订单操作日志。"""

    __tablename__ = "order_operation_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("finance_orders.id"), index=True)
    # create | view | print_receipt | void | update | other
    action: Mapped[str] = mapped_column(String(32), default="other", index=True)
    action_label: Mapped[str] = mapped_column(String(64), default="")
    detail: Mapped[str] = mapped_column(Text, default="")
    operator_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    operator_name: Mapped[str] = mapped_column(String(128), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, index=True)
