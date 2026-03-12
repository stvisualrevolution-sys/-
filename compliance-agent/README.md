# 運送業コンプライアンスAIエージェント（MVP）

24時間365日で運行ログを監視し、
- 違反予防（SAFE/WARNING/VIOLATION判定）
- 現場通知文生成（ドライバー/管理者）
- 月次監査レポート生成

を行うための最小実装です。

## 1. セットアップ

```bash
cd compliance-agent
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8088
```

## 2. API

### 認証
- `POST /v1/auth/signup`
- `POST /v1/auth/login`

JWT取得後、`Authorization: Bearer <token>` で以下APIを利用。

### `POST /v1/analyze`
運行イベントから法令判定を返します。

#### 入力例
```json
{
  "driver_name": "山田太郎",
  "week_violation_over14h_count": 1,
  "events": [
    {"type": "on_duty", "start": "2026-03-12T06:00:00+09:00", "end": "2026-03-12T19:30:00+09:00"},
    {"type": "driving", "start": "2026-03-12T06:30:00+09:00", "end": "2026-03-12T10:20:00+09:00"},
    {"type": "break", "start": "2026-03-12T10:20:00+09:00", "end": "2026-03-12T10:40:00+09:00"}
  ],
  "last_shift_end": "2026-03-11T19:30:00+09:00",
  "two_day_avg_driving_minutes": 500,
  "weekly_driving_minutes": 2500
}
```

### `POST /notify`
`/analyze`結果をもとに通知文を作成します（ドライバー向け必須、社長向けはWARNING/VIOLATIONのみ）。

### `POST /monthly-report`
過去1ヶ月分の分析・通知履歴から監査対応レポート（Markdown）を返します。

## 3. 法令ルール（実装中）

- 拘束時間：原則13時間、最大15時間、14時間超は週2回まで
- 休息期間：基本11時間以上、最低9時間
- 運転時間：2日平均1日9時間以内、週44時間以内
- 連続運転：4時間ごとに合計30分以上の休憩（1回10分以上で分割可）

## 4. Dify / Make 連携

`prompts/` にそのまま貼れるシステム・実行プロンプトを用意。

- `prompts/system_prompt.md`
- `prompts/screening_prompt.md`
- `prompts/notification_prompt.md`
- `prompts/monthly_report_prompt.md`

## 5. 本番化ロードマップ（推奨）

1. デジタコAPI接続（メーカー別アダプタ）
2. ルールエンジンをSQL永続化（PostgreSQL）
3. 通知チャネル追加（LINE WORKS/Slack/メール）
4. 監査証跡の改ざん検知（ハッシュ署名）
5. テナント分離・課金（顧客ごとの契約管理）

---

必要なら次のステップで、DifyワークフローJSON（インポート用）まで作成します。
