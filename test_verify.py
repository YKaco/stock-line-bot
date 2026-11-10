from stock_service import get_stock_data

symbols = ['SPCX', 'NVDA', 'AAPL', 'INTC', '9432.T', '7203.T', '^IXIC', '^N225']
print("--- データ整合性検証テスト ---")
for s in symbols:
    d = get_stock_data(s)
    if d:
        print(f"[{s}] 現在値:{d['current_price']} | 前日終値:{d['prev_price']} | 前日比:{d['change']} ({d['pct_change']}%) | ATR:{d['tech']['atr']} | RSI:{d['tech']['rsi_14']}")
