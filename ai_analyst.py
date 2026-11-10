import os
import json
import requests

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
        "GEMINI_API_KEY": os.environ.get("GEMINI_API_KEY") or cfg.get("GEMINI_API_KEY", "")
    }

def analyze_stock_movement_and_recommendation(stock_data: dict, general_market_context=""):
    """
    専門用語を一切使わず、「なぜ動いたか」「今買うべきか待つべきか」を
    小学生でもわかる日本語でスッキリ解説する。
    """
    config = load_config()
    api_key = config.get("GEMINI_API_KEY", "").strip()

    symbol = stock_data["symbol"]
    name = stock_data["name"]
    price = stock_data["current_price"]
    prev_price = stock_data["prev_price"]
    change = stock_data["change"]
    pct = stock_data["pct_change"]
    currency = stock_data["currency"]
    tech = stock_data.get("tech") or {"rsi_14": 50, "bias25": 0, "atr": 5}
    rsi = tech.get("rsi_14", 50)
    bias = tech.get("bias25", 0)

    news = stock_data.get("news", [])
    news_lines = [f"- {n['title']}" for n in news] if news else ["- 特になし"]

    # 買うべきか待つべきかのベース判定
    if rsi <= 30.0:
        default_advice = f"【今すぐ買いの好機！】大きく売られて割安圏にあります。{price} {currency}付近から打診買いを検討できます。"
    elif rsi >= 65.0 or bias >= 8.0:
        default_advice = f"【今は待つべき！】短期間で上がりすぎて過熱しています。一度値下がりして落ち着くまで様子見しましょう。"
    elif pct < -3.0:
        default_advice = f"【押し目を待つべき】下落の勢いがあるため、焦って買わずに底打ちを確認してから買いましょう。"
    else:
        default_advice = f"【様子見が安全】目立った方向性がないため、無理に手を出さず次のチャンスを待ちましょう。"

    prompt = f"""
あなたは初心者の個人投資家にアドバイスする親切でわかりやすい投資アドバイザーです。
専門用語（RSI、ATR、レジスタンス、ボラティリティ、クオンツなど）は一切使わず、
中学生や初心者でも一瞬で理解できる平易な言葉で解説してください。

【銘柄データ】
- 銘柄: {name} ({symbol})
- 今の株価: {price} {currency}
- 前日からの変化: {change:+} {currency} ({pct:+.2f}%)
- ニュース情報:
{chr(10).join(news_lines)}

【回答してほしい内容】
以下のJSONフォーマットのみを出力してください（Markdownコードブロック ```json ... ``` で囲む）:
{{
  "simple_reason": "株価が動いた原因（『なぜ上がったのか・下がったのか』を、ニュースや世の中の動きを踏まえて1〜2文でやさしく説明）",
  "simple_advice": "買うべきか？待つべきか？（ズバリ『【買い時！】○○だから今が狙い目です』や『【今は待つべき！】○○まで下がるのを待ちましょう』など、初心者が迷わない具体的な一言アドバイス）"
}}
"""

    if not api_key:
        trend = "上昇" if pct > 0 else "下落" if pct < 0 else "横ばい"
        return {
            "simple_reason": f"前日から{change:+}{currency}（{pct:+.2f}%）の{trend}となっています。目立ったニュースがなければ全体の相場に連動した動きです。",
            "simple_advice": default_advice
        }

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.2,
            "response_mime_type": "application/json"
        }
    }

    models_to_try = [
        "gemini-2.5-flash",
        "gemini-flash-latest"
    ]

    for model_name in models_to_try:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
            resp = requests.post(url, json=payload, timeout=20)
            if resp.status_code == 200:
                resp_json = resp.json()
                candidates = resp_json.get("candidates", [])
                if candidates:
                    parts = candidates[0]["content"]["parts"]
                    text = "".join([p.get("text", "") for p in parts]).strip()
                    data = json.loads(text)
                    return data
        except Exception:
            pass

    return {
        "simple_reason": f"前日終値{prev_price}{currency}から{change:+}{currency}（{pct:+.2f}%）で推移しています。",
        "simple_advice": default_advice
    }
