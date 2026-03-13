from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

EventType = Literal["on_duty", "driving", "break", "off_duty"]
StatusType = Literal["SAFE", "WARNING", "VIOLATION"]


class Event(BaseModel):
    type: EventType
    start: datetime
    end: datetime


class AnalyzeRequest(BaseModel):
    driver_name: str
    events: list[Event]
    week_violation_over14h_count: int = 0
    last_shift_end: Optional[datetime] = None
    two_day_avg_driving_minutes: int = 0
    weekly_driving_minutes: int = 0


class AnalysisResult(BaseModel):
    status: StatusType
    driver_name: str
    violation_type: str
    details: str
    action_required: str
    evidence: dict = Field(default_factory=dict)


class NotifyRequest(BaseModel):
    analysis_result: AnalysisResult


class NotifyResponse(BaseModel):
    driver_message: str
    owner_message: Optional[str] = None


class MonthlyRecord(BaseModel):
    driver_name: str
    analysis_result: AnalysisResult
    notification_sent_at: Optional[datetime] = None
    improved_after_notification: Optional[bool] = None
    route_name: Optional[str] = None


class MonthlyReportRequest(BaseModel):
    month: str
    records: list[MonthlyRecord]


class MonthlyReportResponse(BaseModel):
    report_markdown: str
