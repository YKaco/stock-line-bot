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
            cfg = {}
    
    return {
        "GEMINI_API_KEY": os.environ.get("GEMINI_API_KEY") or cfg.get("GEMINI_API_KEY", "")
    }

def analyze_stock_movement_and_recommendation(stock_data: dict, general_market_context=""):
    """
    【数学的完全整合版】
    1. リスクリワード比が不利な銘柄は【新規エントリー見送り】とし、指値注文を出さない。
    2. 損益分岐勝率を明記（「期待値マイナス」の決めつけを廃止）。
    3. 丸め前数値による高精度RR比計算。
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
    status = stock_data.get("market_status", "")
    tech = stock_data.get("tech") or {
        "rsi_14": 50.0, "sma25": price, "bias25": 0.0, "atr": round(price * 0.02, 2),
        "support": round(price * 0.95, 2), "resistance": round(price * 1.05, 2), "tech_score": 25
    }

    atr = tech["atr"]
    support = tech["support"]
    resistance = tech["resistance"]
    tech_score = tech["tech_score"]
    rsi = tech["rsi_14"]
    bias = tech["bias25"]

    # 1. 想定価格の計算
    if rsi <= 28.0:
        raw_entry = price
        tentative_order = "【現在値打診買い】RSIが売られすぎ反発圏のため現値付近からエントリー"
    elif bias < -5.0:
        raw_entry = max(support, price - atr * 0.4)
        tentative_order = f"【指値待機】移動平均線下の支持線（{round(raw_entry, 2)} {currency}付近）まで引きつけて指値"
    elif rsi >= 65.0:
        raw_entry = price - atr * 0.8
        tentative_order = f"【反発確認待ち】過熱警戒のため{round(raw_entry, 2)} {currency}付近まで押し、下ヒゲ陽線を確認後に再評価"
    else:
        raw_entry = price - atr * 0.3
        tentative_order = f"【指値待機】小幅な押し目（{round(raw_entry, 2)} {currency}付近）で指値"

    # 2. 損切りライン
    raw_stop = min(support, raw_entry - atr * 1.0)
    risk_dist = max(atr * 0.5, raw_entry - raw_stop)

    # 3. 利確目標（1.5〜2.5 ATR以内、または直近10日抵抗帯）
    atr_target = raw_entry + atr * 1.8
    if raw_entry < resistance <= raw_entry + atr * 2.5:
        raw_target = resistance
    else:
        raw_target = atr_target

    profit_dist = max(0.01, raw_target - raw_entry)

    # 4. 丸め前の正確なリスクリワード比と損益分岐勝率の算出
    exact_rr = profit_dist / risk_dist
    breakeven_win_rate = round((1.0 / (1.0 + exact_rr)) * 100, 1)
    rr_str = f"{exact_rr:.2f}:1"

    # 5. リスクリワード判定と方針確定
    is_favorable = exact_rr >= 1.2
    entry_val = round(raw_entry, 2)
    target_val = round(raw_target, 2)
    stop_val = round(raw_stop, 2)

    if not is_favorable:
        # ★見送り推奨時は注文方針を「見送り・待機」に完全統一（指値を出させない）
        action_label = "【見送り推奨】損益分岐勝率過高"
        order_type = "【新規注文見送り】リスクリワード比が低く損益分岐に必要な勝率が高すぎるため、注文を行わず条件改善まで監視待機"
        strategy_summary = f"リスクリワード比が{rr_str}と不利（損益分岐勝率が約{breakeven_win_rate}%と高水準）のため、新規エントリーは見送り。上値抵抗線のブレイクまたは深い押し目を待機。"
    else:
        action_label = "押し目買い検討" if tech_score >= 35 else "静観/中立"
        order_type = tentative_order
        strategy_summary = f"支持線({support}{currency})とATR({atr}{currency})に基づく現実的スイング設計。リスクリワード比 {rr_str}（損益分岐勝率 約{breakeven_win_rate}%）。"

    news = stock_data.get("news", [])
    news_lines = [f"- [{n.get('publisher','報道')}] {n['title']}" for n in news] if news else ["- 特になし"]

    prompt = f"""
あなたは数学的規律と市場構造（S/R・ATR）を熟知したクオンツ・ポートフォリオマネージャーです。
以下の客観データに基づき、プロの投資判断を作成してください。

【厳格ルール】
1. リスクリワード比（{rr_str}）が1.2未満の場合、新規注文は一切出さず「見送り・監視待機」としてください。
2. 評価表記は「AI総合評価スコア: ○点/100点」としてください。
   - テクニカル客観点（算出値: {tech_score}点 / 50点）
   - ファンダメンタルズ/地合い点（あなたが0〜50点で客観評価）
   - 合計スコア ＝ テクニカル点 ＋ ファンダ点
3. 事実無根の噂や勝手なストーリーの創作は厳禁です。

【確定銘柄データ】
- 銘柄: {name} ({symbol}) [{status}]
- 現在値: {price} {currency} (前日終値: {prev_price} {currency} / 前日比: {change:+} / {pct:+.2f}%)
- テクニカル客観指標:
  * RSI (14日): {rsi}
  * 25日移動平均線: {tech['sma25']} {currency} (乖離率: {bias:+.2f}%)
  * ATR: {atr} {currency}
  * 直近支持線: {support} {currency} / 短期抵抗線: {resistance} {currency}
- 関連ニュース:
{chr(10).join(news_lines)}
- 参考市場市況: {general_market_context}

【出力フォーマット】
以下のJSONフォーマットのみを出力してください（Markdownコードブロック ```json ... ``` で囲む）:
{{
  "reason": "本日の値動き要因の客観的分析（ニュースとセクター地合いに基づき2〜3文で平易に説明）",
  "fundamental_score": 0〜50の整数,
  "action_label": "{action_label}",
  "strategy_detail": "{strategy_summary}"
}}
"""

    if not api_key:
        total = tech_score + (25 if pct > 0 else 15)
        return {
            "reason": f"前日終値{prev_price}{currency}から{change:+}{currency}（{pct:+.2f}%）で推移。RSI={rsi}、25日線乖離={bias:+.2f}%。",
            "total_score": total,
            "tech_score": tech_score,
            "fundamental_score": 20,
            "action_label": action_label,
            "entry_price": f"{entry_val} {currency}" if is_favorable else "なし (見送り)",
            "order_type": order_type,
            "target_price": f"{target_val} {currency}",
            "stop_loss": f"{stop_val} {currency}",
            "reward_risk": rr_str,
            "entry_val": entry_val,
            "target_val": target_val,
            "stop_val": stop_val,
            "is_favorable": is_favorable,
            "strategy_detail": strategy_summary
        }

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.1,
            "response_mime_type": "application/json"
        }
    }

    models_to_try = [
        "gemini-2.5-flash",
        "gemini-flash-latest",
        "gemini-2.5-pro"
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
                    f_score = data.get("fundamental_score", 25)
                    data["total_score"] = tech_score + f_score
                    data["tech_score"] = tech_score
                    data["entry_price"] = f"{entry_val} {currency}" if is_favorable else "なし (見送り)"
                    data["order_type"] = order_type
                    data["target_price"] = f"{target_val} {currency}"
                    data["stop_loss"] = f"{stop_val} {currency}"
                    data["reward_risk"] = rr_str
                    data["entry_val"] = entry_val
                    data["target_val"] = target_val
                    data["stop_val"] = stop_val
                    data["is_favorable"] = is_favorable
                    return data
        except Exception as e:
            print(f"Error calling {model_name}: {e}")

    total = tech_score + 20
    return {
        "reason": f"前日終値{prev_price}{currency}から{change:+}{currency}（{pct:+.2f}%）で推移。RSI={rsi}、25日線乖離={bias:+.2f}%。",
        "total_score": total,
        "tech_score": tech_score,
        "fundamental_score": 20,
        "action_label": action_label,
        "entry_price": f"{entry_val} {currency}" if is_favorable else "なし (見送り)",
        "order_type": order_type,
        "target_price": f"{target_val} {currency}",
        "stop_loss": f"{stop_val} {currency}",
        "reward_risk": rr_str,
        "entry_val": entry_val,
        "target_val": target_val,
        "stop_val": stop_val,
        "is_favorable": is_favorable,
        "strategy_detail": strategy_summary
    }
