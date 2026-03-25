#!/usr/bin/env python3
import json
from pathlib import Path
from datetime import datetime

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


def classify(change):
    if change >= 0.3:
        return '上昇'
    if change <= -0.3:
        return '下落'
    return '横ばい'


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
        reason_lines.append(f"  - {r.get('name','要因')}: {r.get('score','?')} / {r.get('comment','')}" )
    if not reason_lines:
        reason_lines.append('  - まだ根拠ごとの採点はありません。')

    return f"""## 1. 前回予想の検証
- 予想日: {prev.get('date','不明')}
- 予想方向: {direction}
- 予想変動幅: {predicted_range[0]}% ～ {predicted_range[1]}%
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
    low, high = current.get('predicted_range_pct', ['?', '?'])
    confidence = current.get('confidence', '未設定')
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
    prev = predictions[-1] if predictions else None
    current = {
        'predicted_direction': '未入力',
        'predicted_range_pct': ['未入力', '未入力'],
        'confidence': '未入力',
        'reasons': [],
        'falsifier': '未入力'
    }
    text = f"# 朝株ラボ 日次レポート - {datetime.now().strftime('%Y-%m-%d')}\n\n" + render_validation(prev) + "\n" + render_prediction(current, improvements)
    OUT.write_text(text)
    print(str(OUT))


if __name__ == '__main__':
    main()
