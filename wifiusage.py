#!/usr/bin/env python3
"""Data used per Wi-Fi network, for the Connections panel's DATA view.

network.sh calls this on every refresh (every 30 s):
    wifiusage.py <wifi-dev> <router-mac> <ssid> <ssid-mtime>
It reads the Wi-Fi interface's byte counters, adds what moved since the last call to the network you're on
now, and prints JSON. A network is keyed by its router's MAC address (macOS hides the Wi-Fi name from
scripts; the name comes from the "Wi-Fi Name" shortcut and is attached once it's known).
    wifiusage.py reset <id> [all|today|month|since]    zero that network's count (e.g. a new data bundle);
        today/month subtract what was used so far, so the 14-day bars keep the real history

Data lives in ~/.stark/.wifi-usage.json (git-ignored: it holds your network names).
Counts everything over Wi-Fi (VPN/Tor included); stops counting while the widget isn't running and gives
anything used while it was stopped to whichever network you're on when it next runs.
"""
import fcntl, hashlib, json, os, re, subprocess, sys, time
from datetime import date, datetime, timedelta

D = os.path.expanduser("~/.stark")
F = f"{D}/.wifi-usage.json"
KEEP_DAYS = 100


def counters(dev):
    out = subprocess.run(["netstat", "-ib", "-I", dev], capture_output=True, text=True).stdout.splitlines()
    for line in out[1:]:
        p = line.split()
        if len(p) >= 10 and p[0] == dev and p[2].startswith("<Link"):
            return int(p[6]), int(p[9])
    return None


def boot():
    m = re.search(r"sec = (\d+)", subprocess.run(["sysctl", "-n", "kern.boottime"], capture_output=True, text=True).stdout)
    return int(m.group(1)) if m else 0


def nid(key):  # short id for the widget, so the router MAC itself never leaves this file
    return hashlib.sha1(key.encode()).hexdigest()[:8]


def load():
    try:
        with open(F) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {"last": None, "nets": {}}


def save(s):
    with open(F + ".tmp", "w") as f:
        json.dump(s, f, separators=(",", ":"))
    os.replace(F + ".tmp", F)


def add(day, rx, tx):
    day[0] += rx; day[1] += tx


def raw_today(n):
    return list(n["days"].get(date.today().isoformat(), [0, 0]))


def raw_month(n):
    month = date.today().strftime("%Y-%m")
    return [sum(v[i] for d, v in n["days"].items() if d.startswith(month)) for i in (0, 1)]


def summary(s, cur):
    today = date.today()
    month = today.strftime("%Y-%m")
    out = []
    for key, n in s["nets"].items():
        days = n["days"]
        t, m = raw_today(n), raw_month(n)
        cut = n.get("cut", {})
        tf = mf = 0
        if (cut.get("today") or {}).get("k") == today.isoformat():
            t = [max(0, a - b) for a, b in zip(t, cut["today"]["v"])]; tf = cut["today"]["t"]
        if (cut.get("month") or {}).get("k") == month:
            m = [max(0, a - b) for a, b in zip(m, cut["month"]["v"])]; mf = cut["month"]["t"]
        # last 14 days, oldest first, total bytes per day
        spark = [sum(days.get((today - timedelta(days=13 - i)).isoformat(), [0, 0])) for i in range(14)]
        out.append({"id": nid(key), "name": n.get("name") or "", "tag": key.replace(":", "")[-4:].upper(),
                    "cur": key == cur, "today": t, "month": m, "todayFrom": tf, "monthFrom": mf, "total": [n["rx"], n["tx"]], "since": n["since"],
                    "seen": n["seen"], "spark": spark})
    out.sort(key=lambda x: (not x["cur"], -x["seen"]))
    return out


def main():
    lock = open(F + ".lock", "w")
    fcntl.flock(lock, fcntl.LOCK_EX)
    s = load()
    now = int(time.time())

    if sys.argv[1:2] == ["reset"]:
        for key, n in s["nets"].items():
            if nid(key) != sys.argv[2]:
                continue
            what = (sys.argv[3:4] or ["all"])[0]
            cut = n.setdefault("cut", {})
            if what in ("all", "since"):
                n["rx"] = n["tx"] = 0
                n["since"] = now
            if what in ("all", "today"):
                cut["today"] = {"k": date.today().isoformat(), "v": raw_today(n), "t": now}
            if what in ("all", "month"):
                cut["month"] = {"k": date.today().strftime("%Y-%m"), "v": raw_month(n), "t": now}
        save(s)
        print(json.dumps(summary(s, (s.get("last") or {}).get("key"))))
        return

    dev, key, ssid, ssid_t = (sys.argv[1:] + ["", "", "", "0"])[:4]
    c = counters(dev) if dev else None
    b = boot()
    last = s.get("last")
    key = key if c and re.fullmatch(r"[0-9a-f:]{11,17}", key or "") else ""

    if c:
        if last and last.get("dev") == dev and last.get("boot") == b:
            rx, tx = c[0] - last["rx"], c[1] - last["tx"]
            if rx < 0 or tx < 0:      # the interface's counters were reset
                rx, tx = c
        elif last:                    # rebooted: everything since boot is new
            rx, tx = c
        else:                         # first run ever: start counting from now
            rx = tx = 0
        if key:
            n = s["nets"].setdefault(key, {"name": "", "first": now, "since": now, "rx": 0, "tx": 0, "seen": now, "days": {}})
            n["rx"] += rx; n["tx"] += tx; n["seen"] = now
            add(n["days"].setdefault(date.today().isoformat(), [0, 0]), rx, tx)
            # the shortcut's answer only names this network if it was fetched after we joined it
            switched = last.get("since", 0) if last and last.get("key") == key else now
            if ssid and int(float(ssid_t or 0)) >= switched:
                n["name"] = ssid
            cutoff = (date.today() - timedelta(days=KEEP_DAYS)).isoformat()
            n["days"] = {d: v for d, v in n["days"].items() if d >= cutoff}
        since = last["since"] if last and last.get("key") == key and key else now
        s["last"] = {"dev": dev, "boot": b, "rx": c[0], "tx": c[1], "key": key, "since": since, "t": now}
    save(s)
    print(json.dumps(summary(s, key)))


if __name__ == "__main__":
    main()
