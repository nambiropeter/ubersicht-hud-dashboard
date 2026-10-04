#!/usr/bin/env python3
"""Reads the Mail.app JSON from mail.sh on stdin and adds mail read straight from the servers over IMAP,
so the widget works even when the Mail app is closed.

  Gmail  - Gmail's real *Primary* tab (category:primary), Keychain service "desktop-widget-gmail"
  iCloud - every unread inbox email, as is (no filtering), Keychain service "desktop-widget-icloud"

Each Keychain item holds account = login, password = app password. Accounts without one keep coming
from Mail.app via mail.sh (which skips the ones handled here).
"""
import email.header, email.utils, imaplib, json, os, re, subprocess, sys

# (tab name, Keychain service, IMAP server, name of the same account in Mail.app)
ACCOUNTS = [("Gmail", "desktop-widget-gmail", "imap.gmail.com", "Google"),
            ("iCloud", "desktop-widget-icloud", "imap.mail.me.com", "iCloud")]
SHOW = 6  # emails listed per account

def dec(v):
    return str(email.header.make_header(email.header.decode_header(v or ""))).strip()

def keychain(service, *args):
    return subprocess.run(["security", "find-generic-password", "-s", service, *args], capture_output=True, text=True).stdout

def entry(name, h):
    d = email.utils.parsedate_to_datetime(h["Date"]).astimezone()
    return {"acc": name, "from": dec(h["From"]), "subj": dec(h["Subject"]), "read": False,
            "d": d.isoformat(), "id": (h["Message-ID"] or "").strip().strip("<>")}

def fetch_gmail(im):
    ids = im.search(None, "X-GM-RAW", '"category:primary is:unread"')[1][0].split()
    mail = [entry("Gmail", email.message_from_bytes(
        im.fetch(i, "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE MESSAGE-ID)])")[1][0][1])) for i in reversed(ids[-SHOW:])]
    return len(ids), mail, 0

def fetch_all(im, name):  # iCloud: every unread inbox email, unfiltered
    ids = im.search(None, "UNSEEN")[1][0].split()
    mail = [entry(name, email.message_from_bytes(
        im.fetch(i, "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE MESSAGE-ID)])")[1][0][1])) for i in reversed(ids[-SHOW:])]
    return len(ids), mail, 0

data = json.loads(sys.stdin.read() or '{"running":false,"mail":[]}')
data["mail_app"] = data.get("running", False)  # Mail.app open → accounts not handled here are read from it
try:  # last successful Mail.app sync, written by mail-sync.sh
    data["icloud_synced"] = int(open(os.path.expanduser("~/.stark/.mail-sync-last")).read())
except (OSError, ValueError):
    pass
data.setdefault("accounts", []); data.setdefault("counts", {}); data.setdefault("mail", [])
data["direct"], data["errors"] = [], {}
for name, service, host, app_name in ACCOUNTS:
    pw = keychain(service, "-w").strip()
    user = re.search(r'"acct"<blob>="([^"]+)"', keychain(service)) if pw else None
    if not (pw and user): continue
    # replace whatever Mail.app reported for this account
    data["mail"] = [m for m in data["mail"] if m["acc"] not in (name, app_name)]
    data["accounts"] = [a for a in data["accounts"] if a not in (name, app_name)]
    data["counts"].pop(app_name, None)
    try:
        im = imaplib.IMAP4_SSL(host, timeout=10)
        im.login(user.group(1), pw)
        im.select("INBOX", readonly=True)
        n, mail, hidden = fetch_gmail(im) if name == "Gmail" else fetch_all(im, name)
        im.logout()
        data["mail"] += mail; data["counts"][name] = n; data["hidden"] = data.get("hidden", 0) + hidden
    except Exception as e:  # keep the tab, flagged, instead of silently dropping it
        data["errors"][name] = str(e)[:120]; data["counts"][name] = 0
        if name == "Gmail": data["gmail_error"] = data["errors"][name]
    data["direct"].append(name); data["running"] = True
data["accounts"] = [a for a, *_ in ACCOUNTS if a in data["direct"]] + data["accounts"]
data["unread"] = sum(data["counts"].values())
print(json.dumps(data))
