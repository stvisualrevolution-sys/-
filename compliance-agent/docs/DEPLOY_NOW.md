# 今すぐ本番デプロイ手順（最短）

## 0) 前提
- GitHubアカウント
- Renderアカウント
- （任意）SMTP情報

## 1) GitHubへpush
```bash
cd /Users/macminitakahashi/.openclaw/workspace
git remote add origin <YOUR_GITHUB_REPO_URL>
git push -u origin main
```

## 2) RenderでBlueprintデプロイ
1. Renderダッシュボードで **New +** → **Blueprint**
2. GitHubリポジトリを選択
3. `render.yaml` を読み込んで作成
4. デプロイ完了後、`/health` へアクセスして `{"ok": true}` を確認

## 3) 環境変数（Render）
必須:
- `SECRET_KEY`（強いランダム文字列）
- `ACCESS_TOKEN_EXPIRE_MINUTES=60`
- `DATABASE_URL`（render.yamlでDB連携される）

任意（社長向けメール）:
- `OWNER_EMAIL`
- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_FROM`
- `SMTP_USERNAME`
- `SMTP_PASSWORD`
- `SMTP_USE_TLS=true`

## 4) 初期動作確認
- `GET /` でWebコンソール表示
- `POST /v1/auth/signup` で初期テナント作成
- CSVアップロードで `analyses_created > 0` を確認

## 5) 推奨次アクション
- カスタムドメイン設定
- TLS確認
- 監視（Sentry/Uptime）追加
