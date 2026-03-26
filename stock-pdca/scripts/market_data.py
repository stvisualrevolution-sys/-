#!/usr/bin/env python3
import json
import time
import urllib.request
from datetime import datetime, timezone

YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/%5EN225?range=1mo&interval=1d&includePrePost=false&events=div%2Csplits"


def fetch_n225_history():
    req = urllib.request.Request(
        YAHOO_CHART_URL,
        headers={"User-Agent": "Mozilla/5.0"},
    )
    with urllib.request.urlopen(req, timeout=20) as res:
        data = json.loads(res.read().decode("utf-8"))

    result = data["chart"]["result"][0]
    timestamps = result.get("timestamp", [])
    quote = result.get("indicators", {}).get("quote", [{}])[0]
    closes = quote.get("close", [])

    rows = []
    for ts, close in zip(timestamps, closes):
        if close is None:
            continue
        day = datetime.fromtimestamp(ts, tz=timezone.utc).astimezone().strftime("%Y-%m-%d")
        rows.append({"date": day, "close": float(close)})
    return rows


def classify(change):
    if change >= 0.3:
        return "上昇"
    if change <= -0.3:
        return "下落"
    return "横ばい"
