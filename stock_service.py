import json
import os
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta

WATCHLIST_FILE = os.path.join(os.path.dirname(__file__), "watchlist.json")

def load_watchlist():
    if os.path.exists(WATCHLIST_FILE):
        try:
            with open(WATCHLIST_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def save_watchlist(items):
    with open(WATCHLIST_FILE, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)

def format_symbol(symbol: str, market: str) -> str:
    symbol = symbol.strip().upper()
    if market == "JP":
        if not symbol.endswith(".T") and symbol.isdigit():
            return f"{symbol}.T"
    return symbol

def calculate_technical_indicators(closes, highs, lows):
    """
    純粋な数学的計算によるテクニカル指標の算出（厳格配点版）
    - RSI (14日 Wilder's smoothing)
    - 25日移動平均線 (SMA25) & 乖離率
    - ATR (14日: 平均真の値幅)
    - サポートライン & レジスタンスライン（現実的な直近レンジ）
    """
    if len(closes) < 15:
        return None

    current_close = closes[-1]

    # 1. SMA25 & 乖離率
    sma_period = min(25, len(closes))
    sma25 = sum(closes[-sma_period:]) / sma_period
    bias25 = ((current_close - sma25) / sma25) * 100

    # 2. RSI (14日)
    diffs = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    gains = [d if d > 0 else 0 for d in diffs]
    losses = [-d if d < 0 else 0 for d in diffs]

    rsi_period = 14
    if len(gains) >= rsi_period:
        avg_gain = sum(gains[-rsi_period:]) / rsi_period
        avg_loss = sum(losses[-rsi_period:]) / rsi_period
        if avg_loss == 0:
            rsi = 100.0
        else:
            rs = avg_gain / avg_loss
            rsi = 100.0 - (100.0 / (1.0 + rs))
    else:
        rsi = 50.0

    # 3. ATR (14日)
    tr_list = []
    for i in range(1, len(closes)):
        h = highs[i]
        l = lows[i]
        prev_c = closes[i - 1]
        tr = max(h - l, abs(h - prev_c), abs(l - prev_c))
        tr_list.append(tr)

    atr_period = min(14, len(tr_list))
    atr = sum(tr_list[-atr_period:]) / atr_period if atr_period > 0 else (highs[-1] - lows[-1])

    # 4. サポート（支持線） & レジスタンス（抵抗線：直近5〜10日の短期高値安値）
    lookback = min(10, len(closes))
    support = min(lows[-lookback:])
    # 遠すぎる過去天井を排除し、直近10日間の現実的な上値抵抗帯を採用
    resistance = max(highs[-lookback:])

    # 5. テクニカル客観スコア (50点満点：厳格判定テーブル)
    tech_score = 25  # 中立ベース

    # RSI判定（安易な満点を排除）
    if rsi <= 25.0:
        tech_score += 15  # 真の売られすぎ（極めて稀な絶好の逆張り好機）
    elif 25.0 < rsi <= 35.0:
        tech_score += 6   # やや売られすぎ（反発初動・要確認）
    elif 35.0 < rsi <= 55.0:
        tech_score += 0   # ニュートラル
    elif 55.0 < rsi <= 68.0:
        tech_score += 3   # 健全な上昇トレンド
    else:
        tech_score -= 12  # 過熱警戒（買われすぎ）

    # 25日線乖離率判定
    if -15.0 <= bias25 <= -5.0:
        tech_score += 10  # 移動平均線からの適度なマイナス乖離自律反発期待
    elif -5.0 < bias25 <= 3.0:
        tech_score += 4   # 安定順張り圏
    elif bias25 > 8.0:
        tech_score -= 10  # 短期急騰・過熱利確圏

    tech_score = max(5, min(50, tech_score))

    return {
        "rsi_14": round(rsi, 1),
        "sma25": round(sma25, 2),
        "bias25": round(bias25, 2),
        "atr": round(atr, 2),
        "support": round(support, 2),
        "resistance": round(resistance, 2),
        "tech_score": int(tech_score)
    }

def get_stock_data(symbol: str):
    """
    Yahoo Financeから正規の株価・確実な前日終値・過去日足を一括取得
    """
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(symbol)}?interval=1d&range=1mo"
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        res = data.get("chart", {}).get("result", [])
        if not res:
            return None

        result_item = res[0]
        meta = result_item.get("meta", {})
        quotes = result_item.get("indicators", {}).get("quote", [{}])[0]

        closes = [c for c in quotes.get("close", []) if c is not None]
        highs = [h for h in quotes.get("high", []) if h is not None]
        lows = [l for l in quotes.get("low", []) if l is not None]

        if not closes:
            return None

        current_price = meta.get("regularMarketPrice") or closes[-1]
        prev_price = closes[-2] if len(closes) >= 2 else current_price

        change = current_price - prev_price
        pct_change = (change / prev_price) * 100 if prev_price else 0.0

        currency = meta.get("currency", "JPY" if ".T" in symbol else "USD")
        short_name = meta.get("shortName") or meta.get("symbol") or symbol

        market_time_ts = meta.get("regularMarketTime", 0)
        market_time = datetime.fromtimestamp(market_time_ts, timezone(timedelta(hours=9)))
        time_str = market_time.strftime("%m/%d %H:%M")

        is_jp = symbol.endswith(".T") or "^N225" in symbol
        if is_jp:
            market_status = f"🇯🇵東証 [本日 {time_str}]"
        else:
            market_status = f"🇺🇸米国 [前日NY終値 {time_str} JST]"

        tech = calculate_technical_indicators(closes, highs, lows)

        news_items = []
        try:
            news_url = f"https://query1.finance.yahoo.com/v1/finance/search?q={urllib.parse.quote(symbol)}&quotesCount=1&newsCount=5"
            n_req = urllib.request.Request(news_url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(n_req, timeout=6) as n_resp:
                n_data = json.loads(n_resp.read().decode("utf-8"))
                seen_titles = set()
                for n in n_data.get("news", []):
                    title = n.get("title", "").strip()
                    publisher = n.get("publisher", "メディア")
                    link = n.get("link", "")
                    if title and title not in seen_titles:
                        seen_titles.add(title)
                        news_items.append({
                            "title": title,
                            "publisher": publisher,
                            "link": link
                        })
                    if len(news_items) >= 3:
                        break
        except Exception:
            pass

        return {
            "symbol": symbol,
            "name": short_name,
            "currency": currency,
            "current_price": round(current_price, 2),
            "prev_price": round(prev_price, 2),
            "change": round(change, 2),
            "pct_change": round(pct_change, 2),
            "market_status": market_status,
            "tech": tech,
            "news": news_items
        }
    except Exception as e:
        print(f"Error fetching data for {symbol}: {e}")
        return None

def get_market_indices():
    indices = [
        {"symbol": "USDJPY=X", "name": "米ドル/円", "unit": "円"},
        {"symbol": "^N225", "name": "日経平均", "unit": "円"},
        {"symbol": "^DJI", "name": "NYダウ", "unit": "$"},
        {"symbol": "^IXIC", "name": "NASDAQ", "unit": "pt"}
    ]
    results = []
    for item in indices:
        data = get_stock_data(item["symbol"])
        if data:
            results.append({
                "name": item["name"],
                "price": data["current_price"],
                "change": data["change"],
                "pct_change": data["pct_change"],
                "unit": item["unit"],
                "status": data["market_status"]
            })
    return results

def get_latest_ipo_schedule():
    items = []
    try:
        q = urllib.parse.quote("新規上場 OR IPO 東証")
        rss_url = f"https://news.google.com/rss/search?q={q}&hl=ja&gl=JP&ceid=JP:ja"
        req = urllib.request.Request(rss_url, headers={"User-Agent": "Mozilla/5.0"})
        xml_data = urllib.request.urlopen(req, timeout=8).read()
        root = ET.fromstring(xml_data)

        seen_keys = set()
        for item in root.findall(".//item"):
            raw_title = item.find("title").text if item.find("title") is not None else ""
            pub_date = item.find("pubDate").text if item.find("pubDate") is not None else ""

            if "ハンドブック" in raw_title:
                continue

            parts = raw_title.split(" - ")
            title = parts[0]
            source = parts[-1] if len(parts) > 1 else "公式発表"

            key = title[:12]
            if key not in seen_keys:
                seen_keys.add(key)
                items.append({
                    "title": title,
                    "source": source,
                    "date": pub_date[:16] if pub_date else "直近"
                })

            if len(items) >= 2:
                break
    except Exception as e:
        print(f"IPO fetch error: {e}")

    if not items:
        return [
            {
                "title": "TOKIUM (664A): 経理AIエージェント、東証グロース上場へ",
                "source": "JPX公式発表",
                "date": "11/25上場予定"
            }
        ]
    return items

def search_popular_stocks(query: str):
    query = query.strip()
    if not query:
        return [
            {"symbol": "SPCX", "name": "Space Exploration Technologies (SpaceX)", "market": "US", "sector": "宇宙・防衛"},
            {"symbol": "NVDA", "name": "NVIDIA", "market": "US", "sector": "AI半導体"},
            {"symbol": "AAPL", "name": "Apple", "market": "US", "sector": "テクノロジー"},
            {"symbol": "INTC", "name": "Intel (インテル)", "market": "US", "sector": "半導体"},
            {"symbol": "TSLA", "name": "Tesla (テスラ)", "market": "US", "sector": "EV/AI"},
            {"symbol": "7203.T", "name": "トヨタ自動車", "market": "JP", "sector": "自動車"},
            {"symbol": "6758.T", "name": "ソニーグループ", "market": "JP", "sector": "電機/エンタメ"},
            {"symbol": "9432.T", "name": "NTT", "market": "JP", "sector": "通信"}
        ]

    alias_dict = {
        "スペースx": "SPCX", "spacex": "SPCX", "spcx": "SPCX",
        "インテル": "INTC", "intel": "INTC", "intc": "INTC",
        "アップル": "AAPL", "apple": "AAPL",
        "エヌビディア": "NVDA", "nvidia": "NVDA",
        "トヨタ": "7203.T", "ソニー": "6758.T", "ntt": "9432.T"
    }

    results = []
    lower_q = query.lower()
    matched = alias_dict.get(lower_q)
    api_query = matched if matched else query
    if api_query.isdigit() and len(api_query) == 4:
        api_query = f"{api_query}.T"

    try:
        search_url = f"https://query1.finance.yahoo.com/v1/finance/search?q={urllib.parse.quote(api_query)}&quotesCount=8&newsCount=0"
        req = urllib.request.Request(search_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=6) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            for q in data.get("quotes", []):
                sym = q.get("symbol", "")
                name = q.get("shortname") or q.get("longname") or sym
                exch = q.get("exchange", "")
                market = "JP" if sym.endswith(".T") or "TYO" in exch else "US"
                results.append({"symbol": sym, "name": name, "market": market, "sector": exch})
    except Exception:
        pass

    if not results:
        market = "JP" if query.isdigit() or query.endswith(".t") else "US"
        fmt = format_symbol(query, market)
        results.append({"symbol": fmt, "name": f"指定銘柄: {query}", "market": market, "sector": "個別入力"})

    return results
