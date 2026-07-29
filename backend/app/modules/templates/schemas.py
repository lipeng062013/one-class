from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class CopyTemplateCreate(BaseModel):
    name: str
    scene: str
    body: str = ""
    is_active: bool = True


class CopyTemplateUpdate(BaseModel):
    name: Optional[str] = None
    scene: Optional[str] = None
    body: Optional[str] = None
    is_active: Optional[bool] = None


class CopyTemplateOut(BaseModel):
    id: int
    name: str
    scene: str
    body: str
    is_system: bool
    is_active: bool
    created_by: Optional[int] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class PosterTemplateCreate(BaseModel):
    name: str
    scene: str
    layout_json: str = "{}"
    preview_path: Optional[str] = None
    is_active: bool = True


class PosterTemplateUpdate(BaseModel):
    name: Optional[str] = None
    scene: Optional[str] = None
    layout_json: Optional[str] = None
    preview_path: Optional[str] = None
    is_active: Optional[bool] = None


class PosterTemplateOut(BaseModel):
    id: int
    name: str
    scene: str
    layout_json: str
    preview_path: Optional[str] = None
    is_system: bool
    is_active: bool
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
