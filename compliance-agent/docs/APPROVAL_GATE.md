# 承認ゲート運用（iPhone承認に近い形）

この仕組みは「本人承認が入った時だけ高リスク操作を実行する」ための実装です。

## できること
- manager/owner が承認リクエスト作成
- owner が承認コードで承認
- Telegramにワンタップ承認ボタン送信（iPhone運用）
- 承認済みを1回だけ実行
- 全操作を監査ログに記録

## 対応アクション（現状）
- `git_push_main`
- `alembic_upgrade`

## フロー（通常）
1. `POST /v1/approvals/request`
2. `POST /v1/approvals/approve`（ownerのみ）
3. `POST /v1/approvals/execute`

## フロー（iPhoneワンタップ）
1. `POST /v1/approvals/request-and-send`
2. Telegramの「✅ 承認して実行」ボタンをタップ
3. `/v1/approvals/quick` が承認→実行

## request 例
```json
{
  "action": "git_push_main",
  "payload": {"reason": "release"},
  "ttl_minutes": 15
}
```

## approve 例
```json
{
  "approval_id": "<id>",
  "approval_code": "123456"
}
```

## execute 例
```json
{
  "approval_id": "<id>"
}
```

## 必要な環境変数（ワンタップ運用）
- `PUBLIC_BASE_URL`
- `APPROVAL_LINK_SECRET`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_OWNER_CHAT_ID`

> 注: これは本人認証をバイパスする裏技ではなく、
> 「人間の承認を必須にする安全な代理実行フレーム」です。
