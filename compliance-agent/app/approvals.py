from __future__ import annotations

import hashlib
import json
import secrets
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from .orm import ApprovalRequest

WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
APP_ROOT = WORKSPACE_ROOT / "compliance-agent"

ALLOWED_ACTIONS = {
    "git_push_main": ["git", "-C", str(WORKSPACE_ROOT), "push", "-u", "origin", "main"],
    "alembic_upgrade": ["alembic", "upgrade", "head"],
}


def _sha(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def create_approval_request(db: Session, tenant_id: str, user_id: str, action: str, payload: dict, ttl_minutes: int):
    if action not in ALLOWED_ACTIONS:
        raise ValueError("unsupported action")

    code = f"{secrets.randbelow(900000)+100000}"
    now = datetime.now(timezone.utc)
    row = ApprovalRequest(
        tenant_id=tenant_id,
        requested_by_user_id=user_id,
        action=action,
        payload_json=json.dumps(payload, ensure_ascii=False),
        code_hash=_sha(code),
        status="pending",
        expires_at=now + timedelta(minutes=max(1, min(ttl_minutes, 60))),
    )
    db.add(row)
    db.flush()
    return row, code


def approve_request(db: Session, row: ApprovalRequest, approver_user_id: str, code: str):
    now = datetime.now(timezone.utc)
    if row.status != "pending":
        raise ValueError("request is not pending")
    if row.expires_at.replace(tzinfo=timezone.utc) < now:
        row.status = "expired"
        raise ValueError("request expired")
    if row.code_hash != _sha(code):
        raise ValueError("invalid code")

    row.status = "approved"
    row.approved_by_user_id = approver_user_id
    row.approved_at = now


def execute_approved_action(db: Session, row: ApprovalRequest):
    now = datetime.now(timezone.utc)
    if row.status != "approved":
        raise ValueError("request not approved")
    if row.used_at is not None:
        raise ValueError("request already used")
    if row.expires_at.replace(tzinfo=timezone.utc) < now:
        row.status = "expired"
        raise ValueError("request expired")

    cmd = ALLOWED_ACTIONS.get(row.action)
    if not cmd:
        raise ValueError("unsupported action")

    run_kwargs = {
        "capture_output": True,
        "text": True,
        "timeout": 120,
    }
    if row.action == "alembic_upgrade":
        run_kwargs["cwd"] = str(APP_ROOT)

    proc = subprocess.run(cmd, **run_kwargs)

    row.status = "used"
    row.used_at = now

    return {
        "action": row.action,
        "returncode": proc.returncode,
        "stdout": proc.stdout[-4000:],
        "stderr": proc.stderr[-4000:],
    }
