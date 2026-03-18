# macOS警告を減らす配布方法（署名 + ノータライズ）

Gatekeeper警告を抑えるには以下が必要です。

1. **Developer ID Application** でアプリ署名
2. **Developer ID Installer** でpkg署名
3. Apple Notaryへ提出（notarize）
4. staple（チケット添付）

## 事前準備
- Apple Developer Program加入
- 証明書をキーチェーンにインストール
- App-specific password作成

## 必要環境変数
```bash
export APPLE_DEV_ID_APP="Developer ID Application: Your Name (TEAMID)"
export APPLE_DEV_ID_INSTALLER="Developer ID Installer: Your Name (TEAMID)"
export APPLE_ID="you@example.com"
export APPLE_TEAM_ID="TEAMID"
export APPLE_APP_PASSWORD="xxxx-xxxx-xxxx-xxxx"
```

## 実行
```bash
cd compliance-agent
chmod +x scripts/release_macos_signed.sh
./scripts/release_macos_signed.sh
```

生成物:
- `download/DriveCheck.pkg`（署名済み）

## 注意
- 初回配布時はユーザー環境・証明書状態によって警告が残る場合があります。
- 完全無警告を目指すなら、継続的な署名/ノータライズ運用が必要です。
