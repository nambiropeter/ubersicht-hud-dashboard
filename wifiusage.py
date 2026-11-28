#!/usr/bin/env python3
"""Data used per network (Wi-Fi, Ethernet or iPhone USB), for the Connections panel's DATA view.

network.sh calls this on every refresh (every 30 s):
    wifiusage.py <wifi-dev> <router-mac> <ssid> <ssid-mtime> <default-route-dev>
It reads every physical interface's byte counters (Wi-Fi, Ethernet, USB tethering), adds what moved since the
last call to the network that interface is on now, and prints JSON. A network is keyed by its router's MAC address (macOS hides the Wi-Fi name from
scripts; the name comes from the "Wi-Fi Name" shortcut and is attached once it's known).
    wifiusage.py reset <id> [all|today|month|since]    zero that network's count (e.g. a new data bundle);
        today/month subtract what was used so far, so the 14-day bars keep the real history

Data lives in ~/.stark/.wifi-usage.json (git-ignored: it holds your network names).
Counts everything over each interface (VPN/Tor included); a wired network is named Ethernet / iPhone USB
(an iPhone over USB shares its hotspot's router, so it adds to the same entry); stops counting while the widget isn't running and gives
anything used while it was stopped to whichever network you're on when it next runs.
"""
import fcntl, hashlib, json, os, re, subprocess, sys, time
from datetime import date, datetime, timedelta

D = os.path.expanduser("~/.stark")
F = f"{D}/.wifi-usage.json"
KEEP_DAYS = 100


PORTS = {}  # device -> hardware port name ("Wi-Fi", "iPhone USB", "USB 10/100/1000 LAN", ...)


def ports():
    out = subprocess.run(["networksetup", "-listallhardwareports"], capture_output=True, text=True).stdout
    for name, dev in re.findall(r"Hardware Port: (.+)\nDevice: (\S+)", out):
        if not dev.startswith("bridge"):
            PORTS[dev] = name
    return PORTS


def counters_all():
    """Byte counters of every physical interface (Wi-Fi, Ethernet, USB/iPhone tethering)."""
    ports()
    got = {}
    for line in subprocess.run(["netstat", "-ib"], capture_output=True, text=True).stdout.splitlines()[1:]:
        p = line.split()
        if len(p) >= 10 and p[0] in PORTS and p[2].startswith("<Link") and p[0] not in got:
            got[p[0]] = (int(p[6]), int(p[9]))
    return got


def routed():
    """device -> its router's MAC, for each interface with a real IPv4 address (a network you're on)."""
    out, dev, up = subprocess.run(["ifconfig"], capture_output=True, text=True).stdout, None, []
    for line in out.splitlines():
        m = re.match(r"^(\S+?):", line)
        if m:
            dev = m.group(1)
        elif dev in PORTS and (a := re.match(r"\s+inet (\d+\.\d+\.\d+\.\d+)", line)) and not a.group(1).startswith("169.254."):
            up.append(dev)
    keys = {}
    for dev in dict.fromkeys(up):
        gw = subprocess.run(["ipconfig", "getoption", dev, "router"], capture_output=True, text=True).stdout.strip()
        if not re.fullmatch(r"[\d.]+", gw):
            continue
        m = re.search(r" at ([0-9a-f:]{11,17}) on " + re.escape(dev) + r"\b",
                      subprocess.run(["arp", "-n", gw], capture_output=True, text=True).stdout)
        if m:
            keys[dev] = m.group(1)
    return keys


def wired_name(port):
    return "iPhone USB" if "iPhone" in port else "Ethernet" if port and port != "Wi-Fi" else ""


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

    wdev, wkey, ssid, ssid_t, primary = (sys.argv[1:] + ["", "", "", "0", ""])[:5]
    b = boot()
    last = s.get("last") or {}
    if last and "devs" not in last and last.get("dev"):      # old format: one Wi-Fi baseline
        last = {"boot": last.get("boot"), "key": last.get("key"), "old": True,
                "devs": {last["dev"]: {k: last.get(k) for k in ("rx", "tx", "key", "since")}}}
    same = bool(last) and last.get("boot") == b
    base = last.get("devs", {}) if same else {}
    cnt, links = counters_all(), routed()
    devs, on = dict(base), {}
    for dev, c in cnt.items():
        key = links.get(dev, "")
        if dev == wdev and wkey and re.fullmatch(r"[0-9a-f:]{11,17}", wkey):
            key = wkey
        p = base.get(dev)
        if p:
            rx, tx = c[0] - p["rx"], c[1] - p["tx"]
            if rx < 0 or tx < 0:      # the interface's counters were reset
                rx, tx = c
        elif last and (not same or not last.get("old")):  # rebooted, or an interface that just came up
            rx, tx = c
        else:                         # first run (or first run of this version): start counting from now
            rx = tx = 0
        since = p["since"] if p and p.get("key") == key and key else now
        devs[dev] = {"rx": c[0], "tx": c[1], "key": key, "since": since}
        if not key:
            continue
        n = s["nets"].setdefault(key, {"name": "", "first": now, "since": now, "rx": 0, "tx": 0, "seen": now, "days": {}})
        n["rx"] += rx; n["tx"] += tx; n["seen"] = now
        add(n["days"].setdefault(date.today().isoformat(), [0, 0]), rx, tx)
        if dev == wdev:
            # the shortcut's answer only names this network if it was fetched after we joined it
            if ssid and int(float(ssid_t or 0)) >= since:
                n["name"] = ssid
        elif not n.get("name"):
            n["name"] = wired_name(PORTS.get(dev, ""))
        cutoff = (date.today() - timedelta(days=KEEP_DAYS)).isoformat()
        n["days"] = {d: v for d, v in n["days"].items() if d >= cutoff}
        on[dev] = key
    # the network you're on = the one carrying the default route (a VPN tunnel's falls back to Wi-Fi, then any)
    cur = on.get(primary) or on.get(wdev) or next(iter(on.values()), "")
    s["last"] = {"boot": b, "t": now, "key": cur, "devs": devs}
    key = cur
    save(s)
    print(json.dumps(summary(s, key)))


if __name__ == "__main__":
    main()
