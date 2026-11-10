import sys
import os
from stock_service import load_watchlist, get_stock_data, get_latest_ipo_schedule, get_market_indices
from ai_analyst import analyze_stock_movement_and_recommendation
from line_notifier import format_line_report, send_line_message
from prediction_tracker import record_predictions, evaluate_and_get_performance

def run_daily_notification():
    print("[*] 毎日の投資レポート作成を開始します...")
    
    # 1. 主要市況の取得
    print("[*] 主要マクロ市況（為替・株価指数）を取得中...")
    market_indices = get_market_indices()

    # 2. 監視銘柄の取得
    watchlist = load_watchlist()
    if not watchlist:
        print("[!] 監視リストが空です。")
        return

    market_context_str = ", ".join([f"{m['name']}:{m['price']}{m['unit']}({m['pct_change']:+.2f}%)" for m in market_indices])

    report_data = []
    stock_dict = {}
    for item in watchlist:
        print(f"[*] 株価取得中: {item['name']} ({item['symbol']})...")
        s_data = get_stock_data(item["symbol"])
        if s_data:
            s_data["name"] = item.get("name", s_data["name"])
            stock_dict[item["symbol"]] = s_data
            print(f"[*] AI分析中: {s_data['name']}...")
            ai_res = analyze_stock_movement_and_recommendation(s_data, general_market_context=market_context_str)
            s_data["ai"] = ai_res
            report_data.append(s_data)

    # 3. 予測トラッカーによる過去実績の評価と今回の推奨記録
    print("[*] 過去予測の成績集計 & 今回の予測を記録中...")
    perf = evaluate_and_get_performance(stock_dict)
    record_predictions(report_data)

    # 4. 本物のIPO速報取得
    ipos = get_latest_ipo_schedule()

    # 5. レポート構築
    msg_text = format_line_report(report_data, ipos, market_indices=market_indices, performance=perf)
    
    print("\n--- 送信メッセージプレビュー ---")
    print(msg_text)
    print("----------------------------\n")

    print("[*] LINEへ送信中...")
    ok, status_msg = send_line_message(msg_text)
    print(f"[*] 送信結果: {status_msg}")

if __name__ == "__main__":
    run_daily_notification()
