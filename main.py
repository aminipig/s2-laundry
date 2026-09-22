import os
import requests
import yfinance as yf
import feedparser
from datetime import datetime, timezone, timedelta

# แก้ไขเป็นแบบนี้ เพื่อให้ใช้ค่าสำรองทันทีหาก Secret ว่างเปล่า
TELEGRAM_BOT_TOKEN = (
    os.environ.get("TELEGRAM_BOT_TOKEN")
    or "8657492454:AAG29VOWiEgmw2Lt7IoB8FtPd7QFq24GV3w"
)
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID") or "8479818984"

# รายชื่อหุ้นที่สนใจ (ปรับเพิ่ม/ลด Ticker ได้ตามต้องการ)
WATCHLIST = {
    "สหรัฐฯ": ["PLTR", "AMD", "NVDA"],
    "ไทย": ["DELTA.BK", "PTT.BK"]
}

def get_thai_datetime():
    tz_thai = timezone(timedelta(hours=7))
    return datetime.now(tz_thai)

def get_market_summary():
    """ดึงภาพรวมดัชนีหลัก"""
    tickers = {
        "S&P 500": "^GSPC",
        "Nasdaq": "^IXIC",
        "Dow Jones": "^DJI",
        "SET Index": "^SET.BK"
    }
    
    text = "📊 สรุปภาพรวมดัชนีตลาด\n"
    for name, symbol in tickers.items():
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="2d")
            if len(hist) >= 2:
                prev_close = hist["Close"].iloc[-2]
                curr_close = hist["Close"].iloc[-1]
                chg = curr_close - prev_close
                pct_chg = (chg / prev_close) * 100
                icon = "🟢" if chg >= 0 else "🔴"
                text += f"{icon} {name}: {curr_close:,.2f} ({chg:+,.2f}, {pct_chg:+.2f}%)\n"
            else:
                text += f"▫️ {name}: ข้อมูลไม่เพียงพอ\n"
        except Exception:
            text += f"▫️ {name}: ดึงข้อมูลไม่สำเร็จ\n"
            
    return text

def get_watchlist_summary():
    """ดึงข้อมูลหุ้นรายตัวที่น่าสนใจ"""
    text = "\n🎯 หุ้นเด่นที่น่าจับตา\n"
    for market, symbols in WATCHLIST.items():
        text += f"[{market}]\n"
        for sym in symbols:
            try:
                t = yf.Ticker(sym)
                h = t.history(period="2d")
                if len(h) >= 2:
                    curr = h["Close"].iloc[-1]
                    pct = ((curr - h["Close"].iloc[-2]) / h["Close"].iloc[-2]) * 100
                    icon = "🟢" if pct >= 0 else "🔴"
                    display_name = sym.replace(".BK", "")
                    text += f"{icon} {display_name}: {curr:,.2f} ({pct:+.2f}%)\n"
            except Exception:
                pass
    return text

def get_daily_news():
    """ดึงข่าวเด่นรอบ 24 ชั่วโมงจาก Google News"""
    text = "\n📰 พาดหัวข่าวสำคัญรอบ 24 ชม.\n"
    feeds = [
        ("สหรัฐฯ", "https://news.google.com/rss/search?q=stock+market+when:24h&hl=en-US&gl=US&ceid=US:en"),
        ("ไทย", "https://news.google.com/rss/search?q=ข่าวหุ้น+when:24h&hl=th&gl=TH&ceid=TH:th")
    ]
    for category, url in feeds:
        text += f"\n• ข่าวหุ้น{category}:\n"
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:3]:
                title = entry.title.split(" - ")[0]
                text += f"  - {title}\n"
        except Exception:
            text += "  - ดึงข้อมูลไม่สำเร็จ\n"
    return text

def get_tradingview_news():
    """ดึงพาดหัวข่าวเด่นจาก TradingView"""
    text = "\n📈 ข่าวเด่นจาก TradingView\n"
    url = "https://news-headlines.tradingview.com/v2/headlines?category=stock&lang=en"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    }
    try:
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 200:
            data = res.json()
            items = data.get("items", [])[:4]
            for item in items:
                title = item.get("title")
                provider = item.get("provider", "TradingView")
                text += f"• [{provider}] {title}\n"
        else:
            text += "▫️ ไม่สามารถดึงข่าว TradingView ได้ในขณะนี้\n"
    except Exception:
        text += "▫️ เกิดข้อผิดพลาดในการเชื่อมต่อ TradingView\n"
    return text

def get_upcoming_14d_events():
    """ดึงปัจจัยและปฏิทินเศรษฐกิจล่วงหน้า 14 วัน (สำหรับวันจันทร์)"""
    text = "\n📅 ไฮไลต์ปฏิทินเศรษฐกิจ & ปัจจัยล่วงหน้า 14 วัน\n"
    url = "https://news.google.com/rss/search?q=economic+calendar+OR+FOMC+OR+CPI+OR+earnings+preview+when:7d&hl=en-US&gl=US&ceid=US:en"
    try:
        feed = feedparser.parse(url)
        if feed.entries:
            for entry in feed.entries[:4]:
                title = entry.title.split(" - ")[0]
                text += f"📌 {title}\n"
        else:
            text += "▫️ ติดตามตัวเลขเศรษฐกิจสำคัญประจำสัปดาห์\n"
    except Exception:
        text += "▫️ เกิดข้อผิดพลาดในการดึงข้อมูลปฏิทินเศรษฐกิจ\n"
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
