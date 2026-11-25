#!/usr/bin/env python3
"""Movies & shows picked for the user's taste (Batman, Iron Man / Marvel, AI & tech, money & markets, mind-benders).
  picks.py              JSON for the widget: today's pick, more picks, coming soon, new episodes, seen list
  picks.py seen KEY     mark as watched (never picked again)
  picks.py skip KEY     not interested (never picked again)
  picks.py unmark KEY   unmark from watched/skipped list back to active pool
  picks.py another      a different pick for today
  picks.py refresh      update the cached details (run in the background when they're stale)
The hand-made PICKS list is the starting taste. On top of it, titles are found live on Wikidata (same director, creator,
franchise, universe, source, cast as what you watched; new releases in your genres; big upcoming films) and every
title is ranked by what you've marked SEEN (+) and SKIP (-), so the picks follow what you actually watch.
Posters, blurbs, runtimes and release dates from Wikipedia + Wikidata; show ratings and episodes from TVmaze.
No API keys. Discovery refreshes every 3 days (or after 3 new marks), details weekly, episodes every 3 hours."""
import json, math, os, re, subprocess, sys, time, urllib.parse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta

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
    ("Watchmen_(2009_film)", "movie", "bat"), ("Watchmen_(TV_series)|Watchmen", "show", "bat"),
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
    ("The_Playlist_(TV_series)|The Playlist", "show", "ai"), ("WeCrashed|WeCrashed", "show", "ai"),
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


FOUND = os.path.expanduser("~/.stark/.picks-found.json")
SPARQL = "https://query.wikidata.org/sparql"
SUA = "desktop-dashboard/1.0 (picks.py)"  # ASCII only: some APIs refuse the Ü in UA
FILM = ["Q11424", "Q202866", "Q29168811"]               # film, animated film, animated feature film
TV = ["Q5398426", "Q1259759", "Q581714", "Q117467246"]  # TV series, miniseries, animated series
# How much sharing each Wikidata property says about taste
PW = {"P179": 1.6, "P8345": 1.6, "P1434": 1.6, "P144": 1.4, "P57": 1.3, "P170": 1.3, "P58": 0.9,
      "P921": 0.8, "P136": 0.5, "P161": 0.35, "P86": 0.3, "P272": 0.3}
WEAK = {"P136", "P161", "P86", "P272"}  # not a reason on their own ("Because you watched …")
NOPE = re.compile(r"anime|documentary|reality|children|musical film|telenovela|soap opera|concert|stand-up|pornograph", re.I)
TAGRULES = [("bat", r"\bBatman\b|Gotham"), ("dc", r"\bDC\b|DC Comics|DC Extended|DC Universe|Superman|Wonder Woman"),
            ("iron", r"Iron Man"), ("mcu", r"Marvel"),
            ("ai", r"artificial intelligence|hacker|computer|cyberpunk|robot|android|technology|Silicon|internet|video game"),
            ("money", r"financ|stock market|Wall Street|business|bank|econom|startup|hedge fund|corporate"),
            ("hero", r"superhero|vigilante|comic"),
            ("mind", r"science fiction|time travel|dystopi|space|post-apocalyptic|psychological")]


def get(url):
    r = subprocess.run(["/usr/bin/curl", "-gsfL", "--retry", "3", "--max-time", "20", "-A", UA["User-Agent"], url], capture_output=True)
    try: return json.loads(r.stdout)
    except Exception: return {}


def sparql(q):
    for wait in (20, 45, 0):  # Wikidata allows ~60 s of query time a minute per client; back off when refused
        r = subprocess.run(["/usr/bin/curl", "-gsfG", "--max-time", "90", "-A", SUA, "-H", "Accept: application/sparql-results+json",
                            "--data-urlencode", "query=" + q, SPARQL], capture_output=True)
        try:
            out = json.loads(r.stdout)["results"]["bindings"]
            time.sleep(1.5)
            return out
        except Exception:
            if wait: time.sleep(wait)
    print("sparql failed", r.returncode, q[:80].replace("\n", " "), file=sys.stderr)
    return None


qid = lambda uri: uri.rsplit("/", 1)[1]
vals = lambda qs: " ".join("wd:" + q for q in qs)
iso = lambda d: d.isoformat() + "T00:00:00Z"


def summaries(pages):
    """Wikipedia intro, poster, description and Wikidata id for many pages, 20 per call (one call each got rate-limited)."""
    out = {}
    for i in range(0, len(pages), 20):
        chunk = pages[i:i + 20]
        r = get("https://en.wikipedia.org/w/api.php?" + urllib.parse.urlencode({
            "action": "query", "format": "json", "formatversion": 2, "redirects": 1, "titles": "|".join(p.replace("_", " ") for p in chunk),
            "prop": "extracts|pageimages|description|pageprops|info", "exintro": 1, "explaintext": 1, "exlimit": 20,
            "piprop": "original", "pilicense": "any", "ppprop": "wikibase_item", "inprop": "url"}))
        qr = r.get("query") or {}
        alias = {}
        partial = set()
        for k in ("normalized", "redirects"):
            for x in qr.get(k, []):
                if x.get("tofragment"): partial.add(x["to"])  # redirect to a section of another article: no page of its own yet
                else: alias[x["to"]] = alias.get(x["from"], x["from"])
        for pg in qr.get("pages", []):
            if pg.get("missing") or "title" not in pg or pg["title"] in partial: continue
            src = pg["title"]
            while src in alias: src = alias[src]
            ex = re.sub(r"\s+", " ", pg.get("extract") or "").strip()
            out[src.replace(" ", "_")] = {
                "title": re.sub(r" \((?:\d{4} )?(?:\w+ )?(?:film|TV series|miniseries|animated series)\)$", "", pg["title"]),
                "desc": pg.get("description", ""), "blurb": ex[:700],
                "poster": ((pg.get("original") or {}).get("source") or "").split("?")[0] or None, "url": pg.get("fullurl"),
                "q": (pg.get("pageprops") or {}).get("wikibase_item")}
        time.sleep(0.5)
    return out


def summary(page):
    s = get("https://en.wikipedia.org/api/rest_v1/page/summary/" + urllib.parse.quote(page))
    if not s or "title" not in s: return {}
    return {"title": re.sub(r" \((?:\d{4} )?(?:\w+ )?(?:film|TV series|miniseries|animated series)\)$", "", s["title"]),
            "desc": s.get("description", ""), "blurb": s.get("extract", ""),
            "poster": (s.get("originalimage") or s.get("thumbnail") or {}).get("source"),
            "url": s.get("content_urls", {}).get("desktop", {}).get("page"), "q": s.get("wikibase_item")}


def wiki(page):
    out = summary(page)
    q = out.get("q")
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


def tvmaze(name, sid=None, imdb=None):
    if not sid and imdb:
        res = get("https://api.tvmaze.com/lookup/shows?imdb=" + imdb)
        sid = res.get("id") if isinstance(res, dict) else None
        time.sleep(0.6)
    if not sid and name:
        res = get("https://api.tvmaze.com/singlesearch/shows?" + urllib.parse.urlencode({"q": name}))
        sid = res.get("id") if isinstance(res, dict) else None
        time.sleep(0.6)
    if not sid: return {}
    s = get(f"https://api.tvmaze.com/shows/{sid}?embed[]=nextepisode&embed[]=previousepisode")
    time.sleep(0.6)  # TVmaze allows ~20 calls / 10 s; a refused call used to be cached as an empty show
    if not isinstance(s, dict) or not s.get("id"): return {}
    emb = s.get("_embedded") or {}
    ep = lambda e: e and {"s": e.get("season"), "e": e.get("number"), "name": e.get("name"), "at": e.get("airstamp")}
    return {"id": sid, "rating": (s.get("rating") or {}).get("average"), "status": s.get("status"), "genres": s.get("genres", [])[:3],
            "img": (s.get("image") or {}).get("original"), "net": ((s.get("network") or s.get("webChannel") or {}).get("name")),
            "next": ep(emb.get("nextepisode")), "prev": ep(emb.get("previousepisode")), "years": (s.get("premiered") or "")[:4]}


def load(path, default):
    try: return json.load(open(path))
    except Exception: return default


def save(path, obj):
    tmp = path + ".tmp"
    json.dump(obj, open(tmp, "w"), indent=1)
    os.replace(tmp, path)


# ───────── live discovery from Wikidata, driven by what you've watched ─────────

def info(qs):
    """Wikidata facts for titles: English page, kind, release dates, runtime, IMDb id, popularity (sitelinks),
    Rotten Tomatoes score (used only to rank, so a famous flop like Batman & Robin doesn't lead)."""
    out = {}
    for i in range(0, len(qs), 120):
        rows = sparql(f"""SELECT ?item ?art ?sl ?cls ?d ?dur ?imdb ?rt WHERE {{ VALUES ?item {{ {vals(qs[i:i + 120])} }}
          ?item wikibase:sitelinks ?sl ; wdt:P31 ?cls . ?art schema:about ?item ; schema:isPartOf <https://en.wikipedia.org/> .
          OPTIONAL {{ {{ ?item wdt:P577 ?d }} UNION {{ ?item wdt:P580 ?d }} }} OPTIONAL {{ ?item wdt:P2047 ?dur }} OPTIONAL {{ ?item wdt:P345 ?imdb }}
          OPTIONAL {{ ?item p:P444 ?st . ?st ps:P444 ?rt ; pq:P447 wd:Q105584 ; pq:P459 wd:Q108403393 }} }}""")
        for b in rows or []:
            o = out.setdefault(qid(b["item"]["value"]), {"cls": set(), "dates": set()})
            o["page"] = urllib.parse.unquote(b["art"]["value"].rsplit("/wiki/", 1)[1])
            o["sl"] = int(b["sl"]["value"]); o["cls"].add(qid(b["cls"]["value"]))
            if "d" in b and b["d"]["value"][:1] != "-": o["dates"].add(b["d"]["value"][:10])
            if "dur" in b:
                try: o["mins"] = int(float(b["dur"]["value"]))
                except Exception: pass
            if "imdb" in b: o["imdb"] = b["imdb"]["value"]
            if "rt" in b and re.match(r"\d+%", b["rt"]["value"]): o.setdefault("rts", set()).add(int(b["rt"]["value"][:-1]))
    for o in out.values():
        if o.get("rts"): o["rt"] = round(sum(o["rts"]) / len(o["rts"]))
    return out


def features(qs, labels):
    """What each title is made of: genres, director, creator, writer, franchise, universe, source, subject, cast…"""
    out = {}
    props = " ".join("wdt:" + p for p in PW)
    for i in range(0, len(qs), 80):
        rows = sparql(f"""SELECT ?item ?p ?v ?vl WHERE {{ VALUES ?item {{ {vals(qs[i:i + 80])} }} VALUES ?p {{ {props} }}
          ?item ?p ?v . FILTER(isIRI(?v)) OPTIONAL {{ ?v rdfs:label ?vl FILTER(lang(?vl) = "en") }} }}""")
        if rows is None: continue
        for q in qs[i:i + 80]: out.setdefault(q, set())
        for b in rows:
            v = qid(b["v"]["value"]); out[qid(b["item"]["value"])].add(qid(b["p"]["value"]) + ":" + v)
            if "vl" in b: labels[v] = b["vl"]["value"]
    return {q: sorted(f) for q, f in out.items()}


def weights(items, st):
    """Taste weight of every feature: titles you watched pull it up, skips push it down, the hand-made list nudges."""
    seen, skip = set(st.get("seen", [])), set(st.get("skip", []))
    df = Counter(f for it in items for f in set(it.get("f") or []))
    raw = defaultdict(float)
    for it in items:
        w = 1.0 if it["key"] in seen else -1.3 if it["key"] in skip else 0.25 if it.get("cur") else 0
        for f in set(it.get("f") or []):
            if w: raw[f] += w
    return {f: v * PW.get(f.split(":")[0], 0.3) / math.log(2 + df[f]) for f, v in raw.items()}, df


def score(it, W):
    by = defaultdict(float)
    for f in it.get("f") or []: by[f.split(":")[0]] += W.get(f, 0)
    s = sum(min(v, 1.5) if p == "P136" else min(v, 1.0) if p == "P161" else v for p, v in by.items())
    s += 0.12 * math.log(1 + it.get("sl", 0))
    if it.get("rt") is not None and s > 0: s *= 0.5 + it["rt"] / 100  # critics: 94% → ×1.44, 11% → ×0.61
    return s


def discover(meta, st):
    """Find new titles like the ones you watched: same director/creator/franchise/universe/source/cast (any year),
    new releases in the genres you watch (last 3 years) and big upcoming films. Wikidata, refreshed every 3 days."""
    found = load(FOUND, {"pages": {}, "labels": {}})
    labels = found.setdefault("labels", {})
    cur = {p.partition("|")[0] for p, _, _ in PICKS}
    items = []
    for page, kind, why in PICKS:
        m = meta.get(page) or {}
        items.append({"key": page, "cur": 1, "f": m.get("f"), "q": m.get("q")})
    for key in found["pages"]:
        m = meta.get(key) or {}
        items.append({"key": key, "f": m.get("f"), "q": m.get("q")})
    # features for the hand-made list first (once a month)
    need = [m["q"] for p, m in meta.items() if m.get("q") and (p.partition("|")[0] in cur) and time.time() - m.get("ft", 0) > 30 * 86400]
    if need:
        fx = features(need, labels)
        for p, m in meta.items():
            if m.get("q") in fx: m["f"], m["ft"] = fx[m["q"]], time.time()
        for it in items:
            it["f"] = (meta.get(it["key"]) or {}).get("f")
    W, df = weights(items, st)
    strong = sorted(((f, w) for f, w in W.items() if w > 0 and f.split(":")[0] not in WEAK | {"P161"}), key=lambda x: -x[1])[:60]
    cast = sorted(((f, w) for f, w in W.items() if w > 0 and f.startswith("P161:")), key=lambda x: -x[1])[:20]
    genres = [f.split(":")[1] for f, w in sorted(((f, w) for f, w in W.items() if f.startswith("P136:") and w > 0), key=lambda x: -x[1])[:8]]
    pairs = " ".join(f"(wdt:{f.split(':')[0]} wd:{f.split(':')[1]})" for f, _ in strong + cast)
    classes = vals(FILM + TV)
    today = date.today()
    found_q = {}
    queries = []
    if pairs:
        queries.append(f"""SELECT DISTINCT ?item ?sl WHERE {{ VALUES (?p ?v) {{ {pairs} }} ?item ?p ?v ; wikibase:sitelinks ?sl .
          FILTER(?sl >= 20) VALUES ?cls {{ {classes} }} ?item wdt:P31 ?cls .
          ?art schema:about ?item ; schema:isPartOf <https://en.wikipedia.org/> . }} ORDER BY DESC(?sl) LIMIT 400""")
    if genres:
        queries.append(f"""SELECT DISTINCT ?item ?sl WHERE {{ VALUES ?g {{ {vals(genres)} }} ?item wdt:P136 ?g ; wdt:P577 ?d ; wikibase:sitelinks ?sl .
          FILTER(?d >= "{iso(today - timedelta(days=3 * 365))}"^^xsd:dateTime && ?sl >= 25) VALUES ?cls {{ {classes} }} ?item wdt:P31 ?cls .
          ?art schema:about ?item ; schema:isPartOf <https://en.wikipedia.org/> . }} ORDER BY DESC(?sl) LIMIT 250""")
    queries.append(f"""SELECT DISTINCT ?item ?sl WHERE {{ ?item wdt:P577 ?d .
          FILTER(?d >= "{iso(today - timedelta(days=45))}"^^xsd:dateTime && ?d <= "{iso(today + timedelta(days=540))}"^^xsd:dateTime)
          ?item wikibase:sitelinks ?sl . FILTER(?sl >= 15) VALUES ?cls {{ {vals(FILM)} }} ?item wdt:P31 ?cls .
          ?art schema:about ?item ; schema:isPartOf <https://en.wikipedia.org/> . }} ORDER BY DESC(?sl) LIMIT 200""")
    ok = True
    for q in queries:
        rows = sparql(q)
        if rows is None: ok = False; continue
        for b in rows: found_q[qid(b["item"]["value"])] = int(b["sl"]["value"])
    if not ok and not found_q: return  # Wikidata down: keep what we have, try again next run
    known = {m.get("q") for p, m in meta.items() if p.partition("|")[0] in cur}
    new = [q for q in found_q if q not in known]
    facts = info(new)
    feats = features([q for q in new if q in facts], labels)
    cands = []
    for q, o in facts.items():
        if not o.get("page") or o["page"] in cur or q not in feats: continue
        kind = "show" if o["cls"] & set(TV) else "movie"
        f = feats[q]
        text = " ".join(labels.get(x.split(":")[1], "") for x in f)
        if NOPE.search(text): continue
        dates = sorted(d for d in o["dates"] if d[:4] <= str(today.year + 5))
        if not dates or dates[0][:4] < "1980": continue
        key = o["page"] + ("|" + re.sub(r"_\(.*\)$", "", o["page"]).replace("_", " ") if kind == "show" else "")
        it = {"key": key, "q": q, "f": f, "sl": o["sl"], "kind": kind, "dates": dates, "mins": o.get("mins"), "imdb": o.get("imdb"), "rt": o.get("rt")}
        cands.append(it)
    W, _ = weights(items + cands, st)
    for it in cands: it["s"] = score(it, W)  # includes the critics' score
    cands = [it for it in cands if it["s"] > 0.6]
    up = sorted((it for it in cands if it["kind"] == "movie" and it["dates"][0] >= (today - timedelta(days=45)).isoformat()),
                key=lambda x: -x["s"])[:15]
    rest = sorted((it for it in cands if it not in up), key=lambda x: -x["s"])[:170]
    keep = {it["key"]: it for it in up + rest}
    # titles you've already marked stay known even if they drop out of the live list
    marked = set(st.get("seen", [])) | set(st.get("skip", []))
    pages = {k: v for k, v in found["pages"].items() if k in marked}
    for k, it in keep.items():
        pages[k] = it["kind"]
        m = meta.setdefault(k, {})
        m.update({x: it[x] for x in ("q", "f", "sl", "dates", "mins", "imdb", "rt") if it.get(x)})
        m["ft"] = time.time()
    # details (poster, blurb) for new titles — most promising first, capped per run
    todo = [k for k in sorted(keep, key=lambda k: -keep[k]["s"]) if "title" not in meta[k] or time.time() - meta[k].get("t", 0) > 7 * 86400]
    got = summaries([k.partition("|")[0] for k in todo])
    for k in todo:
        s = got.get(k.partition("|")[0])
        if s: s.pop("q", None); meta[k].update(s, t=time.time())
    for k in list(meta):
        if k.partition("|")[0] not in cur and k not in pages: del meta[k]
    used = {f.split(":")[1] for m in meta.values() for f in m.get("f") or []}
    found.update(t=time.time(), basis=len(marked), pages=pages, labels={q: l for q, l in labels.items() if q in used})
    save(FOUND, found)


def refresh(meta, st, full=True):
    now = time.time()
    todo = [p for p, _, _ in PICKS if now - meta.get(p, {}).get("t", 0) > 7 * 86400]
    got = summaries([p.partition("|")[0] for p in todo])
    facts = info(sorted({s["q"] for s in got.values() if s.get("q")})) if got else {}
    for p in todo:
        s = got.get(p.partition("|")[0])
        if not s:  # page gone or renamed: don't ask again for a week
            meta.setdefault(p, {})["t"] = now
            continue
        m = meta.setdefault(p, {})
        m.update(s, t=now)
        o = facts.get(s.get("q")) or {}
        if o.get("dates"): m["dates"] = sorted(d for d in o["dates"] if not d.endswith("-00") and d[:4] <= str(date.today().year + 5))
        for k in ("mins", "imdb", "sl", "rt"):
            if o.get(k): m[k] = o[k]
    if full and disc_stale(st):
        try: discover(meta, st)
        except Exception as e: print("discover failed:", e, file=sys.stderr)
        save(META, meta)
    found = load(FOUND, {"pages": {}})
    shows = [p for p, k, _ in PICKS if k == "show"] + [p for p, k in found["pages"].items() if k == "show"]
    for page in shows:
        m = meta.get(page)
        if not m or now - m.get("tvt", 0) < 3 * 3600: continue
        try:
            tvinfo = tvmaze(page.partition("|")[2], (m.get("tv") or {}).get("id"), m.get("imdb"))
            if tvinfo: m["tv"], m["tvt"] = tvinfo, now  # failures keep the last good data and retry next time
            elif not (m.get("tv") or {}).get("id"): m["tvt"] = now + 4 * 86400  # TVmaze doesn't know it: ask again in a week
        except Exception: pass
    save(META, meta)
    return meta


def disc_stale(st):
    found = load(FOUND, {})
    marked = len(st.get("seen", [])) + len(st.get("skip", []))
    return time.time() - found.get("t", 0) > 3 * 86400 or abs(marked - found.get("basis", -99)) >= 3


def stale(meta, st):
    now = time.time()
    found = load(FOUND, {})
    if disc_stale(st): return True
    shows = [p for p, k, _ in PICKS if k == "show"] + [p for p, k in found.get("pages", {}).items() if k == "show"]
    return any(now - meta.get(p, {}).get("t", 0) > 7 * 86400 for p, _, _ in PICKS) or \
        any(now - meta.get(p, {}).get("tvt", 0) > 3 * 3600 for p in shows)


ABBR = {"Bros", "Inc", "Jr", "Sr", "Mr", "Mrs", "Dr", "St", "vs", "Co", "Ltd", "Corp", "Vol", "No", "U.S", "Pt"}


def blurb(text):
    """Drop the opening 'X is a 2008 film by …' sentence (the meta line already says that), but not at 'Warner Bros. '."""
    for mt in re.finditer(r"\. (?=[A-Z])", text):
        word = text[:mt.start()].rsplit(" ", 1)[-1]
        if word not in ABBR and not re.fullmatch(r"(?:[A-Z]\.)*[A-Z]", word): return text[mt.end():]
    return text


def tag_of(m, labels):
    text = " ".join([m.get("desc", "")] + [labels.get(f.split(":")[1], "") for f in m.get("f") or []
                                           if f.split(":")[0] in ("P136", "P144", "P179", "P8345", "P1434", "P921")])
    for tag, rx in TAGRULES:
        if re.search(rx, text, re.I): return "mcu" if tag == "iron" else tag
    return "action"


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
    if not (args and args[0] == "refresh"): json.dump(st, open(STATE, "w"), indent=2)

    if args and args[0] == "refresh":
        lock = META + ".lock"
        if os.path.exists(lock) and time.time() - os.path.getmtime(lock) < 1200: return
        open(lock, "w").close()
        try: refresh(load(META, {}), st)
        finally:
            if os.path.exists(lock): os.remove(lock)
        return

    meta = load(META, {})
    if not meta: meta = refresh(meta, st, full=False)
    if stale(meta, st):
        subprocess.Popen([sys.executable, os.path.abspath(__file__), "refresh"], start_new_session=True,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    found = load(FOUND, {"pages": {}, "labels": {}})
    labels = found.get("labels", {})
    entries = [(page, kind, why, 1) for page, kind, why in PICKS]
    for key, kind in found.get("pages", {}).items():
        m = meta.get(key) or {}
        if "title" not in m or not m.get("dates"): continue
        if kind == "movie" and m["dates"][0] >= (date.today() - timedelta(days=45)).isoformat(): kind = "soon"
        entries.append((key, kind, tag_of(m, labels), 0))

    items = []
    seen_map = {}
    for page, kind, why, cur in entries:
        m = meta.get(page) or {}
        if "title" not in m: continue
        tv = m.get("tv") or {}
        it = {"key": page, "kind": kind, "why": WHY.get(why, why), "tag": why, "title": m["title"], "desc": m.get("desc", ""),
              "blurb": blurb(m.get("blurb", "")),
              "poster": tv.get("img") or m.get("poster"), "url": m.get("url"), "mins": m.get("mins"),
              "rating": tv.get("rating"), "net": tv.get("net"), "status": tv.get("status"), "next": tv.get("next"), "prev": tv.get("prev")}
        it["_f"], it["_sl"], it["_cur"], it["_rt"] = m.get("f") or [], m.get("sl", 0), cur, m.get("rt")
        seen_map[page] = it
        if kind == "soon":
            d = (m.get("dates") or [None])[-1 if cur else 0]
            if not d: continue
            it["release"] = d
            if (date.fromisoformat(d) - date.today()).days < -45: continue
        items.append(it)

    # Score everything against what you've watched (+) and skipped (−), right now — marking a title re-ranks at once
    seen, skip = set(st.get("seen", [])), set(st.get("skip", []))
    W, df = weights([{"key": x["key"], "f": x["_f"], "cur": x["_cur"]} for x in seen_map.values()], st)
    watched = [x for x in seen_map.values() if x["key"] in seen]
    for x in items:
        x["_s"] = score({"f": x["_f"], "sl": x["_sl"], "rt": x["_rt"]}, W) + (0.4 if x["_cur"] else 0)
        # the title you watched that this one is most like (shared director, franchise, universe, source, creator…)
        best, link = None, 0.0
        mine = set(x["_f"])
        for w in watched:
            if w["key"] == x["key"]: continue
            sh = [f for f in mine & set(w["_f"]) if f.split(":")[0] not in WEAK]
            v = sum(PW[f.split(":")[0]] / math.log(2 + df[f]) for f in sh)
            if v > link: best, link = w, v
        x["_link"] = link
        if best and link >= 0.6:
            x["why"] = "Because you watched " + best["title"]
            if not x["_cur"]: x["tag"] = "mcu" if best["tag"] == "iron" else best["tag"]

    done = seen | skip
    pool = [x for x in items if x["kind"] != "soon" and x["key"] not in done]
    # Best first, but no taste three times in a row (Batman, then AI, then markets, …)
    # Each taste takes turns (smooth weighted round-robin), weighted by how much of it you watch and how little you skip;
    # within a taste, the closest match to your history comes first.
    queues = defaultdict(list)
    for x in sorted(pool, key=lambda x: -x["_s"]): queues[x["tag"]].append(x)
    tw = {}
    for t in queues:
        a = sum(1 for x in seen_map.values() if x["tag"] == t and x["key"] in seen)
        b = sum(1 for x in seen_map.values() if x["tag"] == t and x["key"] in skip)
        tw[t] = math.sqrt(a + 1) * (a + 1) / (a + 1.5 * b + 1)
    order, cw = [], defaultdict(float)
    while any(queues.values()):
        live = [t for t in queues if queues[t]]
        tot = sum(tw[t] for t in live)
        for t in live: cw[t] += tw[t]
        t = max(live, key=lambda t: cw[t])
        cw[t] -= tot
        order.append(queues[t].pop(0))
    n = len(order)
    seed = (date.today().toordinal() % 5 + st.get("offset", 0)) % n if n else 0
    order = order[seed:] + order[:seed]

    soonc = [x for x in items if x["kind"] == "soon"]
    soon = sorted([x for x in soonc if x["_cur"]] + sorted([x for x in soonc if not x["_cur"] and x["_link"] >= 0.6 and "film" in x["desc"]],
                                                         key=lambda x: -x["_s"])[:10],
                  key=lambda x: x["release"])

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
    eps = sorted([x for x in items if x["kind"] == "show" and x["key"] not in skip and epday(x) is not None], key=epday)

    # Build seen_list in reverse order (most recently watched first)
    seen_list = [seen_map[k] for k in reversed(st.get("seen", [])) if k in seen_map]
    for x in seen_map.values():
        for k in ("_f", "_sl", "_cur", "_s", "_link", "_rt"): x.pop(k, None)

    out = {
        "pick": order[0] if order else None,
        "more": order[1:7],
        "pool": order[:72],
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
