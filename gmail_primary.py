#!/usr/bin/env python3
"""Reads the Mail.app JSON from mail.sh on stdin and adds Gmail's real *Primary* unread emails.

Gmail's tabs (Primary / Promotions / Social / Updates) only exist on Google's side, so this asks
Gmail directly over IMAP with an app password kept in the Keychain (service "desktop-widget-gmail").
Without that password it passes the Mail.app JSON through unchanged.
"""
import email.header, email.utils, imaplib, json, os, re, subprocess, sys

SERVICE = "desktop-widget-gmail"  # Keychain item: account = Gmail address, password = app password

def dec(v):
    return str(email.header.make_header(email.header.decode_header(v or ""))).strip()

data = json.loads(sys.stdin.read() or '{"running":false,"mail":[]}')
data["mail_app"] = data.get("running", False)  # Mail.app open → iCloud is being read and synced
try:  # last successful Mail.app sync, written by mail-sync.sh
    data["icloud_synced"] = int(open(os.path.expanduser("~/.stark/.mail-sync-last")).read())
except (OSError, ValueError):
    pass
def keychain(*args):
    return subprocess.run(["security", "find-generic-password", "-s", SERVICE, *args],
                          capture_output=True, text=True).stdout

pw = keychain("-w").strip()
USER = re.search(r'"acct"<blob>="([^"]+)"', keychain()) if pw else None
if pw and USER:
    USER = USER.group(1)
    try:
        im = imaplib.IMAP4_SSL("imap.gmail.com", timeout=10)
        im.login(USER, pw)
        im.select("INBOX", readonly=True)
        ids = im.search(None, "X-GM-RAW", '"category:primary is:unread"')[1][0].split()
        mail = []
        for i in reversed(ids[-6:]):
            raw = im.fetch(i, "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE MESSAGE-ID)])")[1][0][1]
            h = email.message_from_bytes(raw)
            d = email.utils.parsedate_to_datetime(h["Date"]).astimezone()
            mail.append({"acc": "Gmail", "from": dec(h["From"]), "subj": dec(h["Subject"]), "read": False,
                         "d": d.isoformat(), "id": (h["Message-ID"] or "").strip().strip("<>")})
        im.logout()
        data["mail"] = [m for m in data.get("mail", []) if m["acc"] != "Google"] + mail
        data["accounts"] = ["Gmail"] + [a for a in data.get("accounts", []) if a != "Google"]
        counts = {k: v for k, v in data.get("counts", {}).items() if k != "Google"}
        data["unread"] = sum(counts.values()) + len(ids)
        data["counts"] = {"Gmail": len(ids), **counts}
        data["running"] = True
    except Exception as e:  # keep the Gmail tab, flagged, instead of silently dropping it
        data["gmail_error"] = str(e)[:120]
        data["mail"] = [m for m in data.get("mail", []) if m["acc"] != "Google"]
        data["accounts"] = ["Gmail"] + [a for a in data.get("accounts", []) if a != "Google"]
        data["counts"] = {"Gmail": 0, **{k: v for k, v in data.get("counts", {}).items() if k != "Google"}}
        data["running"] = True
print(json.dumps(data))
