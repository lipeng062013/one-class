from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class GeneratePosterRequest(BaseModel):
    material_id: Optional[int] = None
    template_id: Optional[int] = None
    mode: str = "layout"  # layout | ai_image
    title: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)
    prompt: Optional[str] = None


class PosterBulkDelete(BaseModel):
    ids: list[int] = Field(min_length=1)


class GeneratedPosterOut(BaseModel):
    id: int
    material_id: Optional[int] = None
    template_id: Optional[int] = None
    mode: str
    title: str
    payload_json: str
    file_path: str
    created_by: Optional[int] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
