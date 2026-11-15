#!/usr/bin/env python3
"""Movies & shows picked for the user's taste (Batman, Iron Man / Marvel, AI & tech, money & markets, mind-benders).
  picks.py              JSON for the widget: today's pick, more picks, coming soon, new episodes, seen list
  picks.py seen KEY     mark as watched (never picked again)
  picks.py skip KEY     not interested (never picked again)
  picks.py unmark KEY   unmark from watched/skipped list back to active pool
  picks.py another      a different pick for today
  picks.py refresh      update the cached details (run in the background when they're stale)
Posters, blurbs, runtimes and release dates from Wikipedia + Wikidata; show ratings and episodes from TVmaze.
No API keys. Details are cached for a week, episodes for 3 hours."""
import json, os, re, subprocess, sys, time, urllib.parse
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime

META = os.path.expanduser("~/.stark/.picks-meta.json")
STATE = os.path.expanduser("~/.stark/.picks-state.json")
UA = {"User-Agent": "desktop-dashboard/1.0 (Übersicht widget)"}

WHY = {
    "bat": "Because you love Batman",
    "dc": "From the DC universe",
    "iron": "Because you love Iron Man",
    "mcu": "From the Marvel universe",
    "ai": "AI & tech",
    "money": "Money & markets",
    "mind": "Mind-bending sci-fi",
    "hero": "Superhero & vigilante",
    "action": "Big-screen action"
}

GENRES = [
    {"tag": "all", "label": "ALL"},
    {"tag": "ai", "label": "AI & TECH"},
    {"tag": "money", "label": "MARKETS"},
    {"tag": "mind", "label": "SCI-FI"},
    {"tag": "bat", "label": "BATMAN"},
    {"tag": "mcu", "label": "MARVEL"},
    {"tag": "dc", "label": "DC"},
    {"tag": "hero", "label": "VIGILANTE"},
    {"tag": "action", "label": "ACTION"}
]

# (Wikipedia page, kind, reason). kind: movie | show (TVmaze name after "|") | soon (upcoming film)
PICKS = [
    # Batman & DC
    ("The_Dark_Knight", "movie", "bat"), ("The_Batman_(film)", "movie", "bat"), ("Batman_Begins", "movie", "bat"),
    ("The_Dark_Knight_Rises", "movie", "bat"), ("Joker_(2019_film)", "movie", "dc"), ("Superman_(2025_film)", "movie", "dc"),
    ("The_Penguin_(TV_series)|The Penguin", "show", "bat"), ("Batman:_The_Animated_Series|Batman: The Animated Series", "show", "bat"),
    ("Batman:_Caped_Crusader|Batman: Caped Crusader", "show", "bat"), ("Batman:_Under_the_Red_Hood", "movie", "bat"),
    ("Batman:_The_Long_Halloween_(film)", "movie", "bat"), ("Batman:_Mask_of_the_Phantasm", "movie", "bat"),
    ("Batman:_The_Dark_Knight_Returns_(film)", "movie", "bat"), ("Batman_Beyond:_Return_of_the_Joker", "movie", "bat"),
    ("Watchmen_(film)", "movie", "bat"), ("Watchmen_(TV_series)|Watchmen", "show", "bat"),
    ("Daredevil_(TV_series)|Daredevil", "show", "bat"), ("The_Punisher_(TV_series)|The Punisher", "show", "bat"),
    ("Constantine_(film)", "movie", "bat"), ("V_for_Vendetta_(film)", "movie", "bat"), ("Sin_City_(film)", "movie", "bat"),
    ("Peacemaker_(TV_series)|Peacemaker", "show", "dc"), ("Creature_Commandos_(TV_series)|Creature Commandos", "show", "dc"),
    ("Lanterns_(TV_series)|Lanterns", "show", "dc"), ("Zack_Snyder's_Justice_League", "movie", "dc"),

    # Marvel & Hero & Iron Man
    ("Iron_Man_(2008_film)", "movie", "iron"), ("Avengers:_Endgame", "movie", "iron"), ("Avengers:_Infinity_War", "movie", "mcu"),
    ("Captain_America:_The_Winter_Soldier", "movie", "mcu"), ("Guardians_of_the_Galaxy_Vol._3", "movie", "mcu"),
    ("Deadpool_&_Wolverine", "movie", "mcu"), ("The_Fantastic_Four:_First_Steps", "movie", "mcu"),
    ("Daredevil:_Born_Again|Daredevil: Born Again", "show", "mcu"), ("Loki_(TV_series)|Loki", "show", "mcu"),
    ("X-Men_'97|X-Men '97", "show", "mcu"), ("Moon_Knight_(miniseries)|Moon Knight", "show", "mcu"),
    ("Spider-Man:_Across_the_Spider-Verse", "movie", "hero"), ("Logan_(film)", "movie", "hero"),
    ("Invincible_(TV_series)|Invincible", "show", "hero"), ("The_Boys_(TV_series)|The Boys", "show", "hero"),
    ("Arcane_(TV_series)|Arcane", "show", "hero"),

    # AI & Tech
    ("Ex_Machina_(film)", "movie", "ai"), ("Her_(2013_film)", "movie", "ai"), ("Blade_Runner_2049", "movie", "ai"),
    ("The_Social_Network", "movie", "ai"), ("Steve_Jobs_(film)", "movie", "ai"), ("The_Imitation_Game", "movie", "ai"),
    ("BlackBerry_(film)", "movie", "ai"), ("Tetris_(film)", "movie", "ai"), ("Sneakers_(1992_film)", "movie", "ai"),
    ("Gattaca", "movie", "ai"), ("Upgrade_(film)", "movie", "ai"), ("WarGames", "movie", "ai"),
    ("Tron:_Ares", "movie", "ai"),
    ("Mr._Robot|Mr. Robot", "show", "ai"), ("Silicon_Valley_(TV_series)|Silicon Valley", "show", "ai"),
    ("Person_of_Interest_(TV_series)|Person of Interest", "show", "ai"), ("Pantheon_(TV_series)|Pantheon", "show", "ai"),
    ("Devs_(TV_series)|Devs", "show", "ai"), ("Halt_and_Catch_Fire_(TV_series)|Halt and Catch Fire", "show", "ai"),
    ("The_Playlist_(miniseries)|The Playlist", "show", "ai"), ("WeCrashed|WeCrashed", "show", "ai"),
    ("Super_Pumped_(TV_series)|Super Pumped", "show", "ai"), ("Black_Mirror|Black Mirror", "show", "ai"),
    ("Westworld_(TV_series)|Westworld", "show", "ai"), ("Cyberpunk:_Edgerunners|Cyberpunk: Edgerunners", "show", "ai"),
    ("Scavengers_Reign|Scavengers Reign", "show", "ai"),

    # Money & Markets
    ("The_Big_Short_(film)", "movie", "money"), ("Margin_Call", "movie", "money"), ("Moneyball_(film)", "movie", "money"),
    ("The_Wolf_of_Wall_Street_(2013_film)", "movie", "money"), ("Dumb_Money", "movie", "money"),
    ("Wall_Street_(1987_film)", "movie", "money"), ("Boiler_Room_(film)", "movie", "money"),
    ("Too_Big_to_Fail_(film)", "movie", "money"), ("Rogue_Trader_(film)", "movie", "money"),
    ("The_Hummingbird_Project", "movie", "money"), ("Glengarry_Glen_Ross_(film)", "movie", "money"),
    ("Billions_(TV_series)|Billions", "show", "money"), ("Succession_(TV_series)|Succession", "show", "money"),
    ("Industry_(TV_series)|Industry", "show", "money"), ("Bad_Banks|Bad Banks", "show", "money"),
    ("The_Dropout_(miniseries)|The Dropout", "show", "money"), ("Black_Monday_(TV_series)|Black Monday", "show", "money"),

    # Mind-Bending Sci-Fi
    ("Inception", "movie", "mind"), ("Interstellar_(film)", "movie", "mind"), ("The_Prestige_(film)", "movie", "mind"),
    ("Tenet_(film)", "movie", "mind"), ("Arrival_(film)", "movie", "mind"), ("Dune:_Part_Two", "movie", "mind"),
    ("Edge_of_Tomorrow", "movie", "mind"), ("Oppenheimer_(film)", "movie", "mind"),
    ("Coherence_(film)", "movie", "mind"), ("Primer_(film)", "movie", "mind"),
    ("12_Monkeys_(film)", "movie", "mind"), ("Predestination_(film)", "movie", "mind"),
    ("Everything_Everywhere_All_at_Once", "movie", "mind"), ("Looper_(film)", "movie", "mind"),
    ("Moon_(2009_film)", "movie", "mind"), ("Annihilation_(film)", "movie", "mind"),
    ("Source_Code_(film)", "movie", "mind"),
    ("Severance_(TV_series)|Severance", "show", "mind"), ("Andor_(TV_series)|Andor", "show", "mind"),
    ("Fallout_(American_TV_series)|Fallout", "show", "mind"), ("Dark_(TV_series)|Dark", "show", "mind"),
    ("Counterpart_(TV_series)|Counterpart", "show", "mind"), ("Silo_(TV_series)|Silo", "show", "mind"),
    ("Foundation_(TV_series)|Foundation", "show", "mind"), ("3_Body_Problem_(TV_series)|3 Body Problem", "show", "mind"),

    # Action & Thrillers
    ("Top_Gun:_Maverick", "movie", "action"), ("Mission:_Impossible_–_Dead_Reckoning_Part_One", "movie", "action"),
    ("Mission:_Impossible_–_The_Final_Reckoning", "movie", "action"),
    ("John_Wick_(film)", "movie", "action"), ("John_Wick:_Chapter_4", "movie", "action"),
    ("Heat_(1995_film)", "movie", "action"), ("Sicario_(2015_film)", "movie", "action"),
    ("Baby_Driver", "movie", "action"), ("The_Gentlemen_(2019_film)", "movie", "action"),
    ("The_Gentlemen_(2024_TV_series)|The Gentlemen", "show", "action"),

    # Upcoming Releases
    ("Clayface_(film)", "soon", "bat"), ("Avengers:_Doomsday", "soon", "iron"),
    ("Avengers:_Secret_Wars", "soon", "mcu"), ("Man_of_Tomorrow_(film)", "soon", "dc"),
    ("The_Batman:_Part_II", "soon", "bat"), ("Supergirl_(2026_film)", "soon", "dc"),
    ("Spider-Man:_Brand_New_Day", "soon", "mcu"), ("Dune:_Part_Three", "soon", "mind"),
    ("Spider-Man:_Beyond_the_Spider-Verse", "soon", "hero"),
]


def get(url):
    r = subprocess.run(["/usr/bin/curl", "-gsfL", "--max-time", "15", "-A", UA["User-Agent"], url], capture_output=True)
    try: return json.loads(r.stdout)
    except Exception: return {}


def wiki(page):
    s = get("https://en.wikipedia.org/api/rest_v1/page/summary/" + urllib.parse.quote(page))
    if not s or "title" not in s: return {}
    out = {"title": re.sub(r" \((?:\d{4} )?(?:film|TV series|American TV series|miniseries)\)$", "", s["title"]),
           "desc": s.get("description", ""), "blurb": s.get("extract", ""),
           "poster": (s.get("originalimage") or s.get("thumbnail") or {}).get("source"),
           "url": s.get("content_urls", {}).get("desktop", {}).get("page")}
    q = s.get("wikibase_item")
    if q:
        data = get(f"https://www.wikidata.org/wiki/Special:EntityData/{q}.json")
        claims = data.get("entities", {}).get(q, {}).get("claims", {})
        dates = sorted(c["mainsnak"]["datavalue"]["value"]["time"][1:11] for c in claims.get("P577", []) if "datavalue" in c.get("mainsnak", {}))
        dates = [d for d in dates if not d.endswith("-00")]
        if dates: out["dates"] = dates
        rt = [c["mainsnak"]["datavalue"]["value"]["amount"] for c in claims.get("P2047", []) if "datavalue" in c.get("mainsnak", {})]
        if rt:
            try: out["mins"] = int(float(rt[0]))
            except Exception: pass
    return out


def tvmaze(name, sid=None):
    if not sid:
        res = get("https://api.tvmaze.com/singlesearch/shows?" + urllib.parse.urlencode({"q": name}))
        sid = res.get("id") if isinstance(res, dict) else None
    if not sid: return {}
    s = get(f"https://api.tvmaze.com/shows/{sid}?embed[]=nextepisode&embed[]=previousepisode")
    if not isinstance(s, dict): return {}
    emb = s.get("_embedded") or {}
    ep = lambda e: e and {"s": e.get("season"), "e": e.get("number"), "name": e.get("name"), "at": e.get("airstamp")}
    return {"id": sid, "rating": (s.get("rating") or {}).get("average"), "status": s.get("status"), "genres": s.get("genres", [])[:3],
            "img": (s.get("image") or {}).get("original"), "net": ((s.get("network") or s.get("webChannel") or {}).get("name")),
            "next": ep(emb.get("nextepisode")), "prev": ep(emb.get("previousepisode")), "years": (s.get("premiered") or "")[:4]}


def load(path, default):
    try: return json.load(open(path))
    except Exception: return default


def refresh(meta):
    now = time.time()
    def one(item):
        page = item[0]; m = dict(meta.get(page, {}))
        try:
            if now - m.get("t", 0) > 7 * 86400 or "title" not in m:
                info = wiki(page.partition("|")[0])
                if info and "title" in info:
                    m.update(info)
                    m["t"] = now
        except Exception:
            pass
        return page, m
    with ThreadPoolExecutor(6) as ex:
        for page, m in ex.map(one, PICKS):
            if m and "title" in m: meta[page] = m
    for page, kind, why in PICKS:
        tv = page.partition("|")[2]
        if tv and now - meta.get(page, {}).get("tvt", 0) > 3 * 3600:
            try:
                tvinfo = tvmaze(tv, (meta.get(page, {}).get("tv") or {}).get("id"))
                if tvinfo:
                    meta[page]["tv"] = tvinfo
                    meta[page]["tvt"] = now
            except Exception: pass
    json.dump(meta, open(META, "w"), indent=2)
    return meta


def stale(meta):
    now = time.time()
    return any(now - meta.get(p, {}).get("t", 0) > 7 * 86400 or (p.partition("|")[2] and now - meta.get(p, {}).get("tvt", 0) > 3 * 3600)
               for p, _, _ in PICKS)


def main():
    args = sys.argv[1:]
    st = load(STATE, {"seen": [], "skip": [], "day": "", "offset": 0})
    today = date.today().isoformat()
    if st.get("day") != today: st.update(day=today, offset=0)
    if args and args[0] in ("seen", "skip") and len(args) > 1:
        target = args[1]
        st[args[0]] = sorted(set(st.get(args[0], [])) | {target})
        # If marking seen, remove from skip; if skipping, remove from seen
        other = "skip" if args[0] == "seen" else "seen"
        st[other] = [k for k in st.get(other, []) if k != target]
    elif args and args[0] == "unmark" and len(args) > 1:
        target = args[1]
        st["seen"] = [k for k in st.get("seen", []) if k != target]
        st["skip"] = [k for k in st.get("skip", []) if k != target]
    elif args and args[0] == "another":
        st["offset"] += 1
    json.dump(st, open(STATE, "w"), indent=2)

    if args and args[0] == "refresh":
        lock = META + ".lock"
        if os.path.exists(lock) and time.time() - os.path.getmtime(lock) < 600: return
        open(lock, "w").close()
        try: refresh(load(META, {}))
        finally:
            if os.path.exists(lock): os.remove(lock)
        return

    meta = load(META, {})
    if not meta: meta = refresh(meta)
    elif stale(meta):
        subprocess.Popen([sys.executable, os.path.abspath(__file__), "refresh"], start_new_session=True,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    items = []
    seen_map = {}
    for page, kind, why in PICKS:
        m = meta.get(page) or {}
        if "title" not in m: continue
        tv = m.get("tv") or {}
        it = {"key": page, "kind": kind, "why": WHY.get(why, why), "tag": why, "title": m["title"], "desc": m.get("desc", ""),
              "blurb": re.sub(r"^.*?\. (?=[A-Z])", "", m.get("blurb", ""), count=1),
              "poster": tv.get("img") or m.get("poster"), "url": m.get("url"), "mins": m.get("mins"),
              "rating": tv.get("rating"), "net": tv.get("net"), "status": tv.get("status"), "next": tv.get("next"), "prev": tv.get("prev")}
        seen_map[page] = it
        if kind == "soon":
            d = (m.get("dates") or [None])[-1]
            if not d: continue
            it["release"] = d
            if (date.fromisoformat(d) - date.today()).days < -45: continue
        items.append(it)

    done = set(st.get("seen", [])) | set(st.get("skip", []))
    pool = [x for x in items if x["kind"] != "soon" and x["key"] not in done]
    
    # Deal round-robin across tastes so neighbouring picks differ (Batman, then AI, then markets, …)
    rank = {}
    for x in pool:
        rank[x["key"]] = (sum(1 for y in pool[:pool.index(x)] if y["tag"] == x["tag"]),
                          list(WHY).index(x["tag"]) if x["tag"] in WHY else 99)
    pool.sort(key=lambda x: rank[x["key"]])

    n = len(pool)
    seed = (date.today().toordinal() * 7 + st.get("offset", 0)) % n if n else 0
    order = pool[seed:] + pool[:seed]
    soon = sorted([x for x in items if x["kind"] == "soon"], key=lambda x: x["release"])

    # Shows with an episode out in the last week or coming in the next three weeks
    def epday(x):
        for k, lo, hi in (("next", 0, 21), ("prev", -7, 0)):
            e = x.get(k)
            if e and e.get("at"):
                try:
                    d = (datetime.fromisoformat(e["at"].replace("Z", "+00:00")).date() - date.today()).days
                    if lo <= d <= hi: return d
                except Exception: pass
        return None
    eps = sorted([x for x in items if x["kind"] == "show" and epday(x) is not None], key=epday)

    # Build seen_list in reverse order (most recently watched first)
    seen_list = []
    for k in reversed(st.get("seen", [])):
        if k in seen_map:
            seen_list.append(seen_map[k])

    out = {
        "pick": order[0] if order else None,
        "more": order[1:7],
        "pool": order[:48],
        "soon": soon,
        "eps": eps,
        "seen_list": seen_list,
        "left": n,
        "seen": len(st.get("seen", [])),
        "genres": GENRES
    }
    print(json.dumps(out))


if __name__ == "__main__":
    main()
