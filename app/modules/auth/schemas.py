import uuid
from typing import Optional
from pydantic import BaseModel, EmailStr, ConfigDict


class UserRegister(BaseModel):
    organization_name: str
    email: EmailStr
    password: str
    full_name: Optional[str] = None


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    email: str
    full_name: Optional[str] = None
    role: str
    is_active: bool
    model_config = ConfigDict(from_attributes=True)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
