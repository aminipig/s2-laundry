import os
import time
import requests
import yfinance as yf
import feedparser
from bs4 import BeautifulSoup
from deep_translator import GoogleTranslator
from datetime import datetime, timezone, timedelta

TELEGRAM_BOT_TOKEN = (
    os.environ.get("TELEGRAM_BOT_TOKEN")
    or "8657492454:AAG29VOWiEgmw2Lt7IoB8FtPd7QFq24GV3w"
)
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID") or "8479818984"

# หุ้นเด่นที่มีสภาพคล่องและการเคลื่อนไหวสำคัญของตลาด
WATCHLIST_THAI = ["DELTA.BK", "GULF.BK", "ADVANC.BK", "PTT.BK", "CPALL.BK", "SCB.BK", "KBANK.BK", "AOT.BK"]
WATCHLIST_US = ["AMD", "PLTR", "NVDA", "GOOGL", "MSFT", "AMZN", "AAPL", "TSLA"]

def get_thai_datetime():
    tz_thai = timezone(timedelta(hours=7))
    return datetime.now(tz_thai)

def clean_text(raw_html):
    if not raw_html:
        return ""
    soup = BeautifulSoup(raw_html, "html.parser")
    return " ".join(soup.get_text(separator=" ").strip().split())

def translate_to_thai(text):
    """แปลภาษาไทยด้วย deep-translator พร้อมหน่วงเวลาสั้นๆ ป้องกัน Error 429"""
    if not text or not text.strip():
        return ""
    text_clean = text.strip()
    time.sleep(0.5)

    # 1. แปลด้วย GoogleTranslator
    try:
        translated = GoogleTranslator(source="auto", target="th").translate(text_clean[:450])
        if translated and translated.strip():
            return translated.strip()
    except Exception as e:
        print(f"GoogleTranslator error: {e}")

    # 2. ระบบสำรอง (Google Clients5 Endpoint)
    try:
        url = "https://clients5.google.com/translate_a/t"
        params = {"client": "dict-chrome-ex", "sl": "auto", "tl": "th", "q": text_clean[:450]}
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        res = requests.get(url, params=params, headers=headers, timeout=6)
        if res.status_code == 200:
            data = res.json()
            if isinstance(data, list) and data and isinstance(data[0], list) and data[0]:
                return data[0][0].strip()
            elif isinstance(data, dict) and "sentences" in data:
                return "".join([s.get("trans", "") for s in data["sentences"]]).strip()
    except Exception as e:
        print(f"Clients5 error: {e}")

    return text

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    max_length = 4000
    for i in range(0, len(message), max_length):
        chunk = message[i:i + max_length]
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": chunk}
        res = requests.post(url, json=payload, timeout=15)
        res.raise_for_status()

# ==================== 1. ระบบตลาดหุ้นไทย (รอบ 09:00 น.) ====================

def get_set_index():
    # วิธีที่ 1: TradingView Scanner API (แก้ไข index และ ให้ถูกต้องแล้ว)
    try:
        url = "https://scanner.tradingview.com/thailand/scan"
        payload = {
            "symbols": {"tickers": ["SET:SET"]},
            "columns": ["close", "change", "change_abs"]
        }
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        res = requests.post(url, json=payload, headers=headers, timeout=10)
        if res.status_code == 200:
            items = res.json().get("data", [])
            if items and "d" in items[0]:
                d = items[0]["d"]
                close_price = float(d[0])
                pct_chg = float(d)
                abs_chg = float(d)
                icon = "🟢" if pct_chg >= 0 else "🔴"
                return f"📊 สรุปดัชนีตลาดหุ้นไทย\n{icon} SET Index: {close_price:,.2f} ({abs_chg:+,.2f}, {pct_chg:+.2f}%)\n"
    except Exception as e:
        print(f"TradingView scanner: {e}")

    # วิธีที่ 2 (สำรอง): เว็บตลาดหลักทรัพย์แห่งประเทศไทยโดยตรง
    try:
        url = "https://marketdata.set.or.th/mkt/marketsummary.do?language=th&country=TH"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, "html.parser")
            for r in soup.find_all("tr"):
                cols = [td.get_text(strip=True) for td in r.find_all("td")]
                if cols and cols[0] == "SET":
                    price = cols
                    chg = cols
                    pct = cols
                    icon = "🔴" if chg.startswith("-") else "🟢"
                    return f"📊 สรุปดัชนีตลาดหุ้นไทย\n{icon} SET Index: {price} ({chg}, {pct}%)\n"
    except Exception as e:
        print(f"SET marketdata: {e}")

    return "📊 สรุปดัชนีตลาดหุ้นไทย\n▫️ SET Index: ข้อมูลไม่เพียงพอ\n"

def get_thai_watchlist():
    text = "\n🎯 หุ้นไทยเด่นที่น่าจับตาประจำวัน (Top Movers)\n"
    for sym in WATCHLIST_THAI:
        try:
            t = yf.Ticker(sym)
            curr, prev = None, None
            try:
                curr = getattr(t.fast_info, 'last_price', None) or t.fast_info.get("lastPrice") or t.fast_info.get("regularMarketPrice")
                prev = getattr(t.fast_info, 'previous_close', None) or t.fast_info.get("previousClose") or t.fast_info.get("regularMarketPreviousClose")
            except Exception:
                pass
            if curr is None or prev is None or str(curr) == "nan":
                h = t.history(period="1mo").dropna(subset=["Close"])
                closes = [c for c in h["Close"].tolist() if str(c) != "nan" and c > 0]
                if len(closes) >= 2:
                    curr, prev = closes[-1], closes[-2]
            if curr is not None and prev is not None and str(curr) != "nan":
                pct = ((curr - prev) / prev) * 100
                chg = curr - prev
                icon = "🟢" if pct > 0 else ("🔴" if pct < 0 else "▫️")
                display_name = sym.replace(".BK", "")
                text += f"{icon} {display_name}: {curr:,.2f} ({chg:+,.2f}, {pct:+.2f}%)\n"
        except Exception:
            pass
    return text

def get_thai_news():
    text = "\n📰 ข่าวสำคัญตลาดหุ้นไทยรอบ 24 ชม. (พร้อมสรุปสาระสำคัญ)\n"
    try:
        feed = feedparser.parse("https://www.kaohoon.com/feed")
        entries = [
            e for e in feed.entries 
            if len(e.title.strip()) > 15 and "สังคมข่าวหุ้น" not in e.title and "เด็กแนว" not in e.title
        ][:3]
        if not entries:
            feed = feedparser.parse("https://news.google.com/rss/search?q=(ตลาดหุ้นไทย+OR+ดัชนีหุ้นไทย+OR+SET50)+when:24h&hl=th&gl=TH&ceid=TH:th")
            entries = feed.entries[:3]
            
        for entry in entries:
            title = entry.title.split(" - ")[0].strip()
            summary = clean_text(entry.get("summary", ""))
            if summary and len(summary) > 20 and summary.lower() != title.lower():
                short_sum = summary[:160] + "..." if len(summary) > 160 else summary
                text += f"🔹 {title}\n   ↳ {short_sum}\n\n"
            else:
                text += f"🔹 {title}\n\n"
    except Exception:
        text += "  - ดึงข้อมูลไม่สำเร็จ\n\n"
    return text

def get_thai_upcoming_14d():
    text = "📅 ไฮไลต์ปัจจัยตลาดหุ้นไทยล่วงหน้า 14 วัน\n"
    url = "https://news.google.com/rss/search?q=(กนง.+OR+เงินเฟ้อไทย+OR+ดัชนีหุ้นไทย)+when:7d&hl=th&gl=TH&ceid=TH:th"
    try:
        feed = feedparser.parse(url)
        count = 0
        for entry in feed.entries:
            title = entry.title.split(" - ")[0].strip()
            if len(title) > 20 and count < 4:
                text += f"📌 {title}\n"
                count += 1
        if count == 0:
            text += "▫️ ติดตามทิศทางเม็ดเงินลงทุนต่างชาติและนโยบายเศรษฐกิจในประเทศ\n"
    except Exception:
        text += "▫️ เกิดข้อผิดพลาดในการดึงข้อมูล\n"
    return text + "\n"

def run_thai(is_monday):
    date_str = get_thai_datetime().strftime("%d/%m/%Y")
    day_label = " (ฉบับวันจันทร์ + ปัจจัยล่วงหน้า 14 วัน)" if is_monday else ""
    header = f"☀️ มอร์นิ่งบรีฟตลาดหุ้นไทย {date_str}{day_label}\n{'─'*30}\n"
    msg = header + get_set_index() + get_thai_watchlist() + get_thai_news()
    if is_monday:
        msg += get_thai_upcoming_14d()
    send_telegram(msg)

# ==================== 2. ระบบตลาดหุ้นสหรัฐฯ (รอบ 14:00 น.) ====================

def get_us_market_summary():
    tickers = {"S&P 500": "^GSPC", "Nasdaq": "^IXIC", "Dow Jones": "^DJI"}
    text = "📊 สรุปภาพรวมดัชนีตลาดสหรัฐฯ\n"
    for name, symbol in tickers.items():
        try:
            ticker = yf.Ticker(symbol)
            h = ticker.history(period="5d").dropna(subset=["Close"])
            closes = [c for c in h["Close"].tolist() if str(c) != "nan" and c > 0]
            if len(closes) >= 2:
                prev_close = closes[-2]
                curr_close = closes[-1]
                chg = curr_close - prev_close
                pct_chg = (chg / prev_close) * 100
                icon = "🟢" if chg >= 0 else "🔴"
                text += f"{icon} {name}: {curr_close:,.2f} ({chg:+,.2f}, {pct_chg:+.2f}%)\n"
            else:
                text += f"▫️ {name}: ข้อมูลไม่เพียงพอ\n"
        except Exception:
            text += f"▫️ {name}: ดึงข้อมูลไม่สำเร็จ\n"
    return text

def get_us_watchlist():
    text = "\n🎯 หุ้นสหรัฐฯ เด่นที่น่าจับตาประจำวัน (Top Movers)\n"
    for sym in WATCHLIST_US:
        try:
            t = yf.Ticker(sym)
            curr, prev = None, None
            try:
                curr = getattr(t.fast_info, 'last_price', None) or t.fast_info.get("lastPrice") or t.fast_info.get("regularMarketPrice")
                prev = getattr(t.fast_info, 'previous_close', None) or t.fast_info.get("previousClose") or t.fast_info.get("regularMarketPreviousClose")
            except Exception:
                pass
            if curr is None or prev is None or str(curr) == "nan":
                h = t.history(period="1mo").dropna(subset=["Close"])
                closes = [c for c in h["Close"].tolist() if str(c) != "nan" and c > 0]
                if len(closes) >= 2:
                    curr, prev = closes[-1], closes[-2]
            if curr is not None and prev is not None and str(curr) != "nan":
                pct = ((curr - prev) / prev) * 100
                chg = curr - prev
                icon = "🟢" if pct > 0 else ("🔴" if pct < 0 else "▫️")
                text += f"{icon} {sym}: {curr:,.2f} USD ({chg:+,.2f}, {pct:+.2f}%)\n"
        except Exception:
            pass
    return text

def get_us_news():
    text = "\n📰 ข่าวสำคัญตลาดหุ้นสหรัฐฯ รอบ 24 ชม. (แปลไทยพร้อมสรุปสาระสำคัญ)\n"
    try:
        feed = feedparser.parse("https://finance.yahoo.com/news/rssindex")
        entries = feed.entries[:3]
        if not entries:
            feed = feedparser.parse("https://news.google.com/rss/search?q=stock+market+when:24h&hl=en-US&gl=US&ceid=US:en")
            entries = feed.entries[:3]
        for entry in entries:
            raw_title = entry.title.split(" - ")[0].strip()
            th_title = translate_to_thai(raw_title)
            raw_sum = clean_text(entry.get("summary", ""))
            if raw_sum and len(raw_sum) > 20 and raw_sum.lower() != raw_title.lower():
                th_sum = translate_to_thai(raw_sum[:180])
                text += f"🔹 {th_title}\n   ↳ {th_sum}\n\n"
            else:
                text += f"🔹 {th_title}\n\n"
    except Exception:
        text += "  - ดึงข้อมูลไม่สำเร็จ\n\n"
    return text

def get_tradingview_news():
    text = "📈 ข่าวเด่นและบทวิเคราะห์จาก TradingView (แปลไทย)\n"
    url = "https://news.google.com/rss/search?q=site:tradingview.com/news+when:24h&hl=en-US&gl=US&ceid=US:en"
    try:
        feed = feedparser.parse(url)
        for entry in feed.entries[:3]:
            raw_title = entry.title.split(" - ")[0].strip()
            th_title = translate_to_thai(raw_title)
            raw_sum = clean_text(entry.get("summary", ""))
            if raw_sum and len(raw_sum) > 30 and raw_sum.lower() != raw_title.lower():
                th_sum = translate_to_thai(raw_sum[:160])
                text += f"• {th_title}\n  ↳ {th_sum}\n\n"
            else:
                text += f"• {th_title}\n\n"
    except Exception:
        text += "▫️️ เกิดข้อผิดพลาดในการดึงข่าว TradingView\n\n"
    return text

def get_us_upcoming_14d():
    text = "📅 ไฮไลต์ปฏิทินเศรษฐกิจสหรัฐฯ & ปัจจัยล่วงหน้า 14 วัน (แปลไทย)\n"
    url = "https://news.google.com/rss/search?q=economic+calendar+OR+FOMC+OR+CPI+when:7d&hl=en-US&gl=US&ceid=US:en"
    try:
        feed = feedparser.parse(url)
        for entry in feed.entries[:4]:
            raw_title = entry.title.split(" - ")[0].strip()
            th_title = translate_to_thai(raw_title)
            text += f"📌 {th_title}\n"
    except Exception:
        text += "▫️ เกิดข้อผิดพลาดในการดึงข้อมูล\n"
    return text + "\n"

def run_us(is_monday):
    date_str = get_thai_datetime().strftime("%d/%m/%Y")
    day_label = " (ฉบับวันจันทร์ + ปัจจัยล่วงหน้า 14 วัน)" if is_monday else ""
    header = f"🌤️ อาฟเตอร์นูนบรีฟตลาดหุ้นสหรัฐฯ {date_str}{day_label}\n{'─'*30}\n"
    msg = header + get_us_market_summary() + get_us_watchlist() + get_us_news() + get_tradingview_news()
    if is_monday:
        msg += get_us_upcoming_14d()
    send_telegram(msg)

# ==================== Main Controller ====================

def main():
    target = os.environ.get("INPUT_TARGET", "auto")
    now = get_thai_datetime()
    is_monday = (now.weekday() == 0)

    # 1. กรณีผู้ใช้กดทดสอบผ่านปุ่ม Run workflow ด้วยตนเอง
    if target == "thai":
        run_thai(is_monday)
    elif target == "us":
        run_us(is_monday)
    elif target == "all":
        # ส่งทดสอบทั้งสองตลาดพร้อมกัน
        run_thai(is_monday)
        time.sleep(2)
        run_us(is_monday)
    else:
        # 2. กรณีทำงานอัตโนมัติตามเวลา Cron
        # รอบ 02:00 UTC (09:00 น. ไทย) -> ส่งหุ้นไทย
        # รอบ 07:00 UTC (14:00 น. ไทย) -> ส่งหุ้นสหรัฐฯ
        if now.hour < 12:
            run_thai(is_monday)
        else:
            run_us(is_monday)

if __name__ == "__main__":
    main()
