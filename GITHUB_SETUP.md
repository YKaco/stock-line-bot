# ☁️ PC不要！クラウド（GitHub Actions）で毎日自動配信する手順

GitHub Actions（無料）を使うことで、**自宅のパソコンの電源がOFFになっていても、毎朝 08:30 と 夕方 17:30 に自動で株価・AI解説がLINEに届きます。**

---

### 手順 1: GitHubでリポジトリを作成
1. [GitHub](https://github.com/) にログイン（アカウントがなければ新規登録）。
2. 右上の「＋」アイコンから **「New repository」** をクリック。
3. リポジトリ名（例: `stock-line-bot`）を入力。
4. **必ず「Private（非公開）」を選択** します（APIキーや監視銘柄リストを保護するため）。
5. 「Create repository」をクリック。

---

### 手順 2: このフォルダのファイルをアップロード
GitHubのリポジトリ画面に表示される案内に従うか、以下の手順でアップロードします：

#### 方法 A: コマンドで行う場合
VSCodeのターミナルまたはPowerShellで以下を実行：
```bash
git init
git add .
git commit -m "Initial commit for daily stock line bot"
git branch -M main
git remote add origin https://github.com/あなたのユーザー名/リポジトリ名.git
git push -u origin main
```

#### 方法 B: ブラウザからアップロードする場合
リポジトリ画面の **「uploading an existing file」** リンクをクリックし、このフォルダ内のファイルをドラッグ＆ドロップしてコミットします。

---

### 手順 3: APIキーとLINEトークンを登録（Secrets設定）
GitHub上に安全にキーを保管します：

1. 作成したリポジトリの上部メニューから **「Settings」** をクリック。
2. 左メニューの **「Secrets and variables」** ＞ **「Actions」** をクリック。
3. **「New repository secret」**（緑色のボタン）を押し、以下の3つを1つずつ登録します：

| Secret名（Name） | 値（Secret）に入力するもの |
| :--- | :--- |
| **`GEMINI_API_KEY`** | Google AI Studioで取得したGemini APIキー |
| **`LINE_CHANNEL_ACCESS_TOKEN`** | LINE Developersで取得した長期アクセストークン |
| **`LINE_USER_ID`** | LINE Developersの「あなたのユーザーID（Uから始まる文字列）」 |

---

### 手順 4: 動作テスト（手動実行）
設定が完了したら、PCから離れていても正しく動くかテストできます：

1. リポジトリ上部メニューの **「Actions」** タブをクリック。
2. 左側の **「Daily Stock AI Notification」** を選択。
3. 右上の **「Run workflow」** ボタンを押し、緑色の「Run workflow」をクリック。
4. 1〜2分待つと、スマホのLINEにレポートが届きます！

---

### ⏰ 配信スケジュールについて
`.github/workflows/daily_stock.yml` にて以下のスケジュールが設定されています：
- **平日 朝 08:30**（市場が動く前）
- **平日 夕方 17:30**（市場が閉まった後）

※土日は市場が休みなため配信されません。時間を変更したい場合は `.github/workflows/daily_stock.yml` 内の cron の時間を書き換えるだけで調整できます。
