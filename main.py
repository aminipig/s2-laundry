import os
import requests
import yfinance as yf
import feedparser
from bs4 import BeautifulSoup
from datetime import datetime, timezone, timedelta

TELEGRAM_BOT_TOKEN = (
    os.environ.get("TELEGRAM_BOT_TOKEN")
    or "8657492454:AAG29VOWiEgmw2Lt7IoB8FtPd7QFq24GV3w"
)
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID") or "8479818984"

WATCHLIST = {
    "สหรัฐฯ": ["PLTR", "AMD", "NVDA"],
    "ไทย": ["DELTA.BK", "PTT.BK"]
}

def get_thai_datetime():
    tz_thai = timezone(timedelta(hours=7))
    return datetime.now(tz_thai)

def translate_to_thai(text):
    """แปลข้อความภาษาอังกฤษเป็นภาษาไทย"""
    if not text:
        return ""
    try:
        url = "https://translate.googleapis.com/translate_a/single"
        params = {
            "client": "gtx",
            "sl": "auto",
            "tl": "th",
            "dt": "t",
            "q": text
        }
        res = requests.get(url, params=params, timeout=5)
        if res.status_code == 200:
            data = res.json()
            translated = "".join([seg[0] for seg in data[0] if seg[0]])
            return translated.strip()
    except Exception:
        pass
    return text

def get_set_index():
    """ดึง SET Index จาก TradingView Scanner API (แม่นยำ ไม่ติดหน้า Consent)"""
    try:
        url = "https://scanner.tradingview.com/thailand/scan"
        payload = {
            "symbols": {"tickers": ["SET:SET"]},
            "columns": ["close", "change", "change_abs"]
        }
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        res = requests.post(url, json=payload, headers=headers, timeout=10)
        if res.status_code == 200:
            data = res.json()
            items = data.get("data", [])
            if items:
                row = items[0].get("d", [])
                close_price = row[0]
                pct_chg = row
                abs_chg = row
                icon = "🟢" if pct_chg >= 0 else "🔴"
                return f"{icon} SET Index: {close_price:,.2f} ({abs_chg:+,.2f}, {pct_chg:+.2f}%)\n"
    except Exception:
        pass
    return "▫️ SET Index: ข้อมูลไม่เพียงพอ\n"

def get_market_summary():
    """ดึงภาพรวมดัชนีหลัก"""
    us_tickers = {
        "S&P 500": "^GSPC",
        "Nasdaq": "^IXIC",
        "Dow Jones": "^DJI"
    }
    
    text = "📊 สรุปภาพรวมดัชนีตลาด\n"
    for name, symbol in us_tickers.items():
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
            
    # เพิ่ม SET Index
    text += get_set_index()
    return text

def get_watchlist_summary():
    """ดึงข้อมูลหุ้นรายตัวที่น่าสนใจ (แก้ปัญหาค่า nan)"""
    text = "\n🎯 หุ้นเด่นที่น่าจับตา\n"
    for market, symbols in WATCHLIST.items():
        text += f"[{market}]\n"
        for sym in symbols:
            try:
                t = yf.Ticker(sym)
                curr, prev = None, None
                
                # วิธีที่ 1: ดึงจาก fast_info
                try:
                    curr = t.fast_info.get("lastPrice") or t.fast_info.get("regularMarketPrice")
                    prev = t.fast_info.get("previousClose") or t.fast_info.get("regularMarketPreviousClose")
                except Exception:
                    pass
                
                # วิธีที่ 2 (สำรอง): กรอง NaN ออกจาก History
                if curr is None or prev is None or str(curr) == "nan":
                    h = t.history(period="1mo").dropna(subset=["Close"])
                    closes = [c for c in h["Close"].tolist() if str(c) != "nan" and c > 0]
                    if len(closes) >= 2:
                        curr = closes[-1]
                        prev = closes[-2]
                
                if curr is not None and prev is not None and str(curr) != "nan":
                    pct = ((curr - prev) / prev) * 100
                    icon = "🟢" if pct >= 0 else "🔴"
                    display_name = sym.replace(".BK", "")
                    text += f"{icon} {display_name}: {curr:,.2f} ({pct:+.2f}%)\n"
            except Exception:
                pass
    return text

def get_daily_news():
    """ดึงข่าวรอบ 24 ชม. พร้อมแปลข่าวสหรัฐฯ เป็นภาษาไทย"""
    text = "\n📰 พาดหัวข่าวสำคัญรอบ 24 ชม.\n"
    
    # 1. ข่าวสหรัฐฯ (แปลเป็นไทย)
    text += "\n• ข่าวหุ้นสหรัฐฯ (แปลไทย):\n"
    try:
        us_feed = feedparser.parse("https://news.google.com/rss/search?q=stock+market+when:24h&hl=en-US&gl=US&ceid=US:en")
        for entry in us_feed.entries[:3]:
            raw_title = entry.title.split(" - ")[0].strip()
            th_title = translate_to_thai(raw_title)
            text += f"  - {th_title}\n"
    except Exception:
        text += "  - ดึงข้อมูลไม่สำเร็จ\n"
        
    # 2. ข่าวหุ้นไทย
    text += "\n• ข่าวหุ้นไทย:\n"
    try:
        th_feed = feedparser.parse("https://news.google.com/rss/search?q=(ตลาดหุ้นไทย+OR+ดัชนีหุ้นไทย+OR+SET50)+when:24h&hl=th&gl=TH&ceid=TH:th")
        count = 0
        for entry in th_feed.entries:
            title = entry.title.split(" - ")[0].strip()
            if len(title) > 20 and count < 3:
                text += f"  - {title}\n"
                count += 1
        if count == 0:
            text += "  - ติดตามความเคลื่อนไหวก่อนเปิดตลาด\n"
    except Exception:
        text += "  - ดึงข้อมูลไม่สำเร็จ\n"
        
    return text

def get_tradingview_news():
    """ดึงข่าว TradingView และแปลเป็นภาษาไทย"""
    text = "\n📈 ข่าวเด่นจาก TradingView (แปลไทย)\n"
    url = "https://news.google.com/rss/search?q=site:tradingview.com/news+when:24h&hl=en-US&gl=US&ceid=US:en"
    try:
        feed = feedparser.parse(url)
        items = feed.entries[:3]
        if items:
            for entry in items:
                raw_title = entry.title.split(" - ")[0].strip()
                th_title = translate_to_thai(raw_title)
                text += f"• {th_title}\n"
        else:
            text += "• ติดตามความเคลื่อนไหวด้านเทคนิคและกราฟราคาบน TradingView\n"
    except Exception:
        text += "▫️ เกิดข้อผิดพลาดในการดึงข่าว TradingView\n"
    return text

def get_upcoming_14d_events():
    """ดึงปัจจัยล่วงหน้า 14 วัน (สำหรับวันจันทร์) แปลเป็นภาษาไทย"""
    text = "\n📅 ไฮไลต์ปฏิทินเศรษฐกิจ & ปัจจัยล่วงหน้า 14 วัน (แปลไทย)\n"
    url = "https://news.google.com/rss/search?q=economic+calendar+OR+FOMC+OR+CPI+when:7d&hl=en-US&gl=US&ceid=US:en"
    try:
        feed = feedparser.parse(url)
        if feed.entries:
            for entry in feed.entries[:4]:
                raw_title = entry.title.split(" - ")[0].strip()
                th_title = translate_to_thai(raw_title)
                text += f"📌 {th_title}\n"
        else:
            text += "▫️ ติดตามตัวเลขเศรษฐกิจสำคัญประจำสัปดาห์\n"
    except Exception:
        text += "▫️ เกิดข้อผิดพลาดในการดึงข้อมูล\n"
    return text

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    max_length = 4000
    for i in range(0, len(message), max_length):
        chunk = message[i:i + max_length]
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": chunk
        }
        res = requests.post(url, json=payload, timeout=15)
        res.raise_for_status()

def main():
    now = get_thai_datetime()
    date_str = now.strftime("%d/%m/%Y")
    is_monday = (now.weekday() == 0)
    
    day_label = " (ฉบับวันจันทร์ + ปัจจัยล่วงหน้า 14 วัน)" if is_monday else ""
    header = f"☀️ มอร์นิ่งบรีฟตลาดหุ้น {date_str}{day_label}\n{'─'*30}\n"
    
    message = header
    message += get_market_summary()
    message += get_watchlist_summary()
    message += get_daily_news()
    message += get_tradingview_news()
    
    if is_monday:
        message += get_upcoming_14d_events()
        
    send_telegram_message(message)

if __name__ == "__main__":
    main()
