import os
import json
import base64
import urllib.request
import urllib.error

WATCHLIST_FILE = os.path.join(os.path.dirname(__file__), "watchlist.json")

def load_watchlist():
    if os.path.exists(WATCHLIST_FILE):
        try:
            with open(WATCHLIST_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def save_watchlist(items, github_token=""):
    """
    ローカルのwatchlist.jsonを更新し、
    GitHubトークンがあればGitHubリポジトリ(YKaco/stock-line-bot)のwatchlist.jsonも自動更新する
    """
    # 1. ローカルファイルの保存
    try:
        with open(WATCHLIST_FILE, "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Local save error: {e}")

    # 2. GitHubリポジトリへの同期（クラウド運用時）
    token = github_token or os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN", "")
    if not token:
        return True, "ローカルに保存しました（GitHubトークン未設定のためクラウド同期はスキップ）"

    repo = "YKaco/stock-line-bot"
    path = "watchlist.json"
    api_url = f"https://api.github.com/repos/{repo}/contents/{path}"

    try:
        content_str = json.dumps(items, ensure_ascii=False, indent=2)
        content_b64 = base64.b64encode(content_str.encode("utf-8")).decode("utf-8")

        # 最新のshaハッシュ値を取得
        sha = None
        req_get = urllib.request.Request(
            api_url,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "Streamlit-Stock-Bot"
            }
        )
        try:
            with urllib.request.urlopen(req_get, timeout=8) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                sha = data.get("sha")
        except urllib.error.HTTPError as he:
            if he.code != 404:
                raise he

        payload = {
            "message": "Update watchlist.json from Web Dashboard",
            "content": content_b64
        }
        if sha:
            payload["sha"] = sha

        req_put = urllib.request.Request(
            api_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github.v3+json",
                "Content-Type": "application/json",
                "User-Agent": "Streamlit-Stock-Bot"
            },
            method="PUT"
        )

        with urllib.request.urlopen(req_put, timeout=10) as resp:
            if resp.status in (200, 201):
                return True, "GitHubリポジトリの銘柄リストを更新しました！"
            else:
                return False, f"GitHub更新ステータス: {resp.status}"

    except Exception as e:
        print(f"GitHub Sync Error: {e}")
        return False, f"GitHub同期エラー: {str(e)}"
