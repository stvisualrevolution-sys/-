#!/usr/bin/env python3
import json
from pathlib import Path
from datetime import datetime, timedelta

from market_data import classify, fetch_n225_history

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


def previous_business_day(today_str, available_dates):
    today = datetime.strptime(today_str, '%Y-%m-%d').date()
    for i in range(1, 8):
        d = (today - timedelta(days=i)).strftime('%Y-%m-%d')
        if d in available_dates:
            return d
    return None


def enrich_actuals(predictions, history):
    date_to_close = {r['date']: r['close'] for r in history}
    dates = list(date_to_close.keys())
    changed = False
    for p in predictions:
        if p.get('actual_change_pct') is not None:
            continue
        d = p.get('date')
        if not d or d not in date_to_close:
            continue
        prev = previous_business_day(d, dates)
        if not prev:
            continue
        prev_close = date_to_close[prev]
        close = date_to_close[d]
        change = ((close - prev_close) / prev_close) * 100
        p['actual_change_pct'] = change
        pred_dir = p.get('predicted_direction')
        actual_dir = classify(change)
        p['direction_score'] = '○' if pred_dir == actual_dir else '×'
        rng = p.get('predicted_range_pct') or [None, None]
        low, high = rng[0], rng[1]
        if isinstance(low, (int, float)) and isinstance(high, (int, float)):
            p['range_score'] = '○' if low <= change <= high else '×'
        else:
            p['range_score'] = None
        if not p.get('lesson') or p.get('lesson') == '未検証':
            p['lesson'] = f"実績は{change:+.2f}%（{actual_dir}）。方向判定を翌朝に自動反映。"
        notes = p.get('source_notes', [])
        notes.append(f"Yahoo Finance ^N225終値ベース自動反映: {prev}→{d} で {change:+.2f}%")
        p['source_notes'] = notes[-10:]
        changed = True
    return changed


def ensure_today_prediction(predictions, improvements):
    today = datetime.now().strftime('%Y-%m-%d')
    if predictions and predictions[-1].get('date') == today:
        return predictions[-1], False

    reflected = improvements[-2:] if improvements else []
    current = {
        'date': today,
        'predicted_direction': '未入力',
        'predicted_range_pct': [None, None],
        'confidence': None,
        'reasons': [],
        'falsifier': None,
        'actual_change_pct': None,
        'direction_score': None,
        'range_score': None,
        'reason_scores': [],
        'lesson': '未検証',
        'source_notes': [f'{today} 朝レポート作成時に自動追加']
    }
    predictions.append(current)
    return current, True


def render_validation(prev):
    if not prev:
        return "## 1. 前回予想の検証\n- 初回運用のため、前回予想の検証はまだありません。\n"

    actual = prev.get('actual_change_pct')
    actual_text = '未記録' if actual is None else f"{actual:+.2f}% ({classify(actual)})"
    predicted_range = prev.get('predicted_range_pct', ['?', '?'])
    direction = prev.get('predicted_direction', '不明')
    reasons = prev.get('reason_scores', [])
    reason_lines = []
    for r in reasons:
        reason_lines.append(f"  - {r.get('name','要因')}: {r.get('score','?')} / {r.get('comment','')}")
    if not reason_lines:
        reason_lines.append('  - まだ根拠ごとの採点はありません。')

    low = predicted_range[0] if predicted_range[0] is not None else '未入力'
    high = predicted_range[1] if predicted_range[1] is not None else '未入力'

    return f"""## 1. 前回予想の検証
- 予想日: {prev.get('date','不明')}
- 予想方向: {direction}
- 予想変動幅: {low}% ～ {high}%
- 実績: {actual_text}
- 判定:
  - 方向: {prev.get('direction_score','未判定')}
  - 変動幅: {prev.get('range_score','未判定')}
  - 根拠ごとの当たり外れ:
""" + "\n".join(reason_lines) + f"""
- 学び:
  - {prev.get('lesson','初回のためなし')}
"""


def render_prediction(current, improvements):
    direction = current.get('predicted_direction', '未設定')
    low, high = current.get('predicted_range_pct', [None, None])
    low = '未入力' if low is None else low
    high = '未入力' if high is None else high
    confidence = current.get('confidence', '未入力')
    reasons = current.get('reasons', [])
    if reasons:
        reasons_text = "\n".join([f"  {i+1}. {r}" for i, r in enumerate(reasons[:5])])
    else:
        reasons_text = "  1. ここに米市場・為替・先物・テクニカル・国内イベントを入れる"
    reflected = improvements[-2:] if improvements else []
    reflected_text = "\n".join([f"- {x.get('change','改善点未設定')}" for x in reflected]) if reflected else "- 初回のため改善点はこれから蓄積"

    return f"""## 2. 本日の予想
- 方向: {direction}
- 予想変動幅: {low}% ～ {high}%
- 確信度: {confidence}
- 主因トップ5:
{reasons_text}
- 反証条件:
  - {current.get('falsifier','寄り前の先物・為替・大型ニュースの急変で前提が崩れる可能性あり')}

## 3. 今日の改善反映
{reflected_text}
"""


def main():
    REPORTS.mkdir(parents=True, exist_ok=True)
    predictions = load_json(PRED, [])
    improvements = load_json(IMPR, [])

    history = []
    try:
        history = fetch_n225_history()
    except Exception:
        history = []

    changed = False
    if history:
        changed = enrich_actuals(predictions, history) or changed

    current, appended = ensure_today_prediction(predictions, improvements)
    changed = changed or appended

    prev = predictions[-2] if len(predictions) >= 2 else None
    text = f"# 朝株ラボ 日次レポート - {datetime.now().strftime('%Y-%m-%d')}\n\n" + render_validation(prev) + "\n" + render_prediction(current, improvements)
    OUT.write_text(text)

    if changed:
        save_json(PRED, predictions)

    print(str(OUT))


if __name__ == '__main__':
    main()
