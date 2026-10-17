#!/usr/bin/env python3
"""Chess puzzle for the desktop widget, from Lichess (free; works without an account).
  puzzle.py          the current puzzle (today's daily puzzle the first time each day)
  puzzle.py next     a fresh random puzzle
  puzzle.py daily    back to today's daily puzzle
  puzzle.py login    connect your Lichess account (puzzle-only token, kept in the Keychain)
  puzzle.py result ID 1|0   record a solve/miss on your Lichess puzzle rating
Connected, puzzles are matched to your rating and never repeat, and results count on Lichess.
Prints JSON with every position along the solution and the legal moves on each of your turns, so the widget
needs no chess engine. Also downloads the piece images into the widgets folder (shared with Lichess TV)."""
import json, os, subprocess, sys, time, urllib.request
from datetime import date

import chess  # python-chess (pip3 install --user chess)

CUR = os.path.expanduser("~/.stark/.chess.json")
PIECES = os.path.expanduser("~/Library/Application Support/Übersicht/widgets/chess")
UA = {"User-Agent": "desktop-dashboard (Übersicht widget)", "Accept": "application/json"}


KEY = "desktop-widget-lichess"
TOKEN_PAGE = ("https://lichess.org/account/oauth/token/create?scopes[]=puzzle:read&scopes[]=puzzle:write"
              "&description=Desktop%20dashboard%20puzzles")


def token():
    r = subprocess.run(["security", "find-generic-password", "-s", KEY, "-w"], capture_output=True, text=True)
    return r.stdout.strip() or None


def get(url, tok=None, body=None):
    h = {**UA, **({"Authorization": "Bearer " + tok} if tok else {}), **({"Content-Type": "application/json"} if body else {})}
    req = urllib.request.Request(url, json.dumps(body).encode() if body else None, h)
    return json.load(urllib.request.urlopen(req, timeout=10))


def me(tok, cur, fresh=False):
    """Your Lichess name and puzzle rating (refreshed every 10 min)."""
    m = (cur or {}).get("me")
    if not fresh and m and time.time() - m.get("t", 0) < 600: return m
    a = get("https://lichess.org/api/account", tok)
    p = a.get("perfs", {}).get("puzzle", {})
    return {"name": a["username"], "rating": p.get("rating"), "games": p.get("games", 0), "prov": p.get("prov", False), "t": int(time.time())}


def dialog(text, answer=False):
    script = f'display dialog {json.dumps(text)} with title "Lichess" ' + (
        'default answer "" with hidden answer buttons {"Cancel", "Connect"} default button "Connect"' if answer else 'buttons {"OK"} default button "OK"')
    r = subprocess.run(["osascript", "-e", script, "-e", "text returned of result" if answer else "true"], capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else None


def login():
    subprocess.run(["open", TOKEN_PAGE])
    tok = dialog("Lichess just opened in your browser.\n\n1. Click Create (the token can only play puzzles).\n"
                 "2. Copy the token and paste it here.", answer=True)
    if not tok: return
    try:
        a = get("https://lichess.org/api/account", tok.strip())
    except Exception:
        dialog("That token didn't work. Click the Lichess button in the puzzle panel to try again."); return
    subprocess.run(["security", "add-generic-password", "-U", "-s", KEY, "-a", a["username"], "-w", tok.strip()], capture_output=True)
    dialog(f"Connected as {a['username']}. Your puzzles now count on Lichess.")


def result(pid, win):
    tok, cur = token(), json.load(open(CUR))
    r = get("https://lichess.org/api/puzzle/batch/mix?nb=0", tok, {"solutions": [{"id": pid, "win": win, "rated": True}]})
    diff = next((x.get("ratingDiff") for x in r.get("rounds", []) if x.get("id") == pid), None)
    cur["me"] = me(tok, cur, fresh=True)
    rating = (r.get("glicko") or {}).get("rating")
    if rating: cur["me"]["rating"] = round(rating)
    if cur.get("id") == pid: cur["result"] = {"win": win, "diff": diff}
    json.dump(cur, open(CUR, "w"))
    print(json.dumps(cur))


def pieces():
    os.makedirs(PIECES, exist_ok=True)
    for c in "wb":
        for p in "KQRBNP":
            f = f"{PIECES}/{c}{p}.svg"
            if not os.path.exists(f):
                req = urllib.request.Request(f"https://lichess1.org/assets/piece/cburnett/{c}{p}.svg", headers=UA)
                open(f, "wb").write(urllib.request.urlopen(req, timeout=10).read())


def build(raw, daily):
    p, g = raw["puzzle"], raw["game"]
    if not p.get("fen"):  # some endpoints only carry the game: play it up to the puzzle
        b = chess.Board()
        for san in g["pgn"].split(): b.push_san(san)
        p["fen"], p["lastMove"] = b.fen(), b.peek().uci()
    board = chess.Board(p["fen"])
    fens, legal, mates = [board.fen()], [], []
    for i, uci in enumerate(p["solution"]):
        if i % 2 == 0:  # your turn: legal moves by origin square
            moves = {}
            for m in board.legal_moves:
                moves.setdefault(chess.square_name(m.from_square), []).append(chess.square_name(m.to_square))
            legal.append(moves)
            if i == len(p["solution"]) - 1:  # like Lichess, any mate on the last move counts
                for m in board.legal_moves:
                    board.push(m)
                    if board.is_checkmate(): mates.append(m.uci())
                    board.pop()
        board.push_uci(uci)
        fens.append(board.fen())
    names = {pl["color"]: f'{pl["name"]} ({pl["rating"]})' for pl in g.get("players", [])}
    return {"id": p["id"], "rating": p["rating"], "plays": p.get("plays", 0), "themes": p.get("themes", []),
            "color": fens[0].split()[1], "last": p.get("lastMove", ""), "sol": p["solution"], "fens": fens,
            "legal": legal, "mates": mates, "daily": daily, "day": date.today().isoformat(),
            "game": g.get("perf", {}).get("name", ""), "players": names, "url": f'https://lichess.org/training/{p["id"]}'}


def main():
    arg = sys.argv[1] if len(sys.argv) > 1 else ""
    if arg == "login": login(); arg = ""
    if arg == "result":
        try: result(sys.argv[2], sys.argv[3] == "1")
        except Exception: print(json.dumps({"error": True, "reason": "Couldn't save to Lichess"}))
        return
    tok = token()
    try:
        pieces()
    except Exception:
        pass  # images are retried next run; the board still draws
    cur = None
    try: cur = json.load(open(CUR))
    except Exception: pass
    # a new day brings a new daily puzzle, unless you're mid-way through a random one
    if arg or not cur or (cur.get("daily") and cur.get("day") != date.today().isoformat()):
        try:
            daily = arg != "next"
            cur = build(get("https://lichess.org/api/puzzle/daily" if daily else "https://lichess.org/api/puzzle/next", tok), daily)
            cur["fetched"] = int(time.time())
            json.dump(cur, open(CUR, "w"))
        except Exception as e:
            if not cur:
                print(json.dumps({"error": True, "reason": "Lichess unreachable"})); return
    if tok:
        try: cur["me"] = me(tok, cur)
        except Exception: pass  # keep the last known rating
        json.dump(cur, open(CUR, "w"))
    else:
        cur.pop("me", None)
    print(json.dumps(cur))


main()
