#!/usr/bin/env python3
import json
from pathlib import Path
from datetime import datetime

BASE = Path(__file__).resolve().parents[1]
DATA = BASE / 'data'
PRED = DATA / 'predictions.json'


def load_json(path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text())
    except Exception:
        return default


def save_json(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2))


def main():
    preds = load_json(PRED, [])
    today = datetime.now().strftime('%Y-%m-%d')
    if any(p.get('date') == today for p in preds):
        print('already-exists')
        return
    preds.append({
        'date': today,
        'predicted_direction': '未設定',
        'predicted_range_pct': [None, None],
        'confidence': None,
        'reasons': [],
        'falsifier': None,
        'actual_change_pct': None,
        'direction_score': None,
        'range_score': None,
        'reason_scores': [],
        'lesson': None,
        'source_notes': []
    })
    save_json(PRED, preds)
    print('initialized')


if __name__ == '__main__':
    main()
