from __future__ import annotations

from collections import Counter, defaultdict

from .models import MonthlyReportRequest, MonthlyReportResponse


def build_monthly_report(req: MonthlyReportRequest) -> MonthlyReportResponse:
    total = len(req.records)
    status_counter = Counter(r.analysis_result.status for r in req.records)
    violation_counter = Counter(r.analysis_result.violation_type for r in req.records if r.analysis_result.violation_type != "なし")

    compliance_rate = (status_counter.get("SAFE", 0) / total * 100) if total else 0.0

    route_issues = defaultdict(int)
    for r in req.records:
        if r.route_name and r.analysis_result.status != "SAFE":
            route_issues[r.route_name] += 1

    top_routes = sorted(route_issues.items(), key=lambda x: x[1], reverse=True)[:5]

    lines = []
    lines.append(f"# {req.month} 月次コンプライアンス報告書")
    lines.append("")
    lines.append("## 1. 全社集計")
    lines.append(f"- 総判定件数: {total}")
    lines.append(f"- 法令遵守率(SAFE率): {compliance_rate:.1f}%")
    lines.append(f"- SAFE: {status_counter.get('SAFE', 0)}")
    lines.append(f"- WARNING: {status_counter.get('WARNING', 0)}")
    lines.append(f"- VIOLATION: {status_counter.get('VIOLATION', 0)}")

    lines.append("")
    lines.append("## 2. 個別指導記録（サマリ）")
    for i, r in enumerate(req.records[:20], start=1):
        ar = r.analysis_result
        lines.append(
            f"{i}. {r.driver_name} / {ar.status} / {ar.violation_type} / {ar.details} / 改善確認: {r.improved_after_notification}"
        )

    lines.append("")
    lines.append("## 3. 違反種別の傾向")
    if violation_counter:
        for k, v in violation_counter.items():
            lines.append(f"- {k}: {v}件")
    else:
        lines.append("- 特記すべき違反傾向なし")

    lines.append("")
    lines.append("## 4. ルート別リスク傾向")
    if top_routes:
        for route, count in top_routes:
            lines.append(f"- {route}: 問題判定 {count}件")
    else:
        lines.append("- ルート別の偏りは軽微")

    lines.append("")
    lines.append("## 5. 翌月アクションプラン")
    lines.append("- 14時間超拘束の予兆が出る便を前倒し点検し、配車時点で休憩可能ポイントを確保する。")
    lines.append("- 連続運転4時間接近便に対しては、90分前警告を運行管理者にも同報する。")
    lines.append("- 是正通知後の改善確認フロー（再判定）を翌営業日までに完了する。")

    return MonthlyReportResponse(report_markdown="\n".join(lines))
