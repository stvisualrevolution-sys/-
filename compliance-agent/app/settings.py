from __future__ import annotations

import os


def owner_email_default() -> str | None:
    return os.getenv("OWNER_EMAIL")
