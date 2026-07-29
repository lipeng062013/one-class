from pydantic import BaseModel, Field


class UserCreate(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    display_name: str = Field(min_length=1, max_length=128)
    role: str
    password: str = Field(min_length=6, max_length=128)


class UserUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=128)
    role: str | None = None
    is_active: bool | None = None


class ResetPasswordRequest(BaseModel):
    new_password: str = Field(min_length=6, max_length=128)


class UserPublic(BaseModel):
    id: int
    username: str
    display_name: str
    role: str
    is_active: bool
    created_at: str | None = None

    model_config = {"from_attributes": True}
