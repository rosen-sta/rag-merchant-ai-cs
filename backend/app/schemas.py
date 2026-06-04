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


class AftersaleCreateRequest(BaseModel):
    order_no: Optional[str] = Field(default="", max_length=80)
    customer_name: Optional[str] = Field(default="", max_length=80)
    issue_type: str = Field(default="其他", max_length=40)
    issue_description: str = Field(min_length=1, max_length=1000)
    ai_suggestion: Optional[str] = Field(default="", max_length=1000)
    needs_human: bool = True


class AftersaleStatusUpdate(BaseModel):
    status: str = Field(pattern="^(pending|processing|resolved|rejected)$")
