import sys
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

BACKUP_THAI = ["DELTA.BK", "GULF.BK", "ADVANC.BK", "PTT.BK", "CPALL.BK", "SCB.BK", "KBANK.BK", "AOT.BK"]
BACKUP_US = ["NVDA", "TSLA", "AMD", "PLTR", "AAPL", "MSFT", "AMZN", "GOOGL"]

def get_thai_datetime():
    tz_thai = timezone(timedelta(hours=7))
    return datetime.now(tz_thai)

def clean_text(raw_html):
    if not raw_html:
        return ""
    soup = BeautifulSoup(raw_html, "html.parser")
    return " ".join(soup.get_text(separator=" ").strip().split())

def translate_to_thai(text):
    if not text or not text.strip():
        return ""
    text_clean = text.strip()
    time.sleep(0.5)

    try:
        translated = GoogleTranslator(source="auto", target="th").translate(text_clean[:450])
        if translated and translated.strip():
            return translated.strip()
    except Exception:
        pass

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
    except Exception:
        pass

    return text

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    max_length = 4000
    for i in range(0, len(message), max_length):
        chunk = message[i:i + max_length]
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": chunk}
        res = requests.post(url, json=payload, timeout=15)
        res.raise_for_status()

# ==================== เครื่องมือดึงข้อมูลไทย ====================

def get_set_index(session_title="ดัชนีตลาดหุ้นไทย"):
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
                pct_chg = float(d[1])
                abs_chg = float(d[2])
                icon = "🟢" if pct_chg >= 0 else "🔴"
                return f"📊 สรุป{session_title}\n{icon} SET Index: {close_price:,.2f} ({abs_chg:+,.2f}, {pct_chg:+.2f}%)\n"
    except Exception as e:
        print(f"TradingView scanner: {e}")

    try:
        url = "https://marketdata.set.or.th/mkt/marketsummary.do?language=th&country=TH"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, "html.parser")
            for r in soup.find_all("tr"):
                cols = [td.get_text(strip=True) for td in r.find_all("td")]
                if cols and cols[0] == "SET":
                    price = cols[1]
                    chg = cols[2]
                    pct = cols[3]
                    icon = "🔴" if chg.startswith("-") else "🟢"
                    return f"📊 สรุป{session_title}\n{icon} SET Index: {price} ({chg}, {pct}%)\n"
    except Exception as e:
        print(f"SET marketdata: {e}")

    return f"📊 สรุป{session_title}\n▫️ SET Index: ข้อมูลไม่เพียงพอ\n"

def get_thai_watchlist(title_label="ราคาหุ้นเด่นที่น่าจับตา"):
    text = f"\n🎯 {title_label} (Top Movers ตามข้อมูลจริงของตลาด)\n"
    try:
        url = "https://scanner.tradingview.com/thailand/scan"
        payload = {
            "filter": [
                {"left": "type", "operation": "equal", "right": "stock"},
                {"left": "subtype", "operation": "in_range", "right": ["common", "foreign"]}
            ],
            "options": {"lang": "en"},
            "symbols": {"query": {"types": []}},
            "columns": ["name", "close", "change", "change_abs", "Value.Traded"],
            "sort": {"sortBy": "Value.Traded", "sortOrder": "desc"},
            "range": [0, 8]
        }
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        res = requests.post(url, json=payload, headers=headers, timeout=10)
        if res.status_code == 200:
            items = res.json().get("data", [])
            if items:
                dynamic_text = ""
                for item in items:
                    d = item.get("d", [])
                    if len(d) >= 4:
                        name = str(d[0])
                        close_price = float(d[1])
                        pct_chg = float(d[2])
                        abs_chg = float(d[3])
                        icon = "🟢" if pct_chg > 0 else ("🔴" if pct_chg < 0 else "▫️")
                        dynamic_text += f"{icon} {name}: {close_price:,.2f} บาท ({abs_chg:+,.2f}, {pct_chg:+.2f}%)\n"
                if dynamic_text:
                    return text + dynamic_text
    except Exception as e:
        print(f"Thai dynamic scanner notice: {e}")

    for sym in BACKUP_THAI:
        try:
            t = yf.Ticker(sym)
            curr, prev = None, None
            try:
                curr = getattr(t.fast_info, 'last_price', None) or t.fast_info.get("lastPrice")
                prev = getattr(t.fast_info, 'previous_close', None) or t.fast_info.get("previousClose")
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
                text += f"{icon} {display_name}: {curr:,.2f} บาท ({chg:+,.2f}, {pct:+.2f}%)\n"
        except Exception:
            pass
    return text

def get_thai_news(query_keyword="ตลาดหุ้นไทย", section_title="ข่าวสำคัญรอบ 24 ชม."):
    text = f"\n📰 {section_title}\n"
    try:
        feed = feedparser.parse(f"https://news.google.com/rss/search?q=({query_keyword})+when:24h&hl=th&gl=TH&ceid=TH:th")
        entries = feed.entries[:3]
        if not entries:
            feed = feedparser.parse("https://www.kaohoon.com/feed")
            entries = [
                e for e in feed.entries 
                if len(e.title.strip()) > 15 and "สังคมข่าวหุ้น" not in e.title and "เด็กแนว" not in e.title
            ][:3]
            
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

# ==================== เครื่องมือดึงข้อมูลสหรัฐฯ ====================

def get_us_market_summary(session_title="ดัชนีตลาดสหรัฐฯ"):
    tickers = {"S&P 500": "^GSPC", "Nasdaq": "^IXIC", "Dow Jones": "^DJI"}
    text = f"📊 สรุป{session_title}\n"
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

def get_us_watchlist(title_label="ราคาหุ้นเด่นที่น่าจับตา"):
    text = f"\n🎯 {title_label} (Top Movers ตามข้อมูลจริงของตลาด)\n"
    try:
        url = "https://scanner.tradingview.com/america/scan"
        payload = {
            "filter": [
                {"left": "type", "operation": "equal", "right": "stock"},
                {"left": "subtype", "operation": "in_range", "right": ["common"]},
                {"left": "exchange", "operation": "in_range", "right": ["NASDAQ", "NYSE"]},
                {"left": "close", "operation": "greater", "right": 5}
            ],
            "options": {"lang": "en"},
            "symbols": {"query": {"types": []}},
            "columns": ["name", "close", "change", "change_abs", "volume"],
            "sort": {"sortBy": "volume", "sortOrder": "desc"},
            "range": [0, 8]
        }
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        res = requests.post(url, json=payload, headers=headers, timeout=10)
        if res.status_code == 200:
            items = res.json().get("data", [])
            if items:
                dynamic_text = ""
                for item in items:
                    d = item.get("d", [])
                    if len(d) >= 4:
                        name = str(d[0])
                        close_price = float(d[1])
                        pct_chg = float(d[2])
                        abs_chg = float(d[3])
                        icon = "🟢" if pct_chg > 0 else ("🔴" if pct_chg < 0 else "▫️")
                        dynamic_text += f"{icon} {name}: {close_price:,.2f} USD ({abs_chg:+,.2f}, {pct_chg:+.2f}%)\n"
                if dynamic_text:
                    return text + dynamic_text
    except Exception as e:
        print(f"US dynamic scanner notice: {e}")

    for sym in BACKUP_US:
        try:
            t = yf.Ticker(sym)
            curr, prev = None, None
            try:
                curr = getattr(t.fast_info, 'last_price', None) or t.fast_info.get("lastPrice")
                prev = getattr(t.fast_info, 'previous_close', None) or t.fast_info.get("previousClose")
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

def get_us_news(section_title="ข่าวสำคัญตลาดหุ้นสหรัฐฯ รอบ 24 ชม."):
    text = f"\n📰 {section_title} (แปลไทยพร้อมสรุปสาระสำคัญ)\n"
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
        text += "▫️ เกิดข้อผิดพลาดในการดึงข่าว TradingView\n\n"
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

# ==================== 4 ฟังก์ชันหลัก ====================

def run_us_close():
    now = get_thai_datetime()
    date_str = now.strftime("%d/%m/%Y")
    friday_note = " (สรุปราคาปิดคืนวันศุกร์)" if now.weekday() == 5 else ""
    header = f"🇺🇸 สรุปภาวะตลาดหุ้นสหรัฐฯ หลังปิดตลาด {date_str}{friday_note}\n{'─'*30}\n"
    msg = header
    msg += get_us_market_summary("ราคาปิดตลาดหุ้นสหรัฐฯ")
    msg += get_us_watchlist("หุ้นสหรัฐฯ ที่มีปริมาณการซื้อขายสูงสุด (Most Active)")
    msg += get_us_news("ข่าวสำคัญตลาดหุ้นสหรัฐฯ หลังปิดตลาด")
    msg += get_tradingview_news()
    send_telegram(msg)
    print(">>> [1/4] ส่งรอบ US Close (08:45 น.) สำเร็จ")

def run_thai_morning(is_monday):
    date_str = get_thai_datetime().strftime("%d/%m/%Y")
    day_label = " (ฉบับวันจันทร์ + ปัจจัยล่วงหน้า 14 วัน)" if is_monday else ""
    header = f"🇹🇭 มอร์นิ่งบรีฟตลาดหุ้นไทยก่อนเปิดตลาด {date_str}{day_label}\n{'─'*30}\n"
    msg = header
    msg += get_set_index("ดัชนีตลาดหุ้นไทย (ก่อนเปิดตลาด)")
    msg += get_thai_watchlist("หุ้นไทยที่มีมูลค่าซื้อขายสูงสุด (Most Active)")
    msg += get_thai_news("ตลาดหุ้นไทย+OR+ดัชนีหุ้นไทย+OR+SET50", "ข่าวสำคัญตลาดหุ้นไทยก่อนเปิดตลาด 24 ชม.")
    if is_monday:
        msg += get_thai_upcoming_14d()
    send_telegram(msg)
    print(">>> [2/4] ส่งรอบ Thai Morning (09:00 น.) สำเร็จ")

def run_us_pre(is_monday):
    date_str = get_thai_datetime().strftime("%d/%m/%Y")
    day_label = " (ฉบับวันจันทร์ + ปัจจัยล่วงหน้า 14 วัน)" if is_monday else ""
    header = f"🇺🇸 มอร์นิ่งบรีฟตลาดหุ้นสหรัฐฯ ก่อนเปิดตลาด {date_str}{day_label}\n{'─'*30}\n"
    msg = header
    msg += get_us_market_summary("ดัชนีตลาดสหรัฐฯ (ก่อนเปิดตลาด)")
    msg += get_us_watchlist("หุ้นสหรัฐฯ ที่มีปริมาณการซื้อขายสูงสุด (Most Active)")
    msg += get_us_news("ข่าวสำคัญตลาดหุ้นสหรัฐฯ ก่อนเปิดตลาด 24 ชม.")
    msg += get_tradingview_news()
    if is_monday:
        msg += get_us_upcoming_14d()
    send_telegram(msg)
    print(">>> [3/4] ส่งรอบ US Pre-market (15:00 น.) สำเร็จ")

def run_thai_evening():
    date_str = get_thai_datetime().strftime("%d/%m/%Y")
    header = f"🇹🇭 สรุปภาวะตลาดหุ้นไทยหลังปิดตลาด {date_str}\n{'─'*30}\n"
    msg = header
    msg += get_set_index("ราคาปิดตลาดหุ้นไทย (SET Index)")
    msg += get_thai_watchlist("หุ้นไทยที่มีมูลค่าซื้อขายสูงสุดรอบวัน (Most Active)")
    msg += get_thai_news("ปิดตลาดหุ้นไทย+OR+สรุปภาวะตลาดหุ้นไทย+OR+SET+ปิด", "ข่าวและบทวิเคราะห์หลังปิดตลาด")
    send_telegram(msg)
    print(">>> [4/4] ส่งรอบ Thai Evening (17:00 น.) สำเร็จ")

# ==================== ระบบตัดสินรอบเวลา ====================

def resolve_session_by_time(dt):
    weekday = dt.weekday() # 0=Mon, ..., 4=Fri, 5=Sat, 6=Sun
    hm = dt.hour * 60 + dt.minute
    
    # 08:30 - 08:54 -> us_close (วันอังคาร - วันเสาร์)
    if 510 <= hm < 535:
        if weekday in [1, 2, 3, 4, 5]:
            return "us_close"
        return "none"
        
    # 08:55 - 12:00 -> thai_morning (วันจันทร์ - วันศุกร์)
    elif 535 <= hm < 720:
        if weekday in [0, 1, 2, 3, 4]:
            return "thai_morning"
        return "none"
        
    # 12:00 - 16:15 -> us_pre (วันจันทร์ - วันศุกร์)
    elif 720 <= hm < 975:
        if weekday in [0, 1, 2, 3, 4]:
            return "us_pre"
        return "none"
        
    # 16:15 - 23:59 -> thai_evening (วันจันทร์ - วันศุกร์)
    elif 975 <= hm:
        if weekday in [0, 1, 2, 3, 4]:
            return "thai_evening"
        return "none"
        
    return "none"

def main():
    now = get_thai_datetime()
    is_monday = (now.weekday() == 0)

    # 1. เช็กค่าจาก CLI Arguments
    cli_session = None
    if "--session" in sys.argv:
        idx = sys.argv.index("--session")
        if idx + 1 < len(sys.argv):
            cli_session = sys.argv[idx + 1]

    # 2. เช็กค่าจาก Environment Variable
    env_target = os.environ.get("INPUT_TARGET", "").strip()

    if cli_session:
        session = cli_session
    elif env_target and env_target != "auto":
        session = env_target
    else:
        # ตัดสินรอบตามเวลาจริงของไทยโดยอัตโนมัติ
        session = resolve_session_by_time(now)

    print(f"Current Thai Time: {now.strftime('%Y-%m-%d %H:%M:%S')} (Weekday: {now.weekday()})")
    print(f"Resolved Session: '{session}'")

    if session == "us_close":
        run_us_close()
    elif session == "thai_morning":
        run_thai_morning(is_monday)
    elif session == "us_pre":
        run_us_pre(is_monday)
    elif session == "thai_evening":
        run_thai_evening()
    elif session == "all":
        print("Explicit 'all' requested: running all 4 sessions sequentially...")
        run_us_close()
        time.sleep(3)
        run_thai_morning(is_monday)
        time.sleep(3)
        run_us_pre(is_monday)
        time.sleep(3)
        run_thai_evening()
        print("Completed all 4 sessions!")
    else:
        print(f"No scheduled action needed at this time window (Session: {session}). Exiting cleanly.")

if __name__ == "__main__":
    main()
