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
            cfg = {}

    return {
        "LINE_CHANNEL_ACCESS_TOKEN": os.environ.get("LINE_CHANNEL_ACCESS_TOKEN") or cfg.get("LINE_CHANNEL_ACCESS_TOKEN", ""),
        "LINE_USER_ID": os.environ.get("LINE_USER_ID") or cfg.get("LINE_USER_ID", "")
    }

def format_line_report(watchlist_results, ipo_list, market_indices=None, performance=None):
    """
    専門用語ゼロ！直感的に一目でわかるシンプル投資レポート
    「いくら・どれくらい動いた・なぜ・買うべきか待つべきか」
    """
    jst = timezone(timedelta(hours=9))
    today_str = datetime.now(jst).strftime("%Y/%m/%d %H:%M")

    lines = [
        f"📊【AI株式 投資サマリー】",
        f"🕒 {today_str}",
        "===================="
    ]

    # 1. 全体の空気感（ざっくり）
    if market_indices:
        lines.append("🌐【今の全体の空気感】")
        for idx in market_indices:
            pct = idx["pct_change"]
            trend = "大幅上昇 🟢" if pct >= 1.5 else "小幅高 🟢" if pct > 0 else "大幅下落 🔴" if pct <= -1.5 else "小幅安 🔴" if pct < 0 else "横ばい ⚪"
            sign = "+" if pct > 0 else ""
            lines.append(f"・{idx['name']}: {idx['price']:,}{idx['unit']} ({sign}{pct:.2f}% / {trend})")
        lines.append("--------------------")

    # 2. 監視銘柄の状況（4行構成）
    lines.append("📈【あなたの注目銘柄】")
    for res in watchlist_results:
        symbol = res["symbol"]
        name = res["name"]
        price = res["current_price"]
        prev = res["prev_price"]
        curr = res["currency"]
        change = res["change"]
        pct = res["pct_change"]
        ai = res.get("ai", {})

        icon = "🔺" if pct > 0 else "🔻" if pct < 0 else "➖"
        sign = "+" if change > 0 else ""

        # 結論ラベル（買うべきか待つべきか）
        advice = ai.get("simple_advice", "様子見")
        advice_badge = " 🔥【今すぐ買い候補】" if "買い" in advice and "見送り" not in advice else " ⏸️【今は待つべき】"

        lines.append(f"\n{icon} {name} ({symbol}){advice_badge}")
        lines.append(f"① 今の株価: {price:,} {curr}")
        lines.append(f"② どのくらい動いた？: {sign}{change:,} {curr} ({sign}{pct:.2f}%)")
        lines.append(f"③ 原因は？: {ai.get('simple_reason', '目立った突発材料はなく市場全体に連動した動きです。')}")
        lines.append(f"④ 買うべき？待つべき？:\n   👉 {advice}")
        lines.append("--------------------")

    # 3. 新規上場(IPO)情報
    if ipo_list:
        lines.append("\n🚀【新規上場(IPO)ニュース】")
        for ipo in ipo_list[:2]:
            lines.append(f"・{ipo['title']}")
        lines.append("--------------------")

    lines.append("\n※AIの参考情報です。投資判断はご自身の責任で行ってください。")
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
