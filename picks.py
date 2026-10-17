#!/usr/bin/env python3
"""Movies & shows picked for the user's taste (Batman, Iron Man / Marvel, AI & tech, money & markets, mind-benders).
  picks.py              JSON for the widget: today's pick, more picks, coming soon, new episodes
  picks.py seen KEY     mark as watched (never picked again)
  picks.py skip KEY     not interested (never picked again)
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

WHY = {"bat": "Because you love Batman", "dc": "From the DC universe", "iron": "Because you love Iron Man",
       "mcu": "From the Marvel universe", "ai": "AI & tech", "money": "Money & markets", "mind": "Mind-bending sci-fi",
       "hero": "Superhero, done differently", "action": "Big-screen action"}

# (Wikipedia page, kind, reason). kind: movie | show (TVmaze name after "|") | soon (upcoming film)
PICKS = [
    ("The_Dark_Knight", "movie", "bat"), ("The_Batman_(film)", "movie", "bat"), ("Batman_Begins", "movie", "bat"),
    ("The_Dark_Knight_Rises", "movie", "bat"), ("Joker_(2019_film)", "movie", "dc"), ("Superman_(2025_film)", "movie", "dc"),
    ("Iron_Man_(2008_film)", "movie", "iron"), ("Avengers:_Endgame", "movie", "iron"), ("Avengers:_Infinity_War", "movie", "mcu"),
    ("Captain_America:_The_Winter_Soldier", "movie", "mcu"), ("Guardians_of_the_Galaxy_Vol._3", "movie", "mcu"),
    ("Spider-Man:_Across_the_Spider-Verse", "movie", "hero"), ("Logan_(film)", "movie", "hero"),
    ("Ex_Machina_(film)", "movie", "ai"), ("Her_(2013_film)", "movie", "ai"), ("Blade_Runner_2049", "movie", "ai"),
    ("The_Social_Network", "movie", "ai"), ("Steve_Jobs_(film)", "movie", "ai"), ("The_Imitation_Game", "movie", "ai"),
    ("The_Big_Short_(film)", "movie", "money"), ("Margin_Call", "movie", "money"), ("Moneyball_(film)", "movie", "money"),
    ("The_Wolf_of_Wall_Street_(2013_film)", "movie", "money"), ("Dumb_Money", "movie", "money"),
    ("Inception", "movie", "mind"), ("Interstellar_(film)", "movie", "mind"), ("The_Prestige_(film)", "movie", "mind"),
    ("Tenet_(film)", "movie", "mind"), ("Arrival_(film)", "movie", "mind"), ("Dune:_Part_Two", "movie", "mind"),
    ("Edge_of_Tomorrow", "movie", "mind"), ("Oppenheimer_(film)", "movie", "mind"), ("Top_Gun:_Maverick", "movie", "action"), ("Mission:_Impossible_–_Dead_Reckoning_Part_One", "movie", "action"),
    ("The_Penguin_(TV_series)|The Penguin", "show", "bat"), ("Batman:_The_Animated_Series|Batman: The Animated Series", "show", "bat"),
    ("Batman:_Caped_Crusader|Batman: Caped Crusader", "show", "bat"), ("Peacemaker_(TV_series)|Peacemaker", "show", "dc"),
    ("Creature_Commandos_(TV_series)|Creature Commandos", "show", "dc"), ("Lanterns_(TV_series)|Lanterns", "show", "dc"),
    ("Daredevil:_Born_Again|Daredevil: Born Again", "show", "mcu"), ("Loki_(TV_series)|Loki", "show", "mcu"),
    ("X-Men_'97|X-Men '97", "show", "mcu"), ("Invincible_(TV_series)|Invincible", "show", "hero"),
    ("The_Boys_(TV_series)|The Boys", "show", "hero"), ("Arcane_(TV_series)|Arcane", "show", "hero"),
    ("Mr._Robot|Mr. Robot", "show", "ai"), ("Silicon_Valley_(TV_series)|Silicon Valley", "show", "ai"),
    ("Person_of_Interest_(TV_series)|Person of Interest", "show", "ai"), ("Pantheon_(TV_series)|Pantheon", "show", "ai"),
    ("Devs_(TV_series)|Devs", "show", "ai"), ("Halt_and_Catch_Fire_(TV_series)|Halt and Catch Fire", "show", "ai"),
    ("Black_Mirror|Black Mirror", "show", "ai"), ("Westworld_(TV_series)|Westworld", "show", "ai"),
    ("Cyberpunk:_Edgerunners|Cyberpunk: Edgerunners", "show", "ai"),
    ("Billions_(TV_series)|Billions", "show", "money"), ("Succession_(TV_series)|Succession", "show", "money"),
    ("Industry_(TV_series)|Industry", "show", "money"), ("Severance_(TV_series)|Severance", "show", "mind"),
    ("Andor_(TV_series)|Andor", "show", "mind"), ("Fallout_(American_TV_series)|Fallout", "show", "mind"),
    ("Clayface_(film)", "soon", "bat"), ("Avengers:_Doomsday", "soon", "iron"), ("Man_of_Tomorrow_(film)", "soon", "dc"),
    ("The_Batman:_Part_II", "soon", "bat"), ("Supergirl_(2026_film)", "soon", "dc"),
    ("Spider-Man:_Brand_New_Day", "soon", "mcu"), ("Dune:_Part_Three", "soon", "mind"),
    ("Spider-Man:_Beyond_the_Spider-Verse", "soon", "hero"),
]


def get(url):
    # curl, not urllib (Cloudflare-fronted APIs refuse Python's TLS client). TVmaze takes 10-20 s on a search it
    # hasn't cached, hence the long timeout; the show id is saved so later checks are instant.
    r = subprocess.run(["/usr/bin/curl", "-gsfL", "--max-time", "30", "-A", UA["User-Agent"], url], capture_output=True)
    return json.loads(r.stdout)


def wiki(page):
    s = get("https://en.wikipedia.org/api/rest_v1/page/summary/" + urllib.parse.quote(page))
    out = {"title": re.sub(r" \((?:\d{4} )?(?:film|TV series|American TV series)\)$", "", s["title"]), "desc": s.get("description", ""),
           "blurb": s.get("extract", ""), "poster": (s.get("originalimage") or s.get("thumbnail") or {}).get("source"),
           "url": s.get("content_urls", {}).get("desktop", {}).get("page")}
    q = s.get("wikibase_item")
    if q:  # release dates + runtime from Wikidata (the latest listed date is the current plan for upcoming films)
        e = get(f"https://www.wikidata.org/wiki/Special:EntityData/{q}.json")["entities"][q]["claims"]
        dates = sorted(c["mainsnak"]["datavalue"]["value"]["time"][1:11] for c in e.get("P577", []) if "datavalue" in c["mainsnak"])
        dates = [d for d in dates if not d.endswith("-00")]
        if dates: out["dates"] = dates
        rt = [c["mainsnak"]["datavalue"]["value"]["amount"] for c in e.get("P2047", []) if "datavalue" in c["mainsnak"]]
        if rt: out["mins"] = int(float(rt[0]))
    return out


def tvmaze(name, sid=None):
    sid = sid or get("https://api.tvmaze.com/singlesearch/shows?" + urllib.parse.urlencode({"q": name}))["id"]
    s = get(f"https://api.tvmaze.com/shows/{sid}?embed[]=nextepisode&embed[]=previousepisode")
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
    def one(item):  # Wikipedia + Wikidata: fine in parallel
        page = item[0]; m = dict(meta.get(page, {}))
        try:
            if now - m.get("t", 0) > 7 * 86400 or "title" not in m: m.update(wiki(page.partition("|")[0])); m["t"] = now
        except Exception:
            pass  # keep what we had; the next run tries again
        return page, m
    with ThreadPoolExecutor(6) as ex:
        for page, m in ex.map(one, PICKS): meta[page] = m
    for page, kind, why in PICKS:  # TVmaze stalls when hit in parallel: one at a time
        tv = page.partition("|")[2]
        if tv and now - meta[page].get("tvt", 0) > 3 * 3600:
            try: meta[page]["tv"] = tvmaze(tv, (meta[page].get("tv") or {}).get("id")); meta[page]["tvt"] = now
            except Exception: pass
    json.dump(meta, open(META, "w"))
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
        st[args[0]] = sorted(set(st[args[0]]) | {args[1]})
    elif args and args[0] == "another":
        st["offset"] += 1
    json.dump(st, open(STATE, "w"))

    if args and args[0] == "refresh":  # background job started below
        lock = META + ".lock"
        if os.path.exists(lock) and time.time() - os.path.getmtime(lock) < 600: return
        open(lock, "w").close()
        try: refresh(load(META, {}))
        finally: os.remove(lock)
        return
    meta = load(META, {})
    if not meta: meta = refresh(meta)  # first run: wait for it
    elif stale(meta):  # otherwise show what we have and update in the background
        subprocess.Popen([sys.executable, os.path.abspath(__file__), "refresh"], start_new_session=True,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    items = []
    for page, kind, why in PICKS:
        m = meta.get(page) or {}
        if "title" not in m: continue
        tv = m.get("tv") or {}
        it = {"key": page, "kind": kind, "why": WHY[why], "tag": why, "title": m["title"], "desc": m.get("desc", ""),
              "blurb": re.sub(r"^.*?\. (?=[A-Z])", "", m.get("blurb", ""), count=1),  # skip the "X is a 2013 film…" opener
              "poster": tv.get("img") or m.get("poster"), "url": m.get("url"), "mins": m.get("mins"),
              "rating": tv.get("rating"), "net": tv.get("net"), "status": tv.get("status"), "next": tv.get("next"), "prev": tv.get("prev")}
        if kind == "soon":
            d = (m.get("dates") or [None])[-1]
            if not d: continue
            it["release"] = d
            if (date.fromisoformat(d) - date.today()).days < -45: continue  # out a while: it's just a movie now
        items.append(it)

    done = set(st["seen"]) | set(st["skip"])
    pool = [x for x in items if x["kind"] != "soon" and x["key"] not in done]
    # deal round-robin across tastes so neighbouring picks differ (Batman, then AI, then markets, …)
    rank = {}
    for x in pool: rank[x["key"]] = (sum(1 for y in pool[:pool.index(x)] if y["tag"] == x["tag"]), list(WHY).index(x["tag"]))
    pool.sort(key=lambda x: rank[x["key"]])
    # today's pick rotates daily (same all day), "another" steps through the rest
    n = len(pool)
    seed = (date.today().toordinal() * 7 + st["offset"]) % n if n else 0
    order = pool[seed:] + pool[:seed]
    soon = sorted([x for x in items if x["kind"] == "soon"], key=lambda x: x["release"])
    # shows with an episode out in the last week or coming in the next three
    def epday(x):
        for k, lo, hi in (("next", 0, 21), ("prev", -7, 0)):
            e = x.get(k)
            if e and e.get("at"):
                d = (datetime.fromisoformat(e["at"].replace("Z", "+00:00")).date() - date.today()).days
                if lo <= d <= hi: return d
        return None
    eps = sorted([x for x in items if x["kind"] == "show" and epday(x) is not None], key=epday)
    print(json.dumps({"pick": order[0] if order else None, "more": order[1:7], "soon": soon, "eps": eps,
                      "left": n, "seen": len(st["seen"])}))


main()
