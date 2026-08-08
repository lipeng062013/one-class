from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=6, max_length=128)


class ForgotPasswordRequest(BaseModel):
    """Unauthenticated password-reset request (notifies admins)."""

    username: str = Field(min_length=1, max_length=64)
    note: str = Field(default="", max_length=200)


class UserOut(BaseModel):
    id: int
    username: str
    display_name: str
    role: str
    is_active: bool
    permissions: list[str] = []
    extra_permissions: list[str] = []

    model_config = {"from_attributes": True}
