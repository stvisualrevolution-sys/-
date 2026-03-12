from __future__ import annotations

from fastapi import FastAPI

from .messaging import build_messages
from .models import (
    AnalyzeRequest,
    AnalysisResult,
    MonthlyReportRequest,
    MonthlyReportResponse,
    NotifyRequest,
    NotifyResponse,
)
from .reporting import build_monthly_report
from .rules import analyze

app = FastAPI(title="Compliance Agent MVP", version="0.1.0")


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/analyze", response_model=AnalysisResult)
def analyze_endpoint(req: AnalyzeRequest):
    return analyze(req)


@app.post("/notify", response_model=NotifyResponse)
def notify_endpoint(req: NotifyRequest):
    return build_messages(req.analysis_result)


@app.post("/monthly-report", response_model=MonthlyReportResponse)
def monthly_report_endpoint(req: MonthlyReportRequest):
    return build_monthly_report(req)
