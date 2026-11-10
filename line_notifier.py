import os
import json
import requests
from datetime import datetime, timezone, timedelta

CONFIG_FILE = os.path.join(os.path.dirname(__file__), "config.json")

def load_config():
    cfg = {}
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        except Exception:
            pass
    return {
        "LINE_CHANNEL_ACCESS_TOKEN": os.environ.get("LINE_CHANNEL_ACCESS_TOKEN") or cfg.get("LINE_CHANNEL_ACCESS_TOKEN", ""),
        "LINE_USER_ID": os.environ.get("LINE_USER_ID") or cfg.get("LINE_USER_ID", "")
    }

def format_line_report(watchlist_results, ipo_list, market_indices=None, performance=None):
    """
    ユーザー様提案の洗練された超明快フォーマット
    """
    jst = timezone(timedelta(hours=9))
    today_str = datetime.now(jst).strftime("%Y年%m月%d日 %H:%M")

    lines = [
        f"📈【AI株式投資サマリー】",
        f"🕒 {today_str}",
        "===================="
    ]

    # 1. 全体の空気感
    if market_indices:
        lines.append("🌐【主要市況】")
        for idx in market_indices:
            pct = idx["pct_change"]
            sign = "+" if pct > 0 else ""
            lines.append(f"・{idx['name']}: {idx['price']:,}{idx['unit']} ({sign}{pct:.2f}%)")
        lines.append("--------------------")

    # 2. 監視銘柄（スッキリ4行構成）
    for res in watchlist_results:
        symbol = res["symbol"]
        name = res["name"]
        price = res["current_price"]
        curr = res["currency"]
        change = res["change"]
        pct = res["pct_change"]
        ai = res.get("ai", {})

        icon = "🔺" if pct > 0 else "🔻" if pct < 0 else "➖"
        sign = "+" if change > 0 else ""

        label = ai.get("simple_label", "様子見")
        badge = " 💡[購入検討]" if label == "購入検討" else " ⏸️[様子見]"

        lines.append(f"{icon} {name} ({symbol}){badge}")
        lines.append(f"・株価: {price:,} {curr} (前日比: {sign}{change:,} {curr} / {sign}{pct:.2f}%)")
        lines.append(f"・原因: {ai.get('simple_reason', '現時点で明確な値動きの原因は確認できていません。')}")
        lines.append(f"・判断: {ai.get('simple_advice', '無理に手を出さず様子見が安全です。')}")
        lines.append("--------------------")

    # 3. 本物のIPO速報
    if ipo_list:
        lines.append("🚀【最新IPO・新規上場情報】")
        for ipo in ipo_list[:2]:
            lines.append(f"・{ipo['title']}")
        lines.append("--------------------")

    lines.append("※AIの参考情報です。投資判断は自己責任で行ってください。")
    return "\n".join(lines)

def split_message_if_needed(text: str, max_chars=4000):
    if len(text) <= max_chars:
        return [text]

    chunks = []
    lines = text.split("\n")
    current_chunk = []
    current_len = 0

    for line in lines:
        line_len = len(line) + 1
        if current_len + line_len > max_chars:
            chunks.append("\n".join(current_chunk))
            current_chunk = [line]
            current_len = line_len
        else:
            current_chunk.append(line)
            current_len += line_len

    if current_chunk:
        chunks.append("\n".join(current_chunk))

    return chunks

def send_line_message(text_message: str):
    config = load_config()
    token = config.get("LINE_CHANNEL_ACCESS_TOKEN", "").strip()
    user_id = config.get("LINE_USER_ID", "").strip()

    if not token or not user_id:
        return False, "LINEチャンネルアクセストークンまたはユーザーIDが未設定です。"

    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }

    chunks = split_message_if_needed(text_message)
    message_payloads = [{"type": "text", "text": chunk} for chunk in chunks[:5]]

    payload = {
        "to": user_id,
        "messages": message_payloads
    }

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=15)
        if resp.status_code == 200:
            return True, f"LINE通知の送信に成功しました！（吹き出し数: {len(message_payloads)}）"
        else:
            return False, f"LINE送信失敗 (Status {resp.status_code}): {resp.text}"
    except Exception as e:
        return False, f"送信エラー: {str(e)}"
