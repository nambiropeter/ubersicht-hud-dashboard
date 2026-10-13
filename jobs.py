#!/usr/bin/env python3
"""Job hunt summary for the desktop widget, read from the Job Tracker app's local data
(~/Library/Application Support/JobTracker/applications.json). Prints JSON; never writes anything."""
import json, os, sys
from datetime import date, datetime

DATA = os.path.expanduser("~/Library/Application Support/JobTracker/applications.json")
FOLLOW_UP_DAYS = 14  # same as the app
UPCOMING_DAYS = 30
GHOST_DAYS = {"applied": 60, "interview": 60}  # same as the app: no reply this long = rejected


def day(s):
    try:
        return date.fromisoformat((s or "")[:10])
    except ValueError:
        return None


def main():
    if not os.path.exists(DATA):
        print(json.dumps({"apps": 0, "counts": {}, "events": [], "followups": [], "active": []}))
        return
    try:
        apps = json.load(open(DATA))
    except Exception as e:
        print(json.dumps({"error": True, "reason": "Job Tracker data unreadable"}))
        return
    today = date.today()
    counts, ghosted = {}, 0
    events, followups, active = [], [], []
    for a in apps:
        st = a.get("status", "applied")
        nd, since = day(a.get("nextDate")), day(a.get("updated")) or day(a.get("date"))
        # the app moves these on its next launch; count them that way already
        if st in GHOST_DAYS and since and (today - since).days >= GHOST_DAYS[st] and not (nd and nd >= today):
            st = "rejected"
        ghosted += st == "rejected" and (a.get("ghosted") or a.get("status") != "rejected")
        counts[st] = counts.get(st, 0) + 1
        card = {"id": a.get("id"), "company": a.get("company", ""), "role": a.get("role", ""), "status": st}
        if nd and st != "rejected" and (nd - today).days <= UPCOMING_DAYS:
            events.append({**card, "next": a.get("next") or "Next step", "date": nd.isoformat(), "left": (nd - today).days})
        if st == "applied" and since and (today - since).days >= FOLLOW_UP_DAYS:
            followups.append({**card, "days": (today - since).days})
        if st in ("applied", "interview", "offer"):
            active.append({**card, "days": (today - since).days if since else None})
    events.sort(key=lambda e: e["date"])
    followups.sort(key=lambda f: -f["days"])
    rank = {"offer": 0, "interview": 1, "applied": 2}
    active.sort(key=lambda x: (rank[x["status"]], x["days"] if x["days"] is not None else 999))
    sent = len(apps) - counts.get("wishlist", 0)
    heard = sum(counts.get(k, 0) for k in ("interview", "offer", "rejected")) - ghosted  # silence isn't a reply
    print(json.dumps({"apps": len(apps), "counts": counts, "sent": sent, "rate": round(100 * heard / sent) if sent else 0,
                      "events": events, "followups": followups, "active": active}))


if __name__ == "__main__":
    main()
