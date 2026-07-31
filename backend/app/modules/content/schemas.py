from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class GenerateCopyRequest(BaseModel):
    material_id: Optional[int] = None
    template_id: Optional[int] = None
    mode: str = "template"  # template | llm | template_then_llm
    platform: str = "xhs"
    extra_instruction: Optional[str] = None


class GeneratedCopyUpdate(BaseModel):
    title: Optional[str] = None
    body: Optional[str] = None


class CopyBulkDelete(BaseModel):
    ids: list[int] = Field(min_length=1)


class GeneratedCopyOut(BaseModel):
    id: int
    material_id: Optional[int] = None
    template_id: Optional[int] = None
    mode: str
    platform: str
    title: str
    body: str
    prompt_snapshot: Optional[str] = None
    model_name: Optional[str] = None
    created_by: Optional[int] = None
    created_at: Optional[datetime] = None
    banned_hits: list[str] = Field(default_factory=list)
    llm_error: Optional[str] = None

    model_config = {"from_attributes": True}
