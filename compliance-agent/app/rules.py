from __future__ import annotations

from collections import defaultdict
from datetime import datetime

from .models import AnalyzeRequest, AnalysisResult


def _minutes(start: datetime, end: datetime) -> int:
    return max(0, int((end - start).total_seconds() // 60))


def analyze(req: AnalyzeRequest) -> AnalysisResult:
    on_duty_minutes = sum(_minutes(e.start, e.end) for e in req.events if e.type == "on_duty")
    driving_minutes = sum(_minutes(e.start, e.end) for e in req.events if e.type == "driving")

    break_segments = [_minutes(e.start, e.end) for e in req.events if e.type == "break"]
    qualifying_break_minutes = sum(m for m in break_segments if m >= 10)

    rest_minutes = 0
    if req.last_shift_end:
        shift_starts = [e.start for e in req.events if e.type == "on_duty"]
        if shift_starts:
            rest_minutes = _minutes(req.last_shift_end, min(shift_starts))

    continuous_driving_max = _calc_continuous_driving(req)

    violations = []
    warnings = []

    # 1) 拘束時間
    if on_duty_minutes > 15 * 60:
        violations.append(("拘束時間", f"拘束時間が{on_duty_minutes}分（最大900分超過）"))
    elif on_duty_minutes > 14 * 60 and req.week_violation_over14h_count >= 2:
        violations.append(("拘束時間", "14時間超の週内回数が上限（2回）を超過"))
    elif on_duty_minutes >= 13 * 60 or (14 * 60 - on_duty_minutes) <= 30:
        warnings.append(("拘束時間", f"拘束時間が{on_duty_minutes}分（上限接近）"))

    # 2) 休息期間
    if req.last_shift_end:
        if rest_minutes < 9 * 60:
            violations.append(("休息期間", f"休息期間が{rest_minutes}分（最低540分未満）"))
        elif rest_minutes < 11 * 60:
            warnings.append(("休息期間", f"休息期間が{rest_minutes}分（基本660分未満）"))

    # 3) 運転時間
    if req.two_day_avg_driving_minutes > 9 * 60:
        violations.append(("運転時間", f"2日平均運転時間が{req.two_day_avg_driving_minutes}分（540分超）"))
    elif (9 * 60 - req.two_day_avg_driving_minutes) <= 30:
        warnings.append(("運転時間", f"2日平均運転時間が{req.two_day_avg_driving_minutes}分（上限接近）"))

    if req.weekly_driving_minutes > 44 * 60:
        violations.append(("運転時間", f"週運転時間が{req.weekly_driving_minutes}分（2640分超）"))
    elif (44 * 60 - req.weekly_driving_minutes) <= 30:
        warnings.append(("運転時間", f"週運転時間が{req.weekly_driving_minutes}分（上限接近）"))

    # 4) 連続運転
    if continuous_driving_max > 4 * 60 and qualifying_break_minutes < 30:
        violations.append(("連続運転", f"連続運転{continuous_driving_max}分、4時間内の有効休憩合計{qualifying_break_minutes}分"))
    elif (4 * 60 - continuous_driving_max) <= 30:
        warnings.append(("連続運転", f"連続運転が{continuous_driving_max}分（上限接近）"))

    if violations:
        vt, detail = violations[0]
        return AnalysisResult(
            status="VIOLATION",
            driver_name=req.driver_name,
            violation_type=vt,
            details=detail,
            action_required="直近の安全な停車地点で休憩・運行計画を再調整し、管理者へ即報告してください。",
            evidence={
                "on_duty_minutes": on_duty_minutes,
                "rest_minutes": rest_minutes,
                "continuous_driving_max_minutes": continuous_driving_max,
                "two_day_avg_driving_minutes": req.two_day_avg_driving_minutes,
                "weekly_driving_minutes": req.weekly_driving_minutes,
            },
        )

    if warnings:
        wt, detail = warnings[0]
        return AnalysisResult(
            status="WARNING",
            driver_name=req.driver_name,
            violation_type=wt,
            details=detail,
            action_required="次のSA/PA等で先回り休憩し、違反回避のため運行スケジュールを調整してください。",
            evidence={
                "on_duty_minutes": on_duty_minutes,
                "rest_minutes": rest_minutes,
                "continuous_driving_max_minutes": continuous_driving_max,
                "two_day_avg_driving_minutes": req.two_day_avg_driving_minutes,
                "weekly_driving_minutes": req.weekly_driving_minutes,
            },
        )

    return AnalysisResult(
        status="SAFE",
        driver_name=req.driver_name,
        violation_type="なし",
        details="全基準を満たしています。",
        action_required="このまま安全運行を継続してください。",
        evidence={
            "on_duty_minutes": on_duty_minutes,
            "rest_minutes": rest_minutes,
            "continuous_driving_max_minutes": continuous_driving_max,
            "two_day_avg_driving_minutes": req.two_day_avg_driving_minutes,
            "weekly_driving_minutes": req.weekly_driving_minutes,
        },
    )


def _calc_continuous_driving(req: AnalyzeRequest) -> int:
    timeline = sorted(req.events, key=lambda e: e.start)
    current = 0
    max_cont = 0

    for e in timeline:
        mins = _minutes(e.start, e.end)
        if e.type == "driving":
            current += mins
            max_cont = max(max_cont, current)
        elif e.type == "break":
            if mins >= 10:
                current = 0
        elif e.type in {"off_duty", "on_duty"}:
            # on_dutyのみのイベントを挟んでも運転連続は維持
            pass

    return max_cont
