from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class TodoCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    content: str = ""


class TodoUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=255)
    content: Optional[str] = None
    is_done: Optional[bool] = None


class TodoOut(BaseModel):
    id: int
    user_id: int
    title: str
    content: str
    is_done: bool
    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
