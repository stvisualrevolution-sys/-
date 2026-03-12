from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from .orm import AuditEvent


def append_audit_event(db: Session, tenant_id: str, event_type: str, payload: dict) -> AuditEvent:
    last = (
        db.query(AuditEvent)
        .filter(AuditEvent.tenant_id == tenant_id)
        .order_by(AuditEvent.created_at.desc())
        .first()
    )
    prev_hash = last.event_hash if last else None
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    seed = f"{tenant_id}|{event_type}|{canonical}|{prev_hash or ''}|{datetime.now(timezone.utc).isoformat()}"
    event_hash = hashlib.sha256(seed.encode("utf-8")).hexdigest()

    row = AuditEvent(
        tenant_id=tenant_id,
        event_type=event_type,
        payload_json=canonical,
        prev_hash=prev_hash,
        event_hash=event_hash,
    )
    db.add(row)
    return row
