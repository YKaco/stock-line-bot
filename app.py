import streamlit as st
import json
import os
from stock_service import (
    get_stock_data, search_popular_stocks, get_latest_ipo_schedule, format_symbol, get_market_indices
)
from watchlist_sync import load_watchlist, save_watchlist
from ai_analyst import analyze_stock_movement_and_recommendation, load_config
from line_notifier import format_line_report, send_line_message

st.set_page_config(
    page_title="AI株式アシスタント & LINE通知ダッシュボード",
    page_icon="📈",
    layout="wide"
)

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")

def load_local_config():
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_local_config(cfg):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

current_cfg = load_local_config()
gh_token = current_cfg.get("GITHUB_TOKEN") or os.environ.get("GITHUB_TOKEN", "")

st.title("📈 AI株式投資アシスタント")
st.markdown("毎日の株価追跡、**為替・主要市況サマリー**、**なぜ上がった/下がったかのAI解説**、**推奨度(0〜100%)**、**IPO速報**をLINEにお届けする統合システムです。")

# タブ構成
tab_watchlist, tab_search, tab_report, tab_settings = st.tabs([
    "📋 監視リスト管理",
    "🔍 銘柄検索・追加",
    "📊 デイリーレポート・LINE送信",
    "⚙️ 設定 (APIキー・LINE連携)"
])

# ----------------- タブ1: 監視リスト -----------------
with tab_watchlist:
    st.subheader("現在監視中の銘柄リスト（自動通知の対象）")
    watchlist = load_watchlist()

    if not watchlist:
        st.info("現在監視銘柄が登録されていません。「銘柄検索・追加」タブから銘柄を追加してください。")
    else:
        col_h1, col_h2, col_h3, col_h4 = st.columns([2, 4, 3, 2])
        col_h1.markdown("**コード/ティッカー**")
        col_h2.markdown("**銘柄名**")
        col_h3.markdown("**市場**")
        col_h4.markdown("**区分**")
        st.divider()

        for item in watchlist:
            c1, c2, c3, c4 = st.columns([2, 4, 3, 2])
            c1.code(item["symbol"])
            c2.write(f"**{item['name']}**")
            market_label = "🇯🇵 日本株 (東証)" if item["market"] == "JP" else "🇺🇸 米国株 (US)"
            c3.write(market_label)
            c4.write(item.get("category", "注目"))

        st.write("---")
        col_del1, col_del2 = st.columns([3, 1])
        with col_del1:
            del_targets = [f"{w['symbol']} - {w['name']}" for w in watchlist]
            selected_to_delete = st.selectbox("削除する銘柄を選択", options=del_targets)
        with col_del2:
            st.write("")
            st.write("")
            if st.button("🗑️ リストから削除", use_container_width=True):
                target_sym = selected_to_delete.split(" - ")[0]
                new_wl = [w for w in watchlist if w["symbol"] != target_sym]
                ok, msg = save_watchlist(new_wl, gh_token)
                st.success(f"{target_sym} を削除しました！（{msg}）")
                st.rerun()

# ----------------- タブ2: 銘柄検索・追加 -----------------
with tab_search:
    st.subheader("銘柄検索 & 監視リストへの追加")
    st.markdown("企業名（例: `インテル`, `トヨタ`, `ソニー`, `エヌビディア`, `Apple`）やコード（例: `7203`, `INTC`, `NVDA`）でリアルタイム検索できます。")

    search_query = st.text_input("銘柄検索キーワードを入力", placeholder="例: インテル, 7203, NVDA, アップル, 半導体")
    results = search_popular_stocks(search_query)

    st.write(f"検索結果 ({len(results)} 件)")
    
    current_wl = load_watchlist()
    current_symbols = [w["symbol"] for w in current_wl]

    for item in results:
        col1, col2, col3, col4 = st.columns([1.5, 3, 2, 1.5])
        with col1:
            st.code(item["symbol"])
        with col2:
            st.write(f"**{item['name']}**")
        with col3:
            market_label = "🇯🇵 日本株" if item["market"] == "JP" else "🇺🇸 米国株"
            st.caption(f"{market_label} | {item.get('sector', '')}")
        with col4:
            is_added = item["symbol"] in current_symbols
            if is_added:
                st.button("追加済", key=f"btn_{item['symbol']}", disabled=True)
            else:
                if st.button("➕ 監視に追加", key=f"btn_{item['symbol']}"):
                    current_wl.append({
                        "symbol": item["symbol"],
                        "name": item["name"],
                        "market": item["market"],
                        "category": "注目"
                    })
                    ok, msg = save_watchlist(current_wl, gh_token)
                    st.success(f"{item['name']} ({item['symbol']}) を追加しました！（{msg}）")
                    st.rerun()

# ----------------- タブ3: デイリーレポート・LINE送信 -----------------
with tab_report:
    st.subheader("📊 本日の分析レポートプレビュー ＆ LINE送信")
    st.markdown("リアルタイム株価、主要為替・指数、Gemini AIによる騰落要因と推奨度をプレビューします。")

    col_btn, col_line = st.columns([2, 2])
    with col_btn:
        generate_btn = st.button("🚀 最新データを取得してAI分析を実行", type="primary", use_container_width=True)

    if generate_btn or "cached_report" in st.session_state:
        if generate_btn:
            with st.spinner("市場データ・為替・AI分析を実行中..."):
                indices = get_market_indices()
                wl = load_watchlist()
                market_context_str = ", ".join([f"{m['name']}:{m['price']}{m['unit']}({m['pct_change']:+.2f}%)" for m in indices])

                report_data = []
                for item in wl:
                    s_data = get_stock_data(item["symbol"])
                    if s_data:
                        s_data["name"] = item.get("name", s_data["name"])
                        ai_res = analyze_stock_movement_and_recommendation(s_data, general_market_context=market_context_str)
                        s_data["ai"] = ai_res
                        report_data.append(s_data)

                ipos = get_latest_ipo_schedule()
                st.session_state["cached_report"] = {
                    "indices": indices,
                    "stocks": report_data,
                    "ipos": ipos
                }

        cached = st.session_state.get("cached_report")
        if cached:
            # 1. 市況サマリー表示
            st.markdown("#### 🌐 主要マクロ市況サマリー")
            idx_cols = st.columns(len(cached["indices"]))
            for i, idx in enumerate(cached["indices"]):
                with idx_cols[i]:
                    st.metric(idx["name"], f"{idx['price']:,} {idx['unit']}", f"{idx['change']:+} ({idx['pct_change']:+.2f}%)")

            st.write("---")

            # 2. 銘柄詳細カード
            for s in cached["stocks"]:
                ai = s["ai"]
                score = ai.get("recommendation_score", 50)
                action = ai.get("action_label", "中立")
                pct = s["pct_change"]
                badge = " 🔥[注目買い]" if score >= 70 else " ⚠️[要警戒]" if score <= 30 else ""

                with st.expander(f"{s['name']} ({s['symbol']}){badge} : {s['current_price']:,} {s['currency']} ({pct:+}%)", expanded=True):
                    col_stat1, col_stat2, col_stat3 = st.columns([1, 1, 1])
                    with col_stat1:
                        st.metric("現在値", f"{s['current_price']:,} {s['currency']}", f"{s['change']:+} ({pct:+}%)")
                    with col_stat2:
                        st.metric("💡 買い推奨度", f"{score} / 100 %", action)
                    with col_stat3:
                        st.metric("5日間高値 / 安値", f"{s['high_5d']} / {s['low_5d']}")

                    st.markdown(f"**🔍 なぜ上がった/下がったか（要因解説）:**")
                    st.info(ai.get("reason", "要因分析中"))

                    st.markdown(f"**🎯 買い推奨度スコアの根拠 & リスク:**")
                    st.write(ai.get("recommendation_reason", "中立"))

            # 3. IPO情報
            st.subheader("🚀 最新IPO (新規上場) 情報")
            for ipo in cached["ipos"]:
                st.markdown(f"- **{ipo['name']}** ({ipo['code']}) [{ipo['market']}] | {ipo['date']}")
                st.caption(f"  {ipo['summary']}")

            # 4. 送信ボタン
            st.write("---")
            if st.button("📲 この内容を今すぐLINEに送信する", type="secondary", use_container_width=True):
                msg_text = format_line_report(cached["stocks"], cached["ipos"], market_indices=cached["indices"])
                ok, msg = send_line_message(msg_text)
                if ok:
                    st.success(msg)
                else:
                    st.error(msg)

# ----------------- タブ4: 設定 -----------------
with tab_settings:
    st.subheader("⚙️ 設定 & クラウド完全同期")

    with st.form("settings_form"):
        st.markdown("#### 1. Gemini AI 設定")
        gemini_key = st.text_input("Gemini API Key", value=current_cfg.get("GEMINI_API_KEY", ""), type="password")

        st.markdown("#### 2. LINE Messaging API 設定")
        line_token = st.text_input("LINE Channel Access Token", value=current_cfg.get("LINE_CHANNEL_ACCESS_TOKEN", ""), type="password")
        line_user_id = st.text_input("LINE Your User ID", value=current_cfg.get("LINE_USER_ID", ""))

        st.markdown("#### 3. GitHub 同期用 Personal Access Token (クラウドアプデ保持用)")
        st.caption("Web画面で追加した銘柄を自動配信（GitHub）に永久保存するために使用します。")
        github_pat = st.text_input("GitHub Token (PAT: repo権限付き)", value=current_cfg.get("GITHUB_TOKEN", ""), type="password")

        submit_btn = st.form_submit_button("設定を保存する")
        if submit_btn:
            new_cfg = {
                "GEMINI_API_KEY": gemini_key.strip(),
                "LINE_CHANNEL_ACCESS_TOKEN": line_token.strip(),
                "LINE_USER_ID": line_user_id.strip(),
                "GITHUB_TOKEN": github_pat.strip(),
                "SCHEDULE_TIME_JP": "08:00, 13:30, 21:00"
            }
            save_local_config(new_cfg)
            st.success("設定を正常に保存しました！")
