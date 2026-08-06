from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.core.phone import PhoneInputModel


class LeadCreate(PhoneInputModel):
    student_or_parent_name: str
    phone: str = Field(min_length=11, max_length=11)
    source: str = "other"
    referrer_name: Optional[str] = None
    channel_note: str = ""
    need: str = ""
    status: str = "new"
    next_follow_at: Optional[datetime] = None
    owner_id: Optional[int] = None
    notes: str = ""


class LeadUpdate(PhoneInputModel):
    student_or_parent_name: Optional[str] = None
    phone: Optional[str] = None
    source: Optional[str] = None
    referrer_name: Optional[str] = None
    channel_note: Optional[str] = None
    need: Optional[str] = None
    status: Optional[str] = None
    next_follow_at: Optional[datetime] = None
    owner_id: Optional[int] = None
    notes: Optional[str] = None


class LeadCollaboratorOut(BaseModel):
    id: int
    user_id: int
    name: str
    role: str
    role_label: str
    note: str = ""
    joined_at: Optional[datetime] = None
    is_owner: bool = False


class LeadOut(BaseModel):
    id: int
    student_or_parent_name: str
    phone: Optional[str] = None
    source: str
    referrer_name: Optional[str] = None
    channel_note: str
    need: str
    status: str
    next_follow_at: Optional[datetime] = None
    owner_id: Optional[int] = None
    owner_name: str = ""
    notes: str
    last_contact_at: Optional[datetime] = None
    last_contact_by: Optional[int] = None
    last_contact_by_name: str = ""
    last_contact_method: str = ""
    collaborator_count: int = 0
    followers: list[LeadCollaboratorOut] = Field(default_factory=list)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class LeadActivityCreate(BaseModel):
    content: str = Field(min_length=1, max_length=4000)
    contact_method: str = ""
    # 写跟进时可顺带更新下次跟进时间 / 状态
    next_follow_at: Optional[datetime] = None
    status: Optional[str] = None
    # 写跟进后自动加入协作（默认 true）
    join_as_collaborator: bool = True


class LeadActivityOut(BaseModel):
    id: int
    lead_id: int
    actor_id: Optional[int] = None
    actor_name: str = ""
    kind: str
    kind_label: str
    title: str
    content: str
    contact_method: str = ""
    contact_method_label: str = ""
    meta: dict = Field(default_factory=dict)
    created_at: Optional[datetime] = None


class LeadCollaboratorAdd(BaseModel):
    user_id: int
    note: str = ""


class LeadAssigneeOut(BaseModel):
    id: int
    name: str
    role: str
    role_label: str
