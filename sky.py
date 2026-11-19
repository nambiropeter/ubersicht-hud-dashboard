#!/usr/bin/env python3
"""Sky over Nairobi: live aircraft around you and the ISS's next pass, for the desktop widget.
Aircraft come from adsb.fi open data, with adsb.lol as backup (free community ADS-B, no key). Airline routes come from adsbdb.com (checked against where the plane really is), operators from hexdb.io;
flights with no public route (charter, private, military) get a best guess from their track instead.
ISS passes are worked out here from CelesTrak's orbit elements (TLE): a J2 orbit model is accurate to well under a
minute for pass times over the next few days, so no extra packages are needed.
Prints one JSON object: {t, range, ac: [...], ground, iss: {now, next, vis}}."""
import json, math, os, sys, time, urllib.error, urllib.request

LAT, LON = -1.2833, 36.8167          # same spot as weather.sh
RANGE_KM = 225                        # radar radius
S = os.path.expanduser("~/.stark")
ROUTES, TLE, PASS = f"{S}/.sky-routes.json", f"{S}/.sky-tle", f"{S}/.sky-iss.json"
UA = {"User-Agent": "desktop-dashboard (Ubersicht widget)", "Accept": "application/json"}

TYPES = {"A359": "A350-900", "A35K": "A350-1000", "A332": "A330-200", "A333": "A330-300", "A339": "A330-900neo",
         "A319": "A319", "A320": "A320", "A20N": "A320neo", "A321": "A321", "A21N": "A321neo", "A388": "A380",
         "B737": "737-700", "B738": "737-800", "B739": "737-900", "B38M": "737 MAX 8", "B39M": "737 MAX 9",
         "B744": "747-400", "B748": "747-8", "B763": "767-300", "B772": "777-200", "B77W": "777-300ER", "B77L": "777-200LR",
         "B788": "787-8", "B789": "787-9", "B78X": "787-10", "E190": "Embraer 190", "E195": "Embraer 195",
         "E75L": "Embraer 175", "E145": "Embraer 145", "DH8D": "Dash 8-400", "DH8C": "Dash 8-300", "AT72": "ATR 72",
         "AT76": "ATR 72-600", "AT45": "ATR 42", "C208": "Cessna Caravan", "C172": "Cessna 172", "B350": "King Air 350",
         "BE20": "King Air 200", "PC12": "Pilatus PC-12", "CRJ2": "CRJ-200", "CRJ9": "CRJ-900", "F70": "Fokker 70",
         "F100": "Fokker 100", "GLF6": "Gulfstream G650", "GLEX": "Global Express", "C130": "C-130 Hercules",
         "A400": "A400M", "EC30": "Airbus H130", "B407": "Bell 407", "B206": "Bell 206",
         "R44": "Robinson R44", "R66": "Robinson R66", "EC45": "Airbus H145", "AS65": "Dauphin", "C182": "Cessna 182",
         "C210": "Cessna 210", "PA31": "Piper Navajo", "DHC6": "Twin Otter", "BE9L": "King Air 90", "C25A": "Citation CJ2",
         "C56X": "Citation Excel", "LJ45": "Learjet 45", "E35L": "Legacy 600", "GLF5": "Gulfstream G550", "AS50": "Airbus H125", "EC35": "Airbus H135", "B412": "Bell 412", "MD11": "MD-11"}


def get(url, timeout=8):
    return json.load(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout))


def load(path, default):
    try:
        with open(path) as f: return json.load(f)
    except Exception: return default


def save(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w") as f: json.dump(data, f, separators=(",", ":"))
    os.replace(tmp, path)


def bearing_km(lat, lon):
    p1, p2, dl = math.radians(LAT), math.radians(lat), math.radians(lon - LON)
    km = 6371 * 2 * math.asin(math.sqrt(math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2))
    b = math.degrees(math.atan2(math.sin(dl) * math.cos(p2), math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)))
    return km, b % 360


# ── Aircraft ──
# Airports a local flight is most likely using; airline routes come from adsbdb, everything else is worked out here.
FIELDS = [("JKIA", -1.3192, 36.9278), ("Wilson", -1.3217, 36.8148), ("Nanyuki", -0.0624, 37.0410), ("Eastleigh", -1.2727, 36.8606)]
DIRS = "north north-east east south-east south south-west west north-west".split()


def lookups(planes):
    """Fill in airline routes, airline names and aircraft operators from a shared cache. Found answers keep 30 days,
    "nobody knows" answers 3 days, and network failures aren't cached, so they're retried next run. At most 6 new
    lookups a run so the widget stays quick; the rest fill in over the next refreshes."""
    cache, now, budget = load(ROUTES, {}), time.time(), [6]

    def ask(key, fetch):
        c = cache.get(key)
        if c and now - c["t"] < (30 if len(c) > 1 else 3) * 86400: return c
        if budget[0] <= 0: return c or {}
        budget[0] -= 1
        try: cache[key] = {"t": now, **fetch()}
        except urllib.error.HTTPError as e:
            if e.code == 404: cache[key] = {"t": now}
        except Exception: pass
        return cache.get(key, {})

    def route(cs):
        r = get(f"https://api.adsbdb.com/v0/callsign/{cs}", 4)["response"]
        fr = r.get("flightroute") if isinstance(r, dict) else None
        if not fr: return {}
        o, d, al = fr["origin"], fr["destination"], fr.get("airline") or {}
        return {"o": o["iata_code"] or o["icao_code"], "d": d["iata_code"] or d["icao_code"], "oc": o["municipality"],
                "dc": d["municipality"], "al": al.get("name"), "ol": [o["latitude"], o["longitude"]], "dl": [d["latitude"], d["longitude"]]}

    def airline(code):
        r = get(f"https://api.adsbdb.com/v0/airline/{code}", 4)["response"]
        return {"al": r[0]["name"]} if isinstance(r, list) and r else {}

    def owner(hx):
        r = get(f"https://hexdb.io/api/v1/aircraft/{hx}", 4)
        return {k: v for k, v in {"own": r.get("RegisteredOwners"), "reg": r.get("Registration"), "ty": r.get("ICAOTypeCode")}.items() if v}

    for x in planes:  # nearest first, so the ones on screen fill in first
        cs = x["_cs"]
        if cs:
            r = ask("cs:" + cs, lambda: route(cs))
            if r.get("o") and plausible(x, r): x.update(o=r["o"], d=r["d"], oc=r["oc"], dc=r["dc"])
            if r.get("al"): x["al"] = r["al"]
            elif cs[:3].isalpha() and cs[3:4].isdigit():
                al = ask("al:" + cs[:3], lambda: airline(cs[:3])).get("al")
                if al: x["al"] = al
        if not x.get("al") or not x.get("reg") or not x.get("type"):
            o = ask("hex:" + x["hex"], lambda: owner(x["hex"]))
            x["al"] = x.get("al") or o.get("own")
            x["reg"] = x.get("reg") or o.get("reg")
            x["type"] = x.get("type") or TYPES.get(o.get("ty"), o.get("ty"))
            if x["cs"] == x["hex"].upper() and o.get("reg"): x["cs"] = o["reg"]
    save(ROUTES, {k: v for k, v in cache.items() if now - v["t"] < 30 * 86400})


def plausible(x, r):
    """Callsign routes go stale (airlines reuse flight numbers), so only trust one the plane is actually flying:
    it must be near the great circle from origin to destination and pointing roughly along it."""
    try:
        p = [math.radians(v) for v in (*r["ol"], *r["dl"])]
        def vec(la, lo): return (math.cos(la) * math.cos(lo), math.cos(la) * math.sin(lo), math.sin(la))
        A, B = vec(p[0], p[1]), vec(p[2], p[3])
        n = (A[1] * B[2] - A[2] * B[1], A[2] * B[0] - A[0] * B[2], A[0] * B[1] - A[1] * B[0]); nl = math.sqrt(sum(c * c for c in n))
        if nl < 1e-9: return True
        la, lo = math.radians(x["_lat"]), math.radians(x["_lon"]); P = vec(la, lo)
        off = abs(math.degrees(math.asin(sum(a * b for a, b in zip(P, n)) / nl))) * 111.2
        dla, dlo = math.radians(r["dl"][0]), math.radians(r["dl"][1])
        want = math.degrees(math.atan2(math.sin(dlo - lo) * math.cos(dla), math.cos(la) * math.sin(dla) - math.sin(la) * math.cos(dla) * math.cos(dlo - lo))) % 360
        turn = abs((x["trk"] - want + 180) % 360 - 180)
        near_end = min(math.dist((x["_lat"], x["_lon"]), r["ol"]), math.dist((x["_lat"], x["_lon"]), r["dl"])) < 1.2
        return off < 300 and (turn < 100 or near_end)  # climbing out / turning in near an airport points anywhere
    except Exception:
        return True


def guess(x):
    """No public route (charter, private, military, training): say what the plane is evidently doing."""
    best = None
    for name, la, lo in FIELDS:
        km = math.dist((x["_lat"], x["_lon"]), (la, lo)) * 111.2
        to = math.degrees(math.atan2((lo - x["_lon"]) * math.cos(math.radians(la)), la - x["_lat"])) % 360
        toward = abs((x["trk"] - to + 180) % 360 - 180) < 50
        if km < 45 and x["vs"] < -250 and toward and (not best or km < best[0]): best = (km, "Approaching " + name)
        elif km < 45 and x["vs"] > 250 and not toward and (not best or km < best[0]): best = (km, "Climbing out of " + name)
    if best: return best[1]
    if (x["alt"] or 0) < 9000 and x["kmh"] < 300 and x["km"] < 40: return "Local flight · heading " + DIRS[round(x["trk"] / 45) % 8]
    return "Heading " + DIRS[round(x["trk"] / 45) % 8]


# adsb.fi open data first (personal use, 1 req/s, no daily cap); adsb.lol caps at 500 calls a day (HTTP 429 after),
# so it's only the backup. Same readsb JSON from both.
FEEDS = ["https://opendata.adsb.fi/api/v3/lat/{lat}/lon/{lon}/dist/{nm}", "https://api.adsb.lol/v2/point/{lat}/{lon}/{nm}"]


def feed():
    nm, err = round(RANGE_KM / 1.852) + 5, None
    for u in FEEDS:
        try:
            d = get(u.format(lat=LAT, lon=LON, nm=nm), 6)
            if isinstance(d.get("ac"), list): return d
        except Exception as e: err = e
    raise err or RuntimeError("no feed")


def aircraft():
    d = feed()
    out, ground = [], 0
    for a in d.get("ac") or []:
        if a.get("lat") is None or (a.get("seen_pos") or 0) > 60: continue
        km, b = bearing_km(a["lat"], a["lon"])
        if km > RANGE_KM: continue
        alt = a.get("alt_baro")
        if alt == "ground" or (isinstance(alt, (int, float)) and alt < 50):
            ground += 1; continue
        cs = (a.get("flight") or "").strip()
        cs = cs if len(cs) >= 3 else ""
        if a.get("r") and cs.replace("-", "") == a["r"].replace("-", ""): cs = ""  # private flights call by registration
        out.append({"hex": a["hex"], "cs": cs or (a.get("r") or a["hex"]).upper(), "reg": a.get("r"),
                    "type": TYPES.get(a.get("t"), a.get("t")), "alt": alt if isinstance(alt, (int, float)) else None,
                    "vs": a.get("baro_rate") or a.get("geom_rate") or 0, "kmh": round((a.get("gs") or 0) * 1.852),
                    "trk": round(a.get("track", a.get("true_heading", 0)) or 0), "km": round(km, 1), "b": round(b, 1),
                    "_cs": cs, "_lat": a["lat"], "_lon": a["lon"]})
    out.sort(key=lambda x: x["km"])
    lookups(out)
    for x in out:
        if not x.get("o"): x["g"] = guess(x)
        for k in ("_cs", "_lat", "_lon"): x.pop(k)
        for k in [k for k, v in x.items() if v is None]: x.pop(k)
    return out, ground


# ── ISS ──
MU, RE, J2, F = 398600.4418, 6378.137, 1.08262668e-3, 1 / 298.257223563


def tle():
    if os.path.exists(TLE) and time.time() - os.path.getmtime(TLE) < 12 * 3600:
        lines = open(TLE).read().splitlines()
    else:
        try:
            txt = urllib.request.urlopen(urllib.request.Request(
                "https://celestrak.org/NORAD/elements/gp.php?CATNR=25544&FORMAT=TLE", headers=UA), timeout=8).read().decode()
            lines = [l for l in txt.splitlines() if l.strip()]
            assert lines[-2].startswith("1 ") and lines[-1].startswith("2 ")
            open(TLE, "w").write("\n".join(lines))
        except Exception:
            lines = open(TLE).read().splitlines()  # an old set is still fine for a few days
    l1, l2 = lines[-2], lines[-1]
    yy, doy = int(l1[18:20]), float(l1[20:32])
    epoch = time.mktime(time.strptime(f"{2000 + yy if yy < 57 else 1900 + yy}", "%Y")) - time.timezone + (doy - 1) * 86400
    return {"ep": epoch, "nd": float(l1[33:43]), "i": math.radians(float(l2[8:16])), "raan": math.radians(float(l2[17:25])),
            "e": float("0." + l2[26:33]), "w": math.radians(float(l2[34:42])), "M": math.radians(float(l2[43:51])),
            "n": float(l2[52:63])}


def eci(el, t):
    """Satellite position (km, inertial) at unix time t: Kepler orbit with J2 drift of the node and perigee, plus drag."""
    dt = t - el["ep"]; days = dt / 86400
    n = el["n"] * 2 * math.pi / 86400
    a, e, i = (MU / n ** 2) ** (1 / 3), el["e"], el["i"]
    k = 1.5 * J2 * (RE / (a * (1 - e * e))) ** 2 * n
    raan = el["raan"] - k * math.cos(i) * dt
    w = el["w"] + k * (2 - 2.5 * math.sin(i) ** 2) * dt
    M = el["M"] + n * dt + el["nd"] * 2 * math.pi * days ** 2
    E = M
    for _ in range(8): E -= (E - e * math.sin(E) - M) / (1 - e * math.cos(E))
    x, y = a * (math.cos(E) - e), a * math.sqrt(1 - e * e) * math.sin(E)
    cw, sw, co, so, ci, si = math.cos(w), math.sin(w), math.cos(raan), math.sin(raan), math.cos(i), math.sin(i)
    return ((co * cw - so * sw * ci) * x + (-co * sw - so * cw * ci) * y,
            (so * cw + co * sw * ci) * x + (-so * sw + co * cw * ci) * y,
            (sw * si) * x + (cw * si) * y)


def gmst(t):
    jd = t / 86400 + 2440587.5; T = (jd - 2451545) / 36525
    return math.radians((280.46061837 + 360.98564736629 * (jd - 2451545) + 0.000387933 * T * T) % 360)


def sun(t):
    """Unit vector to the Sun (inertial, low precision)."""
    d = t / 86400 + 2440587.5 - 2451545
    L, g = math.radians((280.46 + 0.9856474 * d) % 360), math.radians((357.528 + 0.9856003 * d) % 360)
    lam, eps = L + math.radians(1.915) * math.sin(g) + math.radians(0.02) * math.sin(2 * g), math.radians(23.439 - 4e-7 * d)
    return math.cos(lam), math.cos(eps) * math.sin(lam), math.sin(eps) * math.sin(lam)


OBS = None
def observer():
    global OBS
    if OBS is None:
        p, l = math.radians(LAT), math.radians(LON); N = RE / math.sqrt(1 - F * (2 - F) * math.sin(p) ** 2); h = 1.7
        OBS = ((N + h) * math.cos(p) * math.cos(l), (N + h) * math.cos(p) * math.sin(l), (N * (1 - F) ** 2 + h) * math.sin(p), p, l)
    return OBS


def ecef(v, t):
    g = gmst(t); c, s = math.cos(g), math.sin(g)
    return c * v[0] + s * v[1], -s * v[0] + c * v[1], v[2]


def look(v_ecef):
    """Elevation and azimuth (degrees) of an Earth-fixed point seen from Nairobi."""
    ox, oy, oz, p, l = observer()
    dx, dy, dz = v_ecef[0] - ox, v_ecef[1] - oy, v_ecef[2] - oz
    e = -math.sin(l) * dx + math.cos(l) * dy
    n = -math.sin(p) * math.cos(l) * dx - math.sin(p) * math.sin(l) * dy + math.cos(p) * dz
    u = math.cos(p) * math.cos(l) * dx + math.cos(p) * math.sin(l) * dy + math.sin(p) * dz
    return math.degrees(math.atan2(u, math.hypot(e, n))), math.degrees(math.atan2(e, n)) % 360


def visible(el, t):
    """True when the ISS is sunlit while the sky here is dark enough to see it (Sun below -6°)."""
    r, s = eci(el, t), sun(t)
    sun_el, _ = look(tuple(x * 1.496e8 for x in ecef(s, t)))
    if sun_el > -6: return False
    d = sum(a * b for a, b in zip(r, s))
    return d > 0 or math.dist(r, tuple(d * x for x in s)) > RE


COMPASS = "N NE E SE S SW W NW".split()
def compass(az): return COMPASS[round(az / 45) % 8]


def passes(el, t0, hours=72, step=30, min_el=10):
    out, cur, t = [], None, t0
    while t < t0 + hours * 3600 and len(out) < 12:
        e, az = look(ecef(eci(el, t), t))
        if e >= min_el:
            if cur is None: cur = {"start": t, "az0": az, "max": e, "tmax": t, "azmax": az, "vis": False}
            if e > cur["max"]: cur.update(max=e, tmax=t, azmax=az)
            cur["end"], cur["az1"] = t, az
            cur["vis"] = cur["vis"] or visible(el, t)
        elif cur:
            out.append(cur); cur = None
            if any(p["vis"] for p in out): break
        t += step
    if cur: out.append(cur)
    return [{"start": round(p["start"]), "end": round(p["end"]), "tmax": round(p["tmax"]), "max": round(p["max"]),
             "from": compass(p["az0"]), "to": compass(p["az1"]), "dir": compass(p["azmax"]), "vis": p["vis"]} for p in out]


def iss():
    el, now = tle(), time.time()
    v = eci(el, now); x, y, z = ecef(v, now); r = math.sqrt(x * x + y * y + z * z)
    lat, lon = math.degrees(math.asin(z / r)), math.degrees(math.atan2(y, x))
    km, _ = bearing_km(lat, lon); e, az = look((x, y, z))
    cache = load(PASS, {})
    if not cache.get("list") or cache.get("ep") != el["ep"] or cache["list"][0]["end"] < now or now - cache.get("t", 0) > 6 * 3600:
        cache = {"t": now, "ep": el["ep"], "list": passes(el, now - 15 * 60)}
        save(PASS, cache)
    up = [p for p in cache["list"] if p["end"] >= now]
    return {"now": {"lat": round(lat, 1), "lon": round(lon, 1), "km": round(km), "alt": round(r - RE), "el": round(e),
                    "az": compass(az), "sunlit": visible(el, now) if e > 0 else None},
            "next": up[0] if up else None, "vis": next((p for p in up if p["vis"]), None)}


if __name__ == "__main__":
    res, errs = {"t": round(time.time()), "range": RANGE_KM}, []
    try: res["ac"], res["ground"] = aircraft()
    except Exception as e: res["ac"], res["ground"] = None, 0; errs.append("flights")
    try: res["iss"] = iss()
    except Exception as e: res["iss"] = None; errs.append("ISS")
    if len(errs) == 2: res["error"] = "Sky feeds unreachable"
    elif errs: res["warn"] = errs[0]
    print(json.dumps(res, separators=(",", ":")))
