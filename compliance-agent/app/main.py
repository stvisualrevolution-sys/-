from __future__ import annotations

import csv
import json
from datetime import datetime, timedelta, timezone
from io import StringIO
from pathlib import Path
from typing import List

import os

from fastapi import Depends, FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, Response
from sqlalchemy.orm import Session

from .api_models import (
    AnalyzeAndNotifyRequest,
    ApprovalApproveRequest,
    ApprovalCreateRequest,
    ApprovalCreateResponse,
    ApprovalExecuteRequest,
    ApprovalRequestAndSendResponse,
    BillingCheckoutRequest,
    BillingCheckoutResponse,
    IngestAlert,
    IngestCsvError,
    IngestCsvResponse,
    LoginRequest,
    PublicCheckoutRequest,
    SignupRequest,
    TokenResponse,
)
from .approval_links import sign as sign_approval_link, verify as verify_approval_link
from .approvals import create_approval_request, approve_request, execute_approved_action
from .audit import append_audit_event
from .billing import create_checkout_session, create_one_time_checkout_session, get_billing_config
from .auth import (
    create_access_token,
    get_current_context,
    hash_password,
    require_manager_or_owner,
    verify_password,
)
from .db import get_db
from .emailer import EmailConfigError, send_email
from .csv_report import build_error_csv
from .messaging import build_messages
from .pdf_report import build_signed_report_pdf
from .settings import owner_email_default
from .telegram_notify import send_approval_buttons
from .models import (
    AnalysisResult,
    MonthlyReportRequest,
    MonthlyReportResponse,
    NotifyRequest,
    NotifyResponse,
)
from .orm import AnalysisLog, ApprovalRequest, AuditEvent, Membership, NotificationLog, Subscription, Tenant, User
from .reporting import build_monthly_report
from .rules import analyze

app = FastAPI(title="Compliance Agent MVP", version="0.4.0")
WEB_DIR = Path(__file__).resolve().parent.parent / "web"
SAMPLES_DIR = Path(__file__).resolve().parent.parent / "samples"
LANDING_DIR = Path(__file__).resolve().parent.parent / "landing"
DOWNLOAD_DIR = Path(__file__).resolve().parent.parent / "download"


@app.get("/", response_class=HTMLResponse)
def web_index():
    index = WEB_DIR / "index.html"
    if not index.exists():
        return HTMLResponse("<h1>Compliance Agent</h1><p>web/index.html not found</p>", status_code=200)
    return HTMLResponse(index.read_text(encoding="utf-8"), status_code=200)


@app.get("/landing", response_class=HTMLResponse)
def landing_home():
    p = LANDING_DIR / "index.html"
    if not p.exists():
        raise HTTPException(status_code=404, detail="landing page not found")
    return HTMLResponse(p.read_text(encoding="utf-8"), status_code=200)


@app.get("/landing/checkout.html", response_class=HTMLResponse)
def landing_checkout():
    p = LANDING_DIR / "checkout.html"
    if not p.exists():
        raise HTTPException(status_code=404, detail="checkout page not found")
    return HTMLResponse(p.read_text(encoding="utf-8"), status_code=200)


@app.get("/landing/success.html", response_class=HTMLResponse)
def landing_success():
    p = LANDING_DIR / "success.html"
    if not p.exists():
        raise HTTPException(status_code=404, detail="success page not found")
    return HTMLResponse(p.read_text(encoding="utf-8"), status_code=200)


@app.get("/download/drivecheck-local.zip")
def download_zip():
    p = DOWNLOAD_DIR / "drivecheck-local.zip"
    if not p.exists():
        raise HTTPException(status_code=404, detail="release zip not found")
    return FileResponse(path=str(p), media_type="application/zip", filename="drivecheck-local.zip")


@app.get("/download/QUICKSTART.md")
def download_quickstart():
    p = DOWNLOAD_DIR / "QUICKSTART.md"
    if not p.exists():
        raise HTTPException(status_code=404, detail="quickstart not found")
    return FileResponse(path=str(p), media_type="text/markdown", filename="QUICKSTART.md")


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/sample/ingest-template.csv")
def sample_ingest_template():
    p = SAMPLES_DIR / "ingest_template.csv"
    if not p.exists():
        raise HTTPException(status_code=404, detail="template not found")
    return FileResponse(path=str(p), media_type="text/csv", filename="ingest_template.csv")


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
    sub = Subscription(tenant_id=tenant.id, plan_code="starter", status="trialing")
    db.add_all([membership, sub])
    db.commit()

    token = create_access_token(user.id, tenant.id, membership.role)
    return TokenResponse(access_token=token, tenant_id=tenant.id, role=membership.role)


@app.post("/v1/auth/login", response_model=TokenResponse)
async def login(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    email = form.get("email") or form.get("username")
    password = form.get("password") or ""

    if not email:
        raise HTTPException(status_code=422, detail="email/username is required")

    user = db.query(User).filter(User.email == str(email)).first()
    if not user or not verify_password(str(password), user.password_hash):
        raise HTTPException(status_code=401, detail="invalid email/password")

    member = db.query(Membership).filter(Membership.user_id == user.id).first()
    if not member:
        raise HTTPException(status_code=403, detail="no tenant membership")

    token = create_access_token(user.id, member.tenant_id, member.role)
    return TokenResponse(access_token=token, tenant_id=member.tenant_id, role=member.role)


@app.post("/v1/auth/login-json", response_model=TokenResponse)
def login_json(req: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == req.email).first()
    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=401, detail="invalid email/password")

    member = db.query(Membership).filter(Membership.user_id == user.id).first()
    if not member:
        raise HTTPException(status_code=403, detail="no tenant membership")

    token = create_access_token(user.id, member.tenant_id, member.role)
    return TokenResponse(access_token=token, tenant_id=member.tenant_id, role=member.role)


@app.post("/v1/approvals/request", response_model=ApprovalCreateResponse)
def approvals_request(req: ApprovalCreateRequest, ctx=Depends(require_manager_or_owner), db: Session = Depends(get_db)):
    try:
        row, code = create_approval_request(
            db,
            tenant_id=ctx["tenant_id"],
            user_id=ctx["user"].id,
            action=req.action,
            payload=req.payload,
            ttl_minutes=req.ttl_minutes,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    append_audit_event(db, ctx["tenant_id"], "approval.requested", {"approval_id": row.id, "action": req.action})
    db.commit()
    return ApprovalCreateResponse(
        approval_id=row.id,
        action=row.action,
        expires_at=row.expires_at.isoformat(),
        approval_code=code,
    )


@app.post("/v1/approvals/request-and-send", response_model=ApprovalRequestAndSendResponse)
def approvals_request_and_send(req: ApprovalCreateRequest, ctx=Depends(require_manager_or_owner), db: Session = Depends(get_db)):
    try:
        row, code = create_approval_request(
            db,
            tenant_id=ctx["tenant_id"],
            user_id=ctx["user"].id,
            action=req.action,
            payload=req.payload,
            ttl_minutes=req.ttl_minutes,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"unsupported action: use one of [git_push_main, alembic_upgrade]")

    base_url = os.getenv("PUBLIC_BASE_URL", "http://localhost:8088")
    approve_token = sign_approval_link(row.id, code, "approve_execute")
    reject_token = sign_approval_link(row.id, code, "reject")
    approve_url = f"{base_url}/v1/approvals/quick?action=approve_execute&approval_id={row.id}&code={code}&token={approve_token}"
    reject_url = f"{base_url}/v1/approvals/quick?action=reject&approval_id={row.id}&code={code}&token={reject_token}"

    sent = send_approval_buttons(
        message=f"承認リクエスト: {row.action}\nID: {row.id}\n有効期限: {row.expires_at.isoformat()}",
        approve_url=approve_url,
        reject_url=reject_url,
    )

    append_audit_event(db, ctx["tenant_id"], "approval.requested", {
        "approval_id": row.id,
        "action": req.action,
        "sent_to_telegram": bool(sent),
    })
    db.commit()

    return ApprovalRequestAndSendResponse(
        approval_id=row.id,
        action=row.action,
        expires_at=row.expires_at.isoformat(),
        sent_to_telegram=bool(sent),
    )


@app.get("/v1/approvals/quick", response_class=HTMLResponse)
def approvals_quick(
    action: str = Query(..., pattern="^(approve_execute|reject)$"),
    approval_id: str = Query(...),
    code: str = Query(...),
    token: str = Query(...),
    db: Session = Depends(get_db),
):
    if not verify_approval_link(approval_id, code, action, token):
        return HTMLResponse("<h3>Invalid approval link</h3>", status_code=403)

    row = db.query(ApprovalRequest).filter(ApprovalRequest.id == approval_id).first()
    if not row:
        return HTMLResponse("<h3>Approval request not found</h3>", status_code=404)

    if action == "reject":
        row.status = "rejected"
        append_audit_event(db, row.tenant_id, "approval.rejected", {"approval_id": row.id, "via": "quick_link"})
        db.commit()
        return HTMLResponse("<h3>却下しました。</h3>", status_code=200)

    try:
        approve_request(db, row, approver_user_id=row.requested_by_user_id, code=code)
        result = execute_approved_action(db, row)
    except ValueError as e:
        return HTMLResponse(f"<h3>承認失敗: {str(e)}</h3>", status_code=400)

    append_audit_event(db, row.tenant_id, "approval.executed", {
        "approval_id": row.id,
        "action": row.action,
        "via": "quick_link",
        "returncode": result["returncode"],
    })
    db.commit()

    if result["returncode"] == 0:
        return HTMLResponse("<h3>承認して実行しました ✅</h3>", status_code=200)
    return HTMLResponse("<h3>承認したが実行でエラーが発生しました。</h3>", status_code=500)


@app.post("/v1/approvals/approve")
def approvals_approve(req: ApprovalApproveRequest, ctx=Depends(get_current_context), db: Session = Depends(get_db)):
    if ctx["role"] != "owner":
        raise HTTPException(status_code=403, detail="only owner can approve")

    row = (
        db.query(ApprovalRequest)
        .filter(ApprovalRequest.id == req.approval_id, ApprovalRequest.tenant_id == ctx["tenant_id"])
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="approval request not found")

    try:
        approve_request(db, row, approver_user_id=ctx["user"].id, code=req.approval_code)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    append_audit_event(db, ctx["tenant_id"], "approval.approved", {"approval_id": row.id, "action": row.action})
    db.commit()
    return {"ok": True, "approval_id": row.id, "status": row.status}


@app.post("/v1/approvals/execute")
def approvals_execute(req: ApprovalExecuteRequest, ctx=Depends(require_manager_or_owner), db: Session = Depends(get_db)):
    row = (
        db.query(ApprovalRequest)
        .filter(ApprovalRequest.id == req.approval_id, ApprovalRequest.tenant_id == ctx["tenant_id"])
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="approval request not found")

    try:
        result = execute_approved_action(db, row)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    append_audit_event(db, ctx["tenant_id"], "approval.executed", {
        "approval_id": row.id,
        "action": row.action,
        "returncode": result["returncode"],
    })
    db.commit()
    return result


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
    append_audit_event(db, ctx["tenant_id"], "analysis.created", {
        "driver_name": result.driver_name,
        "status": result.status,
        "violation_type": result.violation_type,
    })
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

    append_audit_event(db, ctx["tenant_id"], "notification.created", {
        "driver_name": req.analysis_result.driver_name,
        "status": req.analysis_result.status,
        "owner_message": bool(msg.owner_message),
    })
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

    append_audit_event(db, ctx["tenant_id"], "analysis_and_notify.completed", {
        "driver_name": result.driver_name,
        "status": result.status,
        "owner_message": bool(msg.owner_message),
    })
    db.commit()

    _try_send_owner_email(msg.owner_message)
    return {"analysis": result.model_dump(), "notification": msg.model_dump()}


def _parse_csv_rows(content: str):
    reader = csv.DictReader(StringIO(content))
    required_cols = {
        "driver_name",
        "week_violation_over14h_count",
        "last_shift_end",
        "two_day_avg_driving_minutes",
        "weekly_driving_minutes",
        "events_json",
    }
    if not reader.fieldnames or not required_cols.issubset(set(reader.fieldnames)):
        raise HTTPException(
            status_code=400,
            detail={
                "message": "CSV header is invalid",
                "required_columns": sorted(list(required_cols)),
                "received_columns": reader.fieldnames or [],
            },
        )
    return reader


@app.post("/v1/ingest/csv", response_model=IngestCsvResponse)
async def ingest_csv(
    file: UploadFile = File(...),
    ctx=Depends(require_manager_or_owner),
    db: Session = Depends(get_db),
):
    content = (await file.read()).decode("utf-8")
    reader = _parse_csv_rows(content)

    imported = 0
    created = 0
    errors: List[IngestCsvError] = []
    alerts: List[IngestAlert] = []

    for idx, r in enumerate(reader, start=2):  # header is line 1
        imported += 1
        try:
            req = AnalyzeAndNotifyRequest(
                analysis_input={
                    "driver_name": (r.get("driver_name") or "").strip(),
                    "week_violation_over14h_count": int(r.get("week_violation_over14h_count", 0)),
                    "last_shift_end": r.get("last_shift_end") or None,
                    "two_day_avg_driving_minutes": int(r.get("two_day_avg_driving_minutes", 0)),
                    "weekly_driving_minutes": int(r.get("weekly_driving_minutes", 0)),
                    "events": json.loads(r.get("events_json") or "[]"),
                }
            )
            if not req.analysis_input.driver_name:
                raise ValueError("driver_name is empty")

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
            if result.status in {"WARNING", "VIOLATION"}:
                alerts.append(IngestAlert(
                    driver_name=result.driver_name,
                    status=result.status,
                    violation_type=result.violation_type,
                    details=result.details,
                    action_required=result.action_required,
                ))
        except Exception as e:
            errors.append(IngestCsvError(row_number=idx, reason=str(e)))
            continue

    append_audit_event(db, ctx["tenant_id"], "ingest.csv", {
        "imported_rows": imported,
        "analyses_created": created,
        "failed_rows": len(errors),
        "filename": file.filename,
    })
    db.commit()
    return IngestCsvResponse(
        imported_rows=imported,
        analyses_created=created,
        failed_rows=len(errors),
        notifications_created=0,
        errors=errors[:100],
        alerts=alerts[:100],
    )


@app.post("/v1/ingest/csv-analyze-notify", response_model=IngestCsvResponse)
async def ingest_csv_analyze_notify(
    file: UploadFile = File(...),
    ctx=Depends(require_manager_or_owner),
    db: Session = Depends(get_db),
):
    content = (await file.read()).decode("utf-8")
    reader = _parse_csv_rows(content)

    imported = 0
    created = 0
    notified = 0
    errors: List[IngestCsvError] = []
    alerts: List[IngestAlert] = []

    for idx, r in enumerate(reader, start=2):
        imported += 1
        try:
            req = AnalyzeAndNotifyRequest(
                analysis_input={
                    "driver_name": (r.get("driver_name") or "").strip(),
                    "week_violation_over14h_count": int(r.get("week_violation_over14h_count", 0)),
                    "last_shift_end": r.get("last_shift_end") or None,
                    "two_day_avg_driving_minutes": int(r.get("two_day_avg_driving_minutes", 0)),
                    "weekly_driving_minutes": int(r.get("weekly_driving_minutes", 0)),
                    "events": json.loads(r.get("events_json") or "[]"),
                }
            )
            if not req.analysis_input.driver_name:
                raise ValueError("driver_name is empty")

            result = analyze(req.analysis_input)
            msg = build_messages(result)
            if result.status in {"WARNING", "VIOLATION"}:
                alerts.append(IngestAlert(
                    driver_name=result.driver_name,
                    status=result.status,
                    violation_type=result.violation_type,
                    details=result.details,
                    action_required=result.action_required,
                ))

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
            created += 1

            db.add(NotificationLog(tenant_id=ctx["tenant_id"], analysis_id=row.id, target_type="driver", message=msg.driver_message))
            notified += 1
            if msg.owner_message:
                db.add(NotificationLog(tenant_id=ctx["tenant_id"], analysis_id=row.id, target_type="owner", message=msg.owner_message))
                notified += 1
                _try_send_owner_email(msg.owner_message)

        except Exception as e:
            errors.append(IngestCsvError(row_number=idx, reason=str(e)))
            continue

    append_audit_event(db, ctx["tenant_id"], "ingest.csv_analyze_notify", {
        "imported_rows": imported,
        "analyses_created": created,
        "notifications_created": notified,
        "failed_rows": len(errors),
        "filename": file.filename,
    })
    db.commit()

    return IngestCsvResponse(
        imported_rows=imported,
        analyses_created=created,
        failed_rows=len(errors),
        notifications_created=notified,
        errors=errors[:100],
        alerts=alerts[:100],
    )


@app.post("/v1/ingest/csv-errors-report")
async def ingest_csv_errors_report(
    file: UploadFile = File(...),
    ctx=Depends(require_manager_or_owner),
    db: Session = Depends(get_db),
):
    content = (await file.read()).decode("utf-8")
    reader = _parse_csv_rows(content)

    errors: List[IngestCsvError] = []
    for idx, r in enumerate(reader, start=2):
        try:
            req = AnalyzeAndNotifyRequest(
                analysis_input={
                    "driver_name": (r.get("driver_name") or "").strip(),
                    "week_violation_over14h_count": int(r.get("week_violation_over14h_count", 0)),
                    "last_shift_end": r.get("last_shift_end") or None,
                    "two_day_avg_driving_minutes": int(r.get("two_day_avg_driving_minutes", 0)),
                    "weekly_driving_minutes": int(r.get("weekly_driving_minutes", 0)),
                    "events": json.loads(r.get("events_json") or "[]"),
                }
            )
            if not req.analysis_input.driver_name:
                raise ValueError("driver_name is empty")
            _ = analyze(req.analysis_input)
        except Exception as e:
            errors.append(IngestCsvError(row_number=idx, reason=str(e)))

    csv_text = build_error_csv(errors)
    append_audit_event(db, ctx["tenant_id"], "ingest.csv_errors_report", {
        "failed_rows": len(errors),
        "filename": file.filename,
    })
    db.commit()

    return Response(
        content=csv_text,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="ingest-errors.csv"'},
    )


@app.get("/v1/analyses")
def list_analyses(limit: int = 50, ctx=Depends(get_current_context), db: Session = Depends(get_db)):
    rows = (
        db.query(AnalysisLog)
        .filter(AnalysisLog.tenant_id == ctx["tenant_id"])
        .order_by(AnalysisLog.created_at.desc())
        .limit(max(1, min(limit, 200)))
        .all()
    )
    return [
        {
            "id": r.id,
            "driver_name": r.driver_name,
            "status": r.status,
            "violation_type": r.violation_type,
            "details": r.details,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


@app.post("/v1/public/create-checkout", response_model=BillingCheckoutResponse)
def public_create_checkout(req: PublicCheckoutRequest):
    one_time_price_id = os.getenv("STRIPE_ONE_TIME_PRICE_ID")
    if not one_time_price_id:
        raise HTTPException(status_code=500, detail="STRIPE_ONE_TIME_PRICE_ID is not configured")
    try:
        url = create_one_time_checkout_session(req.email, one_time_price_id, req.success_url, req.cancel_url)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return BillingCheckoutResponse(checkout_url=url)


@app.post("/v1/billing/checkout", response_model=BillingCheckoutResponse)
def billing_checkout(req: BillingCheckoutRequest, ctx=Depends(require_manager_or_owner), db: Session = Depends(get_db)):
    email = ctx["user"].email
    url = create_checkout_session(email, req.price_id, req.success_url, req.cancel_url)
    append_audit_event(db, ctx["tenant_id"], "billing.checkout_created", {"price_id": req.price_id, "email": email})
    db.commit()
    return BillingCheckoutResponse(checkout_url=url)


@app.post("/v1/billing/webhook")
async def billing_webhook(request: Request, db: Session = Depends(get_db)):
    cfg = get_billing_config()
    if not cfg.secret_key or not cfg.webhook_secret:
        raise HTTPException(status_code=500, detail="stripe webhook not configured")

    import stripe

    stripe.api_key = cfg.secret_key
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, cfg.webhook_secret)
    except Exception:
        raise HTTPException(status_code=400, detail="invalid stripe signature")

    event_type = event.get("type")
    obj = event.get("data", {}).get("object", {})

    if event_type in {"checkout.session.completed", "customer.subscription.updated", "customer.subscription.created"}:
        customer_id = obj.get("customer")
        subscription_id = obj.get("subscription")
        status = obj.get("status", "active")

        row = db.query(Subscription).filter(Subscription.stripe_customer_id == customer_id).first()
        if not row:
            row = db.query(Subscription).filter(Subscription.stripe_subscription_id == subscription_id).first()
        if not row and event_type == "checkout.session.completed":
            customer_email = obj.get("customer_details", {}).get("email") or obj.get("customer_email")
            if customer_email:
                user = db.query(User).filter(User.email == customer_email).first()
                if user:
                    member = db.query(Membership).filter(Membership.user_id == user.id).first()
                    if member:
                        row = db.query(Subscription).filter(Subscription.tenant_id == member.tenant_id).first()

        if row:
            row.stripe_customer_id = customer_id or row.stripe_customer_id
            row.stripe_subscription_id = subscription_id or row.stripe_subscription_id
            row.status = status
            row.updated_at = datetime.utcnow()
            append_audit_event(db, row.tenant_id, "billing.subscription_updated", {
                "event_type": event_type,
                "customer_id": customer_id,
                "subscription_id": subscription_id,
                "status": status,
            })
            db.commit()

    return {"received": True}


@app.get("/v1/reports/monthly/pdf")
def monthly_report_pdf(month: str, ctx=Depends(get_current_context), db: Session = Depends(get_db)):
    rows = (
        db.query(AnalysisLog)
        .filter(AnalysisLog.tenant_id == ctx["tenant_id"])
        .order_by(AnalysisLog.created_at.desc())
        .limit(500)
        .all()
    )

    # monthは将来的にcreated_atで厳密filterする。今はMVPとして直近データを使用
    md_lines = [f"# {month} 月次コンプライアンス報告（MVP）", ""]
    for r in rows[:150]:
        md_lines.append(f"- {r.created_at}: {r.driver_name} / {r.status} / {r.violation_type} / {r.details}")

    md = "\n".join(md_lines)
    pdf_bytes, meta = build_signed_report_pdf(md, ctx["tenant_id"], month)

    append_audit_event(db, ctx["tenant_id"], "report.pdf_generated", {"month": month, **meta})
    db.commit()

    return Response(content=pdf_bytes, media_type="application/pdf", headers={
        "Content-Disposition": f'attachment; filename="compliance-report-{month}.pdf"',
        "X-Report-SHA256": meta["sha256"],
    })


@app.get("/v1/kpi/summary")
def kpi_summary(ctx=Depends(get_current_context), db: Session = Depends(get_db)):
    tenant_id = ctx["tenant_id"]
    since = datetime.now(timezone.utc) - timedelta(days=30)

    all_rows = db.query(AnalysisLog).filter(AnalysisLog.tenant_id == tenant_id).all()
    month_rows = [r for r in all_rows if r.created_at and r.created_at.replace(tzinfo=timezone.utc) >= since]

    def _count(rows, status):
        return sum(1 for r in rows if r.status == status)

    total = len(month_rows)
    safe = _count(month_rows, "SAFE")
    warning = _count(month_rows, "WARNING")
    violation = _count(month_rows, "VIOLATION")

    notification_count = (
        db.query(NotificationLog)
        .filter(NotificationLog.tenant_id == tenant_id)
        .count()
    )
    audit_count = db.query(AuditEvent).filter(AuditEvent.tenant_id == tenant_id).count()

    return {
        "window": "last_30_days",
        "analysis_total": total,
        "safe": safe,
        "warning": warning,
        "violation": violation,
        "compliance_rate": round((safe / total * 100), 2) if total else 0.0,
        "notification_total_all_time": notification_count,
        "audit_events_all_time": audit_count,
    }


@app.get("/v1/audit/chain")
def audit_chain(limit: int = 50, ctx=Depends(require_manager_or_owner), db: Session = Depends(get_db)):
    rows = (
        db.query(AuditEvent)
        .filter(AuditEvent.tenant_id == ctx["tenant_id"])
        .order_by(AuditEvent.created_at.desc())
        .limit(max(1, min(limit, 200)))
        .all()
    )
    return [
        {
            "id": r.id,
            "event_type": r.event_type,
            "prev_hash": r.prev_hash,
            "event_hash": r.event_hash,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


@app.post("/monthly-report", response_model=MonthlyReportResponse)
def monthly_report_endpoint(req: MonthlyReportRequest):
    return build_monthly_report(req)
