#!/usr/bin/env python3
"""Anime for the desktop widget, from AniList (free, no account): episodes airing in the next day (and the last few
hours), plus what's trending this season. Cached for 15 minutes in ~/.stark/.anime.json. Prints JSON."""
import json, os, subprocess, time

CACHE = os.path.expanduser("~/.stark/.anime.json")
MIN_FANS = 3000  # skip obscure shows nobody follows

Q = """query ($from: Int, $to: Int) {
  air: Page(perPage: 50) { airingSchedules(airingAt_greater: $from, airingAt_lesser: $to, sort: TIME) {
    airingAt episode media { id title { english romaji } coverImage { large color } genres averageScore popularity
      episodes isAdult siteUrl countryOfOrigin } } }
  hot: Page(perPage: 8) { media(type: ANIME, status: RELEASING, sort: TRENDING_DESC, isAdult: false) {
    id title { english romaji } coverImage { large color } genres averageScore episodes siteUrl
    nextAiringEpisode { episode airingAt } } }
}"""


def show(m):
    return {"id": m["id"], "title": m["title"]["english"] or m["title"]["romaji"], "cover": m["coverImage"]["large"],
            "color": m["coverImage"].get("color"), "genres": m.get("genres", [])[:3], "score": m.get("averageScore"),
            "eps": m.get("episodes"), "url": m["siteUrl"]}


def main():
    now = int(time.time())
    try:
        c = json.load(open(CACHE))
        if now - c["fetched"] < 15 * 60:
            print(json.dumps(c)); return
    except Exception:
        c = None
    try:
        body = json.dumps({"query": Q, "variables": {"from": now - 8 * 3600, "to": now + 30 * 3600}}).encode()
        # curl, not urllib: AniList's Cloudflare blocks Python's TLS fingerprint
        r = subprocess.run(["/usr/bin/curl", "-sf", "--max-time", "12", "https://graphql.anilist.co", "-H", "Content-Type: application/json",
                            "-H", "Accept: application/json", "--data-binary", "@-"], input=body, capture_output=True)
        d = json.loads(r.stdout)["data"]
    except Exception:
        print(json.dumps(c or {"error": True, "reason": "AniList unreachable"})); return
    air = [{**show(s["media"]), "ep": s["episode"], "at": s["airingAt"], "fans": s["media"]["popularity"]}
           for s in d["air"]["airingSchedules"]
           if not s["media"]["isAdult"] and s["media"]["popularity"] >= MIN_FANS]
    hot = [{**show(m), "next": m["nextAiringEpisode"]} for m in d["hot"]["media"]]
    out = {"fetched": now, "air": air, "hot": hot}
    json.dump(out, open(CACHE, "w"))
    print(json.dumps(out))


main()
