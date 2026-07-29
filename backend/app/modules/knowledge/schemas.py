from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class KnowledgeCreate(BaseModel):
    category: str
    title: str = ""
    content: str = ""
    tags: str = ""
    is_active: bool = True


class KnowledgeUpdate(BaseModel):
    category: Optional[str] = None
    title: Optional[str] = None
    content: Optional[str] = None
    tags: Optional[str] = None
    is_active: Optional[bool] = None


class KnowledgeOut(BaseModel):
    id: int
    category: str
    title: str
    content: str
    tags: str
    is_active: bool
    updated_by: Optional[int] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
