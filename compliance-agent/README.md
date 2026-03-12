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

# 初回マイグレーション
alembic upgrade head

uvicorn app.main:app --reload --port 8088
```

起動後、`http://localhost:8088/` に簡易Webコンソールがあります。

## 2. API

### 認証
- `POST /v1/auth/signup`
- `POST /v1/auth/login`

JWT取得後、`Authorization: Bearer <token>` で以下APIを利用。

### `POST /v1/analyze`
運行イベントから法令判定を返します。

### `GET /v1/kpi/summary`
直近30日のSAFE/WARNING/VIOLATION比率など、経営KPIを返します。

### `GET /v1/audit/chain`
監査証跡のハッシュチェーン（改ざん検知用途）を返します。

### `POST /v1/approvals/request`
高リスク操作（例: git push / alembic migration）の承認リクエストを作成します。

### `POST /v1/approvals/request-and-send`
承認リクエストを作成し、Telegramへワンタップ承認ボタンを送ります（iPhone向け）。

### `GET /v1/approvals/quick`
Telegramボタンから呼ばれるワンタップ承認/却下エンドポイント。

### `POST /v1/approvals/approve`
オーナーが承認コードで承認します（ワンタイム）。

### `POST /v1/approvals/execute`
承認済みリクエストを実行します（1回限り）。

### `POST /v1/billing/checkout`
Stripe Checkout（サブスク）URLを発行します。

### `POST /v1/billing/webhook`
Stripe Webhook受信（サブスク状態更新）

### `GET /v1/reports/monthly/pdf?month=YYYY-MM`
SHA256付きの署名情報をヘッダに含む月次レポートPDFを返します。

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

## 5. メール通知（任意）

`OWNER_EMAIL` とSMTP環境変数を設定すると、WARNING/VIOLATION時に社長向け通知をメール送信します。

- `OWNER_EMAIL`
- `SMTP_HOST`
- `SMTP_PORT`（デフォルト587）
- `SMTP_FROM`
- `SMTP_USERNAME`（任意）
- `SMTP_PASSWORD`（任意）
- `SMTP_USE_TLS`（デフォルトtrue）

## 6. デプロイ（Render最短）

このリポジトリには `Dockerfile` と `render.yaml` を同梱しています。

1. GitHubにpush
2. Renderで「Blueprint」作成（`render.yaml`を読み込み）
3. 環境変数を設定（必要なら `OWNER_EMAIL`, `SMTP_*`）
4. デプロイ後、`/health` で疎通確認

## 7. 本番化ロードマップ（推奨）

1. デジタコAPI接続（メーカー別アダプタ）
2. ルールエンジンをSQL永続化（PostgreSQL）
3. 通知チャネル追加（LINE WORKS/Slack/メール）
4. 監査証跡の改ざん検知（ハッシュ署名）
5. テナント分離・課金（顧客ごとの契約管理）

---

必要なら次のステップで、DifyワークフローJSON（インポート用）まで作成します。
