from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from io import BytesIO

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas


def build_signed_report_pdf(markdown_text: str, tenant_id: str, month: str) -> tuple[bytes, dict]:
    generated_at = datetime.now(timezone.utc).isoformat()
    canonical = f"tenant={tenant_id}\nmonth={month}\ngenerated_at={generated_at}\n\n{markdown_text}"
    sha256 = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    width, height = A4

    y = height - 40
    c.setFont("Helvetica-Bold", 14)
    c.drawString(40, y, f"Compliance Monthly Report - {month}")
    y -= 24
    c.setFont("Helvetica", 9)
    c.drawString(40, y, f"Tenant: {tenant_id}")
    y -= 14
    c.drawString(40, y, f"GeneratedAt(UTC): {generated_at}")
    y -= 14
    c.drawString(40, y, f"Integrity SHA256: {sha256}")
    y -= 20

    c.setFont("Helvetica", 10)
    for line in markdown_text.splitlines():
        if y < 40:
            c.showPage()
            c.setFont("Helvetica", 10)
            y = height - 40
        c.drawString(40, y, line[:140])
        y -= 12

    c.save()
    pdf_bytes = buf.getvalue()
    buf.close()
    return pdf_bytes, {"sha256": sha256, "generated_at": generated_at}
