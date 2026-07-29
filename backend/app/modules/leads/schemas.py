from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class LeadCreate(BaseModel):
    student_or_parent_name: str
    phone: Optional[str] = None
    source: str = "other"
    referrer_name: Optional[str] = None
    channel_note: str = ""
    need: str = ""
    status: str = "new"
    next_follow_at: Optional[datetime] = None
    owner_id: Optional[int] = None
    notes: str = ""


class LeadUpdate(BaseModel):
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
    notes: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
