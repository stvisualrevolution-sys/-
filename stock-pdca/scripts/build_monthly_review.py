#!/usr/bin/env python3
import json
from pathlib import Path
from datetime import datetime
from collections import Counter

BASE = Path(__file__).resolve().parents[1]
DATA = BASE / 'data'
REPORTS = BASE / 'reports'
PRED = DATA / 'predictions.json'
OUT = REPORTS / f"monthly-review-{datetime.now().strftime('%Y-%m-%d')}.md"


def load_json(path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text())
    except Exception:
        return default


def completed(preds):
    return [p for p in preds if p.get('actual_change_pct') is not None]


def average(nums):
    vals = [x for x in nums if isinstance(x, (int, float))]
    return sum(vals) / len(vals) if vals else None


def mean_abs_error(rows):
    vals = []
    for r in rows:
        rng = r.get('predicted_range_pct') or [None, None]
        low, high = rng[0], rng[1]
        actual = r.get('actual_change_pct')
        if isinstance(low, (int, float)) and isinstance(high, (int, float)) and isinstance(actual, (int, float)):
            mid = (low + high) / 2
            vals.append(abs(mid - actual))
    return sum(vals) / len(vals) if vals else None


def main():
    REPORTS.mkdir(parents=True, exist_ok=True)
    preds = load_json(PRED, [])
    rows = completed(preds)[-30:]
    today = datetime.now().strftime('%Y-%m-%d')
    if not rows:
        text = f"# 日経平均 PDCA 月次レビュー - {today}\n\n- まだ月次集計できるだけの実績データがありません。\n"
        OUT.write_text(text)
        print(str(OUT))
        return

    total = len(rows)
    direction_hits = sum(1 for r in rows if r.get('direction_score') in ('○', '◎'))
    avg_actual = average([r.get('actual_change_pct') for r in rows])
    mae = mean_abs_error(rows)

    conf_rows = [r for r in rows if isinstance(r.get('confidence'), (int, float))]
    high_conf = [r for r in conf_rows if r.get('confidence', 0) >= 70]
    high_conf_hits = sum(1 for r in high_conf if r.get('direction_score') in ('○', '◎'))

    lessons = [f"- {r['date']}: {r['lesson']}" for r in rows if r.get('lesson')]
    lesson_text = "\n".join(lessons[-10:]) if lessons else '- まだ学びログが十分ではありません。'

    reason_counter = Counter()
    for r in rows:
        for rs in r.get('reason_scores', []):
            key = f"{rs.get('name','要因')}:{rs.get('score','-')}"
            reason_counter[key] += 1
    top_reasons = [f"- {k} × {v}" for k, v in reason_counter.most_common(10)]
    reason_text = "\n".join(top_reasons) if top_reasons else '- まだ要因別データが不足しています。'

    avg_actual_text = 'N/A' if avg_actual is None else f"{avg_actual:+.2f}%"
    mae_text = 'N/A' if mae is None else f"{mae:.2f}%"
    high_conf_text = f"{high_conf_hits}/{len(high_conf)}" if high_conf else 'データ不足'

    text = (
        f"# 日経平均 PDCA 月次レビュー - {today}\n\n"
        f"## サマリー\n"
        f"- 集計対象日数: {total}\n"
        f"- 方向的中数: {direction_hits}/{total}\n"
        f"- 平均実績騰落率: {avg_actual_text}\n"
        f"- 予想レンジ中心との平均絶対誤差: {mae_text}\n"
        f"- 高確信日(70以上)の方向的中: {high_conf_text}\n\n"
        f"## 学びの蓄積\n{lesson_text}\n\n"
        f"## 根拠スコアの出現傾向\n{reason_text}\n\n"
        f"## 来月への改善方針\n"
        f"- 継続的に当たる要因の重みを少し上げる\n"
        f"- 外れやすい相場局面を分類する\n"
        f"- 確信度と実際の命中率のズレを補正する\n"
    )
    OUT.write_text(text)
    print(str(OUT))


if __name__ == '__main__':
    main()
