# 運送業コンプライアンスAI SaaS 本番公開設計書

最終更新: 2026-03-12
対象: MVP（FastAPI）を公開SaaSへ拡張

---

## 1. サービス概要

### 1.1 提供価値
- 改善基準告示/労務基準に基づく違反予防（リアルタイム）
- 是正指導の自動記録（ドライバー・運行管理者・社長への通知）
- 監査で提示できる証跡と月次レポート自動生成

### 1.2 主要ユースケース
1. デジタコ/CSVで運行データ取り込み
2. ルールエンジンでSAFE/WARNING/VIOLATION判定
3. LINE/メール等で通知
4. 管理画面で進捗・違反傾向確認
5. 月次報告書（PDF/CSV）出力

---

## 2. システム構成（本番）

- Frontend: Next.js（Vercel）
- Backend API: FastAPI（Render/Fly.io/AWS ECS）
- DB: PostgreSQL（Supabase/Neon/RDS）
- Queue/Worker: Redis + Celery/RQ（通知・レポートの非同期処理）
- Storage: S3（報告書PDF、取込CSV、証跡保管）
- Auth: Clerk/Auth0/Supabase Auth
- Billing: Stripe
- Monitoring: Sentry + OpenTelemetry + Uptime監視

---

## 3. マルチテナントDB設計（初版）

## 3.1 ERD（主要テーブル）

- tenants（契約企業）
- users（利用者）
- memberships（ユーザーと企業の紐付け・権限）
- drivers（ドライバー）
- vehicles（車両）
- routes（運行ルート）
- trips（1運行単位）
- trip_events（on_duty/driving/break等イベント）
- analyses（判定結果）
- notifications（送信履歴）
- monthly_reports（月次レポート）
- audit_logs（監査ログ）
- integrations（外部連携設定）
- subscriptions（課金契約）
- invoices（請求履歴）

## 3.2 SQLスキーマ（叩き台）

```sql
create table tenants (
  id uuid primary key,
  name text not null,
  plan_code text not null,
  timezone text not null default 'Asia/Tokyo',
  created_at timestamptz not null default now()
);

create table users (
  id uuid primary key,
  email text unique not null,
  display_name text,
  created_at timestamptz not null default now()
);

create table memberships (
  tenant_id uuid not null references tenants(id),
  user_id uuid not null references users(id),
  role text not null check (role in ('owner','manager','viewer')),
  primary key (tenant_id, user_id)
);

create table drivers (
  id uuid primary key,
  tenant_id uuid not null references tenants(id),
  name text not null,
  employee_code text,
  active boolean not null default true,
  created_at timestamptz not null default now()
);

create table trips (
  id uuid primary key,
  tenant_id uuid not null references tenants(id),
  driver_id uuid not null references drivers(id),
  vehicle_id uuid,
  route_id uuid,
  shift_start timestamptz not null,
  shift_end timestamptz,
  source_type text not null check (source_type in ('api','csv','manual')),
  created_at timestamptz not null default now()
);

create table trip_events (
  id uuid primary key,
  tenant_id uuid not null references tenants(id),
  trip_id uuid not null references trips(id),
  event_type text not null check (event_type in ('on_duty','driving','break','off_duty')),
  start_at timestamptz not null,
  end_at timestamptz not null,
  metadata jsonb not null default '{}'::jsonb
);

create table analyses (
  id uuid primary key,
  tenant_id uuid not null references tenants(id),
  trip_id uuid not null references trips(id),
  status text not null check (status in ('SAFE','WARNING','VIOLATION')),
  violation_type text not null,
  details text not null,
  action_required text not null,
  evidence jsonb not null,
  ruleset_version text not null,
  analyzed_at timestamptz not null default now()
);

create table notifications (
  id uuid primary key,
  tenant_id uuid not null references tenants(id),
  analysis_id uuid not null references analyses(id),
  target_type text not null check (target_type in ('driver','owner','manager')),
  channel text not null check (channel in ('line','email','slack','sms')),
  target text not null,
  message text not null,
  status text not null check (status in ('queued','sent','failed')),
  sent_at timestamptz,
  error_message text
);

create table monthly_reports (
  id uuid primary key,
  tenant_id uuid not null references tenants(id),
  month text not null,
  report_markdown text not null,
  pdf_url text,
  generated_at timestamptz not null default now(),
  unique (tenant_id, month)
);

create table audit_logs (
  id uuid primary key,
  tenant_id uuid not null references tenants(id),
  actor_user_id uuid,
  action text not null,
  object_type text not null,
  object_id text,
  payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);
```

## 3.3 テナント分離
- すべての業務テーブルに `tenant_id` 必須
- API層で認可（JWTのtenant claim）
- 可能ならPostgres RLS併用

---

## 4. 画面一覧（Web管理画面）

1. ログイン/新規登録
2. 会社初期設定（業種、車両台数、通知先、ルール閾値）
3. ダッシュボード
   - 本日の運行件数
   - SAFE/WARNING/VIOLATION比率
   - 重大アラート一覧
4. ドライバー一覧/詳細
   - 直近判定履歴
   - 違反傾向（拘束時間/連続運転など）
5. 運行履歴（検索・フィルタ）
6. 通知履歴（再送・失敗理由表示）
7. 月次レポート（プレビュー・PDFダウンロード）
8. 外部連携設定（デジタコAPI、CSV、LINE、Slack、メール）
9. 課金管理（プラン変更、請求履歴）
10. 監査ログ閲覧

---

## 5. API一覧（v1）

## 5.1 認証/テナント
- `POST /v1/auth/signup`
- `POST /v1/auth/login`
- `GET /v1/me`
- `POST /v1/tenants`
- `GET /v1/tenants/current`

## 5.2 データ取込
- `POST /v1/ingest/trip-events`（API取込）
- `POST /v1/ingest/csv`（CSVアップロード）
- `GET /v1/ingest/jobs/{jobId}`

## 5.3 判定・通知
- `POST /v1/analyze`
- `POST /v1/notify`
- `POST /v1/analyze-and-notify`（ワンショット）
- `GET /v1/analyses`
- `GET /v1/analyses/{id}`

## 5.4 レポート
- `POST /v1/reports/monthly/generate`
- `GET /v1/reports/monthly?month=YYYY-MM`
- `GET /v1/reports/monthly/{id}/pdf`

## 5.5 管理
- `GET /v1/drivers`
- `POST /v1/drivers`
- `PATCH /v1/drivers/{id}`
- `GET /v1/notifications`
- `POST /v1/notifications/{id}/retry`

---

## 6. 料金プラン案（初期）

## Starter（¥29,800/月）
- ドライバー 〜20名
- 月間運行判定 〜20,000件
- 通知: メール/LINE（基本）
- 月次レポート

## Growth（¥79,800/月）
- ドライバー 〜80名
- 月間運行判定 〜100,000件
- Slack/LINE WORKS対応
- 監査ログ詳細、CSV/API連携

## Enterprise（個別見積）
- 無制限に近い処理上限
- SSO、専用サポート、SLA
- カスタム監査帳票、専用環境

### オプション
- 初期導入支援: ¥150,000〜
- デジタコ個別コネクタ開発: ¥300,000〜

---

## 7. セキュリティ・法務要件

1. 通信/保存暗号化（TLS, at-rest encryption）
2. パスワードハッシュ（Argon2/Bcrypt）
3. RBAC（owner/manager/viewer）
4. 監査ログと改ざん耐性（ハッシュチェーン推奨）
5. バックアップ（毎日 + リストア訓練）
6. 利用規約・プライバシーポリシー
7. 個人情報取り扱い規程
8. データ保持/削除ポリシー
9. 法令改正反映フロー（ruleset_version運用）

---

## 8. 運用設計（24/365）

- Queue監視（滞留アラート）
- 通知失敗自動リトライ（指数バックオフ）
- サーキットブレーカー（外部API障害時）
- 冪等性キー（重複通知防止）
- オンコール手順書（P1/P2障害対応）

---

## 9. 開発ロードマップ（10週間）

## Phase 1（Week 1-2）β基盤
- マルチテナントDB
- 認証/RBAC
- CSV取込
- 現行 `/analyze` `/notify` `/monthly-report` をv1化

## Phase 2（Week 3-5）公開最小機能
- Webダッシュボード
- 通知チャネル（メール＋LINE）
- Stripe課金
- 月次レポートPDF

## Phase 3（Week 6-8）運用品質
- 監査ログ強化
- 失敗時再実行UI
- 外部連携（デジタコAPI 1社目）
- 監視/アラート整備

## Phase 4（Week 9-10）販売準備
- LP公開
- 導入フロー/ヘルプ整備
- SLA/規約確定
- 先行顧客3社PoC開始

---

## 10. KPI（価値検証）

- 違反件数/月（導入前後）
- WARNINGからの回避率
- 通知到達率/既読率
- 監査指摘件数
- 解約率（MRR churn）
- 1社あたり粗利

---

## 11. 次の実装タスク（このリポジトリで着手）

1. `tenant_id` 前提のDBマイグレーション追加
2. JWT認証ミドルウェア追加
3. `analyze_and_notify` ジョブキュー化
4. 月次レポートPDF化（WeasyPrint or wkhtmltopdf）
5. Stripe Webhook実装

