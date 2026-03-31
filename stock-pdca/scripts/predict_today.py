#!/usr/bin/env python3
import json
from pathlib import Path
from datetime import datetime

from market_data import fetch_n225_history, classify, fetched_at_jst

BASE = Path(__file__).resolve().parents[1]
DATA = BASE / 'data'
REPORTS = BASE / 'reports'
PRED = DATA / 'predictions.json'
IMPR = DATA / 'improvements.json'
OUT = REPORTS / f"report-{datetime.now().strftime('%Y-%m-%d')}.md"


def load_json(path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text())
    except Exception:
        return default


def save_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2))


def fetch_quote(symbol):
    import json as _json, urllib.request
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range=5d&interval=1d&includePrePost=false"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=20) as res:
        data = _json.loads(res.read().decode('utf-8'))
    result = data['chart']['result'][0]
    closes = result['indicators']['quote'][0]['close']
    vals = [x for x in closes if x is not None]
    return vals[-1] if vals else None


def build_prediction():
    fetched_at = fetched_at_jst()
    n225 = fetch_n225_history()
    last_close = n225[-1]['close'] if n225 else None
    prev_close = n225[-2]['close'] if len(n225) >= 2 else None
    us_sp = fetch_quote('%5EGSPC')
    us_nq = fetch_quote('%5EIXIC')
    us_dji = fetch_quote('%5EDJI')
    sox = fetch_quote('%5ESOX')
    vix = fetch_quote('%5EVIX')
    oil = fetch_quote('CL=F')
    jpy = fetch_quote('JPY=X')
    tnx = fetch_quote('%5ETNX')
    nkd = fetch_quote('NKD=F')

    reasons = []
    bias = 0

    if us_sp and us_nq and us_dji and prev_close:
        reasons.append(f"前夜の米主要指数を確認（S&P500={us_sp:.2f}, NASDAQ={us_nq:.2f}, ダウ={us_dji:.2f}）。地合い確認を最優先。")
    if sox:
        reasons.append(f"SOX={sox:.2f}で、半導体主導の日経平均への追い風/逆風を確認。")
    if vix:
        reasons.append(f"VIX={vix:.2f}でリスクオン/オフ温度感を確認。")
    if oil:
        reasons.append(f"WTI原油={oil:.2f}ドルでインフレ/地政学の重しを確認。")
    if jpy:
        reasons.append(f"ドル円={jpy:.2f}で輸出株支援の有無を確認。")

    if sox and vix:
        if vix >= 28 or (sox and last_close and nkd and nkd < last_close * 0.99):
            bias -= 1
        elif vix < 22 and nkd and last_close and nkd > last_close * 1.003:
            bias += 1

    if oil and oil >= 95:
        bias -= 1
    if jpy and jpy >= 159.5:
        bias += 0.5
    if tnx and tnx >= 4.4:
        bias -= 0.5

    if bias >= 0.8:
        direction = '上昇'
        low, high = 0.3, 1.2
        confidence = 64
    elif bias <= -0.8:
        direction = '下落'
        low, high = -1.8, -0.5
        confidence = 68
    else:
        direction = '横ばい'
        low, high = -0.3, 0.4
        confidence = 56

    falsifier = '寄り前の日経先物、ドル円、原油、米株先物のどれかが急変した場合はシナリオを再判定する。'
    source_notes = [x for x in [
        f"取得時刻: {fetched_at}",
        "取得元: Yahoo Finance chart API (query1.finance.yahoo.com)",
        f"N225 (^N225)={last_close}" if last_close else None,
        f"NKD=F={nkd}" if nkd else None,
        f"VIX (^VIX)={vix}" if vix else None,
        f"WTI (CL=F)={oil}" if oil else None,
        f"JPY=X={jpy}" if jpy else None,
        f"TNX (^TNX)={tnx}" if tnx else None,
    ] if x]
    return {
        'predicted_direction': direction,
        'predicted_range_pct': [low, high],
        'confidence': confidence,
        'reasons': reasons[:5],
        'falsifier': falsifier,
        'source_notes': source_notes,
    }


def main():
    REPORTS.mkdir(parents=True, exist_ok=True)
    predictions = load_json(PRED, [])
    improvements = load_json(IMPR, [])
    today = datetime.now().strftime('%Y-%m-%d')

    pred = build_prediction()

    current = {
        'date': today,
        **pred,
        'actual_change_pct': None,
        'direction_score': None,
        'range_score': None,
        'reason_scores': [],
        'lesson': '未検証',
    }

    if predictions and predictions[-1].get('date') == today:
        predictions[-1].update(current)
    else:
        predictions.append(current)
    save_json(PRED, predictions)

    prev = predictions[-2] if len(predictions) >= 2 else None
    reflected = improvements[-2:] if improvements else []
    reflected_text = '\n'.join([f"- {x.get('change','改善点未設定')}" for x in reflected]) if reflected else '- 初回のため改善点はこれから蓄積'

    validation = '## 1. 前回予想の検証\n- この検証は引け後レポートで実施します。\n'
    if prev:
        validation = f"## 1. 前回予想の検証\n- 対象日: {prev.get('date')}\n- この詳細検証は引け後16:00レポートで更新します。\n"

    reason_text = '\n'.join([f"  {i+1}. {r}" for i, r in enumerate(current['reasons'])])
    source_notes = '\n'.join([f"- {x}" for x in current.get('source_notes', [])])
    text = (
        f"# 朝株ラボ 朝予想レポート - {today}\n\n"
        + validation + "\n"
        + f"## 2. 本日の予想\n- 方向: {current['predicted_direction']}\n- 予想変動幅: {current['predicted_range_pct'][0]}% ～ {current['predicted_range_pct'][1]}%\n- 確信度: {current['confidence']}\n- 主因トップ5:\n{reason_text}\n- 反証条件:\n  - {current['falsifier']}\n\n"
        + f"## 3. 取得ソースと時刻\n{source_notes}\n\n"
        + f"## 4. 直近の改善反映\n{reflected_text}\n"
    )
    OUT.write_text(text)
    print(str(OUT))


if __name__ == '__main__':
    main()
