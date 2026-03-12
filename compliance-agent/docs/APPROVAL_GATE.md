# 承認ゲート運用（iPhone承認に近い形）

この仕組みは「本人承認が入った時だけ高リスク操作を実行する」ための実装です。

## できること
- manager/owner が承認リクエスト作成
- owner が承認コードで承認
- 承認済みを1回だけ実行
- 全操作を監査ログに記録

## 対応アクション（現状）
- `git_push_main`
- `alembic_upgrade`

## フロー
1. `POST /v1/approvals/request`
2. `POST /v1/approvals/approve`（ownerのみ）
3. `POST /v1/approvals/execute`

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

> 注: これは本人認証をバイパスする裏技ではなく、
> 「人間の承認を必須にする安全な代理実行フレーム」です。
