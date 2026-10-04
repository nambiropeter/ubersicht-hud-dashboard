#!/usr/bin/env python3
"""Market Terminal — live quotes + financial headlines (stdlib only).
usage: market.py quotes [TICKERS...] | market.py news [N]"""
import http.cookiejar, json, re, sys, urllib.parse, urllib.request, xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor

UA = {"User-Agent": "Mozilla/5.0"}
WATCHLIST = ["^IXIC", "SPCX", "NVDA", "AAPL", "MSFT", "GOOGL", "META", "AMZN", "TSLA", "AMD", "AVGO", "TSM"]
NAMES = {"^IXIC": "NASDAQ", "SPCX": "SPACEX", "AVGO": "BROADCOM", "TSM": "TSMC", "PLTR": "PALANTIR", "ORCL": "ORACLE",
         "NFLX": "NETFLIX", "ARM": "ARM", "CRM": "SALESFORCE", "MU": "MICRON", "INTC": "INTEL", "QCOM": "QUALCOMM", "ADBE": "ADOBE"}
FEEDS = [("CNBC", "https://www.cnbc.com/id/100003114/device/rss/rss.html"),
         ("Yahoo", "https://feeds.finance.yahoo.com/rss/2.0/headline?s=^GSPC,AAPL,NVDA,TSLA&region=US&lang=en-US")]
G, R, Y, C, D, B, X = "\033[32m", "\033[31m", "\033[33m", "\033[36m", "\033[2m", "\033[1m", "\033[0m"

def get(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=8).read()

def quote(sym):
    try:
        m = json.loads(get(f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?range=1d&interval=1d"))["chart"]["result"][0]["meta"]
        price, prev = m["regularMarketPrice"], m.get("chartPreviousClose") or m.get("previousClose")
        return sym, price, (price - prev) / prev * 100 if prev else 0.0
    except Exception:
        return sym, None, None

def quotes(syms):
    print(f"{B}{Y}  ⚡ MARKET TERMINAL{X}")
    with ThreadPoolExecutor(12) as ex:
        for sym, p, ch in ex.map(quote, syms):
            label = NAMES.get(sym, sym)
            if p is None:
                print(f"  {label:<10} {D}unavailable{X}"); continue
            col, arrow = (G, "▲") if ch >= 0 else (R, "▼")
            bar = "█" * min(int(abs(ch) * 4), 20)
            print(f"  {B}{label:<10}{X} {p:>12,.2f}  {col}{arrow} {ch:+6.2f}%  {bar}{X}")

def news(n):
    print(f"{B}{C}  🦇 FINANCIAL WIRE{X}")
    for src, url in FEEDS:
        try:
            items = ET.fromstring(get(url)).iter("item")
            print(f"\n  {Y}{src}{X}")
            for i, it in zip(range(n), items):
                print(f"  {C}•{X} {it.findtext('title').strip()}\n    {D}{it.findtext('link')}{X}")
        except Exception:
            print(f"  {D}{src}: feed unavailable{X}")

# Tech-only: NASDAQ hero, featured names, watchlist grid, then the "tech movers" list
SPARK = ["^IXIC", "SPCX", "AVGO", "TSM", "NVDA", "AAPL", "MSFT", "GOOGL", "META", "AMZN", "TSLA", "AMD"]
MOVERS = ["PLTR", "ORCL", "NFLX", "ARM", "CRM", "MU", "INTC", "QCOM", "ADBE"]
TECH_FEEDS = [("CNBC Tech", "https://www.cnbc.com/id/19854910/device/rss/rss.html"),
              ("Yahoo", "https://feeds.finance.yahoo.com/rss/2.0/headline?s=NVDA,MSFT,GOOGL,META,AMD&region=US&lang=en-US")]
AI_WORDS = ("ai", "a.i.", "openai", "anthropic", "nvidia", "chip", "gpu", "llm", "model", "robot", "data center", "agent")

def spark(sym):
    """Price, day change and a 5-day hourly sparkline for one symbol."""
    try:
        r = json.loads(get(f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?range=5d&interval=1h"))["chart"]["result"][0]
        m = r["meta"]; closes = [c for c in r["indicators"]["quote"][0]["close"] if c is not None]
        price, prev = m["regularMarketPrice"], m.get("previousClose") or m.get("chartPreviousClose")
        ch = m.get("regularMarketChangePercent")
        if ch is None and prev: ch = (price - prev) / prev * 100
        return {"sym": sym, "name": NAMES.get(sym, sym), "p": price, "c": ch or 0.0,
                "hi": m.get("regularMarketDayHigh"), "lo": m.get("regularMarketDayLow"),
                "spark": [round(c, 2) for c in closes[-40:]]}
    except Exception:
        return None

def feed(feeds, n, ai_first=False):
    out = []
    for src, url in feeds:
        try: out += [{"src": src, "t": it.findtext("title").strip(), "l": it.findtext("link"), "d": it.findtext("pubDate")}
                     for _, it in zip(range(n), ET.fromstring(get(url)).iter("item"))]
        except Exception: pass
    if ai_first:
        for h in out: h["ai"] = bool(re.search(r"\b(" + "|".join(map(re.escape, AI_WORDS)) + r")\b", h["t"].lower()))
    from email.utils import parsedate_to_datetime
    def ts(h):
        try: return parsedate_to_datetime(h["d"]).timestamp()
        except Exception: return 0
    out.sort(key=ts, reverse=True)  # newest first
    return out

def market_caps(syms):
    """Market caps via Yahoo's quote API (needs a session cookie + crumb). Returns {} on failure."""
    try:
        op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        op.addheaders = list(UA.items())
        try: op.open("https://fc.yahoo.com", timeout=8)
        except Exception: pass  # 404s, but sets the session cookie
        crumb = op.open("https://query1.finance.yahoo.com/v1/test/getcrumb", timeout=8).read().decode()
        url = (f"https://query1.finance.yahoo.com/v7/finance/quote?symbols={','.join(syms)}"
               f"&fields=marketCap&crumb={urllib.parse.quote(crumb)}")
        return {q["symbol"]: q.get("marketCap") for q in json.loads(op.open(url, timeout=8).read())["quoteResponse"]["result"]}
    except Exception:
        return {}

def as_json(kind):
    if kind in ("quotes", "movers"):
        syms = SPARK if kind == "quotes" else MOVERS
        with ThreadPoolExecutor(13) as ex:
            caps = ex.submit(market_caps, syms)
            data = [q for q in ex.map(spark, syms) if q]
        for q in data: q["cap"] = caps.result().get(q["sym"])
    elif kind == "tech": data = feed(TECH_FEEDS, 10, ai_first=True)
    else: data = feed(FEEDS, 6)
    print(json.dumps(data))

if __name__ == "__main__":
    args = sys.argv[1:]
    if args[:1] == ["json"]: as_json(args[1] if len(args) > 1 else "quotes")
    elif args[:1] == ["news"]: news(int(args[1]) if len(args) > 1 else 5)
    else: quotes([a.upper() for a in args if a != "quotes"] or WATCHLIST)
