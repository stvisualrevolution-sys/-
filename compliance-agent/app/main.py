from __future__ import annotations

import csv
import json
from io import StringIO

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from .api_models import (
    AnalyzeAndNotifyRequest,
    IngestCsvResponse,
    LoginRequest,
    SignupRequest,
    TokenResponse,
)
from .auth import (
    create_access_token,
    get_current_context,
    hash_password,
    require_manager_or_owner,
    verify_password,
)
from .db import get_db
from .emailer import EmailConfigError, send_email
from .messaging import build_messages
from .settings import owner_email_default
from .models import (
    AnalysisResult,
    MonthlyReportRequest,
    MonthlyReportResponse,
    NotifyRequest,
    NotifyResponse,
)
from .orm import AnalysisLog, Membership, NotificationLog, Tenant, User
from .reporting import build_monthly_report
from .rules import analyze

app = FastAPI(title="Compliance Agent MVP", version="0.3.0")


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/v1/auth/signup", response_model=TokenResponse)
def signup(req: SignupRequest, db: Session = Depends(get_db)):
    exists = db.query(User).filter(User.email == req.email).first()
    if exists:
        raise HTTPException(status_code=400, detail="email already registered")

    tenant = Tenant(name=req.tenant_name)
    user = User(email=req.email, password_hash=hash_password(req.password), display_name=req.display_name)
    db.add_all([tenant, user])
    db.flush()

    membership = Membership(tenant_id=tenant.id, user_id=user.id, role="owner")
    db.add(membership)
    db.commit()

    token = create_access_token(user.id, tenant.id, membership.role)
    return TokenResponse(access_token=token, tenant_id=tenant.id, role=membership.role)


@app.post("/v1/auth/login", response_model=TokenResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == req.email).first()
    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=401, detail="invalid email/password")

    member = db.query(Membership).filter(Membership.user_id == user.id).first()
    if not member:
        raise HTTPException(status_code=403, detail="no tenant membership")

    token = create_access_token(user.id, member.tenant_id, member.role)
    return TokenResponse(access_token=token, tenant_id=member.tenant_id, role=member.role)


@app.post("/v1/analyze", response_model=AnalysisResult)
def analyze_endpoint(req: AnalyzeAndNotifyRequest, ctx=Depends(get_current_context), db: Session = Depends(get_db)):
    result = analyze(req.analysis_input)
    row = AnalysisLog(
        tenant_id=ctx["tenant_id"],
        driver_name=result.driver_name,
        status=result.status,
        violation_type=result.violation_type,
        details=result.details,
        action_required=result.action_required,
        evidence_json=json.dumps(result.evidence, ensure_ascii=False),
    )
    db.add(row)
    db.commit()
    return result


def _try_send_owner_email(owner_message: str | None):
    if not owner_message:
        return
    to_email = owner_email_default()
    if not to_email:
        return
    try:
        send_email("【コンプライアンス通知】WARNING/VIOLATION検知", owner_message, to_email)
    except EmailConfigError:
        pass
    except Exception:
        pass


@app.post("/v1/notify", response_model=NotifyResponse)
def notify_endpoint(req: NotifyRequest, ctx=Depends(require_manager_or_owner), db: Session = Depends(get_db)):
    msg = build_messages(req.analysis_result)

    fake_analysis = AnalysisLog(
        tenant_id=ctx["tenant_id"],
        driver_name=req.analysis_result.driver_name,
        status=req.analysis_result.status,
        violation_type=req.analysis_result.violation_type,
        details=req.analysis_result.details,
        action_required=req.analysis_result.action_required,
        evidence_json=json.dumps(req.analysis_result.evidence, ensure_ascii=False),
    )
    db.add(fake_analysis)
    db.flush()

    db.add(NotificationLog(tenant_id=ctx["tenant_id"], analysis_id=fake_analysis.id, target_type="driver", message=msg.driver_message))
    if msg.owner_message:
        db.add(NotificationLog(tenant_id=ctx["tenant_id"], analysis_id=fake_analysis.id, target_type="owner", message=msg.owner_message))
    db.commit()

    _try_send_owner_email(msg.owner_message)
    return msg


@app.post("/v1/analyze-and-notify")
def analyze_and_notify(req: AnalyzeAndNotifyRequest, ctx=Depends(get_current_context), db: Session = Depends(get_db)):
    result = analyze(req.analysis_input)
    msg = build_messages(result)

    row = AnalysisLog(
        tenant_id=ctx["tenant_id"],
        driver_name=result.driver_name,
        status=result.status,
        violation_type=result.violation_type,
        details=result.details,
        action_required=result.action_required,
        evidence_json=json.dumps(result.evidence, ensure_ascii=False),
    )
    db.add(row)
    db.flush()

    db.add(NotificationLog(tenant_id=ctx["tenant_id"], analysis_id=row.id, target_type="driver", message=msg.driver_message))
    if msg.owner_message:
        db.add(NotificationLog(tenant_id=ctx["tenant_id"], analysis_id=row.id, target_type="owner", message=msg.owner_message))
    db.commit()

    _try_send_owner_email(msg.owner_message)
    return {"analysis": result.model_dump(), "notification": msg.model_dump()}


@app.post("/v1/ingest/csv", response_model=IngestCsvResponse)
async def ingest_csv(
    file: UploadFile = File(...),
    ctx=Depends(require_manager_or_owner),
    db: Session = Depends(get_db),
):
    content = (await file.read()).decode("utf-8")
    reader = csv.DictReader(StringIO(content))

    imported = 0
    created = 0
    for r in reader:
        imported += 1
        try:
            req = AnalyzeAndNotifyRequest(
                analysis_input={
                    "driver_name": r["driver_name"],
                    "week_violation_over14h_count": int(r.get("week_violation_over14h_count", 0)),
                    "last_shift_end": r.get("last_shift_end") or None,
                    "two_day_avg_driving_minutes": int(r.get("two_day_avg_driving_minutes", 0)),
                    "weekly_driving_minutes": int(r.get("weekly_driving_minutes", 0)),
                    "events": json.loads(r["events_json"]),
                }
            )
            result = analyze(req.analysis_input)
            row = AnalysisLog(
                tenant_id=ctx["tenant_id"],
                driver_name=result.driver_name,
                status=result.status,
                violation_type=result.violation_type,
                details=result.details,
                action_required=result.action_required,
                evidence_json=json.dumps(result.evidence, ensure_ascii=False),
            )
            db.add(row)
            created += 1
        except Exception:
            continue

    db.commit()
    return IngestCsvResponse(imported_rows=imported, analyses_created=created)


@app.post("/monthly-report", response_model=MonthlyReportResponse)
def monthly_report_endpoint(req: MonthlyReportRequest):
    return build_monthly_report(req)
