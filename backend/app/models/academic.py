"""教务域：课程、班级、排课、上课点名、学员课包。"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.timeutil import now as _utcnow

class Course(Base):
    """可售课程（一对一 / 一对多），定价与扣课时规则。"""

    __tablename__ = "courses"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), index=True)
    # one_to_one | group（一对多/班课）
    course_type: Mapped[str] = mapped_column(String(32), default="group", index=True)
    grade: Mapped[str] = mapped_column(String(64), default="")
    subject: Mapped[str] = mapped_column(String(64), default="")
    term: Mapped[str] = mapped_column(String(64), default="")
    # hour | month | day — 当前以 hour 为主
    billing_mode: Mapped[str] = mapped_column(String(32), default="hour")
    unit_price: Mapped[float] = mapped_column(Float, default=0.0)
    # leave: deduct | no_deduct | partial；absent: deduct | no_deduct
    leave_rule: Mapped[str] = mapped_column(String(32), default="no_deduct")
    absent_rule: Mapped[str] = mapped_column(String(32), default="no_deduct")
    color: Mapped[str] = mapped_column(String(32), default="#a16207")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    remark: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow)

class ClassRoom(Base):
    """教学班级（班课或一对一）。"""

    __tablename__ = "class_rooms"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    # group | one_to_one
    mode: Mapped[str] = mapped_column(String(32), default="group", index=True)
    course_id: Mapped[int | None] = mapped_column(ForeignKey("courses.id"), nullable=True, index=True)
    capacity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    over_capacity: Mapped[bool] = mapped_column(Boolean, default=True)
    open_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # 历史字段：在线选班/约课已下线，固定为 False
    online_select: Mapped[bool] = mapped_column(Boolean, default=False)
    category: Mapped[str] = mapped_column(String(64), default="")
    # 默认单次授课课时
    hours_per_session: Mapped[float] = mapped_column(Float, default=1.0)
    # 默认上课教室（展示用，排课可覆盖）
    default_room: Mapped[str] = mapped_column(String(128), default="")
    # 一对一主学员（可空；班课用 ClassMember）
    primary_student_id: Mapped[int | None] = mapped_column(
        ForeignKey("students.id"), nullable=True, index=True
    )
    # active | graduated | archived
    status: Mapped[str] = mapped_column(String(32), default="active", index=True)
    remark: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow)

class ClassTeacher(Base):
    __tablename__ = "class_teachers"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    class_id: Mapped[int] = mapped_column(ForeignKey("class_rooms.id"), index=True)
    teacher_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    is_head: Mapped[bool] = mapped_column(Boolean, default=False)

class ClassMember(Base):
    """班级学员。"""

    __tablename__ = "class_members"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    class_id: Mapped[int] = mapped_column(ForeignKey("class_rooms.id"), index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), index=True)
    # 本班维度剩余课时（可选，优先用 StudentCoursePackage）
    remain_hours: Mapped[float] = mapped_column(Float, default=0.0)
    joined_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    status: Mapped[str] = mapped_column(String(32), default="active")  # active | left

class ScheduleLesson(Base):
    """排课节次。"""

    __tablename__ = "schedule_lessons"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    class_id: Mapped[int] = mapped_column(ForeignKey("class_rooms.id"), index=True)
    course_id: Mapped[int | None] = mapped_column(ForeignKey("courses.id"), nullable=True, index=True)
    start_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    end_at: Mapped[datetime] = mapped_column(DateTime)
    room: Mapped[str] = mapped_column(String(128), default="")
    # scheduled | completed | cancelled
    status: Mapped[str] = mapped_column(String(32), default="scheduled", index=True)
    # JSON teacher ids
    teacher_ids: Mapped[str] = mapped_column(Text, default="[]")
    remark: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

class ClassRecord(Base):
    """上课/点名记录。"""

    __tablename__ = "class_records"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    class_id: Mapped[int] = mapped_column(ForeignKey("class_rooms.id"), index=True)
    schedule_id: Mapped[int | None] = mapped_column(
        ForeignKey("schedule_lessons.id"), nullable=True, index=True
    )
    course_id: Mapped[int | None] = mapped_column(ForeignKey("courses.id"), nullable=True, index=True)
    roll_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, index=True)
    class_start: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    class_end: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    teacher_ids: Mapped[str] = mapped_column(Text, default="[]")
    # 学员扣课基准；每位学员最终扣除仍以 ClassAttendance.hours_consumed 为准。
    hours: Mapped[float] = mapped_column(Float, default=1.0)
    # 老师薪资统计课时，独立于学员扣课。
    salary_hours: Mapped[float] = mapped_column(Float, default=1.0)
    # normal | void
    status: Mapped[str] = mapped_column(String(32), default="normal", index=True)
    content: Mapped[str] = mapped_column(Text, default="")
    # 本课合计课消金额
    amount: Mapped[float] = mapped_column(Float, default=0.0)
    present_count: Mapped[int] = mapped_column(Integer, default=0)
    total_count: Mapped[int] = mapped_column(Integer, default=0)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

class ClassAttendance(Base):
    """点名明细。"""

    __tablename__ = "class_attendances"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    record_id: Mapped[int] = mapped_column(ForeignKey("class_records.id"), index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), index=True)
    # present | absent | leave | late
    status: Mapped[str] = mapped_column(String(32), default="present")
    hours_consumed: Mapped[float] = mapped_column(Float, default=0.0)
    amount: Mapped[float] = mapped_column(Float, default=0.0)

class ClassRecordOperationLog(Base):
    """点名记录的创建、课次编辑和名单变更日志。"""

    __tablename__ = "class_record_operation_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    record_id: Mapped[int] = mapped_column(ForeignKey("class_records.id"), index=True)
    action: Mapped[str] = mapped_column(String(32), default="update", index=True)
    action_label: Mapped[str] = mapped_column(String(64), default="")
    detail: Mapped[str] = mapped_column(Text, default="")
    operator_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, index=True)

class StudentCoursePackage(Base):
    """学员购课课包（报名/续费写入，点名扣减）。"""

    __tablename__ = "student_course_packages"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), index=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), index=True)
    enrollment_id: Mapped[int | None] = mapped_column(
        ForeignKey("enrollment_records.id"), nullable=True, index=True
    )
    purchased_hours: Mapped[float] = mapped_column(Float, default=0.0)
    gift_hours: Mapped[float] = mapped_column(Float, default=0.0)
    total_hours: Mapped[float] = mapped_column(Float, default=0.0)
    remain_hours: Mapped[float] = mapped_column(Float, default=0.0)
    unit_price: Mapped[float] = mapped_column(Float, default=0.0)
    valid_until: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    # active | exhausted | refunded
    status: Mapped[str] = mapped_column(String(32), default="active", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow)
