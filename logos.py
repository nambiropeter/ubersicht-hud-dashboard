#!/usr/bin/env python3
"""Company logos for the Markets / Movers panels, cached as PNGs in the Übersicht widgets folder (served at /logos/SYM.png).
usage: logos.py us SYM...   (Yahoo tickers: FMP's free logo CDN)
       logos.py nse SYM...  (NSE tickers: the company's own site, found on its afx.kwayisi.org page)
Already-cached logos are skipped; a failed lookup (offline, unknown site) is retried after an hour (marker: .SYM.miss). Stdlib only."""
import io, os, re, sys, time, urllib.parse, urllib.request

DIR = os.path.expanduser("~/Library/Application Support/Übersicht/widgets/logos")
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Safari/605.1.15"}
# NSE companies whose listed website is wrong or dead (kplc.co.ke serves someone else's site)
SITES = {"KPLC": "www.kplc.co.ke"}
# Index / exchange logos, keyed by the symbol the widgets use
SPECIAL = {"^IXIC": "https://www.google.com/s2/favicons?domain=nasdaq.com&sz=128",
           "NSE": "https://www.google.com/s2/favicons?domain=nse.co.ke&sz=128"}

def get(url, timeout=10):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout).read()

def image(b):
    """PNG/ICO/JPEG/SVG magic numbers; anything else (an HTML error page) is rejected."""
    return b[:8] == b"\x89PNG\r\n\x1a\n" or b[:4] == b"\0\0\1\0" or b[:3] == b"\xff\xd8\xff" or b"<svg" in b[:400]

def to_png(b, out):
    """Store as PNG (sips converts ICO/JPEG); SVGs are kept as .svg next to it."""
    if b"<svg" in b[:400]:
        open(out[:-4] + ".svg", "wb").write(b); return out[:-4] + ".svg"
    tmp = out + ".src"
    open(tmp, "wb").write(b)
    if b[:8] != b"\x89PNG\r\n\x1a\n":
        os.system(f'sips -s format png "{tmp}" --out "{tmp}.png" >/dev/null 2>&1 && mv "{tmp}.png" "{tmp}"')
    os.replace(tmp, out); return out

def size(b):
    if b[:8] == b"\x89PNG\r\n\x1a\n": return int.from_bytes(b[16:20], "big")
    return 64 if b"<svg" in b[:400] else 32

def site_icons(site):
    """apple-touch-icon / big <link rel=icon> declared by the company's own homepage, biggest first."""
    base = "https://" + site.strip("/") + "/"
    try: html = get(base).decode("utf-8", "replace")
    except Exception:
        try: base = "http://" + site.strip("/") + "/"; html = get(base).decode("utf-8", "replace")
        except Exception: return []
    found = []
    for tag in re.findall(r"<link[^>]+>", html, re.I):
        rel = (re.search(r'rel=["\']?([^"\'>]+)', tag, re.I) or [None, ""])[1].lower()
        href = re.search(r'href=["\']?([^"\'\s>]+)', tag, re.I)
        if "icon" not in rel or not href: continue
        sz = re.search(r'sizes=["\']?(\d+)', tag, re.I)
        found.append((int(sz[1]) if sz else 180 if "apple" in rel else 32, urllib.parse.urljoin(base, href[1])))
    found.append((180, urllib.parse.urljoin(base, "/apple-touch-icon.png")))
    # sites with no usable icon still tend to have their logo on the homepage (<img src=/images/logo.png>)
    found += [(100, urllib.parse.urljoin(base, u)) for u in re.findall(r'src=["\']?([^"\'\s>]*logo[^"\'\s>]*\.png)', html, re.I)[:2]]
    return [u for _, u in sorted(found, reverse=True)]

def nse_site(sym):
    if sym in SITES: return SITES[sym]
    html = get(f"https://afx.kwayisi.org/nse/{sym.lower()}.html").decode("utf-8", "replace")
    m = re.search(r"Website<dd><a[^>]+href=\"?([^\" >]+)", html)
    return m and re.sub(r"^https?://", "", m[1])

def candidates(market, sym):
    if sym in SPECIAL: return [SPECIAL[sym]]
    if market == "us": return [f"https://financialmodelingprep.com/image-stock/{urllib.parse.quote(sym)}.png"]
    site = nse_site(sym)
    if not site: return []
    host = site.split("/")[0]
    return site_icons(site) + [f"https://www.google.com/s2/favicons?domain={host}&sz=128"]

def fetch(market, sym):
    out = os.path.join(DIR, sym.replace("^", "") + ".png")
    miss = os.path.join(DIR, "." + sym.replace("^", "") + ".miss")
    if os.path.exists(out) or os.path.exists(out[:-4] + ".svg"): return
    if missed(sym): return
    best = None
    try:
        for url in candidates(market, sym):
            try: b = get(url)
            except Exception: continue
            if image(b) and len(b) > 200 and (not best or size(b) > size(best)): best = b
            if best and size(best) >= 120: break
    except Exception: pass
    if best: to_png(best, out)
    else: open(miss, "w").close()

def missed(sym):
    """A recent failed lookup: wait before trying again (so a refresh every 5 min doesn't refetch)."""
    try: return time.time() - os.path.getmtime(os.path.join(DIR, "." + sym.replace("^", "") + ".miss")) < 3600
    except OSError: return False

def ensure(market, syms):
    """For the data scripts: fetch any missing logos in a detached process so the widget's output isn't held up."""
    have = set(os.listdir(DIR)) if os.path.isdir(DIR) else set()
    need = [x for x in syms if x.replace("^", "") + ".png" not in have and x.replace("^", "") + ".svg" not in have and not missed(x)]
    if need:
        import subprocess
        subprocess.Popen([sys.executable, os.path.abspath(__file__), market, *need], stdin=subprocess.DEVNULL,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)

if __name__ == "__main__":
    os.makedirs(DIR, exist_ok=True)
    market, syms = sys.argv[1], sys.argv[2:]
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(8) as ex: list(ex.map(lambda s: fetch(market, s.upper() if market == "nse" else s), syms))
