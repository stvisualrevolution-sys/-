from __future__ import annotations

from .models import AnalysisResult, NotifyResponse


def build_messages(result: AnalysisResult) -> NotifyResponse:
    status = result.status
    detail = result.details

    if status == "SAFE":
        return NotifyResponse(
            driver_message=(
                f"お疲れさまです。現在の運行は法令基準を満たしています。"
                f"このまま無理のないペースで安全運行を続けましょう。\n"
                f"（確認内容: {detail}）"
            ),
            owner_message=None,
        )

    if status == "WARNING":
        return NotifyResponse(
            driver_message=(
                f"お疲れさまです。{detail}。\n"
                "このまま進むと違反に近づくため、次の安全な停車地点で"
                "15〜30分の休憩を取って調整しましょう。"
            ),
            owner_message=(
                f"【予兆通知】{result.driver_name}さんが基準接近（{result.violation_type}）。\n"
                f"内容: {detail}\n"
                "早めの運行調整で行政リスク（是正勧告・監査指摘）を予防してください。"
            ),
        )

    return NotifyResponse(
        driver_message=(
            f"安全確保のため重要なお知らせです。{detail}。\n"
            "直近の安全な地点で休憩を取り、運行管理者へ連絡をお願いします。"
        ),
        owner_message=(
            f"【違反通知】{result.driver_name}さんに{result.violation_type}違反を検知。\n"
            f"内容: {detail}\n"
            "是正指示と記録保存を直ちに実施してください。行政処分リスクの管理が必要です。"
        ),
    )
