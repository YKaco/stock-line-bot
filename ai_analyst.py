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
    【誠実・平易・リスク併記版】
    - 断定表現（今すぐ買い・割安・安全）を完全排除
    - 理由がない場合は正直に「現時点で明確な原因は未確認」と表示
    - 日時表現を正確化（米国株＝前日の米国市場、日本株＝本日の東証）
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
    is_jp = symbol.endswith(".T")
    market_name = "本日の東証市場" if is_jp else "前日の米国市場"

    tech = stock_data.get("tech") or {"rsi_14": 50, "bias25": 0}
    rsi = tech.get("rsi_14", 50)
    bias = tech.get("bias25", 0)

    news = stock_data.get("news", [])
    has_real_news = len(news) > 0
    news_lines = [f"- {n['title']}" for n in news] if has_real_news else ["- 特になし"]

    # ベースとなる冷静なアドバイス設計（断定を避けリスク併記）
    if pct <= -3.5 or rsi <= 30.0:
        default_label = "購入検討"
        default_advice = f"大きく値下がりしています。自律反発する可能性がありますが、さらに下がるリスクもあります。購入する場合は一度に買わず、少額からの分散購入を検討したい水準です。"
    elif pct >= 4.0 or rsi >= 65.0 or bias >= 7.0:
        default_label = "様子見"
        default_advice = f"大きく上昇しています。今から追いかけて買うと高値づかみになるリスクがあるため、少し値下がりして落ち着くのを待ちたい銘柄です。"
    else:
        default_label = "様子見"
        default_advice = f"極端な値動きはなく中立的な状態です。無理に手を出さず、より有利な押し目や次のチャンスを待つのが賢明です。"

    # ニュースの有無による正直な原因
    if not has_real_news:
        default_reason = "現時点で明確な値動きの原因は確認できていません。"
    else:
        default_reason = f"{market_name}において前日終値{prev_price}{currency}から{change:+}{currency}（{pct:+.2f}%）で推移しています。"

    prompt = f"""
あなたは初心者の個人投資家にアドバイスする、極めて誠実で冷静なプロの投資アドバイザーです。
以下のルールを厳格に守って文章を作成してください。

【厳格ルール】
1. 「今すぐ買い」「絶対に買い」「安全」などの煽り・断定表現は厳禁です。
   大きく下落している銘柄を「購入検討」とする際も、「反発の可能性がある一方、さらに下落するリスクもあるため、少額からの購入を検討できます」と必ず両面のリスクを併記してください。
2. 上昇している銘柄に対して「目立った方向性がない」と誤認せず、「大きく上昇していますが、今から買うと高値づかみになるリスクもあるため、次の押し目を待ちましょう」と的確に助言してください。
3. 時間や市場の表現は、日本株なら「本日の東証市場」、米国株なら「前日の米国市場」としてください（「今日」と表現しないこと）。
4. 個別ニュースがない（「特になし」）場合は、無理に理由を作らず必ず「現時点で明確な値動きの原因は確認できていません。」と回答してください。
5. 専門用語（RSI、ATR、乖離率など）は使わず、誰でも直感的に理解できる平易な言葉で説明してください。

【銘柄データ】
- 銘柄名: {name} ({symbol}) [{market_name}]
- 今の株価: {price} {currency} (前日比: {change:+} {currency} / {pct:+.2f}%)
- ニュース情報:
{chr(10).join(news_lines)}

【回答フォーマット】
以下のJSONフォーマットのみを出力してください（Markdownコードブロック ```json ... ``` で囲む）:
{{
  "simple_label": "「購入検討」「様子見」のいずれか",
  "simple_reason": "値動きの原因（ニュースがない場合は「現時点で明確な値動きの原因は確認できていません。」と記載）",
  "simple_advice": "買うべきか待つべきかのアドバイス（リスクと注意点を必ず併記）"
}}
"""

    if not api_key:
        return {
            "simple_label": default_label,
            "simple_reason": default_reason,
            "simple_advice": default_advice
        }

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.1,
            "response_mime_type": "application/json"
        }
    }

    models_to_try = ["gemini-2.5-flash", "gemini-flash-latest"]

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
        "simple_label": default_label,
        "simple_reason": default_reason,
        "simple_advice": default_advice
    }
