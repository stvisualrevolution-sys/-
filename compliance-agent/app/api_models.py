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


class IngestCsvError(BaseModel):
    row_number: int
    reason: str


class IngestAlert(BaseModel):
    driver_name: str
    status: str
    violation_type: str
    details: str
    action_required: str


class IngestCsvResponse(BaseModel):
    imported_rows: int
    analyses_created: int
    failed_rows: int
    notifications_created: int = 0
    errors: list[IngestCsvError] = Field(default_factory=list)
    alerts: list[IngestAlert] = Field(default_factory=list)


class BillingCheckoutRequest(BaseModel):
    price_id: str
    success_url: str
    cancel_url: str


class BillingCheckoutResponse(BaseModel):
    checkout_url: str


class PublicCheckoutRequest(BaseModel):
    email: EmailStr
    success_url: str
    cancel_url: str


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
