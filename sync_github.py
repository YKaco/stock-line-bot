import os
import json
import base64
import urllib.request
import urllib.error

CONFIG_FILE = os.path.join(os.path.dirname(__file__), "config.json")

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def push_file_to_github(repo, file_path, github_path, token):
    if not os.path.exists(file_path):
        return False, f"Not found: {file_path}"

    with open(file_path, "rb") as f:
        content_b64 = base64.b64encode(f.read()).decode("utf-8")

    api_url = f"https://api.github.com/repos/{repo}/contents/{github_path}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "AutoPusher"
    }

    # 既存ファイルのshaを取得
    sha = None
    try:
        req_get = urllib.request.Request(api_url, headers=headers)
        with urllib.request.urlopen(req_get, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            sha = data.get("sha")
    except urllib.error.HTTPError as e:
        if e.code != 404:
            return False, f"GET error: {e}"

    payload = {
        "message": f"Auto update {github_path}",
        "content": content_b64
    }
    if sha:
        payload["sha"] = sha

    req_put = urllib.request.Request(
        api_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={**headers, "Content-Type": "application/json"},
        method="PUT"
    )

    try:
        with urllib.request.urlopen(req_put, timeout=15) as resp:
            if resp.status in (200, 201):
                return True, "OK"
            return False, f"Status: {resp.status}"
    except Exception as e:
        return False, str(e)

def main():
    cfg = load_config()
    token = cfg.get("GITHUB_TOKEN") or os.environ.get("GITHUB_TOKEN", "").strip()

    if not token:
        print("[!] config.json に GITHUB_TOKEN (ghp_...) が設定されていません。")
        token = input("GitHub Personal Access Token (ghp_...) を入力してください: ").strip()
        if token:
            cfg["GITHUB_TOKEN"] = token
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(cfg, f, ensure_ascii=False, indent=2)

    repo = "YKaco/stock-line-bot"
    print(f"[*] GitHub リポジトリ ({repo}) への全自動 push を開始します...\n")

    files_to_sync = [
        ("stock_service.py", "stock_service.py"),
        ("ai_analyst.py", "ai_analyst.py"),
        ("line_notifier.py", "line_notifier.py"),
        ("prediction_tracker.py", "prediction_tracker.py"),
        ("daily_job.py", "daily_job.py"),
        ("app.py", "app.py"),
        ("watchlist.json", "watchlist.json"),
        (".github/workflows/daily_stock.yml", ".github/workflows/daily_stock.yml")
    ]

    base_dir = os.path.dirname(__file__)

    for local_f, gh_f in files_to_sync:
        local_full = os.path.join(base_dir, local_f.replace("/", os.sep))
        print(f"[*] アップロード中: {gh_f} ... ", end="", flush=True)
        ok, msg = push_file_to_github(repo, local_full, gh_f, token)
        if ok:
            print("完了 ✅")
        else:
            print(f"失敗 ❌ ({msg})")

    print("\n🎉 すべてのファイルを GitHub へ一括送信（push）完了しました！")

if __name__ == "__main__":
    main()
