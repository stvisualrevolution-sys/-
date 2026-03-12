# 課金なし（Mac mini常駐）運用Runbook

## 目的
Render課金せず、Mac mini上で `compliance-agent` を24/365運用する。

## 1) 初回セットアップ
```bash
cd /Users/macminitakahashi/.openclaw/workspace/compliance-agent
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
```

## 2) 環境変数（最低限）
`.env` を作成して設定:
- SECRET_KEY
- ACCESS_TOKEN_EXPIRE_MINUTES=60
- DATABASE_URL=sqlite:///./compliance.db
- PUBLIC_BASE_URL=http://127.0.0.1:8088
- APPROVAL_LINK_SECRET
- TELEGRAM_BOT_TOKEN
- TELEGRAM_OWNER_CHAT_ID

## 3) 起動
```bash
cd /Users/macminitakahashi/.openclaw/workspace/compliance-agent
source .venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8088
```

## 4) 動作確認
- `http://127.0.0.1:8088/health` -> `{"ok":true}`
- `http://127.0.0.1:8088/docs`
- `POST /v1/approvals/request-and-send` でTelegram承認ボタン送信

## 5) 常駐（任意）
macOSなら launchd か tmux で常駐。最小は tmux:
```bash
tmux new -s compliance
cd /Users/macminitakahashi/.openclaw/workspace/compliance-agent
source .venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8088
```

## 6) 注意
- TelegramボタンURLは `PUBLIC_BASE_URL` を使う。
- iPhoneだけで叩くなら、将来的にトンネル（Cloudflare Tunnel等）か公開先が必要。
