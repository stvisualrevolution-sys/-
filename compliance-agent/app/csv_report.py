from __future__ import annotations

import csv
from io import StringIO
from typing import Iterable

from .api_models import IngestCsvError


def build_error_csv(errors: Iterable[IngestCsvError]) -> str:
    buf = StringIO()
    w = csv.writer(buf)
    w.writerow(["row_number", "reason"])
    for e in errors:
        w.writerow([e.row_number, e.reason])
    return buf.getvalue()
