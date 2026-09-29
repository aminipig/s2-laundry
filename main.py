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

WATCHLIST_THAI = ["DELTA.BK", "PTT.BK"]
WATCHLIST_US = ["PLTR", "AMD", "NVDA"]

def get_thai_datetime():
    tz_thai = timezone(timedelta(hours=7))
    return datetime.now(tz_thai)

def clean_text(raw_html):
    """ล้างแท็ก HTML ออกจากข้อความข่าว"""
    if not raw_html:
        return ""
    soup = BeautifulSoup(raw_html, "html.parser")
    text = soup.get_text(separator=" ").strip()
    return " ".join(text.split())

def translate_to_thai(text):
    """แปลข้อความภาษาอังกฤษเป็นภาษาไทย (ใส่ Header ป้องกัน 403 + มีระบบสำรอง)"""
    if not text or not text.strip():
        return ""
    
    # 1. ลองแปลผ่าน Google Translate API
    try:
        url = "https://translate.googleapis.com/translate_a/single"
        params = {
            "client": "gtx",
            "sl": "auto",
            "tl": "th",
            "dt": "t",
            "q": text.strip()
        }
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept": "*/*"
        }
        res = requests.get(url, params=params, headers=headers, timeout=8)
        if res.status_code == 200:
            data = res.json()
            if data and data[0]:
                translated = "".join([seg[0] for seg in data[0] if seg and seg[0]])
                if translated.strip():
                    return translated.strip()
    except Exception:
        pass

    # 2. ระบบแปลสำรอง (MyMemory API)
    try:
        mm_url = "https://api.mymemory.translated.net/get"
        mm_params = {"q": text.strip()[:450], "langpair": "en|th"}
        res = requests.get(mm_url, params=mm_params, timeout=5)
        if res.status_code == 200:
            translated = res.json().get("responseData", {}).get("translatedText", "")
            if translated and translated.strip():
                return translated.strip()
    except Exception:
        pass

    return text

# ==================== ส่วนข้อมูลตลาดหุ้นไทย (09:00 น.) ====================

def get_thai_market_summary():
    """ดึง SET Index (TradingView Scanner + สำรองจากเว็บตลาดหลักทรัพย์ฯ)"""
    # วิธีที่ 1: ดึงจาก TradingView Scanner API
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
    except Exception:
        pass

    # วิธีที่ 2 (สำรอง): ดึงจากเว็บตลาดหลักทรัพย์แห่งประเทศไทยโดยตรง
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
                    pct = cols[3]
                    icon = "🔴" if chg.startswith("-") else "🟢"
                    return f"📊 สรุปดัชนีตลาดหุ้นไทย\n{icon} SET Index: {price} ({chg}, {pct}%)\n"
    except Exception:
        pass

    return "📊 สรุปดัชนีตลาดหุ้นไทย\n▫️ SET Index: ข้อมูลไม่เพียงพอ\n"

def get_thai_watchlist():
    """ดึงราคาหุ้นไทยเด่น"""
    text = "\n🎯 หุ้นไทยเด่นที่น่าจับตา\n"
    for sym in WATCHLIST_THAI:
        try:
            t = yf.Ticker(sym)
            curr, prev = None, None
            try:
                curr = t.fast_info.get("lastPrice") or t.fast_info.get("regularMarketPrice")
                prev = t.fast_info.get("previousClose") or t.fast_info.get("regularMarketPreviousClose")
            except Exception:
                pass
            if curr is None or prev is None or str(curr) == "nan":
                h = t.history(period="1mo").dropna(subset=["Close"])
                closes = [c for c in h["Close"].tolist() if str(c) != "nan" and c > 0]
                if len(closes) >= 2:
                    curr, prev = closes[-1], closes[-2]
            if curr is not None and prev is not None and str(curr) != "nan":
                pct = ((curr - prev) / prev) * 100
                icon = "🟢" if pct >= 0 else "🔴"
                display_name = sym.replace(".BK", "")
                text += f"{icon} {display_name}: {curr:,.2f} ({pct:+.2f}%)\n"
        except Exception:
            pass
    return text

def get_thai_news():
    """ดึงข่าวหุ้นไทยพร้อมสรุปสาระสำคัญ"""
    text = "\n📰 ข่าวสำคัญตลาดหุ้นไทยรอบ 24 ชม.\n"
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

def get_thai_upcoming_14d_events():
    """ปัจจัยตลาดหุ้นไทยล่วงหน้า 14 วัน (วันจันทร์)"""
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

# ==================== ส่วนข้อมูลตลาดหุ้นสหรัฐฯ (14:00 น.) ====================

def get_us_market_summary():
    """ดึงภาพรวมดัชนีหลักสหรัฐฯ"""
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
    """ดึงราคาหุ้นสหรัฐฯ เด่น"""
    text = "\n🎯 หุ้นสหรัฐฯ เด่นที่น่าจับตา\n"
    for sym in WATCHLIST_US:
        try:
            t = yf.Ticker(sym)
            curr, prev = None, None
            try:
                curr = t.fast_info.get("lastPrice") or t.fast_info.get("regularMarketPrice")
                prev = t.fast_info.get("previousClose") or t.fast_info.get("regularMarketPreviousClose")
            except Exception:
                pass
            if curr is None or prev is None or str(curr) == "nan":
                h = t.history(period="1mo").dropna(subset=["Close"])
                closes = [c for c in h["Close"].tolist() if str(c) != "nan" and c > 0]
                if len(closes) >= 2:
                    curr, prev = closes[-1], closes[-2]
            if curr is not None and prev is not None and str(curr) != "nan":
                pct = ((curr - prev) / prev) * 100
                icon = "🟢" if pct >= 0 else "🔴"
                text += f"{icon} {sym}: {curr:,.2f} ({pct:+.2f}%)\n"
        except Exception:
            pass
    return text

def get_us_news():
    """ดึงข่าวหุ้นสหรัฐฯ แปลไทยพร้อมสรุปย่อ"""
    text = "\n📰 ข่าวสำคัญตลาดหุ้นสหรัฐฯ รอบ 24 ชม. (แปลไทย)\n"
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
    """ดึงข่าว TradingView แปลไทยพร้อมสรุปย่อ"""
    text = "📈 ข่าวเด่นจาก TradingView (แปลไทย)\n"
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
        text += "▫️ เกิดข้อผิดพลาดในการดึงข่าว TradingView\n\n"
    return text

def get_us_upcoming_14d_events():
    """ปัจจัยปฏิทินเศรษฐกิจสหรัฐฯ ล่วงหน้า 14 วัน (วันจันทร์) แปลไทย"""
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

# ==================== ระบบส่งข้อความ ====================

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    max_length = 4000
    for i in range(0, len(message), max_length):
        chunk = message[i:i + max_length]
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": chunk}
        res = requests.post(url, json=payload, timeout=15)
        res.raise_for_status()

def main():
    now = get_thai_datetime()
    date_str = now.strftime("%d/%m/%Y")
    is_monday = (now.weekday() == 0)

    # เลือกรอบ: ก่อนเที่ยง = รอบไทย (09:00 น.), หลังเที่ยง = รอบสหรัฐฯ (14:00 น.)
    override = os.environ.get("SESSION_OVERRIDE", "auto")
    if override in ["thai", "us"]:
        session = override
    else:
        session = "thai" if now.hour < 12 else "us"

    if session == "thai":
        day_label = " (ฉบับวันจันทร์ + ปัจจัยล่วงหน้า 14 วัน)" if is_monday else ""
        header = f"☀️ มอร์นิ่งบรีฟตลาดหุ้นไทย {date_str}{day_label}\n{'─'*30}\n"
        message = header
        message += get_thai_market_summary()
        message += get_thai_watchlist()
        message += get_thai_news()
        if is_monday:
            message += get_thai_upcoming_14d_events()
    else:
        day_label = " (ฉบับวันจันทร์ + ปัจจัยล่วงหน้า 14 วัน)" if is_monday else ""
        header = f"🌤️ อาฟเตอร์นูนบรีฟตลาดหุ้นสหรัฐฯ {date_str}{day_label}\n{'─'*30}\n"
        message = header
        message += get_us_market_summary()
        message += get_us_watchlist()
        message += get_us_news()
        message += get_tradingview_news()
        if is_monday:
            message += get_us_upcoming_14d_events()

    send_telegram_message(message)

if __name__ == "__main__":
    main()
