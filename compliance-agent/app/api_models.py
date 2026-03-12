from __future__ import annotations

from pydantic import BaseModel, EmailStr

from .models import AnalyzeRequest


class SignupRequest(BaseModel):
    email: EmailStr
    password: str
    display_name: str | None = None
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
