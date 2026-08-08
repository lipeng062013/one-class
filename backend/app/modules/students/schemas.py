from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.core.phone import PhoneInputModel


class StudentCourseLink(BaseModel):
    """新建学生时关联的课程快照。"""

    id: Optional[int] = None
    name: str = Field(min_length=1, max_length=128)
    type: str = ""
    price_label: str = ""


class StudentCreate(PhoneInputModel):
    name: str = Field(min_length=1, max_length=128)
    grade: str = Field(min_length=1, max_length=64)
    school: str = ""
    phone: str = Field(min_length=11, max_length=11)
    parent_name: Optional[str] = None
    academic_manager_id: Optional[int] = None
    status: str = "active"
    source_lead_id: Optional[int] = None
    notes: str = ""
    # 建档可选关联课程；报名页新建学生不再要求，课程在报名/续费时选择
    courses: list[StudentCourseLink] = Field(default_factory=list, max_length=20)


class StudentUpdate(PhoneInputModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=128)
    grade: Optional[str] = Field(default=None, min_length=1, max_length=64)
    school: Optional[str] = None
    phone: Optional[str] = None
    parent_name: Optional[str] = None
    academic_manager_id: Optional[int] = None
    status: Optional[str] = None
    source_lead_id: Optional[int] = None
    notes: Optional[str] = None
    # 可选：编辑档案不必传；不传则保留原 linked_courses。报读在报名/续费维护。
    courses: Optional[list[StudentCourseLink]] = Field(default=None, max_length=20)


class StudentReassign(BaseModel):
    """批量转交学管师：手动勾选学生 + 目标学管师。"""

    student_ids: list[int] = Field(min_length=1)
    to_manager_id: int
    from_manager_id: Optional[int] = None  # 可选校验：仅转交该学管师名下


class StudentBulkDelete(BaseModel):
    """批量删除学生（学情记录一并删除）。"""

    student_ids: list[int] = Field(min_length=1)


class StudentOut(BaseModel):
    id: int
    name: str
    grade: str
    school: str
    phone: Optional[str] = None
    parent_name: Optional[str] = None
    academic_manager_id: Optional[int] = None
    academic_manager_name: Optional[str] = None
    status: str
    source_lead_id: Optional[int] = None
    notes: str
    linked_courses: list[dict] = Field(default_factory=list)
    created_by: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    latest_learning_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ManagerOption(BaseModel):
    id: int
    display_name: str
    username: str
    is_active: bool
    student_count: int = 0


class LearningRecordCreate(BaseModel):
    student_id: int
    class_date: Optional[datetime] = None
    class_status: str = "attended"
    subject: Optional[str] = None
    learning_summary: str = Field(min_length=1)
    homework_note: str = ""
    notes: str = ""


class LearningRecordUpdate(BaseModel):
    class_date: Optional[datetime] = None
    class_status: Optional[str] = None
    subject: Optional[str] = None
    learning_summary: Optional[str] = Field(default=None, min_length=1)
    homework_note: Optional[str] = None
    notes: Optional[str] = None


class LearningRecordFileOut(BaseModel):
    id: int
    file_path: str
    file_type: str
    sort_order: int

    model_config = {"from_attributes": True}


class LearningRecordOut(BaseModel):
    id: int
    student_id: int
    student_name: Optional[str] = None
    teacher_id: int
    teacher_name: Optional[str] = None
    class_date: Optional[datetime] = None
    class_status: str
    subject: Optional[str] = None
    learning_summary: str
    homework_note: str
    notes: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    files: list[LearningRecordFileOut] = []

    model_config = {"from_attributes": True}


STUDENT_STATUSES = {"active", "paused", "graduated", "quit"}
CLASS_STATUSES = {"attended", "absent", "late", "leave", "makeup"}


class StudentPackageUpdate(BaseModel):
    """更新课包：有效期 / 优先消耗。"""

    valid_until: Optional[date] = None
    clear_valid_until: bool = False
    priority_consume: Optional[bool] = None


class StudentCourseClose(BaseModel):
    """结课：将某课程下可用课包标记为已结课。"""

    course_id: int
    clear_remain: bool = False


class StudentPackageClearHours(BaseModel):
    """课时清零备注（可选）。"""

    remark: str = ""
