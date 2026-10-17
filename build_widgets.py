"""Builds the Übersicht desktop dashboard from one shared layout grid.
Run: python3 ~/.stark/build_widgets.py   (then Übersicht reloads automatically)"""
import json, os, re, shutil, time, urllib.parse

BUILD = str(int(time.time()))  # Übersicht hot-reloads code onto the same DOM: each build replaces the previous one's handlers

_S = os.path.expanduser("~/.stark")
if not os.path.exists(f"{_S}/wifi") or os.path.getmtime(f"{_S}/wifi.swift") > os.path.getmtime(f"{_S}/wifi"):
    os.system(f"swiftc -O {_S}/wifi.swift -o {_S}/wifi")
if not os.path.exists(f"{_S}/hudcursor") or os.path.getmtime(f"{_S}/hudcursor.swift") > os.path.getmtime(f"{_S}/hudcursor"):
    os.system(f"swiftc -O {_S}/hudcursor.swift -o {_S}/hudcursor")
W = os.path.expanduser("~/Library/Application Support/Übersicht/widgets")
# Übersicht runs widgets with a minimal PATH, so bake in the absolute python3 path at build time
PY = shutil.which("python3") or "/usr/bin/python3"

# ── Layout grid (screen 1470×956 pt): 32 | 400 | 20 | 566 | 20 | 400 | 32 ──
L, C, R = 32, 452, 1038
DY = -36  # Übersicht's canvas starts below the menu bar
POS = {
    "clock":   (L, 56, 400, 230),  "puzzle":  (C, 56, 566, 428),   "batcave":     (R, 56, 400, 276),
    "weather": (L, 306, 400, 320), "anime":   (C, 504, 566, 428),  "chesstv":     (R, 352, 400, 330),
    "system":  (L, 646, 400, 286),                                 "connections": (R, 702, 400, 230),
}

SHARED = """
  font: 500 12.5px -apple-system, "SF Pro Text", sans-serif; color: #f2ede6; -webkit-font-smoothing: antialiased;
  -webkit-user-select: none; user-select: none; cursor: default; box-sizing: content-box;
  background:
    radial-gradient(280px circle at var(--mx, -999px) var(--my, -999px), rgba(255,236,210,.075), transparent 70%),
    linear-gradient(180deg, rgba(255,255,255,.05), rgba(255,255,255,0) 38%),
    rgba(17,14,12,.72);
  backdrop-filter: blur(40px) saturate(150%) brightness(.7); -webkit-backdrop-filter: blur(40px) saturate(150%) brightness(.7);
  border: 1px solid rgba(255,255,255,.075); border-radius: 22px;
  box-shadow: inset 0 1px 0 rgba(255,255,255,.10), 0 24px 60px rgba(0,0,0,.45);
  overflow: hidden; transition: border-color .3s, box-shadow .3s, transform .3s;
  &:hover { border-color: rgba(255,255,255,.13) }
  &.dragging { transform: scale(1.012); box-shadow: inset 0 1px 0 rgba(255,255,255,.14), 0 34px 80px rgba(0,0,0,.6) }
  &.dragging header { cursor: grabbing }
  &::before { content:""; position:absolute; top:0; left:28px; right:28px; height:1px; pointer-events:none;
              background: linear-gradient(90deg, transparent, rgba(245,177,76,.6), transparent) }
  * { box-sizing: border-box }
  header { display:flex; align-items:center; gap:9px; height:46px; padding:0 20px; cursor: grab }
  h1 { margin:0; white-space:nowrap; font: 600 9.5px Orbitron, -apple-system, sans-serif; letter-spacing:.32em; color: rgba(242,237,230,.66) }
  .sub { margin-left:auto; min-width:0; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;
         font: 500 10.5px -apple-system, sans-serif; letter-spacing:.04em; color: rgba(242,237,230,.38) }
  .sub b { color:#f5b14c; font-weight:600 }
  .up { color:#4fd18b } .dn { color:#ff6b6b } .muted { color:#9b938a } .dim { color:#6b645d }
  .num { font-variant-numeric: tabular-nums; letter-spacing:-.01em }
  .lbl { font: 600 8.5px Orbitron, -apple-system, sans-serif; letter-spacing:.24em; color:#857d75 }
  .syncwarn { position:absolute; top:11px; right:14px; z-index:5; display:none; align-items:center; gap:6px; max-width:210px;
              height:24px; padding:0 9px; border-radius:7px; background:rgba(58,20,18,.94); border:1px solid rgba(255,107,107,.5);
              font: 600 10px -apple-system, sans-serif; letter-spacing:.03em; color:#ffc2b8; white-space:nowrap; overflow:hidden; text-overflow:ellipsis }
  .syncwarn.on { display:flex }
"""

AGO = """const ago = d => {
  const m = Math.round((Date.now() - new Date(d)) / 60000);
  return isNaN(m) ? "" : m < 60 ? `${m}m` : m < 1440 ? `${Math.round(m / 60)}h` : `${Math.round(m / 1440)}d`;
};"""

SPARK = """// Price chart: smooth line split green/red at the previous close (the hairline baseline), soft wash to the
// baseline, ringed end dot. With `axis`: day dividers + labels, right-hand price ticks, hover crosshair + tooltip.
// ids must be unique across ALL panels (they share one page), so prefix them per widget load
let _sid = 0; const _pfx = "s" + Math.random().toString(36).slice(2, 7);
const UP = "#4ade80", DN = "#f87171", SURF = "#16120f";
const smooth = P => {  // monotone cubic (Fritsch–Carlson): smooth, never overshoots the real highs/lows
  const n = P.length; if (n < 3) return "M" + P.map(p => p.join(" ")).join("L");
  const m = [], t = [];
  for (let i = 0; i < n - 1; i++) m[i] = (P[i + 1][1] - P[i][1]) / (P[i + 1][0] - P[i][0]);
  t[0] = m[0]; t[n - 1] = m[n - 2];
  for (let i = 1; i < n - 1; i++) t[i] = m[i - 1] * m[i] <= 0 ? 0 : (m[i - 1] + m[i]) / 2;
  for (let i = 0; i < n - 1; i++) {
    if (!m[i]) { t[i] = t[i + 1] = 0; continue; }
    const a = t[i] / m[i], b = t[i + 1] / m[i], q = a * a + b * b;
    if (q > 9) { const k = 3 / Math.sqrt(q); t[i] = k * a * m[i]; t[i + 1] = k * b * m[i]; }
  }
  let d = `M${P[0][0].toFixed(1)} ${P[0][1].toFixed(1)}`;
  for (let i = 0; i < n - 1; i++) {
    const h = (P[i + 1][0] - P[i][0]) / 3;
    d += `C${(P[i][0] + h).toFixed(1)} ${(P[i][1] + t[i] * h).toFixed(1)} ${(P[i + 1][0] - h).toFixed(1)} ${(P[i + 1][1] - t[i + 1] * h).toFixed(1)} ${P[i + 1][0].toFixed(1)} ${P[i + 1][1].toFixed(1)}`;
  }
  return d;
};
const niceTicks = (lo, hi, n = 3) => {
  const raw = (hi - lo) / n, mag = Math.pow(10, Math.floor(Math.log10(raw)));
  const step = [1, 2, 2.5, 5, 10].map(k => k * mag).find(k => k >= raw);
  const out = []; for (let v = Math.ceil(lo / step) * step; v <= hi; v += step) out.push(v);
  return out;
};
const tickFmt = v => v >= 1000 ? Math.round(v).toLocaleString("en-US") : v.toFixed(v >= 100 ? 0 : 2);
const etDay = t => new Date(t * 1000).toLocaleDateString("en-US", { timeZone: "America/New_York", weekday: "short" });
const etTime = t => new Date(t * 1000).toLocaleString("en-US", { timeZone: "America/New_York", weekday: "short", hour: "numeric", minute: "2-digit" });
// `daily` = one point per trading day (NSE portfolio): month labels and dated tooltips instead of ET weekdays/times
const dayLab = (t, daily) => daily ? new Date(t * 1000).toLocaleDateString("en-GB", { month: "short" }) : etDay(t);
const Spark = ({ d, w, h, up, base, ts, axis = false, fill = true, sw = 1.6, fillOp = .26, draw = false, daily = false }) => {
  if (!d || d.length < 2) return <svg width={w} height={h} />;
  const id = _pfx + (++_sid), padR = axis ? 46 : 5, padB = axis ? 18 : 0, cw = w - padR, ch = h - padB;
  const ref = base != null ? base : d[0];
  let mn = Math.min(...d, ref), mx = Math.max(...d, ref); const pad = (mx - mn || 1) * 0.1; mn -= pad; mx += pad;
  const X = i => 2 + (i / (d.length - 1)) * (cw - 4), Y = v => 3 + (1 - (v - mn) / (mx - mn)) * (ch - 6);
  const P = d.map((v, i) => [X(i), Y(v)]), line = smooth(P), by = Y(ref), last = P[P.length - 1];
  const endCol = d[d.length - 1] >= ref ? UP : DN;
  // live price tag on the right axis; tick labels it would cover are dropped
  const tagY = Math.max(9, Math.min(ch - 9, last[1])), near = y => axis && Math.abs(y - tagY) < 13;
  const tagTxt = d[d.length - 1] >= 1000 ? tickFmt(d[d.length - 1]) : d[d.length - 1].toFixed(2);
  const area = `${line}L${last[0].toFixed(1)} ${by.toFixed(1)}L${P[0][0].toFixed(1)} ${by.toFixed(1)}Z`;
  // day dividers (hourly data spans several sessions)
  const days = [];
  if (axis && ts) ts.forEach((t, i) => { if (!i || dayLab(t, daily) !== dayLab(ts[i - 1], daily)) days.push(i); });
  const move = e => {
    const svg = e.currentTarget.ownerSVGElement, r = svg.getBoundingClientRect();
    const i = Math.max(0, Math.min(d.length - 1, Math.round(((e.clientX - r.left - 2) / (cw - 4)) * (d.length - 1))));
    const g = svg.querySelector(".xh"), [x, y] = P[i], ch_ = (d[i] - ref) / ref * 100;
    g.style.opacity = 1;
    g.querySelector("line").setAttribute("x1", x); g.querySelector("line").setAttribute("x2", x);
    const dot = g.querySelector("circle"); dot.setAttribute("cx", x); dot.setAttribute("cy", y); dot.setAttribute("fill", d[i] >= ref ? UP : DN);
    const v = g.querySelector(".tv"), s = g.querySelector(".ts"), bx = g.querySelector("rect");
    v.textContent = tickFmt(d[i]) === String(d[i]) ? String(d[i]) : d[i].toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    s.textContent = (ch_ >= 0 ? "+" : "") + ch_.toFixed(2) + (daily ? "% vs start" : "% vs prev close") + (ts ? " · " + (daily
      ? new Date(ts[i] * 1000).toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short" }) : etTime(ts[i]) + " ET") : "");
    const tw = Math.max(v.getComputedTextLength(), s.getComputedTextLength()) + 20, tx = Math.min(Math.max(x - tw / 2, 0), cw - tw);
    bx.setAttribute("x", tx); bx.setAttribute("width", tw); v.setAttribute("x", tx + 10); s.setAttribute("x", tx + 10);
  };
  const leave = e => { e.currentTarget.ownerSVGElement.querySelector(".xh").style.opacity = 0; };
  return (
    <svg width={w} height={h} style={{ display: "block", overflow: "visible" }}>
      <defs>
        <clipPath id={id + "a"}><rect x="-10" y="-10" width={w + 20} height={by + 10} /></clipPath>
        <clipPath id={id + "b"}><rect x="-10" y={by} width={w + 20} height={h + 10} /></clipPath>
        <linearGradient id={id + "u"} gradientUnits="userSpaceOnUse" x1="0" y1={Y(mx)} x2="0" y2={by}>
          <stop offset="0" stopColor={UP} stopOpacity={fillOp} /><stop offset="1" stopColor={UP} stopOpacity=".02" /></linearGradient>
        <linearGradient id={id + "d"} gradientUnits="userSpaceOnUse" x1="0" y1={by} x2="0" y2={Y(mn)}>
          <stop offset="0" stopColor={DN} stopOpacity=".02" /><stop offset="1" stopColor={DN} stopOpacity={fillOp} /></linearGradient>
      </defs>
      {axis && niceTicks(mn, mx).map(v => <g key={v}>
        <line x1="0" x2={cw} y1={Y(v)} y2={Y(v)} stroke="rgba(255,255,255,.05)" />
        {!near(Y(v)) && !(axis && Math.abs(Y(v) - by) < 12) && <text x={w} y={Y(v) + 3.5} textAnchor="end" fill="#6f665f" fontSize="10" className="num">{tickFmt(v)}</text>}</g>)}
      {days.map((i, k) => <g key={i}>
        {k > 0 && <line x1={X(i) - 2} x2={X(i) - 2} y1="0" y2={ch} stroke="rgba(255,255,255,.06)" />}
        <text x={(X(i) + (k + 1 < days.length ? X(days[k + 1]) : cw)) / 2} y={h - 3} textAnchor="middle" fill="#6f665f" fontSize="9.5" letterSpacing=".12em">{dayLab(ts[i], daily).toUpperCase()}</text></g>)}
      {fill && <path d={area} fill={`url(#${id}u)`} clipPath={`url(#${id}a)`} />}
      {fill && <path d={area} fill={`url(#${id}d)`} clipPath={`url(#${id}b)`} />}
      <line x1="0" x2={cw} y1={by} y2={by} stroke="rgba(255,255,255,.2)" strokeWidth="1" />
      {axis && !near(by) && <text x={w} y={by + 3.5} textAnchor="end" fill="#a39a92" fontSize="10" fontWeight="600" className="num">{tickFmt(ref)}</text>}
      <path d={line} fill="none" stroke={UP} strokeWidth={sw} strokeLinejoin="round" strokeLinecap="round" clipPath={`url(#${id}a)`} pathLength={draw ? 1 : undefined} className={draw ? "draw" : undefined} />
      <path d={line} fill="none" stroke={DN} strokeWidth={sw} strokeLinejoin="round" strokeLinecap="round" clipPath={`url(#${id}b)`} pathLength={draw ? 1 : undefined} className={draw ? "draw" : undefined} />
      {axis && <circle cx={last[0]} cy={last[1]} r="9" fill={endCol} opacity=".35" className="pulse" />}
      {axis && <line x1={last[0]} x2={cw + 3} y1={last[1]} y2={tagY} stroke={endCol} strokeOpacity=".45" strokeDasharray="2 3" />}
      {axis && <g><rect x={cw + 3} y={tagY - 8.5} width={padR - 3} height="17" rx="4.5" fill={endCol} />
        <text x={w - 4} y={tagY + 3.5} textAnchor="end" fill={SURF} fontSize="10" fontWeight="700" className="num">{tagTxt}</text></g>}
      {axis ? <circle cx={last[0]} cy={last[1]} r="4" fill={endCol} stroke={SURF} strokeOpacity=".6" strokeWidth="2" />
        : <circle cx={last[0]} cy={last[1]} r="2.4" fill={endCol} style={{ filter: `drop-shadow(0 0 3px ${endCol})` }} />}
      {axis && <g className="xh" style={{ opacity: 0, pointerEvents: "none", transition: "opacity .15s" }}>
        <line y1="0" y2={ch} stroke="rgba(255,255,255,.35)" />
        <circle r="4.5" stroke={SURF} strokeWidth="2" />
        <rect y="-44" height="38" rx="8" fill="rgba(24,20,17,.96)" stroke="rgba(255,255,255,.1)" />
        <text className="tv num" y="-26" fill="#ffffff" fontSize="13" fontWeight="600" />
        <text className="ts" y="-12" fill="#a39a92" fontSize="10" />
      </g>}
      {axis && <rect x="0" y="0" width={cw} height={ch} fill="transparent" onMouseMove={move} onMouseLeave={leave} />}
    </svg>
  );
};"""

FMT = """const fmt = p => p == null ? "—" : p.toLocaleString("en-US", { maximumFractionDigits: p > 1000 ? 0 : 2, minimumFractionDigits: p > 1000 ? 0 : 2 });
const pct = c => `${c >= 0 ? "▲" : "▼"} ${Math.abs(c).toFixed(2)}%`;
// Company / exchange logo from the widgets folder (fetched by ~/.stark/logos.py). A missing one hides itself and is
// retried a few times a minute apart, since a newly added stock's logo is still downloading on first draw.
const Logo = ({ s, big }) => <img className={"lg" + (big ? " big" : "")} src={`logos/${s.replace("^", "")}.png`} alt=""
  onError={e => { const i = e.currentTarget, n = +(i.dataset.n || 0); i.style.display = "none"; if (n < 5) setTimeout(() => {
    i.dataset.n = n + 1; i.style.display = ""; i.src = i.src.split("?")[0] + "?" + Date.now(); }, 60000); }} />;"""

HOURS = """// World clocks under the main time (hover one to put it on the big display)
const CITIES = [
  { city: "NEW YORK", tz: "America/New_York", cc: "US" },
  { city: "LONDON",   tz: "Europe/London",    cc: "GB" },
  { city: "TOKYO",    tz: "Asia/Tokyo",       cc: "JP" },
];
const localParts = (tz, now) => {
  const p = Object.fromEntries(new Intl.DateTimeFormat("en-US", { timeZone: tz, hour12: false, hour: "2-digit", minute: "2-digit" })
    .formatToParts(now).map(x => [x.type, x.value]));
  const h = +p.hour % 24;
  return { h, hm: String(h).padStart(2, "0") + ":" + p.minute };
};
"""

# Time zone -> country code (from the system tz database), so the clock can show the flag of wherever the Mac thinks it is.
_zones = {}
for _f in ("/usr/share/zoneinfo/zone.tab",):
    try:
        for _l in open(_f):
            if _l[:1] != "#" and _l.strip(): _c, _, _tz = _l.split("\t")[:3]; _zones[_tz.strip()] = _c
    except OSError: pass
ZONES = "const ZONES = " + json.dumps(_zones, separators=(",", ":")) + ";"

SYNC = """// Sync warning: a red badge over the header when this panel's data fails, comes back empty, or stops updating.
// A widget can define `problem = data => "message" | null` for its own checks (e.g. Gmail login failing).
const syncCheck = (name, props) => {
  const S = (window.__sync = window.__sync || {}), s = (S[name] = S[name] || { ok: 0, born: Date.now() });
  const out = (props.output || "").trim(); let msg = null, data;
  if (props.error) msg = "Script failed";
  else if (!out) msg = s.ok ? "No data" : null;  // empty before the first run is just loading
  else { try { data = JSON.parse(out); } catch (e) { msg = "Unreadable data"; } }
  if (!msg && Array.isArray(data) && !data.length) msg = "Source sent nothing";
  if (!msg && data && data.error) msg = data.reason || (typeof data.error === "string" ? data.error : "Source reported an error");
  const bad = !!msg;  // the source itself failed (not just a widget's own problem() check)
  if (!msg && data && typeof problem === "function") msg = problem(data);
  // offline explains every failure at once (connections panel and the browser both report it)
  if (msg && (window.__offline || !navigator.onLine)) msg = "No internet";
  if (!msg && out) { s.ok = Date.now(); s.last = props.output; }
  s.msg = msg; setTimeout(syncPaint, 0);
  // when the script or its source fails, keep showing the last good data under the warning instead of a blank panel
  return bad && s.last ? { ...props, output: s.last, error: null } : props;
};
const syncAgo = t => { const m = Math.round((Date.now() - t) / 60000); return m < 1 ? "just now" : m < 60 ? m + "m ago" : m < 1440 ? Math.round(m / 60) + "h ago" : Math.round(m / 1440) + "d ago"; };
const syncPaint = () => document.querySelectorAll("[data-sync]").forEach(el => {
  const s = (window.__sync || {})[el.dataset.sync]; if (!s) return;
  // never loaded → warn after 2 min; otherwise after missing ~3 refreshes
  const stale = Date.now() - (s.ok || s.born) > (s.ok ? Math.max(3 * +el.dataset.every, 2 * 60000) : 2 * 60000);
  // Übersicht pauses refreshes while offline, so check the connection here too (internet panels only)
  const offline = el.dataset.net && (!navigator.onLine || window.__offline);
  const msg = offline ? "No internet" : s.msg || (stale ? "Not updating" : "");
  el.textContent = msg ? "⚠ " + msg + (s.ok ? " · " + syncAgo(s.ok) : "") : "";
  el.title = msg ? "This panel's data isn't syncing. It will clear itself once the source responds again." : "";
  el.classList.toggle("on", !!msg); });
// one shared timer that also catches scripts that hang; replaced on every hot reload so it runs the newest code
clearInterval(window.__syncTimer); window.__syncTimer = setInterval(syncPaint, 10000);
window.onoffline = window.ononline = () => syncPaint();  // react to Wi-Fi changes instantly"""

# ── Sci-fi HUD palette: holographic cyan, Stark gold, neon green/red ──
THEME = [
    ("rgba(255,179,92,", "rgba(245,177,76,"), ("rgba(255,214,170,", "rgba(255,255,255,"),
    ("rgba(74,222,128,", "rgba(79,209,139,"), ("rgba(248,113,113,", "rgba(255,107,107,"), ("rgba(36,27,22,1)", "rgba(24,20,18,1)"),
    ("#ffb35c", "#f5b14c"), ("#4ade80", "#4fd18b"), ("#f87171", "#ff6b6b"), ("#7fdcff", "#7cc8ff"),
    ("#fff7ee", "#ffffff"), ("#f3ece6", "#f2ede6"), ("#e6dcd2", "#ebe5dd"), ("#d9cfc6", "#d9d2c8"),
    ("#a39a92", "#9b938a"), ("#8c8178", "#857d75"), ("#6f665f", "#6b645d"), ("#4a403a", "#3e3934"),
    ("#d9b48a", "#e9c48e"), ("#a78bfa", "#b39cff"), ("#c4a1ff", "#b39cff"),
]

HUD = """// Drag a panel by its header.
// Its chains stretch as you pull and never break: let go and they spring it back home. Cursor light for the glass.
const hud = name => el => {
  if (!el) return; const box = el.parentElement; if (!box || box.__hud === "%%BUILD%%") return;
  if (box.__hudOff) box.__hudOff.abort(); const off = new AbortController(), on = { signal: off.signal };
  box.__hud = "%%BUILD%%"; box.__hudOff = off; box.dataset.hud = name;
  // Hot reloads keep the old DOM: drop handlers an older build left on anything else tagged as this panel
  // (e.g. an inner element that once got the ref by mistake), so only the panel itself drags.
  document.querySelectorAll(`[data-hud="${name}"]`).forEach(o => { if (o === box) return;
    if (o.__hudOff) o.__hudOff.abort(); delete o.__hud; delete o.dataset.hud; delete o.dataset.tether; delete o.dataset.hx; delete o.dataset.hy;
    o.getAnimations().forEach(a => a.cancel()); o.classList.remove("dragging"); o.style.left = o.style.top = o.style.transition = o.style.zIndex = ""; });
  box.getAnimations().forEach(a => a.cancel()); box.classList.remove("dragging");
  box.style.left = box.style.top = box.style.transition = ""; box.dataset.tether = "";
  const anywhere = name === "clock";
  const home = { x: box.offsetLeft, y: box.offsetTop };
  const BASE = "border-color .3s, box-shadow .3s, transform .3s";
  // chains measure strain from here; layout offsets, because the rect would include a hover/drag scale still easing out
  { const p = box.offsetParent ? box.offsetParent.getBoundingClientRect() : { left: 0, top: 0 };
    box.dataset.hx = p.left + home.x; box.dataset.hy = p.top + home.y; }
  let anim = null, done = 0;
  const place = (x, y) => { box.style.transition = BASE; box.style.left = x + "px"; box.style.top = y + "px"; };
  // Under-damped spring, precomputed and played with the Web Animations API: the panel's real position is home
  // straight away, so even if the animation never gets a frame (Übersicht throttles hidden views) it can't get stuck.
  const pullHome = () => {
    const dx = box.offsetLeft - home.x, dy = box.offsetTop - home.y;
    place(home.x, home.y); if (Math.hypot(dx, dy) < 1) return;
    let x = dx, y = dy, vx = 0, vy = 0; const frames = [];
    for (let i = 0; i < 180; i++) { frames.push({ transform: `translate(${x.toFixed(1)}px, ${y.toFixed(1)}px)` });
      if (Math.hypot(x, y) < 0.4 && Math.hypot(vx, vy) < 6) break;
      vx += (-170 * x - 15 * vx) / 60; vy += (-170 * y - 15 * vy) / 60; x += vx / 60; y += vy / 60; }
    frames.push({ transform: "translate(0px, 0px)" });
    const ms = frames.length * 1000 / 60, settle = () => { clearTimeout(done); anim = null; box.dataset.tether = ""; };
    box.dataset.tether = "taut";
    anim = box.animate(frames, { duration: ms, easing: "linear" }); anim.onfinish = settle; anim.oncancel = settle;
    clearTimeout(done); done = setTimeout(settle, ms + 100); };
  box.addEventListener("mousemove", e => { const r = box.getBoundingClientRect();
    box.style.setProperty("--mx", (e.clientX - r.left) + "px"); box.style.setProperty("--my", (e.clientY - r.top) + "px"); }, on);
  box.addEventListener("mouseleave", () => box.style.setProperty("--mx", "-999px"), on);
  box.addEventListener("mousedown", e => {
    if (e.button !== 0 || e.target.closest(".seg, .tabs") || !(anywhere || e.target.closest("header"))) return;
    if (anim) { const r = box.getBoundingClientRect(); anim.cancel(); place(r.left - box.dataset.hx + home.x, r.top - box.dataset.hy + home.y); }
    const sx = e.clientX, sy = e.clientY, ox = box.offsetLeft, oy = box.offsetTop, W = box.offsetWidth, H = box.offsetHeight;
    window.__hudZ = (window.__hudZ || 10) + 1; box.style.zIndex = window.__hudZ; box.classList.add("dragging");
    const mv = ev => {
      const x = Math.max(0, Math.min(window.innerWidth - W, ox + ev.clientX - sx)), y = Math.max(0, Math.min(window.innerHeight - 40, oy + ev.clientY - sy));
      place(Math.round(x), Math.round(y)); box.dataset.tether = "taut"; };
    const up = () => {
      document.removeEventListener("mousemove", mv); document.removeEventListener("mouseup", up);
      box.classList.remove("dragging"); pullHome(); };
    document.addEventListener("mousemove", mv); document.addEventListener("mouseup", up);
  }, on);

};"""

# ── Stark armour HUD: amber holograms on smoked-bronze glass (blends with a warm wallpaper) ──
WARM = [
    ("rgba(62,232,255,", "rgba(245,177,76,"), ("#3ee8ff", "#f5b14c"), ("rgba(255,201,74,", "rgba(245,177,76,"), ("#ffc94a", "#f5b14c"),
    ("rgba(57,255,159,", "rgba(79,209,139,"), ("#39ff9f", "#4fd18b"), ("rgba(255,59,78,", "rgba(255,107,107,"), ("#ff3b4e", "#ff6b6b"),
    ("rgba(255,75,58,", "rgba(255,214,150,"), ("#ff4b3a", "#ffd696"),
    ("rgba(190,250,255,", "rgba(255,255,255,"), ("rgba(190,245,255,", "rgba(255,255,255,"),
    ("#e8fbff", "#ffffff"), ("#bff6ff", "#f2ede6"), ("#dff6ff", "#f2ede6"), ("#cfeffa", "#ebe5dd"), ("#b8dce8", "#d9d2c8"),
    ("#7fa9b8", "#9b938a"), ("#5f8a99", "#857d75"), ("#46707f", "#6b645d"), ("#1e3b47", "#3e3934"),
    ("#6fe8ff", "#7cc8ff"), ("#b388ff", "#b39cff"),
]

# ── HUD cursor: the system pointer is hidden over panels and aa-links draws the amber aimer + spinning ring
# itself (Übersicht's WebKit ignores image cursors; CSS can't be trusted to draw it).
CURSOR = "none"

NET = {"weather", "puzzle", "anime", "chesstv", "connections"}  # panels that need the internet

# Chess board shared by the puzzle and Lichess TV panels (pieces: Lichess cburnett set, downloaded by puzzle.py)
CHESS = r"""const FILES = "abcdefgh";
const parseFen = fen => { const b = {}; fen.split(" ")[0].split("/").forEach((row, r) => { let f = 0;
  for (const c of row) { if (/\d/.test(c)) f += +c; else { b[FILES[f] + (8 - r)] = (c === c.toUpperCase() ? "w" : "b") + c.toUpperCase(); f++; } } });
  return b; };
// display-only move (an alternative mate the solution didn't list): castling, en passant and promotion
const applyUci = (fen, uci) => { const b = parseFen(fen), [f, t] = [uci.slice(0, 2), uci.slice(2, 4)], pc = b[f];
  if (pc[1] === "K" && Math.abs(FILES.indexOf(f[0]) - FILES.indexOf(t[0])) === 2) { const k = t[0] === "g", r = (k ? "h" : "a") + f[1];
    b[(k ? "f" : "d") + f[1]] = b[r]; delete b[r]; }
  if (pc[1] === "P" && f[0] !== t[0] && !b[t]) delete b[t[0] + f[1]];
  delete b[f]; b[t] = uci[4] ? pc[0] + uci[4].toUpperCase() : pc;
  const rows = []; for (let r = 8; r >= 1; r--) { let row = "", e = 0;
    for (const fl of FILES) { const p = b[fl + r]; if (!p) { e++; continue; } if (e) { row += e; e = 0; } row += p[0] === "w" ? p[1] : p[1].toLowerCase(); }
    rows.push(row + (e || "")); }
  return rows.join("/") + " " + (fen.split(" ")[1] === "w" ? "b" : "w"); };
const Board = ({ fen, flip, size, lm, sel, hint, bad, targets = [], movable, onSelect, onMove, coords = true }) => {
  const q = size / 8, b = parseFen(fen);
  const xy = sq => { const f = FILES.indexOf(sq[0]), r = +sq[1] - 1; return flip ? [(7 - f) * q, r * q] : [f * q, (7 - r) * q]; };
  const at = (e, el) => { const r = el.getBoundingClientRect(), c = Math.floor((e.clientX - r.left) / q), w = Math.floor((e.clientY - r.top) / q);
    if (c < 0 || c > 7 || w < 0 || w > 7) return null; return flip ? FILES[7 - c] + (w + 1) : FILES[c] + (8 - w); };
  const down = e => {
    if (!onMove || e.button !== 0) return; const el = e.currentTarget, sq = at(e, el); if (!sq) return;
    if (!movable(sq)) { if (sel && sq !== sel) onMove(sel, sq) || onSelect(null); return; }
    e.preventDefault(); onSelect(sq);
    const img = el.querySelector(`img[data-sq="${sq}"]`), sx = e.clientX, sy = e.clientY;
    const mv = ev => { if (img) { img.style.transform = `translate(${ev.clientX - sx}px, ${ev.clientY - sy}px) scale(1.1)`; img.style.zIndex = 9; img.style.animation = "none"; } };
    const up = ev => { document.removeEventListener("mousemove", mv); document.removeEventListener("mouseup", up);
      if (img) { img.style.transform = ""; img.style.zIndex = ""; }
      const to = at(ev, el); if (to && to !== sq && !onMove(sq, to)) onSelect(null); };
    document.addEventListener("mousemove", mv); document.addEventListener("mouseup", up); };
  const sqs = []; for (let r = 0; r < 8; r++) for (let f = 0; f < 8; f++) sqs.push(FILES[f] + (8 - r));
  const lf = lm && lm.slice(0, 2), lt = lm && lm.slice(2, 4);
  return (
    <div className="board" onMouseDown={down}>
      {sqs.map(s => { const [x, y] = xy(s), dark = (FILES.indexOf(s[0]) + +s[1]) % 2 === 0;
        return <div key={s} className={"sq" + (dark ? " d" : "") + (s === lf || s === lt ? " lm" : "") + (s === sel ? " sel" : "") + (s === hint ? " hint" : "")}
          style={{ left: x, top: y, width: q, height: q }}>
          {coords && (flip ? s[1] === "8" : s[1] === "1") && <span className="cf">{s[0]}</span>}
          {coords && (flip ? s[0] === "h" : s[0] === "a") && <span className="cr">{s[1]}</span>}
        </div>; })}
      {bad && <div key={bad} className="sq bad" style={{ left: xy(bad.slice(0, 2))[0], top: xy(bad.slice(0, 2))[1], width: q, height: q }} />}
      {Object.entries(b).map(([s, p]) => { const [x, y] = xy(s), slide = s === lt && lf ? xy(lf) : null;
        return <img key={fen + s} data-sq={s} src={`chess/${p}.svg`} alt="" className={slide ? "slide" : ""}
          style={{ left: x, top: y, width: q, height: q, ...(slide ? { "--dx": slide[0] - x + "px", "--dy": slide[1] - y + "px" } : {}) }} />; })}
      {targets.map(s => { const [x, y] = xy(s);
        return <div key={"t" + s} className={"dot" + (b[s] ? " cap" : "")} style={{ left: x, top: y, width: q, height: q }} />; })}
    </div>
  );
};"""

BOARDCSS = """.board { position:relative; border-radius:10px; overflow:hidden; box-shadow:0 10px 30px rgba(0,0,0,.4) }
  .sq { position:absolute; background:#d9c4a3 } .sq.d { background:#a17b59 }
  .sq.lm { box-shadow: inset 0 0 0 999px rgba(245,177,76,.42) }
  .sq.sel { box-shadow: inset 0 0 0 999px rgba(120,190,110,.55) }
  .sq.hint { box-shadow: inset 0 0 0 999px rgba(124,200,255,.5) }
  .sq.bad { background:transparent; z-index:3; pointer-events:none; animation: badsq .9s ease-out forwards }
  @keyframes badsq { 0%, 40% { box-shadow: inset 0 0 0 999px rgba(255,80,80,.65) } 100% { box-shadow: inset 0 0 0 999px rgba(255,80,80,0) } }
  .cf, .cr { position:absolute; font-size:9px; font-weight:700; color:rgba(40,28,20,.55) }
  .cf { right:3px; bottom:1px } .cr { left:3px; top:2px }
  .board img { position:absolute; z-index:2; pointer-events:none; -webkit-user-drag:none }
  .board img.slide { animation: slide .2s ease-out }
  @keyframes slide { from { transform: translate(var(--dx), var(--dy)) } }
  .dot { position:absolute; z-index:4; pointer-events:none; display:grid; place-items:center }
  .dot::after { content:""; width:28%; height:28%; border-radius:50%; background:rgba(30,60,25,.38) }
  .dot.cap::after { width:86%; height:86%; background:transparent; border:4px solid rgba(30,60,25,.38) }"""


def after_tag(src, attr, insert):
    """Put `insert` just inside every opening tag that carries `attr`; the tag's other props may hold arrows (`=>`)."""
    out, i = [], 0
    while (j := src.find(attr, i)) >= 0:
        k, depth = j + len(attr), 0
        while depth or src[k] != ">":
            depth += {"{": 1, "}": -1}.get(src[k], 0); k += 1
        out.append(src[i:k + 1] + insert); i = k + 1
    return "".join(out) + src[i:]

def widget(name, body):
    x, y, w, h = POS.get(name, (0, 0, 0, 0)); y += DY
    body = (body.replace("%%SHARED%%", SHARED)
                .replace("%%POS%%", f"left: {x}px; top: {y}px; width: {w}px; height: {h}px;")
                .replace("%%ZONES%%", ZONES).replace("%%PY%%", PY).replace("%%AGO%%", AGO).replace("%%SPARK%%", SPARK)
                .replace("%%FMT%%", FMT).replace("%%HOURS%%", HOURS).replace("%%CHESS%%", CHESS).replace("%%BOARDCSS%%", BOARDCSS)
                .replace("%%W2%%", str(w + 2)).replace("%%H2%%", str(h + 2)))
    for old, new in THEME:
        body = body.replace(old, new)
    for old, new in WARM:
        body = body.replace(old, new)
    body = re.sub(r";?\s*text-shadow:[^;}]*", "", body)
    # one custom cursor everywhere: no system hand/arrow over headers, buttons or rows
    body = re.sub(r"cursor: ?(default|grabbing|grab|pointer)\b", f"cursor: {CURSOR}", body)
    if name != "aa-links":
        head, mark, tail = body.partition("\nexport const render")
        # the ref goes first, so a root with its own props (the clock's hover handlers) still gets dragging + chains
        tail = re.sub(r"(\n  (?:if \([^\n]*?\) )?return (?:\(\s*)?<div)(?=[\s>])", lambda m: m.group(1) + ' ref={hud("' + name + '")}', tail)
        body = head + mark + tail
        body = body.replace("\nexport const render", "\n" + HUD + "\nexport const render", 1)
    if name not in ("aa-links", "clock"):
        # badge goes in every root the render returns (e.g. loading + loaded), not in helper components above it
        head, mark, tail = body.partition("\nexport const render")
        net = ' data-net="1"' if name in NET else ""
        body = head + mark + after_tag(tail, 'ref={hud("' + name + '")}', '<span className="syncwarn" data-sync="' + name + '"' + net + ' data-every={refreshFrequency} />')
        body = body.replace("\nexport const render =", "\n" + SYNC + "\nconst __render =", 1)
        body += '\nexport const render = (p, d) => __render(syncCheck("' + name + '", p), d);'
    body = body.replace("%%BUILD%%", BUILD)
    with open(os.path.join(W, name + ".jsx"), "w") as f:
        f.write(body + "\n")


# ───────────────────────── CLOCK ─────────────────────────
widget("clock", r'''// Clock, greeting and world clocks (hover a city to put its time on the big display).
export const command = "date +%s";
export const refreshFrequency = 1000;
export const className = `
  %%POS%%%%SHARED%%
  box-sizing: border-box; width: %%W2%%px; height: %%H2%%px; padding: 20px 20px 18px 22px;  /* same outer size as the panels below */
  .time { display:flex; align-items:baseline; gap:8px }
  .time b { font: 200 68px -apple-system, "SF Pro Display", sans-serif; letter-spacing:-.03em; line-height:1; color:#ffffff }
  .time span { font: 300 22px -apple-system, sans-serif; color:#f5b14c }
  .date { margin-top:10px; font: 500 15px -apple-system, sans-serif; color:#ebe5dd }
  .greet { margin-top:2px; font-size:12.5px; letter-spacing:.06em; color:#5f8a99 }
  .ex { display:grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap:10px; margin-top:18px }
  .cell { background:rgba(255,255,255,.04); border:1px solid rgba(255,255,255,.06); border-radius:12px; padding:8px 11px; min-width:0 }
  .cell .c { font: 700 8.5px Orbitron, sans-serif; letter-spacing:.1em; color:#8c8178; white-space:nowrap; overflow:hidden }
  .cell .t { font-size:17px; font-weight:500; margin:3px 0 2px }
  .cell .s { font-size:10px; white-space:nowrap; color:#a39a92 }
  .here { position:absolute; text-align:center; cursor:default }
  .here .f { font-size:38px; line-height:1; display:inline-block; transform-origin: 8% 50%; filter: drop-shadow(0 3px 8px rgba(0,0,0,.45)) }
  .here:hover .f { animation: wave 1.1s ease-in-out infinite }
  @keyframes wave { 0%, 100% { transform: perspective(80px) rotateY(0) skewY(0) } 25% { transform: perspective(80px) rotateY(-18deg) skewY(-3deg) }
                    75% { transform: perspective(80px) rotateY(12deg) skewY(2deg) } }
  .here .n { font: 700 7.5px Orbitron, sans-serif; letter-spacing:.18em; color:#8c8178; margin-top:4px }
  .cell { cursor:default; transition: background .25s, border-color .25s }
  .cell:hover, .cell.sel { background:rgba(255,255,255,.075); border-color: rgba(245,177,76,.35) }
  .stage { display:grid }
  .view { grid-area: 1 / 1; position:relative; opacity:0; visibility:hidden; transition: opacity .25s, visibility .25s }
  .view.on { opacity:1; visibility:visible }
  .here { top:0; right:0 }
`;
%%HOURS%%
%%ZONES%%
// "KE" -> 🇰🇪 (two regional indicator letters)
const flag = cc => cc ? String.fromCodePoint(...[...cc.toUpperCase()].map(c => 0x1F1A5 + c.charCodeAt(0))) : "🌐";
const region = cc => { try { return new Intl.DisplayNames(["en"], { type: "region" }).of(cc); } catch (e) { return cc; } };
// Hover a city to put its clock on the big display; leaving the panel (or 8 s idle) brings yours back, like Weather.
const pick = (root, k) => { if (!root) return;
  root.querySelectorAll(".view").forEach(v => v.classList.toggle("on", v.dataset.k === k));
  root.querySelectorAll(".cell").forEach(v => v.classList.toggle("sel", v.dataset.k === k)); };
const home = e => { const el = e.currentTarget; clearTimeout(window.__ckHome); window.__ckHome = setTimeout(() => pick(el, "here"), 8000); };
// how far ahead (+) or behind (−) a time zone is from here, e.g. "−7h", "+5h 30m"
const diff = (tz, now) => { const at = z => new Date(now.toLocaleString("en-US", z ? { timeZone: z } : {}));
  const m = Math.round((at(tz) - at()) / 60000 / 15) * 15; if (!m) return "";
  const a = Math.abs(m); return (m > 0 ? "+" : "−") + Math.floor(a / 60) + "h" + (a % 60 ? " " + a % 60 + "m" : ""); };
const offset = (tz, now) => { const d = diff(tz, now); return !d ? "same time as you" : d + (d[0] === "+" ? " ahead" : " behind"); };
const partOf = h => h < 5 ? ["night", "☾"] : h < 12 ? ["morning", "☀︎"] : h < 17 ? ["afternoon", "☀︎"] : h < 21 ? ["evening", "☾"] : ["night", "☾"];
export const render = () => {
  const now = new Date(), h = now.getHours();
  const tz = Intl.DateTimeFormat().resolvedOptions().timeZone, cc = ZONES[tz], city = (tz.split("/").pop() || "").replace(/_/g, " ");
  return (
    <div onMouseLeave={e => pick(e.currentTarget, "here")} onMouseMove={home}>
      <div className="stage">
        <div className="view on" data-k="here">
          <div className="here" title={city}><div className="f">{flag(cc)}</div><div className="n">{(cc ? region(cc) : city).toUpperCase()}</div></div>
          <div className="time num"><b>{now.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" })}</b>
            <span>{String(now.getSeconds()).padStart(2, "0")}</span></div>
          <div className="date">{now.toLocaleDateString("en-GB", { weekday: "long", day: "numeric", month: "long" })}</div>
          <div className="greet">Good {partOf(h)[0] === "night" ? "evening" : partOf(h)[0]}, Anthony</div>
        </div>
        {CITIES.map(c => { const t = localParts(c.tz, now); return (
          <div className="view" data-k={c.city} key={c.city}>
            <div className="here"><div className="f">{flag(c.cc)}</div><div className="n">{c.city}</div></div>
            <div className="time num"><b>{t.hm}</b><span>{String(now.getSeconds()).padStart(2, "0")}</span></div>
            <div className="date">{now.toLocaleDateString("en-GB", { timeZone: c.tz, weekday: "long", day: "numeric", month: "long" })}</div>
            <div className="greet">{partOf(t.h)[1]} {partOf(t.h)[0]} there · {offset(c.tz, now)}</div>
          </div>); })}
      </div>
      <div className="ex">
        {CITIES.map(c => { const t = localParts(c.tz, now); return (
          <div className="cell" key={c.city} data-k={c.city} onMouseEnter={e => pick(e.currentTarget.closest(".ex").parentElement, c.city)}>
            <div className="c">{flag(c.cc)} {c.city}</div>
            <div className="t num">{t.hm}</div>
            <div className="s num">{partOf(t.h)[1]} {diff(c.tz, now) || "same time"}</div>
          </div>); })}
      </div>
    </div>
  );
};''')

# ───────────────────────── WEATHER ─────────────────────────
widget("weather", r'''// Nairobi weather (Open-Meteo). Change location in ~/.stark/weather.sh
export const command = "~/.stark/weather.sh";
export const refreshFrequency = 15 * 60 * 1000;
export const className = `
  %%POS%%%%SHARED%%
  .stage { display:grid }
  .view { grid-area: 1 / 1; opacity:0; visibility:hidden; transition: opacity .25s, visibility .25s }
  .view.on { opacity:1; visibility:visible }
  .main { display:flex; align-items:center; gap:16px; padding:16px 22px 10px }
  .temp .lo { font-size:24px; color:#8c8178; margin-left:4px; letter-spacing:0 }
  .cond .when { font-size:9.5px; letter-spacing:.16em; color:#f5b14c; font-weight:600 }
  .ico { font-size:54px; line-height:1; filter: drop-shadow(0 4px 12px rgba(255,179,92,.35)) }
  .temp { font: 200 60px -apple-system, "SF Pro Display", sans-serif; letter-spacing:-.02em; line-height:1; color:#ffffff }
  .temp sup { font-size:18px; color:#ffb35c; vertical-align: 20px; margin-left:2px }
  .cond { margin-left:auto; text-align:right }
  .cond b { display:block; font-size:17px; font-weight:600 }
  .cond span { display:block; font-size:12px; color:#a39a92; line-height:1.5 }
  .chips { display:flex; gap:8px; padding:6px 20px 16px }
  .chip { flex:1; text-align:center; font-size:11.5px; padding:7px 0; border-radius:10px; background:rgba(255,214,170,.04); border:1px solid rgba(255,214,170,.06); color:#d9cfc6; white-space:nowrap }
  .days { display:grid; grid-template-columns: repeat(5, 1fr); gap:6px; margin:6px 16px 0; padding-top:18px; border-top:1px solid rgba(255,214,170,.08); text-align:center }
  .d { border-radius:10px; padding:10px 0 12px; cursor:pointer; transition: background .25s, box-shadow .25s }
  .d:hover, .d.sel { background:rgba(255,255,255,.06); box-shadow: inset 0 0 0 1px rgba(245,177,76,.3) }
  .d .n { font-size:9.5px; letter-spacing:.14em; color:#8c8178; font-weight:600 }
  .d .i { font-size:24px; margin:8px 0 5px }
  .d .hl { font-size:12px } .d .hl span { color:#6f665f }
  .bar { height:3px; margin:5px 12px 0; border-radius:2px; background:rgba(127,220,255,.12); overflow:hidden }
  .bar i { display:block; height:100%; background:#7fdcff }
`;
const WMO = { 0:["Clear","☀️","🌙"], 1:["Mostly clear","🌤","🌙"], 2:["Partly cloudy","⛅️","☁️"], 3:["Overcast","☁️","☁️"],
  45:["Fog","🌫","🌫"], 48:["Fog","🌫","🌫"], 51:["Drizzle","🌦","🌧"], 53:["Drizzle","🌦","🌧"], 55:["Drizzle","🌧","🌧"],
  61:["Light rain","🌦","🌧"], 63:["Rain","🌧","🌧"], 65:["Heavy rain","🌧","🌧"], 80:["Showers","🌦","🌧"], 81:["Showers","🌧","🌧"],
  82:["Heavy showers","⛈","⛈"], 95:["Thunderstorm","⛈","⛈"], 96:["Thunderstorm","⛈","⛈"], 99:["Thunderstorm","⛈","⛈"] };
const wmo = (c, day = 1) => { const w = WMO[c] || ["—", "🌡", "🌡"]; return [w[0], day ? w[1] : w[2]]; };
const hm = s => (s || "").slice(11, 16);
// Hover a day to put its full forecast where "now" is; leaving the panel (or 8 s idle) brings now back, like Tech Markets.
const pick = (root, k) => { if (!root) return;
  root.querySelectorAll(".view").forEach(v => v.classList.toggle("on", v.dataset.k === k));
  root.querySelectorAll(".d").forEach(v => v.classList.toggle("sel", v.dataset.k === k)); };
// Übersicht sends no mouseleave when the mouse leaves into a gap between panels, hence the idle fallback.
const home = e => { const el = e.currentTarget; clearTimeout(window.__wxHome); window.__wxHome = setTimeout(() => pick(el, "now"), 8000); };
const DayView = ({ d, i }) => { const [label, icon] = wmo(d.weather_code[i]), at = new Date(d.time[i] + "T12:00");
  return (
    <div className="view" data-k={"d" + i}>
      <div className="main">
        <div className="ico">{icon}</div>
        <div className="temp num">{Math.round(d.temperature_2m_max[i])}<sup>°C</sup><span className="lo">{Math.round(d.temperature_2m_min[i])}°</span></div>
        <div className="cond"><span className="when">{at.toLocaleDateString("en-GB", { weekday: "long", day: "numeric", month: "short" }).toUpperCase()}</span>
          <b>{label}</b>
          <span className="num">Rain chance {d.precipitation_probability_max[i] ?? 0}%</span></div>
      </div>
      <div className="chips num">
        <span className="chip">🌧 {(d.precipitation_sum?.[i] ?? 0).toFixed(1)} mm</span>
        <span className="chip">💨 {Math.round(d.wind_speed_10m_max?.[i] ?? 0)} km/h</span>
        <span className="chip">UV {Math.round(d.uv_index_max[i])}</span>
        <span className="chip">☀︎ {hm(d.sunrise[i])}</span>
        <span className="chip">☾ {hm(d.sunset[i])}</span>
      </div>
    </div>); };
export const render = ({ output }) => {
  let w = null; try { w = JSON.parse(output); } catch (e) {}
  const ok = w && w.current;
  const head = <header><span style={{ color: "#ffb35c" }}>◎</span><h1>WEATHER</h1><span className="sub">NAIROBI · <b>{ok ? "LIVE" : "SCANNING"}</b></span></header>;
  if (!ok) return <div>{head}</div>;
  const c = w.current, d = w.daily, [label, icon] = wmo(c.weather_code, c.is_day);
  return (
    <div onMouseLeave={e => pick(e.currentTarget, "now")} onMouseMove={home}>{head}
      <div className="stage">
      <div className="view on" data-k="now">
      <div className="main">
        <div className="ico">{icon}</div>
        <div className="temp num">{Math.round(c.temperature_2m)}<sup>°C</sup></div>
        <div className="cond"><b>{label}</b>
          <span>Feels like {Math.round(c.apparent_temperature)}°</span>
          <span className="num">H {Math.round(d.temperature_2m_max[0])}° · L {Math.round(d.temperature_2m_min[0])}°</span></div>
      </div>
      <div className="chips num">
        <span className="chip">💧 {c.relative_humidity_2m}%</span>
        <span className="chip">💨 {Math.round(c.wind_speed_10m)} km/h</span>
        <span className="chip">UV {Math.round(d.uv_index_max[0])}</span>
        <span className="chip">☀︎ {hm(d.sunrise[0])}</span>
        <span className="chip">☾ {hm(d.sunset[0])}</span>
      </div>
      </div>
      {d.time.slice(1, 6).map((t, i) => <DayView key={t} d={d} i={i + 1} />)}
      </div>
      <div className="days">
        {d.time.slice(1, 6).map((t, i) => { const rain = d.precipitation_probability_max[i + 1] ?? 0; return (
          <div className="d" key={t} data-k={"d" + (i + 1)} onMouseEnter={e => pick(e.currentTarget.closest(".days").parentElement, "d" + (i + 1))}>
            <div className="n">{new Date(t + "T12:00").toLocaleDateString("en-US", { weekday: "short" }).toUpperCase()}</div>
            <div className="i">{wmo(d.weather_code[i + 1])[1]}</div>
            <div className="hl num">{Math.round(d.temperature_2m_max[i + 1])}° <span>{Math.round(d.temperature_2m_min[i + 1])}°</span></div>
            <div className="bar"><i style={{ width: rain + "%" }} /></div>
          </div>); })}
      </div>
    </div>
  );
};''')

# ───────────────────────── SYSTEM ─────────────────────────
widget("system", r'''// System monitor: CPU, memory, disk, battery charge + battery health (maximum capacity, cycles, condition).
export const command = "~/.stark/system.sh";
export const refreshFrequency = 10 * 1000;
export const className = `
  %%POS%%%%SHARED%%
  .rings { display:grid; grid-template-columns: repeat(5, 1fr); padding:26px 10px 10px; text-align:center }
  .ring { position:relative; width:64px; height:64px; margin:0 auto }
  .ring svg { width:64px; height:64px }
  .ring b { position:absolute; inset:0; display:flex; align-items:center; justify-content:center; font-size:14.5px; font-weight:500 }
  .ring b small { font-size:8.5px; color:#8c8178; margin-left:1px }
  .rl { margin-top:7px; letter-spacing:.18em }
  .rs { margin-top:3px; font-size:9.5px; color:#a39a92; white-space:nowrap }
  .load { margin:20px 20px 0 }
  .load .top { display:flex; justify-content:space-between; font-size:10.5px; color:#a39a92 } .load .top b { color:#e6dcd2; font-weight:500 }
  .load .bar { height:5px; margin-top:6px; border-radius:3px; background:rgba(255,214,170,.08); overflow:hidden }
  .load .bar i { display:block; height:100%; border-radius:3px; transition: width .6s ease }
  .foot { display:flex; justify-content:space-between; margin:20px 20px 0; padding-top:14px; border-top:1px solid rgba(255,214,170,.08); font-size:10.5px; color:#a39a92 }
  .foot b { color:#e6dcd2; font-weight:500 }
`;
const Ring = ({ v, col, label, sub, title }) => {
  const r = 23, C = 2 * Math.PI * r, f = Math.max(0, Math.min(100, v)) / 100;
  return (
    <div title={title}>
      <div className="ring">
        <svg width="56" height="56" viewBox="0 0 56 56">
          <circle cx="28" cy="28" r={r} fill="none" stroke="rgba(255,214,170,.08)" strokeWidth="4.5" />
          <circle cx="28" cy="28" r={r} fill="none" stroke={col} strokeWidth="4.5" strokeLinecap="round"
            strokeDasharray={`${C * f} ${C}`} transform="rotate(-90 28 28)" style={{ filter: `drop-shadow(0 0 4px ${col})` }} />
        </svg>
        <b className="num">{Math.round(v)}<small>%</small></b>
      </div>
      <div className="lbl rl">{label}</div>
      {sub && <div className="rs num">{sub}</div>}
    </div>
  );
};
const heat = v => v > 85 ? "#f87171" : v > 65 ? "#ffb35c" : null;
// Combined load: CPU counts most, then memory, battery drain (a charging Mac counts a little) and disk.
const loadOf = s => Math.round(Math.max(0, Math.min(100,
  .45 * s.cpu + .25 * s.mem + .2 * (s.charging ? 25 : 100 - s.batt) + .1 * s.disk)));
// Battery health: maximum capacity as the ring, cycles + condition under it. Apple calls 80% or less worn,
// and any condition other than "Normal" (e.g. "Service Recommended") turns it red.
const Health = ({ s }) => {
  const ok = !s.condition || s.condition === "Normal";
  const col = !ok || s.health <= 80 ? "#f87171" : s.health <= 85 ? "#ffb35c" : "#4ade80";
  return <Ring v={s.health ?? 0} col={col} label="HEALTH"
    sub={<span>{s.cycles ?? "—"} cyc · <span className={ok ? "up" : "dn"}>{ok ? "OK" : "SERVICE"}</span></span>}
    title={`Maximum capacity ${s.health ?? "?"}% · ${s.cycles ?? "?"} charge cycles · condition: ${s.condition || "unknown"}`} />;
};
export const render = ({ output }) => {
  let s = null; try { s = JSON.parse(output); } catch (e) {}
  const load = s ? loadOf(s) : 0;
  return (
    <div>
      <header><span style={{ color: "#ffb35c" }}>⌁</span><h1>SYSTEM</h1>
        <span className="sub">MACBOOK · <b>{!s ? "…" : load > 85 ? "HOT" : load > 65 ? "WORKING HARD" : load > 40 ? "BUSY" : "NOMINAL"}</b></span></header>
      {s && <div className="rings">
        <Ring v={s.cpu} col={heat(s.cpu) || "#7fdcff"} label="CPU" />
        <Ring v={s.mem} col={heat(s.mem) || "#a78bfa"} label="MEMORY" />
        <Ring v={s.disk} col={heat(s.disk) || "#ffb35c"} label="DISK" />
        <Ring v={s.batt} col={s.batt < 20 ? "#f87171" : "#4ade80"} label={s.charging ? "⚡ POWER" : "BATTERY"} />
        <Health s={s} />
      </div>}
      {s && <div className="load num"><div className="top"><span>Combined load</span><b>{load}%</b></div>
        <div className="bar"><i style={{ width: load + "%", background: load > 85 ? "#f87171" : load > 65 ? "#ffb35c" : "#4ade80" }} /></div></div>}
      {s && <div className="foot num"><span>Uptime <b>{s.uptime}</b></span><span>Processes <b>{s.procs}</b></span><span>Free <b>{s.diskFree}</b></span></div>}
    </div>
  );
};''')

# ───────────────────────── CONNECTIONS ─────────────────────────
widget("connections", r'''// Connections, two views (toggle in the header, remembered):
// LIVE = throughput and latency to the services you use; LINK = Wi-Fi link, VPN + public IP, last speed test.
// The VPN row's OFF/US/UK switch runs ~/.stark/vpn.sh (free: Tor with the exit pinned to that country).
import { run } from "uebersicht";
export const command = "~/.stark/network.sh";
export const refreshFrequency = 30 * 1000;
export const className = `
  %%POS%%%%SHARED%%
  .body { display:flex; align-items:center; padding:8px 18px 0 14px }
  .flow { stroke-dasharray: 3 5; animation: f 1.2s linear infinite } @keyframes f { to { stroke-dashoffset: -16 } }
  .pulse { animation: p 2.4s ease-in-out infinite } @keyframes p { 50% { opacity:.45 } }
  .wave { transform-box: fill-box; transform-origin: center; animation: wave 2.6s ease-out infinite }
  .wave.b { animation-delay: 1.3s } .hub.alert .wave { animation-duration: 1.1s } .hub.alert .wave.b { animation-delay: .55s }
  @keyframes wave { from { transform: scale(1); opacity: .7 } to { transform: scale(2.1); opacity: 0 } }
  .hub.alert .ring { animation: beat 1.1s ease-in-out infinite } @keyframes beat { 50% { stroke-width: 2.4 } }
  .reach { animation: reach 2.4s ease-out infinite; animation-delay: var(--d) }
  @keyframes reach { 0% { stroke-dashoffset: var(--o); opacity: .9 } 55% { stroke-dashoffset: 0; opacity: .9 } 62% { opacity: .25 } 68% { opacity: .8 } 74% { opacity: .15 } 100% { stroke-dashoffset: 0; opacity: 0 } }
  .fizz { transform-box: fill-box; transform-origin: center; animation: fizz 2.4s ease-out infinite; animation-delay: var(--d) }
  @keyframes fizz { 0%, 52% { transform: scale(0); opacity: 0 } 58% { transform: scale(1.4); opacity: 1 } 80% { transform: scale(.6); opacity: .5 } 100% { transform: scale(0); opacity: 0 } }
  .flame { transform-box: fill-box; transform-origin: 50% 100%; animation: burn var(--t) ease-in-out infinite alternate; animation-delay: var(--d) }
  @keyframes burn { 0% { transform: scale(.75, .7) skewX(-6deg); opacity: .75 } 50% { transform: scale(1.05, 1.15) skewX(5deg); opacity: 1 } 100% { transform: scale(.9, .9) skewX(-3deg); opacity: .85 } }
  .ember { animation: ember var(--t) ease-out infinite; animation-delay: var(--d) }
  @keyframes ember { 0% { transform: translate(0, 0); opacity: 0 } 15% { opacity: 1 } 100% { transform: translate(var(--dx), -26px); opacity: 0 } }
  .smoke { transform-box: fill-box; transform-origin: center; animation: smoke var(--t) ease-out infinite; animation-delay: var(--d) }
  @keyframes smoke { 0% { transform: translate(0, 0) scale(.4); opacity: 0 } 25% { opacity: .35 } 100% { transform: translate(var(--dx), -30px) scale(1.8); opacity: 0 } }
  .char { animation: char .18s steps(2) infinite } @keyframes char { 50% { opacity: .55 } }
  .hub.ok .ring { animation: glow 2.6s ease-in-out infinite } @keyframes glow { 50% { filter: drop-shadow(0 0 5px var(--hub)) } }
  .weak { animation: f .5s linear infinite, flick .35s steps(2) infinite } @keyframes flick { 50% { stroke-opacity: .25 } }
  .spark { animation: spark var(--t) ease-out infinite; animation-delay: var(--d) }
  @keyframes spark { 0% { transform: translate(0, 0); opacity: 1 } 70% { opacity: .8 } 100% { transform: translate(var(--dx), var(--dy)); opacity: 0 } }
  .live { user-select:none; -webkit-user-select:none }
  .node .dot { transform-box: fill-box; transform-origin: center; transition: transform .2s cubic-bezier(.3,1.6,.5,1) }
  .node:hover .dot { transform: scale(1.6) } .node.held .dot { transform: scale(1.9) }
  .node:hover text, .node.held text { fill:#fff7ee }
  .node.pinged .dot { animation: pinged .6s ease-out } @keyframes pinged { 0% { transform: scale(2.6) } 100% { transform: scale(1) } }
  .ln.taut { stroke-dasharray: 2 4; stroke-width: 1.6 }
  .rates { margin-left:auto; text-align:right; padding-right:8px }
  .rate { font: 200 28px -apple-system, sans-serif; line-height:1.15 } .rate small { font-size:10px; color:#8c8178; margin-left:3px }
  .rl { font-size:9.5px; letter-spacing:.16em; color:#8c8178; font-weight:600; margin-top:8px }
  .lip { font-size:9.5px; color:#6f665f; margin-top:9px; letter-spacing:.04em }
  .seg { display:inline-flex; gap:2px; padding:2px; border-radius:7px; background:rgba(0,0,0,.18); vertical-align:middle }
  .seg span { padding:2px 7px; border-radius:5px; font-size:8.5px; font-weight:700; letter-spacing:.12em; color:#8c8178; cursor:pointer }
  .seg span:hover { color:#e6dcd2 } .seg .on { background:rgba(255,255,255,.08); color:#fff7ee }
  .vpn { font-size:8.5px; font-weight:700; letter-spacing:.1em; padding:2px 6px; border-radius:5px; margin-right:6px; vertical-align:middle;
         color:#4ade80; background:rgba(74,222,128,.12) }
  .link { padding:4px 22px 0 }
  .row { display:grid; grid-template-columns: 50px 1fr auto; align-items:baseline; padding:6px 0 7px; border-top:1px solid rgba(255,255,255,.05) }
  .row:first-child { border-top:none }
  .k { font-size:9px; font-weight:700; letter-spacing:.14em; color:#8c8178 }
  .v { font-size:13px; color:#f3ece6; white-space:nowrap; overflow:hidden; text-overflow:ellipsis }
  .v small { font-size:10px; color:#8c8178; margin-left:2px }
  .d { grid-column: 2 / span 2; font-size:10.5px; color:#8c8178; margin-top:2px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis }
  .bars { display:inline-flex; align-items:flex-end; gap:2px; height:11px; margin-right:6px }
  .bars i { width:3px; border-radius:1px; background:rgba(255,255,255,.12) }
  .r { font-size:10.5px; color:#a39a92; text-align:right }
  .go { margin-left:6px; padding:1px 6px; border-radius:5px; background:rgba(255,255,255,.06); color:#e6dcd2; cursor:pointer }
  .go:hover { background:rgba(255,255,255,.12) } .go.busy { color:#ffb35c; cursor:default }
`;
// ring around the HUB (order set in network.sh); side nodes put their labels below, anchored inward so they stay
// inside the svg; the last two sit top/bottom centre, so they get the short names
const NODES = [[36, 24], [164, 24], [14, 70], [186, 70], [36, 116], [164, 116], [100, 26], [100, 114]];
const savedView = () => { try { return localStorage.getItem("conn-view") || "LIVE"; } catch (e) { return "LIVE"; } };
export const initialState = { output: "", view: savedView() };
export const updateState = (ev, prev) => ev.type === "VIEW" ? { ...prev, view: ev.view }
  : ev.type === "VPN" ? { ...prev, vpnBusy: ev.busy }
  : ev.type === "SPEED" ? { ...prev, speed: ev.speed, testing: ev.testing } : { ...prev, output: ev.output, error: ev.error };
const problem = n => (window.__offline = n.ip === "offline" || n.services.every(x => !x.ms)) ? "No internet" : null;
// per-service [amber from, red from] in ms, set from how each one reaches Nairobi (measured 2026-10-04, DNS + TCP connect):
// Meta, TikTok and Google sit on edge caches in Kenya (~20ms); Apple and Netflix are local too but their DNS takes
// longer (~70ms); Claude's edge and GitHub's Johannesburg servers are ~70ms; Yahoo comes from London (~145ms).
// Amber is about 2x a service's normal time and red about 5x; services not listed use the default.
const LIMITS = { Meta: [90, 250], TikTok: [90, 250], Google: [90, 250], Apple: [150, 400], Netflix: [150, 400],
                 Claude: [150, 400], GitHub: [150, 400], Yahoo: [300, 750] }, LIMIT = [150, 450];
const lim = s => LIMITS[s.name] || LIMIT;
const weak = s => !s.ms || s.ms >= lim(s)[0];   // amber, red or down: the link flickers and throws sparks
// a few sparks per weak link, spraying out from the node and from the middle of the line; fixed angles so they don't jump on refresh
const sparks = (x, y, c, k) => [0, 1, 2, 3, 4, 5, 6, 7, 8].map(j => {
  const mid = j > 5, px = mid ? (x + 100) / 2 : x, py = mid ? (y + 70) / 2 : y;
  const a = (j * 2.4 + k * 1.3), r = 12 + ((j * 7 + k * 3) % 12);
  return <circle key={"s" + k + "-" + j} className="spark" cx={px} cy={py} r={j % 2 ? 1.3 : 1.9} fill={j % 3 ? c : "#fff3d6"}
    style={{ "--dx": (Math.cos(a) * r).toFixed(1) + "px", "--dy": (Math.sin(a) * r).toFixed(1) + "px",
             "--t": (0.7 + (j % 3) * 0.25) + "s", "--d": (j * 0.17 + k * 0.11).toFixed(2) + "s",
             filter: `drop-shadow(0 0 2px ${c})` }} />; });
// the hub keeps reaching out to a down service: a line stretches 70% of the way, stalls, flickers out and tries again
const reach = (x, y, c, k) => { const L = Math.hypot(x - 100, y - 70), r = .7, d = (k * 0.37).toFixed(2) + "s";
  return <g key={"r" + k}>
    <line className="reach" x1="100" y1="70" x2={x} y2={y} stroke={c} strokeWidth="1.3" strokeLinecap="round"
      strokeDasharray={`${(L * r).toFixed(1)} ${L.toFixed(1)}`} style={{ "--o": (L * r).toFixed(1) + "px", "--d": d }} />
    <circle className="fizz" cx={100 + (x - 100) * r} cy={70 + (y - 70) * r} r="2" fill={c} style={{ "--d": d, filter: `drop-shadow(0 0 3px ${c})` }} />
  </g>; };
// a burning service: smoke, three flickering flame tongues and embers drifting up; fixed offsets so refreshes don't jump
const fire = (x, y, k) => <g key={"f" + k} transform={`translate(${x} ${y})`}>
  {[0, 1, 2].map(j => <circle key={"sm" + j} className="smoke" cx={(j - 1) * 2} cy="-6" r="4" fill="#4a4040"
    style={{ "--dx": ((j - 1) * 4 + (k % 3) - 1) + "px", "--t": (2.2 + j * 0.4) + "s", "--d": (j * 0.7 + k * 0.23).toFixed(2) + "s", filter: "blur(1.5px)" }} />)}
  {[[-3, 9, .8], [3, 10, .7], [0, 14, 1]].map(([dx, h, w], j) => <path key={"fl" + j} className="flame"
    d={`M${dx - 3.5 * w},1 C${dx - 4.5 * w},${-h * .45} ${dx - 1},${-h * .7} ${dx},${-h} C${dx + 1},${-h * .7} ${dx + 4.5 * w},${-h * .45} ${dx + 3.5 * w},1 Z`}
    fill="url(#flame)" style={{ "--t": (0.28 + j * 0.09 + (k % 3) * 0.04).toFixed(2) + "s", "--d": (j * 0.13 + k * 0.07).toFixed(2) + "s",
    filter: "drop-shadow(0 0 3px #ff6a2a)" }} />)}
  {[0, 1, 2, 3, 4].map(j => <circle key={"em" + j} className="ember" cx={((j * 5 + k * 3) % 9) - 4} cy="-4" r={j % 2 ? .9 : 1.3} fill={j % 2 ? "#ffd27a" : "#ff7a3a"}
    style={{ "--dx": (((j * 7 + k) % 11) - 5) + "px", "--t": (1 + (j % 3) * 0.35) + "s", "--d": (j * 0.27 + k * 0.19).toFixed(2) + "s",
    filter: "drop-shadow(0 0 2px #ff8a3a)" }} />)}
</g>;
const col = s => !s.ms ? "#6f665f" : s.ms < lim(s)[0] ? "#4ade80" : s.ms < lim(s)[1] ? "#ffb35c" : "#f87171";
const rate = b => b > 1048576 ? [(b / 1048576).toFixed(1), "MB/s"] : [(b / 1024).toFixed(0), "KB/s"];
const mbps = b => b >= 1e8 ? Math.round(b / 1e6) : (b / 1e6).toFixed(b >= 1e7 ? 0 : 1);
const hm = t => new Date(t * 1000).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" });
// signal: 4 bars ≥ -55 dBm, 3 ≥ -65, 2 ≥ -75, else 1
const bars = rssi => rssi >= -55 ? 4 : rssi >= -65 ? 3 : rssi >= -75 ? 2 : 1;
const sigCol = n => n >= 3 ? "#4ade80" : n === 2 ? "#ffb35c" : "#f87171";

// Nodes you can play with: grab one and its line stretches after it; let go and it springs home with a wobble; flick it and
// it flies off, bounces around the panel and comes back. A click without dragging pings that service once and shows the result.
// Offsets live outside React (window.__connPlay) and are written straight to the DOM, so refreshes don't fight a drag.
const PLAY = window.__connPlay || (window.__connPlay = { o: {}, run: {} });
const nodeXY = i => { const o = PLAY.o[i] || [0, 0]; return [NODES[i][0] + o[0], NODES[i][1] + o[1]]; };
const place = (svg, i) => { const o = PLAY.o[i] || [0, 0], [x, y] = nodeXY(i), far = Math.hypot(o[0], o[1]) > 2;
  const g = svg.querySelector(`.node[data-i="${i}"]`); if (g) g.setAttribute("transform", far ? `translate(${o[0].toFixed(1)} ${o[1].toFixed(1)})` : "");
  const l = svg.querySelector(`.ln[data-i="${i}"]`); if (l) { l.setAttribute("x2", x.toFixed(1)); l.setAttribute("y2", y.toFixed(1)); l.classList.toggle("taut", far); }
  svg.querySelectorAll(`.fx[data-i="${i}"]`).forEach(f => f.style.display = far ? "none" : ""); };   // sparks/reach stay put, so hide them while away
// the panel's inside, in svg units, so nodes can roam the whole panel but not leave it
const bounds = svg => { const m = svg.getScreenCTM(), sr = svg.getBoundingClientRect(), pr = (svg.closest(".widget") || svg).getBoundingClientRect();
  return [(pr.left - sr.left) / m.a + 8, (pr.top - sr.top) / m.d + 34, (pr.right - sr.left) / m.a - 8, (pr.bottom - sr.top) / m.d - 8]; };
// spring home (underdamped, so it overshoots and wobbles), bouncing off the panel edges; runs only while the node is moving
const fly = (svg, i, vx, vy) => { const id = PLAY.run[i] = (PLAY.run[i] || 0) + 1, [L, T, R, B] = bounds(svg); let t = performance.now();
  const step = now => { if (PLAY.run[i] !== id || !svg.isConnected) return;
    const dt = Math.min(.033, (now - t) / 1000); t = now; const o = PLAY.o[i] || [0, 0];
    vx += (-120 * o[0] - 9 * vx) * dt; vy += (-120 * o[1] - 9 * vy) * dt; o[0] += vx * dt; o[1] += vy * dt;
    const [x, y] = [NODES[i][0] + o[0], NODES[i][1] + o[1]];
    if (x < L || x > R) { o[0] = Math.max(L, Math.min(R, x)) - NODES[i][0]; vx *= -.7; }
    if (y < T || y > B) { o[1] = Math.max(T, Math.min(B, y)) - NODES[i][1]; vy *= -.7; }
    PLAY.o[i] = o; const done = Math.hypot(o[0], o[1]) < .3 && Math.hypot(vx, vy) < 4;
    if (done) PLAY.o[i] = [0, 0]; place(svg, i); if (!done) requestAnimationFrame(step); };
  requestAnimationFrame(step); };
// a packet runs out along the line, and back in the service's colour once the ping answers
const packet = (svg, i, toNode, colour) => new Promise(res => { const c = document.createElementNS("http://www.w3.org/2000/svg", "circle");
  c.setAttribute("r", "2.4"); c.setAttribute("fill", colour); c.style.filter = `drop-shadow(0 0 3px ${colour})`; svg.appendChild(c); const t0 = performance.now();
  const step = now => { const k = Math.min(1, (now - t0) / 280), [x, y] = nodeXY(i), f = toNode ? k : 1 - k;
    c.setAttribute("cx", 100 + (x - 100) * f); c.setAttribute("cy", 70 + (y - 70) * f);
    if (k < 1) requestAnimationFrame(step); else { c.remove(); res(); } };
  requestAnimationFrame(step); });
const ping = async (svg, i, s) => { const g = svg.querySelector(`.node[data-i="${i}"]`); if (!g || g.dataset.busy) return; g.dataset.busy = 1;
  const out = await Promise.all([run(`%%PY%% ~/.stark/ping.py ${s.host}`).catch(() => "0"), packet(svg, i, true, "#fff3d6")]);
  const ms = parseInt(out[0]) || 0, colour = col({ ...s, ms }); await packet(svg, i, false, colour);
  const t = g.querySelector("tspan"); if (t) { t.textContent = ms ? ms + "ms" : "down"; t.setAttribute("fill", colour); }
  g.classList.remove("pinged"); void g.getBBox(); g.classList.add("pinged"); delete g.dataset.busy; };
const grab = (e, i, s) => { if (e.button) return; e.preventDefault(); e.stopPropagation();
  const g = e.currentTarget, svg = g.ownerSVGElement, m = svg.getScreenCTM(), [L, T, R, B] = bounds(svg);
  PLAY.run[i] = (PLAY.run[i] || 0) + 1;   // stop any spring already running on it
  const o0 = [...(PLAY.o[i] || [0, 0])], sx = e.clientX, sy = e.clientY; let moved = false, trail = [[performance.now(), sx, sy]];
  g.classList.add("held");
  const move = ev => { if (!ev.buttons) return up(ev);   // the release happened outside the panel
    const dx = (ev.clientX - sx) / m.a, dy = (ev.clientY - sy) / m.d; if (Math.hypot(dx, dy) > 3) moved = true;
    PLAY.o[i] = [Math.max(L, Math.min(R, NODES[i][0] + o0[0] + dx)) - NODES[i][0], Math.max(T, Math.min(B, NODES[i][1] + o0[1] + dy)) - NODES[i][1]];
    place(svg, i); trail.push([performance.now(), ev.clientX, ev.clientY]); if (trail.length > 6) trail.shift(); };
  const up = ev => { document.removeEventListener("mousemove", move); document.removeEventListener("mouseup", up); g.classList.remove("held");
    if (!moved) { fly(svg, i, 0, 0); return ping(svg, i, s); }
    const now = performance.now(), a = trail.find(p => now - p[0] < 90) || trail[trail.length - 1], dt = Math.max(.016, (now - a[0]) / 1000);
    fly(svg, i, (ev.clientX - a[1]) / m.a / dt, (ev.clientY - a[2]) / m.d / dt); };   // throw speed from the last ~90 ms
  document.addEventListener("mousemove", move); document.addEventListener("mouseup", up); };
const Live = ({ n }) => {
  const svcs = n ? n.services : [];
  // the hub pulses green when every link is fast, grey when exactly one service is down; a weak link turns it amber
  // and speeds it up, two or more down turn it red, any down service burns, and if everything is down the whole panel goes red
  const down = svcs.filter(s => !s.ms).length, dead = svcs.length > 0 && (down === svcs.length || n.ip === "offline");
  const alert = svcs.some(s => s.ms && weak(s)) || down > 1, ok = svcs.length > 0 && !alert && down <= 1;
  const hub = dead || down > 1 ? "#f87171" : ok ? (down ? "#a39a92" : "#4ade80") : "#ffb35c", c = s => dead ? "#f87171" : col(s);
  const [dv, du] = n ? rate(n.down) : ["—", ""], [uv, uu] = n ? rate(n.up) : ["—", ""];
  return (
    <div className="body">
      <svg className="live" width="236" height="165" viewBox="0 0 200 140" style={{ overflow: "visible" }}>
        <defs><linearGradient id="flame" x1="0" y1="1" x2="0" y2="0">
          <stop offset="0" stopColor="#fff1b0" /><stop offset=".35" stopColor="#ffb340" /><stop offset=".7" stopColor="#ff5a24" /><stop offset="1" stopColor="#d9261c" stopOpacity="0" />
        </linearGradient></defs>
        {svcs.slice(0, NODES.length).map((s, i) => !s.ms ? null : <line key={"l" + i} data-i={i} className={"ln " + (weak(s) ? "flow weak" : "flow")} x1="100" y1="70" x2={nodeXY(i)[0]} y2={nodeXY(i)[1]} stroke={c(s)} strokeWidth="1.3" strokeOpacity=".8" />)}
        {svcs.slice(0, NODES.length).map((s, i) => s.ms ? null : <g key={"rf" + i} className="fx" data-i={i}>{reach(NODES[i][0], NODES[i][1], dead ? "#f87171" : "#a39a92", i)}</g>)}
        {svcs.slice(0, NODES.length).map((s, i) => weak(s) ? <g key={"sf" + i} className="fx" data-i={i}>{sparks(NODES[i][0], NODES[i][1], c(s), i)}</g> : null)}
        {dead && [8, 9, 10].map(k => sparks(100, 70, "#f87171", k))}
        <g className={"hub" + (alert || dead ? " alert" : ok ? " ok" : "")} style={{ "--hub": hub }}>
          <circle className="wave" cx="100" cy="70" r="16" fill="none" stroke={hub} strokeWidth="1" />
          <circle className="wave b" cx="100" cy="70" r="16" fill="none" stroke={hub} strokeWidth="1" />
          <circle className="ring" cx="100" cy="70" r="16" fill="rgba(36,27,22,1)" stroke={hub} strokeWidth="1.3" />
          <text x="100" y="73.5" textAnchor="middle" fontSize="7.5" fontWeight="700" fill={hub} letterSpacing=".8" fontFamily="Orbitron">HUB</text>
        </g>
        {svcs.slice(0, NODES.length).map((s, i) => { const [x, y] = NODES[i], side = y === 70 ? (x < 100 ? -1 : 1) : 0; return (
          <g key={s.name} className="node" data-i={i} onMouseDown={e => grab(e, i, s)}>
            <circle cx={x} cy={y} r="11" fill="transparent" />
            <circle className={"dot " + (s.ms ? "pulse" : "char")} cx={x} cy={y} r="4.5" fill={s.ms ? c(s) : "#2a1512"} stroke={s.ms ? "none" : "#ff5a24"} strokeWidth="1.2"
              style={{ filter: `drop-shadow(0 0 4px ${s.ms ? c(s) : "#ff5a24"})` }} />
            {!s.ms && fire(x, y, i)}
            <text x={side ? x + side * 10 : x} y={y > 70 || side ? y + 16 : y - 9} textAnchor={side < 0 ? "start" : side > 0 ? "end" : "middle"} fontSize="9" fill={dead ? "#f87171" : "#d9cfc6"}>{s.name} <tspan fill={c(s)}>{s.ms ? s.ms + "ms" : "down"}</tspan></text>
          </g>); })}
      </svg>
      <div className="rates num" style={dead ? { color: "#f87171" } : null}>
        <div className="rl">DOWN</div><div className="rate up" style={dead ? { color: "#f87171" } : null}>↓ {dv}<small>{du}</small></div>
        <div className="rl">UP</div><div className="rate" style={{ color: dead ? "#f87171" : "#7fdcff" }}>↑ {uv}<small>{uu}</small></div>
        {n && <div className="lip">{n.dev.toUpperCase()} · {n.ip}</div>}
      </div>
    </div>
  );
};

const Link = ({ n, speed, testing, test, busy, setVpn }) => {
  const w = (n && n.wifi) || {}, v = n && n.vpn, p = n && n.pub, onWifi = w.rssi !== undefined && w.rssi !== 0;
  const t = n && n.tor, failed = t && t.state.startsWith("failed") ? t.state.replace(/^failed: */, "") : null;
  const going = busy || (t && t.state === "connecting" && t.cc);   // also when started from the terminal
  const sel = going || (t && t.state === "on" ? t.cc : "off");
  const b = onWifi ? bars(w.rssi) : 0;
  return (
    <div className="link">
      <div className="row">
        <span className="k">WI‑FI</span>
        {onWifi ? <span className="v" title={w.ssid ? "" : "macOS hides the network name. Create a Shortcuts shortcut named \"Wi-Fi Name\" with Get Network Details."}>
            {w.ssid || <span className="muted">Name hidden</span>}</span>
          : <span className="v muted">{n && n.dev !== "en0" ? "Using " + n.dev.toUpperCase() : "Not connected"}</span>}
        {onWifi ? <span className="r num"><span className="bars">{[5, 7, 9, 11].map((h, i) =>
            <i key={i} style={{ height: h, background: i < b ? sigCol(b) : undefined }} />)}</span>{w.rssi} dBm</span> : <span />}
        {onWifi && <span className="d num">Ch {w.ch} · {w.band} GHz{w.width ? " · " + w.width + " MHz" : ""}{w.phy ? " · Wi‑Fi " + w.phy : ""} · {w.rate} Mbps link</span>}
      </div>
      <div className="row">
        <span className="k">VPN</span>
        <span className="v">{going ? <span><span className="pulse" style={{ color: "#ffb35c" }}>●</span> {going === "off" ? "Stopping" : "Connecting"}…</span>
          : v && v.tor ? <span><span className="up">●</span> {v.cc.toUpperCase()}<small>via Tor</small></span>
          : v ? <span><span className="up">●</span> {v.name}<small>{v.full ? "all traffic" : "split tunnel"}</small></span>
          : failed ? <span><span className="dn">●</span> Failed</span>
          : <span><span className="dim">●</span> <span className="muted">Off</span></span>}</span>
        <span className="r"><span className="seg">{["off", "us", "uk"].map(c => <span key={c} className={sel === c ? "on" : ""}
          title={c === "off" ? "Disconnect" : "Route browsers and apps out of " + c.toUpperCase() + " (free, via Tor; slower than a paid VPN)"}
          onClick={() => setVpn(c)}>{c.toUpperCase()}</span>)}</span></span>
        <span className="d num">{failed && !going ? <span className="dn">{failed}</span> : p ? (v ? "Exit " : "Public ") + p.ip + " · " + [p.city, p.cc].filter(Boolean).join(", ") + (p.isp ? " · " + p.isp : "") : "Public IP unknown"}</span>
      </div>
      <div className="row">
        <span className="k">SPEED</span>
        <span className="v num">{speed ? <span><span className="up">↓ {mbps(speed.down)}</span><small>Mbps</small>&nbsp;&nbsp;
          <span style={{ color: "#7fdcff" }}>↑ {mbps(speed.up)}</span><small>Mbps</small></span> : <span className="muted">No test yet</span>}</span>
        <span className="r num">{speed ? hm(speed.at) : ""}
          <span className={"go" + (testing ? " busy" : "")} title="Run a speed test now (~150 MB)" onClick={testing ? null : test}>{testing ? "testing…" : "↻"}</span></span>
        {speed && <span className="d num">Idle ping {speed.rtt} ms{speed.rpm ? " · under load " + Math.round(60000 / speed.rpm) + " ms" : ""}</span>}
      </div>
    </div>
  );
};

export const render = ({ output, view, speed: mine, testing: busy, vpnBusy }, dispatch) => {
  let n = null; try { n = JSON.parse(output); } catch (e) {}
  const pick = v => { try { localStorage.setItem("conn-view", v); } catch (e) {} dispatch({ type: "VIEW", view: v }); };
  // a test started from the button wins until the regular refresh has a newer result
  const speed = mine && (!n || !n.speed || mine.at >= n.speed.at) ? mine : n && n.speed;
  const testing = busy || !!(n && n.testing);
  const test = () => { dispatch({ type: "SPEED", speed, testing: true });
    run("~/.stark/speedtest.sh now; cat ~/.stark/.speed.json").then(out => {
      let s = speed; try { s = JSON.parse(out); } catch (e) {} dispatch({ type: "SPEED", speed: s, testing: false }); }); };
  // connecting takes ~10 s (Tor starts and the exit country is checked); then refresh straight away
  const setVpn = c => { if (vpnBusy) return; dispatch({ type: "VPN", busy: c });
    run(`~/.stark/vpn.sh ${c} >/dev/null; ~/.stark/network.sh`).then(out => dispatch({ type: "NET", output: out }))
      .catch(() => {}).then(() => dispatch({ type: "VPN", busy: null })); };
  return (
    <div>
      <header><span style={{ color: "#ffb35c" }}>⟡</span><h1>CONNECTIONS</h1>
        <span className="sub">{n && n.vpn && <span className="vpn" title={n.vpn.name}>VPN{n.vpn.tor ? " " + n.vpn.cc.toUpperCase() : ""}</span>}
          <span className="seg">{["LIVE", "LINK"].map(v => <span key={v} className={view === v ? "on" : ""} onClick={() => pick(v)}>{v}</span>)}</span></span></header>
      {view === "LINK" ? <Link n={n} speed={speed} testing={testing} test={test} busy={vpnBusy} setVpn={setVpn} /> : <Live n={n} />}
    </div>
  );
};''')

# ───────────────────────── BATCAVE ─────────────────────────
widget("batcave", r'''// Batcave: git projects (click to open in VS Code) + your own 12-week commit activity (see batcave.sh).
import { run } from "uebersicht";
export const command = "~/.stark/batcave.sh";
export const refreshFrequency = 60 * 1000;
export const className = `
  %%POS%%%%SHARED%%
  .list { padding:8px 10px 0 }
  .row { display:grid; grid-template-columns: 10px 1fr auto 30px; align-items:center; gap:10px; height:36px; padding:0 9px; border-radius:8px; cursor:pointer }
  .row:hover { background:rgba(255,179,92,.08) } .row:hover .name { color:#ffb35c }
  .dot { width:7px; height:7px; border-radius:50% }
  .name { font-weight:600; font-size:12.5px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis }
  .name i { font-style:normal; color:#ffb35c; font-size:10px; margin-left:6px; font-weight:500 }
  .br { font:10px "SF Mono", Menlo, monospace; color:#d9b48a; background:rgba(255,179,92,.07); border:1px solid rgba(255,179,92,.14); border-radius:5px; padding:1px 6px; max-width:130px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis }
  .ago { text-align:right; color:#6f665f; font-size:10.5px }
  .act { display:flex; gap:16px; margin:10px 16px 0; padding-top:12px; border-top:1px solid rgba(255,214,170,.08) }
  .hm { display:grid; grid-template-rows: repeat(7, 13px); grid-auto-flow: column; grid-auto-columns: 13px; gap:3px; margin-top:8px }
  .hm i { border-radius:3px }
  .stats { flex:1; display:flex; flex-direction:column; justify-content:flex-end; gap:9px; padding-bottom:2px }
  .st b { display:block; font: 200 22px -apple-system, sans-serif; color:#ffffff; line-height:1.1 }
  .st span { font-size:9.5px; letter-spacing:.14em; color:#8c8178; font-weight:600 }
`;
const half = [[0,-30],[18,-60],[22,-22],[60,-34],[140,-80],[250,-70],[330,-20],[300,-10],[270,15],[230,10],[200,40],[150,25],[110,55],[70,30],[30,40],[0,90]];
const bat = half.concat(half.slice(0, -1).reverse().map(([x, y]) => [-x, y])).map(([x, y]) => `${x},${y}`).join(" ");
const ago = ts => { if (!ts) return "—"; const m = (Date.now() / 1000 - ts) / 60;
  return m < 60 ? `${Math.round(m)}m` : m < 1440 ? `${Math.round(m / 60)}h` : m < 43200 ? `${Math.round(m / 1440)}d` : `${Math.round(m / 10080)}w`; };
const shade = n => !n ? "rgba(255,214,170,.06)" : n < 2 ? "rgba(255,179,92,.3)" : n < 4 ? "rgba(255,179,92,.55)" : n < 7 ? "rgba(255,179,92,.8)" : "#ffb35c";
const iso = d => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
export const render = ({ output }) => {
  let data = { repos: [], activity: {} }; try { data = JSON.parse(output); } catch (e) {}
  const repos = data.repos.sort((a, b) => b.ts - a.ts), active = repos.filter(r => r.dirty).length;
  // 12 weeks of cells, columns are weeks starting Sunday, ending this week
  const today = new Date(), start = new Date(today); start.setDate(today.getDate() - today.getDay() - 77);
  const cells = []; let total = 0;
  for (let i = 0; i < 84; i++) {
    const d = new Date(start); d.setDate(start.getDate() + i);
    const n = d > today ? null : (data.activity[iso(d)] || 0); if (n) total += n; cells.push(n);
  }
  // streak: consecutive days with commits, ending today (or yesterday if nothing yet today)
  let streak = 0; const d = new Date(today);
  if (!data.activity[iso(d)]) d.setDate(d.getDate() - 1);
  while (data.activity[iso(d)] && streak < 365) { streak++; d.setDate(d.getDate() - 1); }
  return (
    <div>
      <header><svg width="28" height="13" viewBox="-340 -90 680 190"><polygon points={bat} fill="#ffb35c" /></svg>
        <h1>BATCAVE</h1><span className="sub" title="Uncommitted repos · your commits in the last 12 weeks"><b>{active}</b> ACTIVE · <b>{total}</b> COMMITS</span></header>
      <div className="list">
        {repos.slice(0, 6).map(r => (
          <div className="row" key={r.path} onClick={() => run(`open -a "Visual Studio Code" "${r.path}"`)}>
            <span className="dot" style={{ background: r.dirty ? "#ffb35c" : "#4a403a", boxShadow: r.dirty ? "0 0 8px #ffb35c" : "none" }} />
            <span className="name">{r.name}{r.dirty > 0 && <i>✎ {r.dirty}</i>}</span>
            <span className="br">{r.branch || "—"}</span>
            <span className="ago num">{ago(r.ts)}</span>
          </div>))}
      </div>
    </div>
  );
};''')

# ───────────────────────── CHESS PUZZLE ─────────────────────────
widget("puzzle", r'''// Playable Lichess puzzle (daily, or a fresh one on demand; see puzzle.py). Drag or click a piece to move it.
// The opponent answers on its own; a wrong move snaps back. Solved count and streak are remembered on this Mac.
import { run } from "uebersicht";
export const command = "%%PY%% ~/.stark/puzzle.py";
export const refreshFrequency = 10 * 60 * 1000;  // only picks up a new daily puzzle; moves happen locally
export const className = `
  %%POS%%%%SHARED%%
  .wrap { display:flex; gap:20px; padding:4px 20px 0 }
  %%BOARDCSS%%
  .board { width:352px; height:352px; flex:none }
  .side { flex:1; min-width:0; display:flex; flex-direction:column }
  .rt { font: 200 34px -apple-system, "SF Pro Display", sans-serif; line-height:1.1; color:#fff7ee; margin-top:3px }
  .turn { display:flex; align-items:center; gap:8px; margin-top:14px; font-size:13px; color:#e6dcd2 }
  .turn i { width:12px; height:12px; border-radius:50%; flex:none; border:1px solid rgba(255,255,255,.35) }
  .msg { min-height:34px; margin-top:6px; font-size:11.5px; line-height:1.45; color:#8c8178 }
  .msg.ok { color:#4ade80 } .msg.bad { color:#f87171 } .msg.win { color:#ffb35c; font-weight:600 }
  .chips { display:flex; flex-wrap:wrap; gap:5px; margin-top:4px }
  .chip { font-size:9.5px; padding:2px 7px; border-radius:5px; color:#b8aea4; background:rgba(255,255,255,.05); white-space:nowrap }
  .stats { display:flex; justify-content:space-between; margin-top:auto; padding-top:10px }
  .stats .v { font: 300 20px -apple-system, "SF Pro Display", sans-serif; color:#fff7ee }
  .btns { display:grid; grid-template-columns: 1fr 1fr; gap:6px; margin:12px 0 14px }
  .btn { height:28px; border-radius:8px; display:grid; place-items:center; cursor:pointer; font-size:9.5px; font-weight:700; letter-spacing:.12em;
         color:#d9cfc6; background:rgba(255,255,255,.06); border:1px solid rgba(255,255,255,.06) }
  .btn:hover { background:rgba(255,255,255,.11); color:#fff7ee }
  .btn.wide { grid-column: 1 / span 2 }
  .btn.main { grid-column: 1 / span 2; color:#241b16; background:#ffb35c; border-color:transparent }
  .btn.main:hover { background:#ffc47e; color:#241b16 }
  .btn.busy { opacity:.5 }
  .empty { padding:120px 20px 0; text-align:center; color:#8c8178 }
`;
%%CHESS%%
const THEMES = { mateIn1: "Mate in 1", mateIn2: "Mate in 2", mateIn3: "Mate in 3", mateIn4: "Mate in 4", mateIn5: "Mate in 5+" };
const hide = new Set(["short", "long", "veryLong", "oneMove", "master", "masterVsMaster", "superGM", "middlegame", "opening", "endgame", "crushing", "advantage", "equality"]);
const theme = t => THEMES[t] || t.replace(/([A-Z])/g, " $1").replace(/^./, c => c.toUpperCase());
const store = (k, v) => { try { if (v === undefined) return JSON.parse(localStorage.getItem(k) || "null"); localStorage.setItem(k, JSON.stringify(v)); } catch (e) {} };
const blank = { ply: 0, sel: null, msg: "", tone: "", done: false, shown: false, hint: null, end: null, missed: false };
export const initialState = { output: "", ...blank };
export const updateState = (ev, s) => {
  if (ev.type === "MOVE" || ev.type === "SET") return { ...s, ...ev.set };
  if (ev.type === "UB/COMMAND_RAN" || ev.output !== undefined) {
    let id = null; try { id = JSON.parse(ev.output).id; } catch (e) {}
    let was = null; try { was = JSON.parse(s.output).id; } catch (e) {}
    if (id && id !== was) {  // new puzzle: start over, or resume where you were after a restart
      const p = store("chess-progress"); return { ...s, ...blank, ...(p && p.id === id ? p.st : {}), output: ev.output, error: ev.error };
    }
    return { ...s, output: ev.output, error: ev.error };
  }
  return s;
};
const loadNew = (dispatch, what) => {
  if (window.__pzBusy) return; window.__pzBusy = 1; dispatch({ type: "SET", set: { msg: "Loading a new puzzle…", tone: "" } });
  run("%%PY%% ~/.stark/puzzle.py " + what).then(out => { window.__pzBusy = 0; dispatch({ type: "UB/COMMAND_RAN", output: out }); })
    .catch(() => { window.__pzBusy = 0; dispatch({ type: "SET", set: { msg: "Couldn't reach Lichess.", tone: "bad" } }); });
};
export const render = (s, dispatch) => {
  let p = null; try { p = JSON.parse(s.output); } catch (e) {}
  if (!p || !p.fens) return <div><header><span style={{ color: "#ffb35c" }}>♞</span><h1>CHESS PUZZLE</h1></header>
    <div className="empty">{p ? "Couldn't load a puzzle." : "Setting up the board…"}</div></div>;
  const stats = store("chess-stats") || { solved: 0, streak: 0, best: 0, seen: [] };
  const flip = p.color === "b", mine = s.ply % 2 === 0 && !s.done;
  const fen = s.end || p.fens[Math.min(s.ply, p.fens.length - 1)];
  const lm = s.ply ? (s.endMove || p.sol[s.ply - 1]) : p.last;
  const legal = mine ? p.legal[s.ply / 2] || {} : {};
  const set = st => { store("chess-progress", { id: p.id, st: { ply: st.ply ?? s.ply, done: st.done ?? s.done, shown: st.shown ?? s.shown,
    missed: st.missed ?? s.missed, end: st.end ?? s.end, endMove: st.endMove ?? s.endMove } }); dispatch({ type: "SET", set: st }); };
  const finish = (won, extra) => {
    if (!stats.seen.includes(p.id)) {  // each puzzle counts once
      stats.seen = [...stats.seen, p.id].slice(-200);
      if (won) { stats.solved++; stats.streak++; stats.best = Math.max(stats.best, stats.streak); } else stats.streak = 0;
      store("chess-stats", stats);
    }
    set({ done: true, sel: null, hint: null, ...extra });
  };
  const reply = ply => setTimeout(() => {   // the opponent answers after a beat
    if (ply + 1 >= p.sol.length) return;
    set({ ply: ply + 1, msg: "Best move! Keep going.", tone: "ok" }); }, 480);
  const tryMove = (from, to) => {
    if (!(legal[from] || []).includes(to)) return false;
    const want = p.sol[s.ply], last = s.ply === p.sol.length - 1;
    if (want.startsWith(from + to)) {
      if (last) finish(!s.missed && !s.shown, { ply: s.ply + 1, msg: s.missed ? "Solved, with a slip." : "Solved! ★", tone: "win" });
      else { set({ ply: s.ply + 1, sel: null, hint: null, msg: "", tone: "" }); reply(s.ply + 1); }
      return true;
    }
    const mate = last && p.mates.find(m => m.startsWith(from + to));
    if (mate) { finish(!s.missed && !s.shown, { ply: s.ply + 1, end: applyUci(fen, mate), endMove: mate, msg: "Checkmate! Solved ★", tone: "win" }); return true; }
    if (!s.missed && !stats.seen.includes(p.id)) { stats.streak = 0; store("chess-stats", stats); }
    set({ sel: null, hint: null, missed: true, msg: "Not the move. Try again.", tone: "bad", bad: to + Date.now() });
    return true;
  };
  const showSolution = () => {
    if (s.done) return; finish(false, { shown: true, msg: "Here's the solution.", tone: "" });
    let ply = s.ply; const step = () => { if (ply >= p.sol.length) return; ply++; set({ ply, done: true, shown: true }); setTimeout(step, 700); };
    setTimeout(step, 200);
  };
  const hint = () => { if (mine) set({ hint: p.sol[s.ply].slice(0, 2), sel: null, msg: "Move the highlighted piece.", tone: "" }); };
  const tags = p.themes.filter(t => !hide.has(t)).slice(0, 4);
  const mate = p.themes.find(t => THEMES[t]);
  const side = flip ? "Black" : "White";
  return (
    <div>
      <header><span style={{ color: "#ffb35c" }}>♞</span><h1>CHESS PUZZLE</h1>
        <span className="sub">{p.daily ? <b>DAILY</b> : "PUZZLE"} · {mate ? theme(mate).toUpperCase() : "FIND THE BEST LINE"} · {(p.plays / 1000).toFixed(0)}K PLAYS</span></header>
      <div className="wrap">
        <Board fen={fen} flip={flip} size={352} lm={lm} sel={s.sel} hint={s.hint} bad={s.bad} targets={s.sel ? legal[s.sel] || [] : []}
          movable={sq => mine && !!legal[sq]} onSelect={sq => set({ sel: sq })} onMove={tryMove} />
        <div className="side">
          <div className="lbl">PUZZLE RATING</div>
          <div className="rt num">{p.rating}</div>
          <div className="turn"><i style={{ background: flip ? "#16120f" : "#f3ece6" }} />
            {s.done ? (s.tone === "win" ? "Puzzle solved" : "Puzzle over") : mine ? side + " to move" : "Opponent replies…"}</div>
          <div className={"msg " + s.tone}>{s.msg || (s.done ? "" : "Find the best move for " + side.toLowerCase() + ".")}</div>
          <div className="chips">{tags.map(t => <span className="chip" key={t}>{theme(t)}</span>)}</div>
          <div className="stats">
            <div><div className="lbl">SOLVED</div><div className="v num">{stats.solved}</div></div>
            <div><div className="lbl">STREAK</div><div className="v num">{stats.streak}</div></div>
            <div><div className="lbl">BEST</div><div className="v num">{stats.best}</div></div>
          </div>
          <div className="btns">
            {s.done ? <span className="btn main" onClick={() => loadNew(dispatch, "next")}>NEXT PUZZLE ›</span>
              : <span className="btn" onClick={hint}>HINT</span>}
            {s.done ? <span className="btn" onClick={() => run(`open "${p.url}"`)}>LICHESS ↗</span>
              : <span className="btn" onClick={showSolution}>SOLUTION</span>}
            {s.done ? <span className="btn" onClick={() => loadNew(dispatch, "daily")}>DAILY</span>
              : <span className="btn wide" onClick={() => loadNew(dispatch, "next")}>SKIP ›</span>}
          </div>
        </div>
      </div>
    </div>
  );
};''')

# ───────────────────────── ANIME ─────────────────────────
widget("anime", r'''// Anime from AniList (anime.py): episodes airing around now with countdowns, and what's trending this season.
// Click a show to open it on AniList.
import { run } from "uebersicht";
export const command = "%%PY%% ~/.stark/anime.py";
export const refreshFrequency = 60 * 1000;  // countdowns tick each minute; the script only refetches every 15 min
export const className = `
  %%POS%%%%SHARED%%
  .hero { display:flex; gap:16px; margin:2px 20px 10px; padding:12px; border-radius:14px; cursor:pointer;
          background:rgba(255,255,255,.035); border:1px solid rgba(255,255,255,.06); position:relative; overflow:hidden }
  .hero:hover { background:rgba(255,255,255,.06) }
  .hero .bg { position:absolute; inset:0; opacity:.16; filter:blur(26px) saturate(140%); background-size:cover; background-position:center }
  .hero img { width:76px; height:106px; border-radius:9px; object-fit:cover; flex:none; position:relative; box-shadow:0 8px 20px rgba(0,0,0,.4) }
  .hero .info { position:relative; min-width:0; display:flex; flex-direction:column }
  .hero .ttl { font-size:16px; font-weight:600; color:#fff7ee; line-height:1.25; display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; overflow:hidden; margin-top:3px }
  .hero .ep { font-size:11.5px; color:#a39a92; margin-top:4px }
  .cd { font: 200 28px -apple-system, "SF Pro Display", sans-serif; color:#ffb35c; margin-top:auto; line-height:1 }
  .cd small { font-size:11px; color:#8c8178; margin-left:6px; font-weight:500 }
  .list { padding:0 10px }
  .row { display:grid; grid-template-columns: 24px 1fr auto; align-items:center; gap:11px; height:36px; padding:0 10px; border-radius:8px; cursor:pointer }
  .row:hover { background:rgba(255,179,92,.08) } .row:hover .nm { color:#fff7ee }
  .row img { width:24px; height:32px; border-radius:4px; object-fit:cover }
  .nm { min-width:0; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; font-size:12.5px; color:#e6dcd2 }
  .nm span { font-size:10.5px; color:#857d75; margin-left:7px }
  .when { font-size:10.5px; font-weight:600; padding:2px 7px; border-radius:5px; white-space:nowrap; color:#b8aea4; background:rgba(255,255,255,.05) }
  .when.soon { color:#ffb35c; background:rgba(255,179,92,.1) }
  .when.out { color:#4ade80; background:rgba(74,222,128,.1) }
  .grid { display:grid; grid-template-columns: repeat(4, 1fr); gap:10px; padding:2px 20px }
  .card { position:relative; height:176px; border-radius:11px; overflow:hidden; cursor:pointer; background:#1d1814 }
  .card img { width:100%; height:100%; object-fit:cover; transition: transform .3s }
  .card:hover img { transform: scale(1.05) }
  .card .ov { position:absolute; left:0; right:0; bottom:0; padding:28px 9px 8px; background:linear-gradient(transparent, rgba(10,8,6,.92)) }
  .card .ct { font-size:11.5px; font-weight:600; color:#fff7ee; line-height:1.25; display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; overflow:hidden }
  .card .cn { font-size:9.5px; color:#a39a92; margin-top:3px }
  .card .sc { position:absolute; top:7px; right:7px; font-size:10px; font-weight:700; padding:2px 6px; border-radius:5px; color:#241b16; background:#ffb35c }
  .card .rk { position:absolute; top:5px; left:8px; font: 700 16px -apple-system, sans-serif; color:#fff7ee }
  .empty { padding:120px 20px 0; text-align:center; color:#8c8178 }
  .seg { display:inline-flex; gap:2px; padding:2px; border-radius:7px; background:rgba(0,0,0,.18); vertical-align:middle }
  .seg span { padding:2px 7px; border-radius:5px; font-size:8.5px; font-weight:700; letter-spacing:.12em; color:#8c8178; cursor:pointer }
  .seg span:hover { color:#e6dcd2 } .seg .on { background:rgba(255,255,255,.08); color:#fff7ee }
`;
const savedTab = () => { try { return localStorage.getItem("anime-tab") || "AIRING"; } catch (e) { return "AIRING"; } };
export const initialState = { output: "", tab: savedTab() };
export const updateState = (ev, s) => ev.type === "TAB" ? { ...s, tab: ev.tab } : { ...s, output: ev.output, error: ev.error };
const left = at => at - Date.now() / 1000;
const span = sec => { const m = Math.round(Math.abs(sec) / 60);
  return m < 60 ? m + "m" : m < 1440 ? Math.floor(m / 60) + "h " + String(m % 60).padStart(2, "0") + "m" : Math.round(m / 1440) + "d"; };
const clock = at => new Date(at * 1000).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" });
const day = at => { const d = new Date(at * 1000), t = new Date(); return d.toDateString() === t.toDateString() ? "Today"
  : d.toDateString() === new Date(+t + 864e5).toDateString() ? "Tomorrow" : d.toLocaleDateString("en-GB", { weekday: "short" }); };
const open = u => run(`open "${u}"`);
export const render = ({ output, tab }, dispatch) => {
  let a = null; try { a = JSON.parse(output); } catch (e) {}
  const pick = t => { try { localStorage.setItem("anime-tab", t); } catch (e) {} dispatch({ type: "TAB", tab: t }); };
  const air = (a && a.air) || [], soon = air.filter(x => left(x.at) > 0), out = air.filter(x => left(x.at) <= 0);
  // the hero is the most-followed show still to air in the next 24 h (else the next one at all)
  const near = soon.filter(x => left(x.at) < 24 * 3600), hero = near.length ? near.reduce((b, x) => x.fans > b.fans ? x : b) : soon[0];
  // then what's next, with the biggest shows that just came out mixed in
  const rows = [...soon.filter(x => x !== hero).slice(0, 4), ...out.sort((x, y) => y.fans - x.fans).slice(0, 2)].sort((x, y) => x.at - y.at).slice(0, 6);
  const sub = soon.filter(x => left(x.at) < 86400).length;
  return (
    <div>
      <header><span style={{ color: "#ffb35c" }}>✦</span><h1>ANIME</h1>
        <span className="sub"><span className="seg">{["AIRING", "TRENDING"].map(t =>
          <span key={t} className={tab === t ? "on" : ""} onClick={() => pick(t)}>{t}</span>)}</span>
          {tab === "AIRING" && <span> · <b>{sub}</b> IN NEXT 24H</span>}</span></header>
      {!a ? <div className="empty">Checking the schedule…</div>
        : tab === "TRENDING" ? <div className="grid">
          {(a.hot || []).slice(0, 8).map((x, i) => <div className="card" key={x.id} onClick={() => open(x.url)}>
            <img src={x.cover} alt="" /><span className="rk">{i + 1}</span>{x.score && <span className="sc">{x.score}%</span>}
            <div className="ov"><div className="ct">{x.title}</div>
              <div className="cn">{x.next ? "EP " + x.next.episode + " in " + span(left(x.next.airingAt)) : (x.genres || []).slice(0, 2).join(" · ")}</div></div>
          </div>)}</div>
        : <div>
          {hero && <div className="hero" onClick={() => open(hero.url)}>
            <div className="bg" style={{ backgroundImage: `url(${hero.cover})` }} />
            <img src={hero.cover} alt="" />
            <div className="info">
              <div className="lbl" style={{ color: "#ffb35c" }}>NEXT UP</div>
              <div className="ttl">{hero.title}</div>
              <div className="ep">Episode {hero.ep}{hero.eps ? " of " + hero.eps : ""} · {day(hero.at)} {clock(hero.at)}{hero.score ? " · ★ " + hero.score + "%" : ""}</div>
              <div className="cd num">{span(left(hero.at))}<small>TO GO</small></div>
            </div></div>}
          <div className="list">
            {rows.map(x => { const t = left(x.at);
              return <div className="row" key={x.id + "-" + x.ep} onClick={() => open(x.url)}>
                <img src={x.cover} alt="" />
                <span className="nm">{x.title}<span>EP {x.ep}</span></span>
                <span className={"when" + (t <= 0 ? " out" : t < 3 * 3600 ? " soon" : "")}>{t <= 0 ? "Out " + span(t) + " ago" : day(x.at) + " " + clock(x.at)}</span>
              </div>; })}
          </div></div>}
    </div>
  );
};''')

# ───────────────────────── LICHESS TV ─────────────────────────
widget("chesstv", r'''// Lichess TV: the top-rated game being played right now, live. Click the board to watch it on Lichess.
import { run } from "uebersicht";
export const command = "/usr/bin/curl -sN --max-time 3 https://lichess.org/api/tv/feed | head -n 2 | paste -sd, - | sed 's/^/[/;s/$/]/'";
export const refreshFrequency = 3000;
export const className = `
  %%POS%%%%SHARED%%
  .wrap { display:flex; gap:16px; padding:2px 18px 0 }
  %%BOARDCSS%%
  .board { width:248px; height:248px; flex:none; cursor:pointer }
  .side { flex:1; min-width:0; display:flex; flex-direction:column; justify-content:space-between; padding:2px 0 }
  .pl .nm { font-size:12.5px; color:#e6dcd2; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; margin-top:3px }
  .pl .ti { font-size:9px; font-weight:800; color:#ffb35c; margin-right:5px }
  .pl .rt { font-size:10.5px; color:#857d75; margin-top:1px }
  .clk { display:inline-block; margin-top:6px; padding:3px 8px; border-radius:6px; font: 500 15px -apple-system, sans-serif;
         color:#a39a92; background:rgba(255,255,255,.05) }
  .clk.run { color:#241b16; background:#ffb35c }
  .clk.low.run { background:#f87171 }
  .live { display:flex; align-items:center; gap:7px; font-size:9px; font-weight:700; letter-spacing:.16em; color:#f87171 }
  .live i { width:7px; height:7px; border-radius:50%; background:#f87171; animation: lv 1.6s ease-in-out infinite }
  @keyframes lv { 50% { opacity:.3 } }
  .empty { padding:110px 20px 0; text-align:center; color:#8c8178 }
`;
%%CHESS%%
const fmtClk = s => { s = Math.max(0, Math.round(s)); return Math.floor(s / 60) + ":" + String(s % 60).padStart(2, "0"); };
// the running clock ticks locally between refreshes
clearInterval(window.__tvTick); window.__tvTick = setInterval(() => document.querySelectorAll(".clk.run[data-s]").forEach(el => {
  el.textContent = fmtClk(+el.dataset.s - (Date.now() - +el.dataset.t) / 1000); }), 1000);
export const render = ({ output }) => {
  let f = []; try { f = JSON.parse(output); } catch (e) {}
  const feat = f.find(x => x.t === "featured"), mv = [...f].reverse().find(x => x.t === "fen");
  if (!feat) return <div><header><span style={{ color: "#ffb35c" }}>♟</span><h1>LICHESS TV</h1></header><div className="empty">Tuning in…</div></div>;
  const g = feat.d, fen = mv ? mv.d.fen : g.fen, flip = g.orientation === "black", turn = fen.split(" ")[1];
  const P = c => { const p = g.players.find(x => x.color === c), sec = mv ? (c === "white" ? mv.d.wc : mv.d.bc) : p.seconds;
    return { ...p, sec, run: turn === c[0] }; };
  const [top, bot] = flip ? [P("white"), P("black")] : [P("black"), P("white")];
  const now = Date.now();
  const Pl = ({ p }) => <div className="pl">
    <div className="nm">{p.user.title && <span className="ti">{p.user.title}</span>}{p.user.name}</div>
    <div className="rt num">{p.rating}</div>
    <span className={"clk num" + (p.run ? " run" : "") + (p.sec < 20 ? " low" : "")} data-s={p.sec} data-t={now}>{fmtClk(p.sec)}</span></div>;
  return (
    <div>
      <header><span style={{ color: "#ffb35c" }}>♟</span><h1>LICHESS TV</h1>
        <span className="sub">TOP RATED · <b>{Math.round((top.rating + bot.rating) / 2)}</b> AVG</span></header>
      <div className="wrap">
        <div onClick={() => run(`open "https://lichess.org/${g.id}"`)}>
          <Board fen={fen} flip={flip} size={248} lm={mv ? mv.d.lm : null} coords={false} /></div>
        <div className="side">
          <Pl p={top} />
          <div className="live"><i />LIVE</div>
          <Pl p={bot} />
        </div>
      </div>
    </div>
  );
};''')


# ───────────────────────── CONNECTORS between panels ─────────────────────────
links = []
def h(x1, x2, y):
    y += DY
    links.append(f'<path className="flow" d="M {x1} {y} H {x2}" /><circle cx="{x1}" cy="{y}" r="2.5" /><circle cx="{x2}" cy="{y}" r="2.5" />')
def v(x, y1, y2):
    y1 += DY; y2 += DY
    links.append(f'<path className="flow" d="M {x} {y1} V {y2}" /><circle cx="{x}" cy="{y1}" r="2.5" /><circle cx="{x}" cy="{y2}" r="2.5" />')
for x in (L + 90, L + 310):                                             # left stack
    v(x, 286, 306); v(x, 626, 646)
for x in (C + 140, C + 426): v(x, 484, 504)                             # puzzle ↔ anime
for x in (R + 90, R + 310):                                             # right stack
    v(x, 332, 352); v(x, 682, 702)
h(432, 452, 171); h(432, 452, 466); h(432, 452, 789)                    # left column ↔ centre
h(1018, 1038, 194); h(1018, 1038, 517); h(1018, 1038, 817)              # centre ↔ right column
POS["aa-links"] = (0, 0, 0, 0)
widget("aa-links", '''// Glowing connectors between panels (file name sorts first so it draws behind them).
export const command = "true";
export const refreshFrequency = 60 * 1000;   // nothing to fetch; everything here runs on its own timers
const CURSOR_CSS = `
  #hud-aim { position:fixed; left:-14px; top:-14px; width:28px; height:28px; pointer-events:none; z-index:100000; display:none }
  #hud-aim.on { display:block }
  #hud-ring { position:fixed; left:0; top:0; width:0; height:0; pointer-events:none; z-index:99999; opacity:0; transition:opacity .25s }
  #hud-ring.on { opacity:1 }
  #hud-ring i, #hud-ring b { position:absolute; border-radius:50%; transition: all .22s ease }
  #hud-ring i { left:-18px; top:-18px; width:36px; height:36px; border:1px dashed rgba(62,232,255,.75);
                box-shadow: 0 0 12px rgba(62,232,255,.35), inset 0 0 10px rgba(62,232,255,.15); animation: hudspin 7s linear infinite }
  #hud-ring b { left:-11px; top:-11px; width:22px; height:22px; border:1.6px solid #3ee8ff; border-left-color:transparent; border-right-color:transparent;
                filter: drop-shadow(0 0 4px #3ee8ff); animation: hudspin 1.4s linear infinite reverse }
  #hud-ring.hot i { left:-25px; top:-25px; width:50px; height:50px; border-color:rgba(255,75,58,.9); box-shadow: 0 0 18px rgba(255,75,58,.5) }
  #hud-ring.hot b { border-top-color:#ff4b3a; border-bottom-color:#ff4b3a; filter: drop-shadow(0 0 5px #ff4b3a) }
  #hud-ring.grab i { border-radius:6px; border-style:solid; animation:none; transform: rotate(45deg) }
  #hud-ring.down b { left:-6px; top:-6px; width:12px; height:12px }
  @keyframes hudspin { to { transform: rotate(360deg) } }
  #hud-links { position:fixed; left:0; top:0; width:100%; height:100%; pointer-events:none; z-index:0; overflow:visible }
  #hud-links .l { fill:none; stroke:rgba(245,177,76,.22); stroke-width:1 }
  #hud-links .f { fill:none; stroke:#f5b14c; stroke-width:1.4; stroke-dasharray:3 9; animation: hudflow 1.6s linear infinite;
                  filter: drop-shadow(0 0 3px rgba(245,177,76,.9)) }
  #hud-links circle { fill:#f5b14c; filter: drop-shadow(0 0 4px #f5b14c); animation: hudpulse 2.6s ease-in-out infinite }
  #hud-cables { position:fixed; left:0; top:0; width:100%; height:100%; pointer-events:none; z-index:99990; overflow:visible }
  #hud-cables .l { fill:none; stroke-linecap:round; filter: drop-shadow(0 3px 4px rgba(0,0,0,.75)) }
  #hud-cables .f { fill:none; stroke:#ffd696; stroke-width:1.8; animation: hudflow .45s linear infinite; filter: drop-shadow(0 0 3px rgba(245,177,76,.9)) }
  #hud-cables circle { fill:#f5b14c; r:3.4px; filter: drop-shadow(0 0 5px #f5b14c) }
  @keyframes hudflow { to { stroke-dashoffset: -24 } }
  @keyframes hudpulse { 50% { opacity:.35 } }
  .hud-ripple { position:fixed; width:12px; height:12px; margin:-6px 0 0 -6px; border:2px solid #3ee8ff; border-radius:50%;
                pointer-events:none; z-index:99998; box-shadow: 0 0 10px #3ee8ff; animation: hudrip .65s ease-out forwards }
  .hud-ripple.hot { border-color:#ff4b3a; box-shadow: 0 0 10px #ff4b3a }
  @keyframes hudrip { to { transform: scale(7); opacity:0 } }
`;
const installCursor = () => {
  let st = document.getElementById("hud-style");
  if (!st) { st = document.createElement("style"); st.id = "hud-style"; document.head.appendChild(st); }
  st.textContent = CURSOR_CSS;
  if (window.__hudCursor === "%%BUILD%%") return; window.__hudCursor = "%%BUILD%%";
  if (window.__hudCursorOff) window.__hudCursorOff.abort(); const off = new AbortController(), on = { signal: off.signal };
  window.__hudCursorOff = off; document.querySelectorAll("#hud-ring, #hud-aim").forEach(n => n.remove());
  const aim = document.createElement("div"); aim.id = "hud-aim";
  aim.innerHTML = '<svg width="28" height="28" viewBox="0 0 28 28"><g fill="none" stroke="#f5b14c" stroke-width="1.6"><circle cx="14" cy="14" r="5.5"/>' +
    '<path d="M14 1v6M14 21v6M1 14h6M21 14h6"/></g><circle cx="14" cy="14" r="1.6" fill="#f5b14c"/></svg>';
  document.body.appendChild(aim);
  const ring = document.createElement("div"); ring.id = "hud-ring"; ring.innerHTML = "<i></i><b></b>"; document.body.appendChild(ring);
  let x = -200, y = -200, tx = -200, ty = -200, hot = false;
  document.addEventListener("mousemove", e => {
    tx = e.clientX; ty = e.clientY; ring.classList.add("on"); if (!running) { running = true; requestAnimationFrame(loop); }
    aim.style.transform = `translate(${tx}px, ${ty}px)`; aim.classList.toggle("on", !!(e.target.closest && e.target.closest(".widget")));
    const t = e.target.closest ? e.target.closest(".row,.tile,.it,.hero,.node,header") : null;
    hot = !!t && !t.matches("header");
    ring.classList.toggle("hot", hot); ring.classList.toggle("grab", !!t && t.matches("header"));
  }, on);

  document.addEventListener("mouseout", e => { if (!e.relatedTarget) { ring.classList.remove("on"); aim.classList.remove("on"); } }, on);
  document.addEventListener("mousedown", e => {
    ring.classList.add("down");
    const r = document.createElement("div"); r.className = "hud-ripple" + (hot ? " hot" : "");
    r.style.left = e.clientX + "px"; r.style.top = e.clientY + "px"; document.body.appendChild(r); setTimeout(() => r.remove(), 700);
  }, on);

  document.addEventListener("mouseup", () => ring.classList.remove("down"), on);
  // the ring eases after the mouse and stops redrawing once it has caught up (no 60 fps loop while the mouse is still)
  let running = false;
  const loop = () => { x += (tx - x) * 0.24; y += (ty - y) * 0.24; ring.style.transform = `translate(${x}px, ${y}px)`;
    running = window.__hudCursor === "%%BUILD%%" && Math.hypot(tx - x, ty - y) > .3; if (running) requestAnimationFrame(loop); };
};
// Three monkeys, each on its own schedule, that get around only by swinging: one swings in on a vine and catches the bottom
// edge of a top panel, swings hand over hand along it (stopping to hang and sway), then pumps a big swing, lets go and flies
// across to catch the edge of the next widget along or below, and finally swings away on a vine.
// Click a monkey to knock it off: it tumbles away and comes back about 30 s later. window.__monkeyNow() sends one in right away.
// With no internet they panic (red eyes, shaking) and bound off the nearest side of the screen, staying away until it's back.
const MONKEY_CSS = `
  #hud-monkey { position:fixed; left:0; top:0; width:100%; height:100%; z-index:99985; pointer-events:none; overflow:visible }
  #hud-monkey .vine { fill:none; stroke:#8f8064; stroke-width:1.4; stroke-linecap:round }
  #hud-monkey .mk { position:absolute; left:-20px; top:-20px; width:40px; height:40px; overflow:visible; pointer-events:auto; cursor:none; display:none;
                    filter: drop-shadow(0 1px 1.5px rgba(0,0,0,.65)) drop-shadow(0 0 2px rgba(242,237,230,.22)) }
  #hud-monkey .mk.on { display:block }
  #hud-monkey .mk > g { display:none }
  #hud-monkey .mk.hang .p-hang, #hud-monkey .mk.leap .p-leap { display:inline }
  #hud-monkey .fur { fill:#5e4e40; stroke:rgba(242,237,230,.7); stroke-width:.5 }
  #hud-monkey .face { fill:#d8c2a2 }
  #hud-monkey .eye { fill:#2a1d12 }
  #hud-monkey .lm { fill:none; stroke:#a8977f; stroke-width:1.8; stroke-linecap:round; stroke-linejoin:round; transform-box:view-box }
  #hud-monkey .far { opacity:.7 }
  #hud-monkey .tl { fill:none; stroke:#a8977f; stroke-width:1.3; stroke-linecap:round; transform-box:view-box }
  #hud-monkey .hang .a { animation: mka 1.1s ease-in-out infinite alternate }
  #hud-monkey .hang .b { animation: mkb 1.1s ease-in-out infinite alternate }
  #hud-monkey .hang .fa { animation: mkreach .6s ease-in-out infinite alternate }
  @keyframes mka { from { transform: rotate(-16deg) } to { transform: rotate(16deg) } }
  @keyframes mkb { from { transform: rotate(16deg) } to { transform: rotate(-16deg) } }
  @keyframes mkreach { from { transform: rotate(-25deg) } to { transform: rotate(20deg) } }
  #hud-monkey.panic .eye { fill:#ff3b2f }
  #hud-monkey.panic .mk .a { animation: mka .07s linear infinite alternate }
  #hud-monkey.panic .mk .b { animation: mkb .07s linear infinite alternate }
`;
// Side view facing right, one group per pose. The anchor (0,0) is the hand for hang and the middle for leap.
const MONKEY_SVG = '<svg class="mk" viewBox="-20 -20 40 40">' +
  '<g class="p-hang"><path class="tl" d="M0 20C-6 23 -9 29 -6 32C-4 34 -2 32 -4 30"/>' +
  '<path class="lm b far" style="transform-origin:-1.5px 19px" d="M-1.5 19L-2.5 24L-.5 27.5"/>' +
  '<path class="lm fa far" style="transform-origin:-1.5px 10px" d="M-1.5 10L3 6L7 3"/>' +
  '<ellipse class="fur" cx="0" cy="15" rx="3.8" ry="5.6"/><path class="lm a" style="transform-origin:1.5px 19px" d="M1.5 19L3 24L5 26.5"/>' +
  '<path class="lm" d="M0 0L1.6 5L2.8 10.5"/><circle class="fur" cx="-3.6" cy="7.2" r="1.5"/><circle class="fur" cx="-.8" cy="8" r="3.8"/>' +
  '<ellipse class="face" cx=".8" cy="8.6" rx="2.3" ry="2.5"/><circle class="eye" cx="1.4" cy="7.8" r=".55"/></g>' +
  '<g class="p-leap"><path class="tl" d="M-6 0C-11 -3 -15 1 -18 -2C-19.5 -3.5 -17.5 -5 -16.5 -3.5"/>' +
  '<path class="lm far" d="M-4 2L-7 6L-11 7"/><path class="lm far" d="M5 0L10 -2L14 -2"/>' +
  '<ellipse class="fur" cx="0" cy="0" rx="6.8" ry="3.4"/><path class="lm" d="M-5 1L-9 4L-13 4"/>' +
  '<path class="lm" d="M4 -1L9 -4L13 -6"/><circle class="fur" cx="6" cy="-4.8" r="1.5"/><circle class="fur" cx="8" cy="-2.5" r="3.8"/>' +
  '<ellipse class="face" cx="9.6" cy="-2" rx="2.2" ry="2.4"/><circle class="eye" cx="10.2" cy="-3" r=".55"/></g></svg>';
const MONKEYS = 3;
const installMonkey = () => {
  let st = document.getElementById("hud-monkey-style");
  if (!st) { st = document.createElement("style"); st.id = "hud-monkey-style"; document.head.appendChild(st); }
  st.textContent = MONKEY_CSS;
  if (window.__hudMonkey === "%%BUILD%%") return; window.__hudMonkey = "%%BUILD%%";
  (window.__hudMonkeyTimers || []).forEach(clearTimeout); clearInterval(window.__hudMonkeyTimer);
  // the spiders (and their webs) from older builds go away
  window.__hudSpider = null; (window.__hudSpiderTimers || []).forEach(clearTimeout); clearInterval(window.__hudWebTimer); delete window.__spiderNow;
  document.querySelectorAll("#hud-spider, #hud-spider-style, #hud-monkey").forEach(n => n.remove());
  try { localStorage.removeItem("hud-webs"); } catch (e) {}
  const timers = window.__hudMonkeyTimers = [];
  const alive = () => window.__hudMonkey === "%%BUILD%%";
  const NS = "http://www.w3.org/2000/svg", root = document.createElement("div"); root.id = "hud-monkey";
  root.innerHTML = '<svg width="100%" height="100%" style="position:absolute;left:0;top:0;overflow:visible"><g class="vines"></g></svg>';
  document.body.appendChild(root);
  const vinesG = root.querySelector(".vines");
  const rnd = (a, b) => a + Math.random() * (b - a);
  const offline = () => !!window.__offline || !navigator.onLine;
  const frame = () => new Promise(r => requestAnimationFrame(r));
  const panels = () => [...document.querySelectorAll("[data-hud]")].map(o => [o, o.getBoundingClientRect()]).filter(([, r]) => r.width > 120);
  const where = {};   // monkey -> panel it is on
  // Monkeys are shared out by size: each panel's fair share of the troop is its area over the
  // total, and a monkey goes to the panel furthest below its share, so big panels get more monkeys and small ones fewer.
  const share = (i, weight, among) => { const all = panels(), ps = all.map(([o, r]) => [o, weight(o, r)]).filter(([, w]) => w > 0);
    const sum = ps.reduce((a, [, w]) => a + w, 0), crew = Object.keys(where).filter(j => +j !== i).length + 1;
    const gaps = ps.filter(([o]) => !among || among.some(([q]) => q === o)).map(([o, w]) =>
      [o, crew * w / sum - Object.entries(where).filter(([j, p]) => +j !== i && p === o.dataset.hud).length]);
    if (!gaps.length) return [null, 0];   // random pick weighted by how far each panel is below its share (so still uniform overall)
    let k = Math.random() * gaps.reduce((a, [, g]) => a + Math.max(.02, g), 0);
    for (const [o, g] of gaps) if ((k -= Math.max(.02, g)) <= 0) return [o, g];
    return gaps[gaps.length - 1]; };
  const area = (o, r) => r.width * r.height;
  window.__hudMonkeyTimer = setInterval(() => { if (alive()) root.classList.toggle("panic", offline()); }, 500);

  // ── One monkey.
  const monkey = (i) => {
    const size = rnd(.95, 1.2), pace = rnd(.85, 1.2), L = 15 * size;   // L: hand to belly
    const holder = document.createElement("div"); holder.innerHTML = MONKEY_SVG; const mk = holder.firstChild; root.appendChild(mk);
    const vine = document.createElementNS(NS, "path"); vine.setAttribute("class", "vine"); vinesG.appendChild(vine);
    let busy = false, scared = false, x = 0, y = -40, ang = 0, dir = 1, vineTop = null, vineEnd = null, kick = [0, 0];
    mk.addEventListener("mousedown", e => { e.stopPropagation(); if (!busy || scared) return; scared = true;
      const dx = x - e.clientX; kick = [(dx < 0 ? -1 : 1) * rnd(200, 360), -rnd(280, 420)]; });   // knocked away from the click
    const pose = p => mk.setAttribute("class", "mk on " + p);
    const put = () => { const p = offline(), jx = p ? rnd(-1.2, 1.2) : 0, jy = p ? rnd(-1.2, 1.2) : 0;   // trembling
      mk.style.transform = `translate(${x + jx}px, ${y + jy}px) rotate(${ang}deg) scale(${dir * size}, ${size})`;
      if (vineTop) { const [ex, ey] = vineEnd || [x, y]; vine.style.transition = "none"; vine.style.opacity = 1;
        vine.setAttribute("d", `M${vineTop[0]} ${vineTop[1]}L${ex} ${ey}`); } };
    const stop = () => { if (!alive()) throw "gone"; };
    const quit = () => scared || offline();   // knocked off, or the internet dropped: stop whatever it's doing
    const dropVine = () => { vineTop = vineEnd = null; vine.style.transition = "opacity 1.2s"; vine.style.opacity = 0; };
    // Plays fn(k) for k 0..1 over ms, one step per frame; returns false if it was cut short.
    const run = async (ms, fn, until = quit) => { const t0 = performance.now();
      for (;;) { stop(); await frame(); const k = Math.min(1, (performance.now() - t0) / ms); fn(k); put();
        if (k >= 1) return true; if (until()) return false; } };
    const ease = k => (1 - Math.cos(Math.PI * k)) / 2;   // a pendulum: slow at the ends, fastest through the middle
    const belly = () => { const a = ang * Math.PI / 180; return [x - L * Math.sin(a), y + L * Math.cos(a)]; };   // hanging from the hand at (x, y)
    // Swing on a vine hanging from P (length R) from angle f0 to f1 (radians from straight down).
    const pendulum = (P, R, f0, f1, ms) => { pose("hang"); vineTop = P; dir = f1 > f0 ? 1 : -1;
      return run(ms, k => { const f = f0 + (f1 - f0) * ease(k); x = P[0] + R * Math.sin(f); y = P[1] + R * Math.cos(f); ang = -f * 180 / Math.PI; }, () => scared); };
    // Hang from the bottom edge of o at g (relative to the panel): the swing it arrived with dies down to a lazy sway.
    const hold = (o, g, a0, ms) => { pose("hang"); const ph = rnd(0, 6);
      return run(ms, k => { const r = o.getBoundingClientRect(), t = k * ms; x = r.left + g; y = r.bottom;
        ang = a0 * Math.exp(-t / 900) * Math.cos(t / 280) + 7 * Math.sin(t / 700 + ph) * (1 - Math.exp(-t / 900)); }); };
    // Hand over hand along the bottom edge to g = to: each swing goes from behind the hand to in front of it, and the other
    // hand grabs exactly where that leaves the body, so the motion carries on smoothly.
    const swingAlong = async (o, to) => { pose("hang"); let g = x - o.getBoundingClientRect().left, th = 0;
      while (Math.abs(to - g) > 1 && !quit()) { dir = Math.sign(to - g);
        const st = Math.min(2 * L * Math.sin(.75), Math.abs(to - g)); th = Math.asin(st / 2 / L) * 180 / Math.PI;
        await run(520 / pace, k => { const r = o.getBoundingClientRect(); x = r.left + g; y = r.bottom; ang = dir * th * (1 - 2 * ease(k)); });
        g += dir * st; }
      ang = dir * th; };
    // Jump through the air from its belly now to a belly position (tx, ty), arms out front.
    const leap = async (tx, ty, h) => { const x0 = x, y0 = y, d = Math.hypot(tx - x0, ty - y0); dir = tx >= x0 ? 1 : -1; pose("leap"); dropVine();
      h = h == null ? 24 + d * .15 : h;
      return run((420 + d * 1.1) / pace / (offline() ? 1.8 : 1), k => { x = x0 + (tx - x0) * k; y = y0 + (ty - y0) * k - h * 4 * k * (1 - k);
        const vy = ty - y0 - h * 4 * (1 - 2 * k); ang = Math.max(-50, Math.min(50, Math.atan2(vy, Math.abs(tx - x0) + 1) * 180 / Math.PI)) * dir * .7; }, () => scared); };
    // Pump a few big swings, let go at the top of one and fly across to catch panel q's bottom edge at tg.
    const fling = async (o, q, tg) => { const gx = x - o.getBoundingClientRect().left; dir = q.getBoundingClientRect().left + tg >= x ? 1 : -1;
      if (!await run(1500 / pace, k => { const r = o.getBoundingClientRect(); x = r.left + gx; y = r.bottom;
        ang = -dir * (14 + 36 * k) * Math.sin(Math.PI * 2.5 * k); })) return;
      [x, y] = belly(); const b = q.getBoundingClientRect(), a = dir * 35 * Math.PI / 180;   // caught with the body still behind the hand
      if (!await leap(b.left + tg - L * Math.sin(a), b.bottom + L * Math.cos(a))) return;
      ang = dir * 35; await hold(q, tg, ang, rnd(1200, 2500)); };
    // A vine comes down beside it, it grabs on and swings up and away off the top of the screen.
    const swingOut = async () => { dir = x < innerWidth / 2 ? -1 : 1; const P = [x + dir * rnd(90, 160), -40], R = Math.hypot(x - P[0], y - P[1]);
      vineTop = P; const [x0, y0] = [x, y];
      if (!await run(600, k => { vineEnd = [P[0] + (x0 - P[0]) * k, P[1] + (y0 - P[1]) * k]; }, () => scared)) return; vineEnd = null;
      await pendulum(P, R, Math.atan2(x0 - P[0], y0 - P[1]), dir * 1.75, (900 + R) / pace); };
    // In on a vine from above the screen, catching the bottom edge of panel o.
    const swingIn = async (o) => { const r = o.getBoundingClientRect(), tx = r.left + rnd(30, r.width - 30), gy = r.bottom;
      const d = Math.random() < .5 ? 1 : -1, P = [tx - d * rnd(90, 160), -40], R = Math.hypot(tx - P[0], gy - P[1]);
      const f1 = Math.atan2(tx - P[0], gy - P[1]), f0 = -d * Math.acos(Math.min(1, 10 / R));
      if (!await pendulum(P, R, f0, f1, (1100 + R * .8) / pace)) return; dropVine();
      await hold(o, tx - o.getBoundingClientRect().left, ang, rnd(1200, 2500)); };
    // Offline: lets go and bounds off the nearest side of the screen.
    const flee = async () => { const W = innerWidth; if (mk.classList.contains("hang")) [x, y] = belly(); dir = x < W / 2 ? -1 : 1;
      while (x > -40 && x < W + 40 && !scared) await leap(x + dir * rnd(160, 240), y, rnd(40, 70)); };
    const tumble = async () => { if (mk.classList.contains("hang")) [x, y] = belly(); dropVine(); pose("leap");
      let [vx, vy] = kick, spin = rnd(500, 800) * (vx < 0 ? -1 : 1), t = performance.now();
      while (y < innerHeight + 50 && x > -60 && x < innerWidth + 60) { stop(); await frame();
        const now = performance.now(), dt = Math.min(.05, (now - t) / 1000); t = now;
        vy += 1500 * dt; vx *= 1 - .4 * dt; x += vx * dt; y += vy * dt; ang += spin * dt; put(); } };
    const cameo = async () => {
      if (busy) return false; if (offline()) return "away"; busy = true; scared = false;
      try {
        const all = panels(); if (!all.length) throw "none";
        const top = Math.min(...all.map(([, r]) => r.top));
        let o = share(i, area, all.filter(([, r]) => r.top < top + 40))[0]; where[i] = o.dataset.hud;
        await swingIn(o);
        for (let hops = 0; !quit(); hops++) {
          let r = o.getBoundingClientRect();   // wider panels get swung along for longer
          for (let n = Math.max(1, Math.round(rnd(1, 2.5) * r.width / 350)); n > 0 && !quit(); n--) {
            r = o.getBoundingClientRect(); await swingAlong(o, rnd(14, r.width - 14));
            if (!quit()) await hold(o, x - r.left, ang, rnd(1500, 4000)); }
          if (quit()) break;
          // on to a panel beside or below that's short of monkeys; otherwise away on a vine
          r = o.getBoundingClientRect();
          const side = panels().filter(([q, b]) => q !== o && Math.abs(b.top - r.top) < 80 && (Math.abs(b.left - r.right) < 60 || Math.abs(r.left - b.right) < 60));
          const below = panels().filter(([q, b]) => q !== o && b.top > r.bottom - 4 && b.top - r.bottom < 60 && b.left < r.right - 40 && b.right > r.left + 40);
          const [q, need] = share(i, area, [...side, ...below]);
          if (!q || need < .2 || hops >= 4) { await swingOut(); break; }
          const b = q.getBoundingClientRect();
          if (below.some(([p]) => p === q)) {   // from over the panel below, drop across to its bottom edge
            const lo = Math.max(r.left, b.left) + 30, hi = Math.min(r.right, b.right) - 30, land = rnd(lo, Math.max(lo, hi));
            await swingAlong(o, Math.max(14, Math.min(r.width - 14, land - r.left + rnd(-60, 60)))); if (quit()) break;
            await fling(o, q, land - b.left);
          } else {   // from the near end, across the gap to the next panel along
            const right = b.left > r.left; await swingAlong(o, right ? r.width - 14 : 14); if (quit()) break;
            await fling(o, q, right ? rnd(20, 70) : b.width - rnd(20, 70));
          }
          if (quit()) break; o = q; where[i] = o.dataset.hud;
        }
        if (scared) await tumble(); else if (offline()) await flee();
      } catch (e) { if (e !== "gone" && e !== "none") console.error(e); }
      delete where[i];
      dropVine(); mk.setAttribute("class", "mk"); busy = false; return scared ? "kicked" : true;
    };
    const plan = ms => timers[i] = setTimeout(async () => { if (!alive()) return; const how = await cameo();
      if (alive()) plan(next(how)); }, ms);
    const next = how => how === "kicked" ? rnd(27000, 33000) : offline() ? rnd(20000, 40000) : rnd(60000, 240000);
    const go = () => { clearTimeout(timers[i]); const p = cameo(); p.then(how => { if (how && alive()) plan(next(how)); }); return p; };
    plan(rnd(8000, 20000) + i * rnd(15000, 30000));   // staggered arrivals
    return go;
  };
  const troop = Array.from({ length: MONKEYS }, (_, i) => monkey(i));
  window.__monkeyNow = async () => { for (const go of troop) { const p = go(); if (await Promise.race([p, Promise.resolve("running")]) === "running") return "sent"; } return "all out"; };
};
const PAIRS = [["clock", "weather"], ["weather", "system"], ["puzzle", "anime"], ["batcave", "chesstv"], ["chesstv", "connections"],
  ["clock", "puzzle"], ["weather", "puzzle"], ["system", "anime"], ["puzzle", "batcave"], ["puzzle", "chesstv"],
  ["anime", "chesstv"], ["anime", "connections"]];
const LAYOUT_VERSION = "3";  // clears positions saved back when panels could be rearranged
const installLinks = () => {
  if (window.__hudLinks === "%%BUILD%%") return; window.__hudLinks = "%%BUILD%%";
  document.querySelectorAll("#hud-links, #hud-cables").forEach(n => n.remove());
  try { if (localStorage.getItem("hud-layout") !== LAYOUT_VERSION) {
    Object.keys(localStorage).filter(k => k.startsWith("hud-pos:")).forEach(k => localStorage.removeItem(k));
    localStorage.setItem("hud-layout", LAYOUT_VERSION); } } catch (e) {}
  const NS = "http://www.w3.org/2000/svg", svg = document.createElementNS(NS, "svg");
  svg.id = "hud-links";
  svg.style.cssText = "position:fixed;left:0;top:0;width:100%;height:100%;pointer-events:none;z-index:0;overflow:visible";
  document.body.prepend(svg);
  const top = svg.cloneNode(false); top.id = "hud-cables"; top.style.zIndex = "99990"; document.body.appendChild(top);
  const els = PAIRS.map(() => { const g = document.createElementNS(NS, "g");
    g.innerHTML = '<path class="l"/><path class="f"/><circle r="2.6"/><circle r="2.6"/>'; svg.appendChild(g); return g; });
  let sig = "";
  const link = (a, b) => {
    const ox = Math.min(a.right, b.right) - Math.max(a.left, b.left), oy = Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top);
    if (oy > 24) { const [L, R] = a.left < b.left ? [a, b] : [b, a], y = (Math.max(a.top, b.top) + Math.min(a.bottom, b.bottom)) / 2;
      return [L.right, y, R.left, y]; }
    if (ox > 24) { const [T, B] = a.top < b.top ? [a, b] : [b, a], x = (Math.max(a.left, b.left) + Math.min(a.right, b.right)) / 2;
      return [x, T.bottom, x, B.top]; }
    const ac = [(a.left + a.right) / 2, (a.top + a.bottom) / 2], bc = [(b.left + b.right) / 2, (b.top + b.bottom) / 2];
    const side = Math.abs(bc[0] - ac[0]) > Math.abs(bc[1] - ac[1]);
    return side ? [bc[0] > ac[0] ? a.right : a.left, ac[1], bc[0] > ac[0] ? b.left : b.right, bc[1]]
                : [ac[0], bc[1] > ac[1] ? a.bottom : a.top, bc[0], bc[1] > ac[1] ? b.top : b.bottom];
  };
  const tick = () => {
    const boxes = {}; document.querySelectorAll("[data-hud]").forEach(o => { boxes[o.dataset.hud] = o.getBoundingClientRect(); });
    const state = {}; document.querySelectorAll("[data-hud]").forEach(o => {
      const r = boxes[o.dataset.hud], d = Math.hypot(r.left - o.dataset.hx, r.top - o.dataset.hy);
      state[o.dataset.hud] = [o.dataset.tether || "", Math.min(1, d / 240)]; });
    const now = Object.entries(boxes).map(([k, r]) => k + (r.left | 0) + "," + (r.top | 0) + state[k]).join("|");
    if (now !== sig) { sig = now;
      PAIRS.forEach(([p, q], i) => { const g = els[i], a = boxes[p], b = boxes[q];
        if (!a || !b) { g.style.display = "none"; return; }
        // A panel being pulled keeps its chains however far they stretch.
        const [tp, sp] = state[p], [tq, sq] = state[q], mode = tp || tq;
        const [x1, y1, x2, y2] = link(a, b), len = Math.hypot(x2 - x1, y2 - y1);
        if (len < 4 || (len > 340 && mode !== "taut")) { g.style.display = "none"; return; }
        g.style.display = ""; g.setAttribute("class", mode);
        const layer = mode === "taut" ? top : svg; if (g.parentNode !== layer) layer.appendChild(g);
        const s = mode === "taut" ? Math.max(sp, sq, .05) : 0, [l, f] = g.children;  // links stretch thinner-dashed and brighter
        l.style.stroke = mode === "taut" ? `rgba(245,177,76,${(.55 + .4 * s).toFixed(2)})` : ""; l.style.strokeWidth = s ? 2.2 - 0.9 * s : "";  // thins as it stretches
        f.style.strokeDasharray = s ? `2 ${(9 + 14 * s).toFixed(1)}` : "";
        const straight = mode === "taut" || Math.abs(x1 - x2) < 1 || Math.abs(y1 - y2) < 1, mx = (x1 + x2) / 2;
        const d = straight ? `M${x1} ${y1}L${x2} ${y2}` : `M${x1} ${y1}C${mx} ${y1} ${mx} ${y2} ${x2} ${y2}`;
        g.children[0].setAttribute("d", d); g.children[1].setAttribute("d", d);
        g.children[2].setAttribute("cx", x1); g.children[2].setAttribute("cy", y1);
        g.children[3].setAttribute("cx", x2); g.children[3].setAttribute("cy", y2); }); }
    if (window.__hudLinks !== "%%BUILD%%") return;
    const moving = Object.values(state).some(([t, d]) => t || d > .002);   // dragged or springing home (> ½px): follow every frame
    moving ? requestAnimationFrame(tick) : setTimeout(tick, 500); };
  tick();
};
export const className = `
  left: 0; top: 0; width: 100%; height: 100%; pointer-events: none;
  .flow { stroke-dasharray: 3 4; animation: f 1.6s linear infinite } @keyframes f { to { stroke-dashoffset: -14 } }
  circle { animation: p 2.6s ease-in-out infinite } @keyframes p { 50% { opacity:.4 } }
`;
const FONTS = "@import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@500;600;700&family=Rajdhani:wght@500;600;700&family=Share+Tech+Mono&display=swap');";
export const render = () => { installCursor(); installLinks(); installMonkey(); return (
  <svg width="100%" height="100%" viewBox="0 0 1470 923" preserveAspectRatio="none">
    <style>{FONTS}</style>
    {false && <g>
    <g stroke="#ffb35c" strokeWidth="1.4" fill="#ffb35c" style={{ filter: "drop-shadow(0 0 4px rgba(255,179,92,.9))" }}>
      ''' + "\n      ".join(links) + '''
    </g></g>}
  </svg>
); };''')

# Panel rects (canvas px, incl. the 1px border) for hudcursor, which hides the system pointer over them.
json.dump([[x, y + DY, w + 2, h + 2] for n, (x, y, w, h) in POS.items() if n != "aa-links"], open(f"{_S}/.panels.json", "w"))
os.system(f"launchctl kickstart -k gui/{os.getuid()}/com.stark.hudcursor >/dev/null 2>&1")  # pick up a rebuilt helper

print("wrote", sorted(f for f in os.listdir(W) if f.endswith(".jsx")))
