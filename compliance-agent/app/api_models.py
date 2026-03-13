from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, EmailStr, Field

from .models import AnalyzeRequest


class SignupRequest(BaseModel):
    email: EmailStr
    password: str
    display_name: Optional[str] = None
    tenant_name: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    tenant_id: str
    role: str


class AnalyzeAndNotifyRequest(BaseModel):
    analysis_input: AnalyzeRequest


class IngestCsvResponse(BaseModel):
    imported_rows: int
    analyses_created: int


class BillingCheckoutRequest(BaseModel):
    price_id: str
    success_url: str
    cancel_url: str


class BillingCheckoutResponse(BaseModel):
    checkout_url: str


class ApprovalCreateRequest(BaseModel):
    action: str
    payload: dict = Field(default_factory=dict)
    ttl_minutes: int = 15


class ApprovalCreateResponse(BaseModel):
    approval_id: str
    action: str
    expires_at: str
    approval_code: str


class ApprovalApproveRequest(BaseModel):
    approval_id: str
    approval_code: str


class ApprovalExecuteRequest(BaseModel):
    approval_id: str


class ApprovalRequestAndSendResponse(BaseModel):
    approval_id: str
    action: str
    expires_at: str
    sent_to_telegram: bool
