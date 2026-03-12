# 実行プロンプト：運行データ・スクリーニング

## 入力データ
{{運行ログデータ}}

## 手順
1. ログから拘束時間、休息期間、連続運転時間を1分単位で計算。
2. 法的基準と照合し、以下で判定。
   - [SAFE]
   - [WARNING]（30分以内で違反到達、または基準ギリギリ）
   - [VIOLATION]
3. 判定理由は必ず数値で示す。

## 出力（JSON）
```json
{
  "status": "SAFE|WARNING|VIOLATION",
  "driver_name": "氏名",
  "violation_type": "拘束時間|休息期間|運転時間|連続運転|なし",
  "details": "具体的な超過/不足分（分）",
  "action_required": "今すぐ取るべき行動",
  "evidence": {
    "on_duty_minutes": 0,
    "rest_minutes": 0,
    "continuous_driving_max_minutes": 0,
    "two_day_avg_driving_minutes": 0,
    "weekly_driving_minutes": 0
  }
}
```
