from __future__ import annotations

import json
import os
import urllib.request


def _post_json(url: str, payload: dict):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as res:
        return json.loads(res.read().decode("utf-8"))


def send_approval_buttons(message: str, approve_url: str, reject_url: str) -> dict | None:
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_OWNER_CHAT_ID")
    if not bot_token or not chat_id:
        return None

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "reply_markup": {
            "inline_keyboard": [
                [
                    {"text": "✅ 承認して実行", "url": approve_url},
                    {"text": "❌ 却下", "url": reject_url},
                ]
            ]
        },
    }
    return _post_json(url, payload)
