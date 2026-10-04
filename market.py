#!/usr/bin/env python3
"""Market Terminal — live quotes + financial headlines (stdlib only).
usage: market.py quotes [TICKERS...] | market.py news [N]"""
import http.cookiejar, json, re, sys, time, urllib.parse, urllib.request, xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor

UA = {"User-Agent": "Mozilla/5.0"}
WATCHLIST = ["^IXIC", "SPCX", "NVDA", "AAPL", "MSFT", "GOOGL", "META", "AMZN", "TSLA", "AMD", "AVGO", "TSM"]
NAMES = {"^IXIC": "NASDAQ", "SPCX": "SPACEX", "AVGO": "BROADCOM", "TSM": "TSMC", "PLTR": "PALANTIR", "ORCL": "ORACLE",
         "NFLX": "NETFLIX", "ARM": "ARM", "CRM": "SALESFORCE", "MU": "MICRON", "INTC": "INTEL", "QCOM": "QUALCOMM", "ADBE": "ADOBE",
         "UBER": "UBER", "SHOP": "SHOPIFY", "PANW": "PALO ALTO", "CRWD": "CROWDSTRIKE", "NOW": "SERVICENOW", "IBM": "IBM",
         "CSCO": "CISCO", "AMAT": "APPLIED MAT.", "SNOW": "SNOWFLAKE", "DELL": "DELL", "SPOT": "SPOTIFY", "COIN": "COINBASE"}
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
# Movers pool: the top 3 gainers and losers are picked from all of these (+ the SPARK names)
MOVERS = ["PLTR", "ORCL", "NFLX", "ARM", "CRM", "MU", "INTC", "QCOM", "ADBE",
          "UBER", "SHOP", "PANW", "CRWD", "NOW", "IBM", "CSCO", "AMAT", "SNOW", "DELL", "SPOT", "COIN"]
TECH_FEEDS = [("CNBC Tech", "https://www.cnbc.com/id/19854910/device/rss/rss.html"),
              ("Yahoo", "https://feeds.finance.yahoo.com/rss/2.0/headline?s=NVDA,MSFT,GOOGL,META,AMD&region=US&lang=en-US"),
              ("TechCrunch", "https://techcrunch.com/feed/"),
              ("Hacker News", "https://hnrss.org/frontpage?points=100")]

# Ranking for a software engineer in the job market: topic weight x freshness (18 h half-life).
# The strongest matching topic also becomes the row's tag.
TOPICS = [
    ("JOBS", 5, r"hir(e|es|ing)|job market|jobs? (report|data|openings)|recruit\w*|salar(y|ies)|compensation|h-?1b|visas?|"
                r"remote work|return to (the )?office|rto|offshor\w*|outsourc\w*|entry.level|new grads?|graduates|internships?|"
                r"engineers?|developer jobs|workforce|talent|careers?|resumes?|interviews?"),
    ("AI", 4, r"ai|a\.i\.|artificial intelligence|llms?|openai|anthropic|claude|chatgpt|gpt-?\d*|gemini|copilot|agents?|agentic|"
              r"coding assistants?|cursor|vibe coding|machine learning|deepmind|mistral|llama"),
    ("DEV", 3, r"developers?|programming|programmers?|software|open.source|github|gitlab|apis?|frameworks?|javascript|typescript|"
               r"python|rust|golang|kubernetes|devops|cloud|aws|azure|vulnerabilit\w*|breach\w*|outages?|databases?|compilers?|linux"),
    ("BIG TECH", 2, r"google|alphabet|microsoft|meta|amazon|apple|nvidia|netflix|tesla|oracle|ibm|salesforce|intel|spacex"),
    ("STARTUPS", 2, r"raises?|funding|series [a-f]|seed round|valuation|unicorn|ipo|acquir\w*|acquisition|y combinator"),
]
TOPIC_RE = [(tag, w, re.compile(r"\b(" + rx + r")\b", re.I)) for tag, w, rx in TOPICS]
# investing / markets angle: a story about share prices, not about the industry or jobs
NOISE_RE = re.compile(r"\b(stocks?|shares|investors?|investment|invest(ing)?|etfs?|dividends?|could be worth|portfolio|price target|"
                      r"wall street|dow jones|futures|oil|mining|bull market|bear market|retire\w*|millionaire|asset class\w*|"
                      r"buy (now|today)|earnings call)\b", re.I)
# ads and promos (e.g. conference ticket deals) are dropped entirely
PROMO_RE = re.compile(r"(\$\d+ (deal|off)|\d+% off|don.t miss|tickets?|discount|save \$|sponsored|promo code|last chance)", re.I)
SOURCE_BONUS = {"Hacker News": 1, "TechCrunch": 1}

def rank_for_engineer(h, now):
    hits = [(tag, w) for tag, w, rx in TOPIC_RE if rx.search(h["t"])]
    rel = sum(w for _, w in hits) + SOURCE_BONUS.get(h["src"], 0) - (6 if NOISE_RE.search(h["t"]) else 0)
    if h.get("alert"): rel += 6
    age_h = max(0, (now - h["ts"]) / 3600) if h["ts"] else 48
    h["tag"] = "LAYOFFS" if h.get("alert") else (max(hits, key=lambda x: x[1])[0] if hits else "TECH")
    h["score"] = round((2 + rel) * 0.5 ** (age_h / 18), 3)
# Headlines about job losses get flagged as alerts (shown in red and pinned to the top of the wire)
ALERT_RE = re.compile(r"\b(lay ?offs?|laid off|laying off|lays off|job cuts?|workforce reduction|redundanc(y|ies)|"
                      r"downsiz(e|es|ing)|hiring freeze|reduc(e|es|ing) (its )?(workforce|headcount)|"
                      r"(cut|cuts|cutting|slash\w*|eliminat\w*|shed\w*) ((?!(rates?|prices?|costs?|as|and|after|but|while)\b)[\w,.%-]+ ){0,3}"
                      r"(jobs|roles|positions|workers|employees|staff))\b", re.I)
AI_WORDS = ("ai", "a.i.", "openai", "anthropic", "nvidia", "chip", "gpu", "llm", "model", "robot", "data center", "agent")

def spark(sym):
    """Price, day change and a 5-day hourly sparkline for one symbol."""
    try:
        r = json.loads(get(f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?range=5d&interval=1h"))["chart"]["result"][0]
        m = r["meta"]
        pts = [(t, c) for t, c in zip(r["timestamp"], r["indicators"]["quote"][0]["close"]) if c is not None][-40:]
        closes = [c for _, c in pts]
        price, prev = m["regularMarketPrice"], m.get("previousClose") or m.get("chartPreviousClose")
        ch = m.get("regularMarketChangePercent")
        if ch is None and prev: ch = (price - prev) / prev * 100
        return {"sym": sym, "name": NAMES.get(sym, sym), "p": price, "c": ch or 0.0,
                "hi": m.get("regularMarketDayHigh"), "lo": m.get("regularMarketDayLow"),
                "spark": [round(c, 2) for c in closes], "ts": [t for t, _ in pts],
                "prev": prev}  # previous close: the chart baseline and what the day % is measured against
    except Exception:
        return None

def feed(feeds, n, ai_first=False, rank=False):
    from email.utils import parsedate_to_datetime
    out, seen = [], set()
    for src, url in feeds:
        try:
            for _, it in zip(range(n), ET.fromstring(get(url)).iter("item")):
                t = it.findtext("title").strip()
                if t.lower() in seen: continue
                seen.add(t.lower()); out.append({"src": src, "t": t, "l": it.findtext("link"), "d": it.findtext("pubDate")})
        except Exception: pass
    out = [h for h in out if not PROMO_RE.search(h["t"])]
    for h in out:
        h["alert"] = bool(ALERT_RE.search(h["t"]))
        try: h["ts"] = parsedate_to_datetime(h["d"]).timestamp()
        except Exception: h["ts"] = 0
    if ai_first:
        for h in out: h["ai"] = bool(re.search(r"\b(" + "|".join(map(re.escape, AI_WORDS)) + r")\b", h["t"].lower()))
    if rank:  # layoff alerts first, then relevance x freshness
        now = time.time()
        for h in out: rank_for_engineer(h, now)
        out.sort(key=lambda h: (h["alert"], h["score"]), reverse=True)
    else:
        out.sort(key=lambda h: h["ts"], reverse=True)  # newest first
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
        syms = SPARK if kind == "quotes" else MOVERS + [x for x in SPARK if x != "^IXIC" and x not in MOVERS]
        with ThreadPoolExecutor(16) as ex:
            caps = ex.submit(market_caps, syms)
            data = [q for q in ex.map(spark, syms) if q]
        for q in data: q["cap"] = caps.result().get(q["sym"])
    elif kind == "tech": data = feed(TECH_FEEDS, 12, ai_first=True, rank=True)
    else: data = feed(FEEDS, 6)
    print(json.dumps(data))

if __name__ == "__main__":
    args = sys.argv[1:]
    if args[:1] == ["json"]: as_json(args[1] if len(args) > 1 else "quotes")
    elif args[:1] == ["news"]: news(int(args[1]) if len(args) > 1 else 5)
    else: quotes([a.upper() for a in args if a != "quotes"] or WATCHLIST)
