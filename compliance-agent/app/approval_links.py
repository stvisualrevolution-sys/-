from __future__ import annotations

import hashlib
import hmac
import os


def _secret() -> str:
    return os.getenv("APPROVAL_LINK_SECRET", "change-this")


def sign(approval_id: str, approval_code: str, action: str) -> str:
    msg = f"{approval_id}:{approval_code}:{action}".encode("utf-8")
    return hmac.new(_secret().encode("utf-8"), msg, hashlib.sha256).hexdigest()


def verify(approval_id: str, approval_code: str, action: str, token: str) -> bool:
    expected = sign(approval_id, approval_code, action)
    return hmac.compare_digest(expected, token)
