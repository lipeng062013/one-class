from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class CourseCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    course_type: str = Field(default="group", pattern="^(group|one_to_one)$")
    grade: str = ""
    subject: str = ""
    term: str = ""
    billing_mode: str = "hour"
    unit_price: float = Field(default=0, ge=0)
    leave_rule: str = "no_deduct"
    absent_rule: str = "no_deduct"
    color: str = "#a16207"
    enabled: bool = True
    remark: str = ""


class CourseUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=128)
    course_type: Optional[str] = Field(default=None, pattern="^(group|one_to_one)$")
    grade: Optional[str] = None
    subject: Optional[str] = None
    term: Optional[str] = None
    billing_mode: Optional[str] = None
    unit_price: Optional[float] = Field(default=None, ge=0)
    leave_rule: Optional[str] = None
    absent_rule: Optional[str] = None
    color: Optional[str] = None
    enabled: Optional[bool] = None
    remark: Optional[str] = None


class ClassCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    mode: str = Field(default="group", pattern="^(group|one_to_one)$")
    course_id: Optional[int] = None
    capacity: Optional[int] = None
    over_capacity: bool = True
    open_count: Optional[int] = None
    category: str = ""
    hours_per_session: float = Field(default=1.0, gt=0)
    default_room: str = ""
    teacher_ids: list[int] = Field(default_factory=list)
    head_teacher_id: Optional[int] = None
    primary_student_id: Optional[int] = None
    remark: str = ""


class ClassUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    course_id: Optional[int] = None
    capacity: Optional[int] = None
    over_capacity: Optional[bool] = None
    open_count: Optional[int] = None
    category: Optional[str] = None
    hours_per_session: Optional[float] = Field(default=None, gt=0)
    default_room: Optional[str] = None
    teacher_ids: Optional[list[int]] = None
    head_teacher_id: Optional[int] = None
    student_ids: Optional[list[int]] = None
    primary_student_id: Optional[int] = None
    status: Optional[str] = None
    remark: Optional[str] = None


class ClassMembersUpdate(BaseModel):
    student_ids: list[int] = Field(default_factory=list)
    teacher_ids: list[int] = Field(default_factory=list)
    head_teacher_id: Optional[int] = None


class ClassStudentsAdd(BaseModel):
    student_ids: list[int] = Field(min_length=1)


class ScheduleCreate(BaseModel):
    class_id: int
    start_at: datetime
    end_at: datetime
    room: str = ""
    teacher_ids: list[int] = Field(default_factory=list)
    remark: str = ""
    force: bool = False


class ScheduleBatchCreate(BaseModel):
    """规则排课：按重复规则批量生成课次。"""

    class_id: int
    # 开始日期 YYYY-MM-DD
    start_date: str
    # 上课时段 HH:MM
    start_time: str
    end_time: str
    # daily | alternate | weekly | biweekly
    repeat_mode: str = Field(default="weekly", pattern="^(daily|alternate|weekly|biweekly)$")
    # by_date | by_count
    end_mode: str = Field(default="by_date", pattern="^(by_date|by_count)$")
    end_date: Optional[str] = None
    session_count: Optional[int] = Field(default=None, ge=1, le=200)
    # 每周排课日：1=周一 ... 7=周日；为空时兼容旧逻辑，按开始日期每周重复
    weekdays: list[int] = Field(default_factory=list)
    room: str = ""
    teacher_ids: list[int] = Field(default_factory=list)
    remark: str = ""
    # 冲突时：skip 跳过 | fail 整批失败 | force 强制创建
    on_conflict: str = Field(default="skip", pattern="^(skip|fail|force)$")


class ScheduleUpdate(BaseModel):
    start_at: Optional[datetime] = None
    end_at: Optional[datetime] = None
    room: Optional[str] = None
    teacher_ids: Optional[list[int]] = None
    status: Optional[str] = None
    remark: Optional[str] = None
    force: bool = False


class ScheduleBatchUpdate(BaseModel):
    """批量修改已排课次（老师请假换人、改教室等）。

    仅勾选/开启的字段会写入；未开启的字段保持各课次原值。
    上课时间仅改时刻（start_time/end_time），日期保留各课次原日期。
    修改后与课表管理共用同一 schedule 数据源，自动同步。
    """

    ids: list[int] = Field(min_length=1, max_length=200)
    # 字段开关
    update_teachers: bool = False
    update_room: bool = False
    update_remark: bool = False
    update_time: bool = False
    teacher_ids: list[int] = Field(default_factory=list)
    room: Optional[str] = None
    remark: Optional[str] = None
    # HH:MM，仅在 update_time 时生效
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    force: bool = False


class ScheduleBatchDelete(BaseModel):
    """批量删除/取消课次。"""

    ids: list[int] = Field(min_length=1, max_length=200)


class ScheduleConflictQuery(BaseModel):
    """查询老师/教室在指定时段的冲突状态。"""

    start_at: datetime
    end_at: datetime
    teacher_ids: list[int] = Field(default_factory=list)
    room: str = ""
    exclude_id: Optional[int] = None


class AttendanceIn(BaseModel):
    student_id: int
    status: str = Field(default="present", pattern="^(present|absent|leave|late)$")


class ClassRecordCreate(BaseModel):
    class_id: int
    schedule_id: Optional[int] = None
    class_start: Optional[datetime] = None
    class_end: Optional[datetime] = None
    hours: float = Field(default=1.0, gt=0)
    salary_hours: Optional[float] = Field(default=None, gt=0)
    teacher_ids: list[int] = Field(default_factory=list)
    content: str = ""
    attendances: list[AttendanceIn] = Field(default_factory=list)


class ClassRecordUpdate(BaseModel):
    class_start: Optional[datetime] = None
    class_end: Optional[datetime] = None
    hours: Optional[float] = Field(default=None, gt=0)
    salary_hours: Optional[float] = Field(default=None, gt=0)
    room: Optional[str] = None
    teacher_ids: Optional[list[int]] = None
    content: Optional[str] = None


class ClassAttendanceUpdate(BaseModel):
    status: str = Field(pattern="^(present|absent|leave|late)$")
