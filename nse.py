#!/usr/bin/env python3
"""Your NSE (Nairobi Securities Exchange) portfolio for the Tech Markets panel (MY NSE view).
Prices come from afx.kwayisi.org: free, no key, delayed (the NSE sells its live feed only to licensed vendors).
Holdings live in ~/.stark/portfolio.json, which is private and git-ignored:
  {"holdings": [{"sym": "EQTY", "shares": 100, "cost": 45.5}]}      cost = average price paid per share (optional)
usage: nse.py                    JSON for the widget
       nse.py add                dialogs: symbol, shares, price paid (from the panel's + ADD tile)
       nse.py edit SYM           dialog: change shares (0 removes) or open the stock's page (clicking a holding)
       nse.py set SYM SHARES [COST]"""
import json, os, re, subprocess, sys, time, urllib.request
from concurrent.futures import ThreadPoolExecutor

D = os.path.expanduser("~/.stark")
PF, LIST, HIST = f"{D}/portfolio.json", f"{D}/.nse-list.json", f"{D}/.nse-hist"
LIST_FRESH, HIST_FRESH, DAYS = 5 * 60, 6 * 3600, 66   # ~3 months of trading days on the big chart
UA = {"User-Agent": "Mozilla/5.0"}

def get(url, ref=None):
    h = dict(UA, **({"Referer": ref} if ref else {}))
    return urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=10).read().decode("utf-8", "replace")

def fresh(path, age):
    try: return time.time() - os.path.getmtime(path) < age
    except OSError: return False

def save(path, data):
    tmp = f"{path}.{os.getpid()}"; json.dump(data, open(tmp, "w")); os.replace(tmp, path)

def board():
    """Every NSE stock: {SYM: {name, p, ch}} plus the time afx last updated, cached for 5 minutes."""
    if fresh(LIST, LIST_FRESH):
        try: return json.load(open(LIST))
        except Exception: pass
    h = get("https://afx.kwayisi.org/nse/")
    rows = re.findall(r'<tr><td><a [^>]*>([A-Z0-9.\-]+)</a><td><a [^>]*title="([^"]*)"[^>]*>[^<]*</a><td>[\d,]*<td>([\d.,]+)<td[^>]*>([+\-]?[\d.,]*)', h)
    out = {"asof": (re.search(r"[A-Z][a-z]{2} \d{1,2}, \d{4} at \d\d:\d\d", re.sub(r"<[^>]+>|\s+", " ", h).replace("  ", " ")) or [None])[0],
           "stocks": {s: {"name": n.replace("&amp;", "&"), "p": float(p.replace(",", "")), "ch": float(c.replace(",", "") or 0)} for s, n, p, c in rows}}
    if out["stocks"]: save(LIST, out)
    return out

def history(sym):
    """Daily closes [[epoch, close], ...] for one stock, cached for 6 hours."""
    os.makedirs(HIST, exist_ok=True); path = f"{HIST}/{sym}.json"
    if fresh(path, HIST_FRESH):
        try: return json.load(open(path))
        except Exception: pass
    js = get(f"https://afx.kwayisi.org/chart/nse/{sym.lower()}", f"https://afx.kwayisi.org/nse/{sym.lower()}.html")
    pts = [[int(time.mktime(time.strptime(d, "%Y-%m-%d"))), float(v)] for d, v in re.findall(r'd\("(\d{4}-\d\d-\d\d)"\),([\d.]+)', js)]
    if pts: save(path, pts[-400:])
    return pts[-400:]

def holdings():
    try: return [h for h in json.load(open(PF)).get("holdings", []) if h.get("sym") and h.get("shares", 0) > 0]
    except Exception: return []

def report():
    hs = holdings()
    if not hs: return {"holdings": [], "total": None, "asof": None}
    b = board(); st = b["stocks"]
    with ThreadPoolExecutor(6) as ex: hists = dict(zip([h["sym"] for h in hs], ex.map(lambda h: safe(history, h["sym"]), hs)))
    out, missing = [], []
    for h in hs:
        s = st.get(h["sym"]);
        if not s: missing.append(h["sym"]); continue
        hist = [x for x in hists.get(h["sym"]) or [] if x[1] > 0]
        prev = s["p"] - s["ch"]
        out.append({"sym": h["sym"], "name": s["name"], "shares": h["shares"], "cost": h.get("cost"), "p": s["p"], "ch": s["ch"],
                    "pct": s["ch"] / prev * 100 if prev else 0, "value": s["p"] * h["shares"], "day": s["ch"] * h["shares"],
                    "hist": [x[1] for x in hist[-DAYS:]], "ts": [x[0] for x in hist[-DAYS:]]})
    # portfolio value per trading day: shares x that day's close, carrying each stock's last close over days it didn't trade
    days = sorted({t for x in out for t in x["ts"]})
    last, series = {}, []
    for t in days:
        for x in out:
            if t in x["ts"]: last[x["sym"]] = x["hist"][x["ts"].index(t)]
        if len(last) == len(out): series.append([t, sum(last[x["sym"]] * x["shares"] for x in out)])
    value, day = sum(x["value"] for x in out), sum(x["day"] for x in out)
    paid = sum(x["cost"] * x["shares"] for x in out if x["cost"]) if all(x["cost"] for x in out) else None
    if series and abs(series[-1][1] - value) > .005: series.append([int(time.time()), value])   # today's price if newer than the last close
    out.sort(key=lambda x: -x["value"])
    return {"asof": b.get("asof"), "missing": missing, "holdings": out,
            "total": {"value": value, "day": day, "pct": day / (value - day) * 100 if value != day else 0, "paid": paid,
                      "hist": [v for _, v in series], "ts": [t for t, _ in series]}}

def safe(f, *a):
    try: return f(*a)
    except Exception: return None

# ── editing holdings (also driven by the panel through macOS dialogs) ──
def write(sym, shares, cost=None):
    try: data = json.load(open(PF))
    except Exception: data = {"holdings": []}
    hs = [h for h in data.get("holdings", []) if h.get("sym") != sym]
    if shares > 0:
        old = next((h for h in data.get("holdings", []) if h.get("sym") == sym), {})
        hs.append({"sym": sym, "shares": shares, **({"cost": cost} if cost else {"cost": old["cost"]} if old.get("cost") else {})})
    data["holdings"] = hs; save(PF, data)

def ask(prompt, default="", buttons=("Cancel", "OK")):
    btns = "{" + ",".join(f'"{b}"' for b in buttons) + "}"
    r = subprocess.run(["osascript", "-e", f'display dialog "{prompt}" default answer "{default}" with title "My NSE portfolio" '
                        f'buttons {btns} default button "{buttons[-1]}" cancel button "Cancel"',
                        "-e", 'return (button returned of result) & "|" & (text returned of result)'], capture_output=True, text=True)
    if r.returncode: return None, None
    b, _, t = r.stdout.strip().partition("|"); return b, t.strip()

def alert(msg):
    subprocess.run(["osascript", "-e", f'display alert "My NSE portfolio" message "{msg}"'], capture_output=True)

def num(t):
    try: return float(t.replace(",", "")) if t else None
    except ValueError: return None

def add():
    _, sym = ask("NSE symbol of the company (e.g. EQTY, KCB, EABL)")
    if not sym: return
    sym = sym.upper().strip(); st = board()["stocks"]
    if sym not in st: return alert(f"{sym} isn't listed on the NSE. Check the symbol on afx.kwayisi.org/nse.")
    _, n = ask(f"How many {sym} shares ({st[sym]['name']}) do you own?")
    if num(n) is None or num(n) <= 0: return
    _, c = ask(f"Average price you paid per {sym} share in KES (optional, for your total gain)")
    write(sym, num(n), num(c))

def edit(sym):
    h = next((h for h in holdings() if h["sym"] == sym), None)
    if not h: return
    b, n = ask(f"Shares of {sym} you own (0 removes it)", f"{h['shares']:g}", ("Cancel", "Open page", "Save"))
    if b == "Open page": subprocess.run(["open", f"https://afx.kwayisi.org/nse/{sym.lower()}.html"])
    elif b == "Save" and num(n) is not None: write(sym, num(n))

if __name__ == "__main__":
    a = sys.argv[1:]
    if a[:1] == ["add"]: add()
    elif a[:1] == ["edit"] and len(a) > 1: edit(a[1].upper())
    elif a[:1] == ["set"] and len(a) > 2: write(a[1].upper(), float(a[2]), float(a[3]) if len(a) > 3 else None)
    if not a or a[0] in ("add", "edit", "set"):
        try: print(json.dumps(report(), separators=(",", ":")))
        except Exception as e: print(json.dumps({"error": True, "reason": "NSE prices unavailable", "detail": str(e)[:200]}))
