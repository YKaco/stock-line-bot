import os
import json
from datetime import datetime, timezone, timedelta

HISTORY_FILE = os.path.join(os.path.dirname(__file__), "prediction_history.json")

def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def save_history(history):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

def record_predictions(watchlist_results):
    """
    本日の推奨銘柄（エントリー価格、目標株価、損切りライン）を履歴に自動記録
    """
    history = load_history()
    jst = timezone(timedelta(hours=9))
    today_str = datetime.now(jst).strftime("%Y-%m-%d")

    for item in watchlist_results:
        symbol = item["symbol"]
        price = item["current_price"]
        ai = item.get("ai", {})
        score = ai.get("total_score", 50)
        entry_val = ai.get("entry_val", price)
        target_val = ai.get("target_val", round(price * 1.08, 2))
        stop_val = ai.get("stop_val", round(price * 0.95, 2))

        # 同じ日の同一銘柄は重複記録しない
        already_recorded = any(h["date"] == today_str and h["symbol"] == symbol for h in history)
        if not already_recorded:
            history.append({
                "date": today_str,
                "symbol": symbol,
                "name": item["name"],
                "score": score,
                "action": ai.get("action_label", "中立"),
                "entry_price": entry_val,
                "target_price": target_val,
                "stop_price": stop_val,
                "current_price_at_rec": price,
                "status": "TRACKING", # TRACKING -> WIN / LOSS / EXPIRED
                "evaluated_date": None,
                "pnl_pct": None
            })

    save_history(history)

def evaluate_and_get_performance(current_stock_data_dict):
    """
    過去の予測が目標株価に到達したか（利確）、損切りにかかったかを自動検証し、
    通算勝率・平均損益率を算出する
    """
    history = load_history()
    if not history:
        return {
            "total_count": 0,
            "win_count": 0,
            "loss_count": 0,
            "win_rate": 0.0,
            "avg_profit": 0.0,
            "avg_loss": 0.0,
            "recent_results": []
        }

    updated = False
    jst = timezone(timedelta(hours=9))
    today_str = datetime.now(jst).strftime("%Y-%m-%d")

    for h in history:
        if h["status"] == "TRACKING":
            sym = h["symbol"]
            curr_data = current_stock_data_dict.get(sym)
            if not curr_data:
                continue

            curr_p = curr_data["current_price"]
            target_p = h["target_price"]
            stop_p = h["stop_price"]
            entry_p = h["entry_price"]

            # 利確目標到達
            if curr_p >= target_p:
                h["status"] = "WIN"
                h["evaluated_date"] = today_str
                h["pnl_pct"] = round(((target_p - entry_p) / entry_p) * 100, 2)
                updated = True
            # 損切りライン割れ
            elif curr_p <= stop_p:
                h["status"] = "LOSS"
                h["evaluated_date"] = today_str
                h["pnl_pct"] = round(((stop_p - entry_p) / entry_p) * 100, 2)
                updated = True

    if updated:
        save_history(history)

    # 成績集計
    completed = [h for h in history if h["status"] in ("WIN", "LOSS")]
    wins = [h for h in completed if h["status"] == "WIN"]
    losses = [h for h in completed if h["status"] == "LOSS"]

    total_closed = len(completed)
    win_rate = (len(wins) / total_closed * 100) if total_closed > 0 else 0.0
    avg_profit = (sum(w["pnl_pct"] for w in wins) / len(wins)) if wins else 0.0
    avg_loss = (sum(l["pnl_pct"] for l in losses) / len(losses)) if losses else 0.0

    return {
        "total_count": len(history),
        "closed_count": total_closed,
        "win_count": len(wins),
        "loss_count": len(losses),
        "win_rate": round(win_rate, 1),
        "avg_profit": round(avg_profit, 1),
        "avg_loss": round(avg_loss, 1),
        "tracking_count": len(history) - total_closed,
        "recent_results": completed[-3:] if completed else []
    }
