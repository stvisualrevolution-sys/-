#!/usr/bin/env python3
import json
from pathlib import Path
from datetime import datetime

from market_data import fetch_n225_history, classify

BASE = Path(__file__).resolve().parents[1]
DATA = BASE / 'data'
REPORTS = BASE / 'reports'
PRED = DATA / 'predictions.json'
IMPR = DATA / 'improvements.json'
OUT = REPORTS / f"review-{datetime.now().strftime('%Y-%m-%d')}.md"


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


def main():
    REPORTS.mkdir(parents=True, exist_ok=True)
    predictions = load_json(PRED, [])
    improvements = load_json(IMPR, [])
    today = datetime.now().strftime('%Y-%m-%d')
    if not predictions or predictions[-1].get('date') != today:
        text = f"# 朝株ラボ 引け後レビュー - {today}\n\n- 本日分の予想レコードがありません。"
        OUT.write_text(text)
        print(str(OUT))
        return

    history = fetch_n225_history()
    date_to_close = {r['date']: r['close'] for r in history}
    if today not in date_to_close:
        text = f"# 朝株ラボ 引け後レビュー - {today}\n\n- まだ本日の終値が取得できません。"
        OUT.write_text(text)
        print(str(OUT))
        return

    # previous business day
    keys = list(date_to_close.keys())
    idx = keys.index(today)
    if idx == 0:
        text = f"# 朝株ラボ 引け後レビュー - {today}\n\n- 前営業日データが不足しています。"
        OUT.write_text(text)
        print(str(OUT))
        return
    prev_day = keys[idx-1]
    prev_close = date_to_close[prev_day]
    close = date_to_close[today]
    change = ((close - prev_close) / prev_close) * 100
    actual_dir = classify(change)

    p = predictions[-1]
    p['actual_change_pct'] = change
    p['direction_score'] = '○' if p.get('predicted_direction') == actual_dir else '×'
    rng = p.get('predicted_range_pct') or [None, None]
    low, high = rng[0], rng[1]
    p['range_score'] = '○' if isinstance(low, (int, float)) and isinstance(high, (int, float)) and low <= change <= high else '×'

    lesson = []
    if p['direction_score'] == '○':
        lesson.append('方向感の見立ては概ね合っていた。')
    else:
        lesson.append('方向感の見立てが外れた。寄り前要因の重み付けを見直す必要がある。')
    if p['range_score'] == '×':
        lesson.append('レンジ感がずれたため、ボラティリティ前提を補正する。')
    if actual_dir == '下落':
        improvement_change = '弱材料が複数（原油高・VIX高・SOX安など）同時発生した日は、下落バイアスを1段強める。'
        improvement_why = 'リスクオフの同時発生時は、円安の下支えより売り圧力が勝ちやすいため。'
    elif actual_dir == '上昇':
        improvement_change = '米株高・先物高・円安が揃った日は、横ばいではなく上昇寄りに初期判定する。'
        improvement_why = '外部市場が揃って追い風のときは、自律反発が想定以上に強く出やすいため。'
    else:
        improvement_change = '材料が強弱まちまちの日は、方向よりレンジ管理を優先する。'
        improvement_why = '横ばい日に方向当てへ寄りすぎると、再現性が下がるため。'

    p['lesson'] = ' '.join(lesson) + f" 実績は{change:+.2f}%（{actual_dir}）。"
    improvements.append({'date': today, 'change': improvement_change, 'why': improvement_why})

    save_json(PRED, predictions)
    save_json(IMPR, improvements)

    text = (
        f"# 朝株ラボ 引け後レビュー - {today}\n\n"
        f"## 1. 本日の実績\n- 前営業日終値: {prev_close:.2f}\n- 本日終値: {close:.2f}\n- 騰落率: {change:+.2f}%（{actual_dir}）\n\n"
        f"## 2. 朝予想の検証\n- 予想方向: {p.get('predicted_direction')}\n- 予想レンジ: {low}% ～ {high}%\n- 方向判定: {p['direction_score']}\n- レンジ判定: {p['range_score']}\n\n"
        f"## 3. 学び\n- {p['lesson']}\n\n"
        f"## 4. 次回への改善\n- {improvement_change}\n- 理由: {improvement_why}\n"
    )
    OUT.write_text(text)
    print(str(OUT))


if __name__ == '__main__':
    main()
