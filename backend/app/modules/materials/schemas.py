from pydantic import BaseModel, Field


class MaterialCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    grade: str | None = None
    subject: str | None = None
    pain_point: str | None = None
    teacher_action: str | None = None
    next_step: str | None = None
    auth_status: str = "pending"


class MaterialUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    grade: str | None = None
    subject: str | None = None
    pain_point: str | None = None
    teacher_action: str | None = None
    next_step: str | None = None
    auth_status: str | None = None
    status: str | None = None


AUTH_STATUSES = {"pending", "authorized", "denied", "anonymized"}
STATUSES = {"new", "usable", "used", "archived"}
