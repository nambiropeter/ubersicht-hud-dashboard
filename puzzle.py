#!/usr/bin/env python3
"""Chess puzzle for the desktop widget, from Lichess (free, no account).
  puzzle.py          the current puzzle (today's daily puzzle the first time each day)
  puzzle.py next     a fresh random puzzle
  puzzle.py daily    back to today's daily puzzle
Prints JSON with every position along the solution and the legal moves on each of your turns, so the widget
needs no chess engine. Also downloads the piece images into the widgets folder (shared with Lichess TV)."""
import json, os, sys, time, urllib.request
from datetime import date

import chess  # python-chess (pip3 install --user chess)

CUR = os.path.expanduser("~/.stark/.chess.json")
PIECES = os.path.expanduser("~/Library/Application Support/Übersicht/widgets/chess")
UA = {"User-Agent": "desktop-dashboard (Übersicht widget)", "Accept": "application/json"}


def get(url):
    return json.load(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=10))


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
            cur = build(get("https://lichess.org/api/puzzle/daily" if daily else "https://lichess.org/api/puzzle/next"), daily)
            cur["fetched"] = int(time.time())
            json.dump(cur, open(CUR, "w"))
        except Exception as e:
            if not cur:
                print(json.dumps({"error": True, "reason": "Lichess unreachable"})); return
    print(json.dumps(cur))


main()
