from typing import Optional

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str
    password: str


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    top_k: Optional[int] = Field(default=5, ge=3, le=5)
    session_id: Optional[str] = Field(default=None, max_length=120)
    user_type: str = Field(default="customer", pattern="^(customer|merchant_test)$")
