# V睡録画ソフト

VRChatのV睡中に、参加してきた人の活動を自動録画するソフトウェアです。

## 機能

- VRChatのプレイヤー出入りを自動検知
- OBS Studioとの連携で自動録画開始/停止
- 一緒に寝る人の除外設定
- ログ出力機能

## 必要な環境

- Python 3.8以上
- OBS Studio（WebSocketサーバー有効化が必要）
- VRChat（OSC有効化が必要）

## セットアップ

1. 依存パッケージのインストール

**Windowsの場合:**
```bash
install.bat
```
または手動で:
```bash
pip install -r requirements.txt
```

**Mac/Linuxの場合:**
```bash
pip3 install -r requirements.txt
```

2. OBS Studioの設定
   - OBS Studioを起動
   - ツール → WebSocketサーバー設定
   - WebSocketサーバーを有効化（デフォルトポート: 4455）
   - 必要に応じてパスワードを設定し、`config.yaml`に記載

3. VRChatの設定
   - VRChatを起動するだけでOK（ログファイル監視方式を使用）
   - オプション: OSCを使用する場合は、設定 → OSCタブでOSCを有効化

4. 設定ファイルの編集
   - `config.yaml`を編集して、除外するユーザー名やIDを設定
   - 一緒に寝る人のユーザー名やIDを`exclude`セクションに追加

## 使用方法

### GUI版（推奨）

**Windowsの場合:**
```bash
run_gui.bat
```
または:
```bash
py gui_app.py
```

**Mac/Linuxの場合:**
```bash
python3 gui_app.py
```

GUIアプリケーションが起動します。以下の操作が可能です：
- **監視開始/停止**: ボタンで監視の開始・停止
- **プレイヤーリスト**: 現在参加しているプレイヤーを表示
- **ログ表示**: リアルタイムでログを確認
- **設定**: OBS接続情報を設定
- **除外ユーザー管理**: 一緒に寝る人を除外リストに追加・削除

### コマンドライン版

```bash
python main.py
```

## 動作フロー

1. プログラム起動 → 録画停止状態で待機
2. 誰かがワールドにJoin → 自動録画開始
3. インスタンスの全員がLeave → 録画停止

除外設定されたユーザーは、プレイヤー数のカウントから除外されます。

## 除外設定の方法

`config.yaml`の`exclude`セクションで、一緒に寝る人を除外できます：

```yaml
exclude:
  users:
    - "Friend1"  # ユーザー名（部分一致も可能）
    - "Friend2"
  user_ids:
    - "usr_xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"  # ユーザーID
```

除外されたユーザーが参加しても録画は開始されず、退出しても録画は停止しません。

## プレイヤー検知の仕組み

このソフトウェアは、VRChatのログファイル（`output_log.txt`）を監視してプレイヤーの出入りを検知します。
- VRChatが起動していれば自動的にログファイルを検出します
- ログファイルのパスは`config.yaml`で手動指定も可能です
