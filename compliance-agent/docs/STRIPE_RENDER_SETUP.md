# Stripe + Render 本番設定手順（このまま実施用）

最終更新: 2026-03-12

## 0. 前提
- Renderに `compliance-agent` がデプロイ済み
- 公開URL例: `https://your-app.onrender.com`

---

## 1) Stripeで商品/価格を作成

1. Stripe Dashboard → **商品カタログ** → **商品を追加**
2. 例: `Compliance Agent Starter`
3. 料金: `月額`（例: 98,000円）
4. 作成後、価格ID（`price_xxx`）を控える

この `price_xxx` を API `POST /v1/billing/checkout` で使う。

---

## 2) Stripe APIキー取得

Stripe Dashboard → **開発者** → **APIキー**
- `シークレットキー`（`sk_live_...` もしくはテスト時 `sk_test_...`）を取得

---

## 3) Render 環境変数設定

Render → 対象サービス → Environment で以下を設定

必須:
- `SECRET_KEY` = 強いランダム文字列
- `ACCESS_TOKEN_EXPIRE_MINUTES` = `60`
- `STRIPE_SECRET_KEY` = `sk_live_...`

任意（通知）:
- `OWNER_EMAIL`
- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_FROM`
- `SMTP_USERNAME`
- `SMTP_PASSWORD`
- `SMTP_USE_TLS=true`

保存後、再デプロイ。

---

## 4) Stripe Webhook設定

1. Stripe Dashboard → **開発者** → **Webhook** → **エンドポイントを追加**
2. URL:  
   `https://your-app.onrender.com/v1/billing/webhook`
3. 受信イベント（最低限）:
   - `checkout.session.completed`
   - `customer.subscription.created`
   - `customer.subscription.updated`
4. 作成後、`Signing secret`（`whsec_...`）を控える

Render環境変数に追加:
- `STRIPE_WEBHOOK_SECRET` = `whsec_...`

保存後、再デプロイ。

---

## 5) Checkout URL発行テスト

### 5-1. まずログインしてJWT取得
`POST /v1/auth/login`

```json
{
  "email": "admin@example.com",
  "password": "your-password"
}
```

### 5-2. Checkout URL発行
`POST /v1/billing/checkout`

Headers:
- `Authorization: Bearer <JWT>`

Body:
```json
{
  "price_id": "price_xxx",
  "success_url": "https://your-app.onrender.com/?billing=success",
  "cancel_url": "https://your-app.onrender.com/?billing=cancel"
}
```

成功レスポンス:
```json
{
  "checkout_url": "https://checkout.stripe.com/..."
}
```

このURLを開いて決済フロー確認。

---

## 6) Webhook反映確認

1. StripeのWebhookログで 2xx を確認
2. APIで監査チェーン確認:
   - `GET /v1/audit/chain`
3. `billing.subscription_updated` が入っていればOK

---

## 7) 署名付きPDF確認

`GET /v1/reports/monthly/pdf?month=2026-03`

- レスポンスヘッダ `X-Report-SHA256` を確認
- PDFがDLでき、監査ログに `report.pdf_generated` が記録されることを確認

---

## 8) よくある詰まりどころ

- 400 invalid stripe signature  
  → `STRIPE_WEBHOOK_SECRET` が一致してない

- checkout作成時に500  
  → `STRIPE_SECRET_KEY` 未設定または誤り

- webhookが404  
  → Render URL/パス誤り（`/v1/billing/webhook`）

- 通知メールが来ない  
  → SMTP環境変数不足（`SMTP_HOST`,`SMTP_FROM` は必須）

---

## 9) 本番切替チェック

- [ ] Stripeキーが `live` に切替済み
- [ ] Webhook先が本番URL
- [ ] test決済導線をUIから無効化
- [ ] 価格IDが本番商品に置換済み
- [ ] 1件実課金でend-to-end確認
