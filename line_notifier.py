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
    検証済み正規データ・独立リスクリワード比・執行トリガー・実績勝率付き最高峰レポート
    """
    jst = timezone(timedelta(hours=9))
    today_str = datetime.now(jst).strftime("%Y/%m/%d %H:%M")

    lines = [
        f"📊【AI株式投資レポート】",
        f"🕒 配信時刻: {today_str} (JST)",
        "===================="
    ]

    # 1. 主要マクロ市況サマリー
    if market_indices:
        lines.append("🌐【主要市況サマリー】")
        for idx in market_indices:
            sign = "+" if idx["pct_change"] > 0 else ""
            status_tag = "🇯🇵本日" if "東証" in idx.get("status", "") else "🇺🇸前日終値"
            lines.append(f"・{idx['name']}: {idx['price']:,}{idx['unit']} ({sign}{idx['pct_change']:.2f}%) [{status_tag}]")
        lines.append("--------------------")

    # 2. 監視銘柄の状況＆AI精密判断
    lines.append("📈【監視銘柄の精密テクニカル & AI分析】")
    for res in watchlist_results:
        symbol = res["symbol"]
        name = res["name"]
        price = res["current_price"]
        prev = res["prev_price"]
        curr = res["currency"]
        change = res["change"]
        pct = res["pct_change"]
        status = res.get("market_status", "")
        tech = res.get("tech") or {}
        ai = res.get("ai", {})

        icon = "🔺" if pct > 0 else "🔻" if pct < 0 else "➖"
        total_score = ai.get("total_score", 50)
        t_score = ai.get("tech_score", tech.get("tech_score", 25))
        f_score = ai.get("fundamental_score", 25)
        action = ai.get("action_label", "中立")
        is_favorable = ai.get("is_favorable", True)

        badge = " 🔥[注目好機]" if (total_score >= 68 and is_favorable) else " 🚫[見送り推奨]" if not is_favorable else ""

        lines.append(f"\n{icon} {name} ({symbol}){badge}")
        lines.append(f"・ステータス: {status}")
        lines.append(f"・株価: {price:,} {curr} (前日終値: {prev:,} / {change:+}, {pct:+.2f}%)")
        
        if tech:
            lines.append(f"・📊テクニカル指標: RSI={tech.get('rsi_14')} | 25日乖離={tech.get('bias25'):+.1f}% | ATR={tech.get('atr')} {curr}")

        lines.append(f"・💡AI総合評価スコア: 【{total_score}点 / 100点】 ({action})")
        lines.append(f"   [内訳: テクニカル客観点 {t_score}/50点 ＋ ファンダ/地合い点 {f_score}/50点]")
        lines.append(f"・🔍分析根拠: {ai.get('reason', '')}")
        lines.append(f"・🎯売買戦略 & リスクリワード:")
        lines.append(f"   ▶ 執行方針: {ai.get('order_type', '指値待機')}")
        lines.append(f"   ▶ 利確目標株価: {ai.get('target_price', '未定')}")
        lines.append(f"   ▶ 撤退損切りライン: {ai.get('stop_loss', '未定')}")
        lines.append(f"   ▶ リスクリワード比: {ai.get('reward_risk', '1.5:1')}")
        lines.append(f"・⚠️戦略＆リスク: {ai.get('strategy_detail', '')}")
        lines.append("--------------------")

    # 3. AI予測の実績検証・通算成績
    if performance and performance.get("total_count", 0) > 0:
        lines.append("\n🏆【AI推奨の通算実績・勝率検証】")
        lines.append(f"・過去記録数: {performance['total_count']}件 (判定完了: {performance['closed_count']}件 / 追跡中: {performance['tracking_count']}件)")
        if performance['closed_count'] > 0:
            lines.append(f"・通算勝率: {performance['win_rate']}% ({performance['win_count']}勝 {performance['loss_count']}敗)")
            lines.append(f"・平均利益: +{performance['avg_profit']}% / 平均損失: {performance['avg_loss']}%")
        else:
            lines.append("・判定状況: 過去推奨銘柄の目標・損切り到達をリアルタイム追跡中")
        lines.append("--------------------")

    # 4. 重複排除済み・本物のIPO速報
    if ipo_list:
        lines.append("\n🚀【最新IPO・新規上場速報】")
        for ipo in ipo_list:
            lines.append(f"・{ipo['title']}")
            lines.append(f"  (出典: {ipo.get('source','公式発表')} / {ipo.get('date','本日')})")
        lines.append("--------------------")

    lines.append("\n※AI及びテクニカル指標による参考情報です。投資判断は自己責任で行ってください。")
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
