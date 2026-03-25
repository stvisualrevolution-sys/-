#!/usr/bin/env python3
import json
from pathlib import Path
from datetime import datetime

BASE = Path(__file__).resolve().parents[1]
DATA = BASE / 'data'
REPORTS = BASE / 'reports'
PRED = DATA / 'predictions.json'
OUT = REPORTS / f"weekly-review-{datetime.now().strftime('%Y-%m-%d')}.md"


def load_json(path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text())
    except Exception:
        return default


def recent_completed(preds, n=5):
    done = [p for p in preds if p.get('actual_change_pct') is not None]
    return done[-n:]


def average(nums):
    vals = [x for x in nums if isinstance(x, (int, float))]
    return sum(vals) / len(vals) if vals else None


def main():
    REPORTS.mkdir(parents=True, exist_ok=True)
    preds = load_json(PRED, [])
    rows = recent_completed(preds, 5)
    today = datetime.now().strftime('%Y-%m-%d')
    if not rows:
        text = f"# 朝株ラボ 週次レビュー - {today}\n\n- まだ週次集計できるだけの実績データがありません。\n"
        OUT.write_text(text)
        print(str(OUT))
        return

    total = len(rows)
    direction_hits = sum(1 for r in rows if r.get('direction_score') in ('○', '◎'))
    avg_move = average([r.get('actual_change_pct') for r in rows])

    lessons = []
    reason_stats = {}
    for r in rows:
        if r.get('lesson'):
            lessons.append(f"- {r['date']}: {r['lesson']}")
        for rs in r.get('reason_scores', []):
            name = rs.get('name', '要因')
            score = rs.get('score', '-')
            reason_stats.setdefault(name, []).append(score)

    lessons_text = "\n".join(lessons) if lessons else '- まだ学びログが十分ではありません。'

    reason_lines = []
    for name, scores in reason_stats.items():
        reason_lines.append(f"- {name}: {', '.join(scores)}")
    reason_text = "\n".join(reason_lines) if reason_lines else '- まだ要因別の十分な採点データがありません。'

    avg_move_text = 'N/A' if avg_move is None else f"{avg_move:+.2f}%"

    text = (
        f"# 朝株ラボ 週次レビュー - {today}\n\n"
        f"## サマリー\n"
        f"- 集計対象日数: {total}\n"
        f"- 方向的中数: {direction_hits}/{total}\n"
        f"- 平均実績騰落率: {avg_move_text}\n\n"
        f"## 学びの蓄積\n{lessons_text}\n\n"
        f"## 根拠別メモ\n{reason_text}\n\n"
        f"## 次週の改善方針\n"
        f"- 当たりやすい要因と外れやすい要因の重みを見直す\n"
        f"- 高確信予想の妥当性を確認する\n"
        f"- 不確実性が高い日は確信度を抑える\n"
    )
    OUT.write_text(text)
    print(str(OUT))


if __name__ == '__main__':
    main()
