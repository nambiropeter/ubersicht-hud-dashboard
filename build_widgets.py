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

# ── Layout grid (screen 1470×956 pt): 32 | 340 | 20 | 686 | 20 | 340 | 32 ──
L, C, R = 32, 392, 1098
DY = -36  # Übersicht's canvas starts below the menu bar
POS = {
    "clock":   (L, 56, 340, 200),  "weather":     (L, 276, 340, 226),
    "system":  (L, 522, 340, 200), "connections": (L, 742, 340, 190),
    "markets": (C, 56, 686, 560),  "ai-wire":     (C, 636, 686, 296),
    "batcave": (R, 56, 340, 252),  "mail":        (R, 328, 340, 288),
    "movers":  (R, 636, 340, 296),
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
const Spark = ({ d, w, h, up, base, ts, axis = false, fill = true, sw = 1.6 }) => {
  if (!d || d.length < 2) return <svg width={w} height={h} />;
  const id = _pfx + (++_sid), padR = axis ? 46 : 5, padB = axis ? 18 : 0, cw = w - padR, ch = h - padB;
  const ref = base != null ? base : d[0];
  let mn = Math.min(...d, ref), mx = Math.max(...d, ref); const pad = (mx - mn || 1) * 0.1; mn -= pad; mx += pad;
  const X = i => 2 + (i / (d.length - 1)) * (cw - 4), Y = v => 3 + (1 - (v - mn) / (mx - mn)) * (ch - 6);
  const P = d.map((v, i) => [X(i), Y(v)]), line = smooth(P), by = Y(ref), last = P[P.length - 1];
  const endCol = d[d.length - 1] >= ref ? UP : DN;
  const area = `${line}L${last[0].toFixed(1)} ${by.toFixed(1)}L${P[0][0].toFixed(1)} ${by.toFixed(1)}Z`;
  // day dividers (hourly data spans several sessions)
  const days = [];
  if (axis && ts) ts.forEach((t, i) => { if (!i || etDay(t) !== etDay(ts[i - 1])) days.push(i); });
  const move = e => {
    const svg = e.currentTarget.ownerSVGElement, r = svg.getBoundingClientRect();
    const i = Math.max(0, Math.min(d.length - 1, Math.round(((e.clientX - r.left - 2) / (cw - 4)) * (d.length - 1))));
    const g = svg.querySelector(".xh"), [x, y] = P[i], ch_ = (d[i] - ref) / ref * 100;
    g.style.opacity = 1;
    g.querySelector("line").setAttribute("x1", x); g.querySelector("line").setAttribute("x2", x);
    const dot = g.querySelector("circle"); dot.setAttribute("cx", x); dot.setAttribute("cy", y); dot.setAttribute("fill", d[i] >= ref ? UP : DN);
    const v = g.querySelector(".tv"), s = g.querySelector(".ts"), bx = g.querySelector("rect");
    v.textContent = tickFmt(d[i]) === String(d[i]) ? String(d[i]) : d[i].toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    s.textContent = (ch_ >= 0 ? "+" : "") + ch_.toFixed(2) + "% vs prev close" + (ts ? " · " + etTime(ts[i]) + " ET" : "");
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
          <stop offset="0" stopColor={UP} stopOpacity=".26" /><stop offset="1" stopColor={UP} stopOpacity=".02" /></linearGradient>
        <linearGradient id={id + "d"} gradientUnits="userSpaceOnUse" x1="0" y1={by} x2="0" y2={Y(mn)}>
          <stop offset="0" stopColor={DN} stopOpacity=".02" /><stop offset="1" stopColor={DN} stopOpacity=".26" /></linearGradient>
      </defs>
      {axis && niceTicks(mn, mx).map(v => <g key={v}>
        <line x1="0" x2={cw} y1={Y(v)} y2={Y(v)} stroke="rgba(255,255,255,.05)" />
        <text x={w} y={Y(v) + 3.5} textAnchor="end" fill="#6f665f" fontSize="10" className="num">{tickFmt(v)}</text></g>)}
      {days.map((i, k) => <g key={i}>
        {k > 0 && <line x1={X(i) - 2} x2={X(i) - 2} y1="0" y2={ch} stroke="rgba(255,255,255,.06)" />}
        <text x={(X(i) + (k + 1 < days.length ? X(days[k + 1]) : cw)) / 2} y={h - 3} textAnchor="middle" fill="#6f665f" fontSize="9.5" letterSpacing=".12em">{etDay(ts[i]).toUpperCase()}</text></g>)}
      {fill && <path d={area} fill={`url(#${id}u)`} clipPath={`url(#${id}a)`} />}
      {fill && <path d={area} fill={`url(#${id}d)`} clipPath={`url(#${id}b)`} />}
      <line x1="0" x2={cw} y1={by} y2={by} stroke="rgba(255,255,255,.2)" strokeWidth="1" />
      {axis && <text x={w} y={by + 3.5} textAnchor="end" fill="#a39a92" fontSize="10" fontWeight="600" className="num">{tickFmt(ref)}</text>}
      <path d={line} fill="none" stroke={UP} strokeWidth={sw} strokeLinejoin="round" strokeLinecap="round" clipPath={`url(#${id}a)`} />
      <path d={line} fill="none" stroke={DN} strokeWidth={sw} strokeLinejoin="round" strokeLinecap="round" clipPath={`url(#${id}b)`} />
      {axis && <circle cx={last[0]} cy={last[1]} r="9" fill={endCol} opacity=".18" className="pulse" />}
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
const pct = c => `${c >= 0 ? "▲" : "▼"} ${Math.abs(c).toFixed(2)}%`;"""

HOURS = """// Exchange sessions in local time (Mon–Fri), minutes after midnight
const EXCHANGES = [
  { city: "NEW YORK", tz: "America/New_York", open: 570, close: 960 },
  { city: "LONDON",   tz: "Europe/London",    open: 480, close: 990 },
  { city: "TOKYO",    tz: "Asia/Tokyo",       open: 540, close: 900 },
];
const DAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const weekday = d => d !== "Sat" && d !== "Sun";
const localParts = (tz, now) => {
  const p = Object.fromEntries(new Intl.DateTimeFormat("en-US", { timeZone: tz, hour12: false, weekday: "short", hour: "2-digit", minute: "2-digit" })
    .formatToParts(now).map(x => [x.type, x.value]));
  const hr = +p.hour % 24;
  return { day: p.weekday, min: hr * 60 + +p.minute, hm: String(hr).padStart(2, "0") + ":" + p.minute };
};
const session = (ex, now) => {
  const { day, min, hm } = localParts(ex.tz, now);
  const open = weekday(day) && min >= ex.open && min < ex.close;
  let left = ex.close - min;
  if (!open) {
    const d0 = DAYS.indexOf(day);
    for (let i = 0; i < 8; i++) {
      if (weekday(DAYS[(d0 + i) % 7]) && (i > 0 || min < ex.open)) { left = i * 1440 + ex.open - min; break; }
    }
  }
  const dur = left >= 1440 ? `${Math.floor(left / 1440)}d ${Math.floor(left % 1440 / 60)}h` : `${Math.floor(left / 60)}h ${left % 60}m`;
  return { open, hm, dur };
};"""


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
  if (!msg && data && typeof problem === "function") msg = problem(data);
  // offline explains every failure at once (connections panel and the browser both report it)
  if (msg && (window.__offline || !navigator.onLine)) msg = "No internet";
  if (!msg && out) { s.ok = Date.now(); s.last = props.output; }
  s.msg = msg; setTimeout(syncPaint, 0);
  // when the script fails, keep showing the last good data under the warning instead of a blank panel
  return (props.error || !out) && s.last ? { ...props, output: s.last, error: null } : props;
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
  box.getAnimations().forEach(a => a.cancel()); box.style.left = box.style.top = box.style.transition = ""; box.dataset.tether = "";
  const anywhere = name === "clock";
  const home = { x: box.offsetLeft, y: box.offsetTop };
  const BASE = "border-color .3s, box-shadow .3s, transform .3s";
  { const r = box.getBoundingClientRect(); box.dataset.hx = r.left; box.dataset.hy = r.top; }  // chains measure strain from here
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

NET = {"weather", "markets", "ai-wire", "movers", "mail", "connections"}  # panels that need the internet

def widget(name, body):
    x, y, w, h = POS.get(name, (0, 0, 0, 0)); y += DY
    body = (body.replace("%%SHARED%%", SHARED)
                .replace("%%POS%%", f"left: {x}px; top: {y}px; width: {w}px; height: {h}px;")
                .replace("%%PY%%", PY).replace("%%AGO%%", AGO).replace("%%SPARK%%", SPARK)
                .replace("%%FMT%%", FMT).replace("%%HOURS%%", HOURS))
    for old, new in THEME:
        body = body.replace(old, new)
    for old, new in WARM:
        body = body.replace(old, new)
    body = re.sub(r";?\s*text-shadow:[^;}]*", "", body)
    # one custom cursor everywhere: no system hand/arrow over headers, buttons or rows
    body = re.sub(r"cursor: ?(default|grabbing|grab|pointer)\b", f"cursor: {CURSOR}", body)
    if name != "aa-links":
        head, mark, tail = body.partition("\nexport const render")
        tail = re.sub(r"(return \(\s*<div)>", lambda m: m.group(1) + ' ref={hud("' + name + '")}>', tail)
        tail = re.sub(r"(return <div)>", lambda m: m.group(1) + ' ref={hud("' + name + '")}>', tail)
        body = head + mark + tail
        body = body.replace("\nexport const render", "\n" + HUD + "\nexport const render", 1)
    if name not in ("aa-links", "clock"):
        # badge goes in every root the render returns (e.g. loading + loaded), not in helper components above it
        head, mark, tail = body.partition("\nexport const render")
        ref = 'ref={hud("' + name + '")}>'
        net = ' data-net="1"' if name in NET else ""
        body = head + mark + tail.replace(ref, ref + '<span className="syncwarn" data-sync="' + name + '"' + net + ' data-every={refreshFrequency} />')
        body = body.replace("\nexport const render =", "\n" + SYNC + "\nconst __render =", 1)
        body += '\nexport const render = (p, d) => __render(syncCheck("' + name + '", p), d);'
    body = body.replace("%%BUILD%%", BUILD)
    with open(os.path.join(W, name + ".jsx"), "w") as f:
        f.write(body + "\n")


# ───────────────────────── CLOCK ─────────────────────────
widget("clock", r'''// Clock, greeting and world-market sessions.
export const command = "date +%s";
export const refreshFrequency = 1000;
export const className = `
  %%POS%%%%SHARED%%
  box-sizing: border-box; width: 342px; height: 202px; padding: 16px 16px 16px 18px;  /* same outer size as the panels below */
  .time { display:flex; align-items:baseline; gap:8px }
  .time b { font: 200 60px -apple-system, "SF Pro Display", sans-serif; letter-spacing:-.03em; line-height:1; color:#ffffff }
  .time span { font: 300 20px -apple-system, sans-serif; color:#f5b14c }
  .date { margin-top:8px; font: 500 14px -apple-system, sans-serif; color:#ebe5dd }
  .greet { margin-top:1px; font-size:12px; letter-spacing:.06em; color:#5f8a99 }
  .ex { display:grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap:7px; margin-top:12px }
  .cell { background:rgba(255,255,255,.04); border:1px solid rgba(255,255,255,.06); border-radius:12px; padding:6px 8px; min-width:0 }
  .cell .c { font: 700 8.5px Orbitron, sans-serif; letter-spacing:.16em; color:#8c8178 }
  .cell .t { font-size:15px; font-weight:500; margin:2px 0 }
  .cell .s { font-size:9.5px; white-space:nowrap }
  .dot { display:inline-block; width:6px; height:6px; border-radius:50%; margin-right:5px; vertical-align:1px }
`;
%%HOURS%%
export const render = () => {
  const now = new Date(), h = now.getHours();
  const part = h < 12 ? "morning" : h < 17 ? "afternoon" : "evening";
  return (
    <div>
      <div className="time num"><b>{now.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" })}</b>
        <span>{String(now.getSeconds()).padStart(2, "0")}</span></div>
      <div className="date">{now.toLocaleDateString("en-GB", { weekday: "long", day: "numeric", month: "long" })}</div>
      <div className="greet">Good {part}, Anthony</div>
      <div className="ex">
        {EXCHANGES.map(ex => { const s = session(ex, now); return (
          <div className="cell" key={ex.city}>
            <div className="c">{ex.city}</div>
            <div className="t num">{s.hm}</div>
            <div className={"s " + (s.open ? "up" : "muted")}>
              <span className="dot" style={{ background: s.open ? "#4ade80" : "#6f665f", boxShadow: s.open ? "0 0 6px #4ade80" : "none" }} />
              {s.open ? `closes ${s.dur}` : `opens ${s.dur}`}</div>
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
  .main { display:flex; align-items:center; gap:14px; padding:10px 18px 4px }
  .ico { font-size:44px; line-height:1; filter: drop-shadow(0 4px 12px rgba(255,179,92,.35)) }
  .temp { font: 200 50px -apple-system, "SF Pro Display", sans-serif; letter-spacing:-.02em; line-height:1; color:#ffffff }
  .temp sup { font-size:18px; color:#ffb35c; vertical-align: 20px; margin-left:2px }
  .cond { margin-left:auto; text-align:right }
  .cond b { display:block; font-size:15px; font-weight:600 }
  .cond span { display:block; font-size:11px; color:#a39a92; line-height:1.5 }
  .chips { display:flex; gap:6px; padding:4px 16px 10px }
  .chip { flex:1; text-align:center; font-size:10.5px; padding:5px 0; border-radius:10px; background:rgba(255,214,170,.04); border:1px solid rgba(255,214,170,.06); color:#d9cfc6; white-space:nowrap }
  .days { display:grid; grid-template-columns: repeat(5, 1fr); margin:0 12px; padding-top:8px; border-top:1px solid rgba(255,214,170,.08); text-align:center }
  .d .n { font-size:9.5px; letter-spacing:.14em; color:#8c8178; font-weight:600 }
  .d .i { font-size:17px; margin:3px 0 1px }
  .d .hl { font-size:11px } .d .hl span { color:#6f665f }
  .bar { height:3px; margin:5px 12px 0; border-radius:2px; background:rgba(127,220,255,.12); overflow:hidden }
  .bar i { display:block; height:100%; background:#7fdcff }
`;
const WMO = { 0:["Clear","☀️","🌙"], 1:["Mostly clear","🌤","🌙"], 2:["Partly cloudy","⛅️","☁️"], 3:["Overcast","☁️","☁️"],
  45:["Fog","🌫","🌫"], 48:["Fog","🌫","🌫"], 51:["Drizzle","🌦","🌧"], 53:["Drizzle","🌦","🌧"], 55:["Drizzle","🌧","🌧"],
  61:["Light rain","🌦","🌧"], 63:["Rain","🌧","🌧"], 65:["Heavy rain","🌧","🌧"], 80:["Showers","🌦","🌧"], 81:["Showers","🌧","🌧"],
  82:["Heavy showers","⛈","⛈"], 95:["Thunderstorm","⛈","⛈"], 96:["Thunderstorm","⛈","⛈"], 99:["Thunderstorm","⛈","⛈"] };
const wmo = (c, day = 1) => { const w = WMO[c] || ["—", "🌡", "🌡"]; return [w[0], day ? w[1] : w[2]]; };
const hm = s => (s || "").slice(11, 16);
export const render = ({ output }) => {
  let w = null; try { w = JSON.parse(output); } catch (e) {}
  const ok = w && w.current;
  const head = <header><span style={{ color: "#ffb35c" }}>◎</span><h1>WEATHER</h1><span className="sub">NAIROBI · <b>{ok ? "LIVE" : "SCANNING"}</b></span></header>;
  if (!ok) return <div>{head}</div>;
  const c = w.current, d = w.daily, [label, icon] = wmo(c.weather_code, c.is_day);
  return (
    <div>{head}
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
      <div className="days">
        {d.time.slice(1, 6).map((t, i) => { const rain = d.precipitation_probability_max[i + 1] ?? 0; return (
          <div className="d" key={t}>
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
widget("system", r'''// System monitor: CPU, memory, disk, battery.
export const command = "~/.stark/system.sh";
export const refreshFrequency = 10 * 1000;
export const className = `
  %%POS%%%%SHARED%%
  .rings { display:grid; grid-template-columns: repeat(4, 1fr); padding:16px 12px 8px; text-align:center }
  .ring { position:relative; width:64px; height:64px; margin:0 auto }
  .ring b { position:absolute; inset:0; display:flex; align-items:center; justify-content:center; font-size:14px; font-weight:500 }
  .ring b small { font-size:9px; color:#8c8178; margin-left:1px }
  .rl { margin-top:7px }
  .foot { display:flex; justify-content:space-between; margin:6px 16px 0; padding-top:10px; border-top:1px solid rgba(255,214,170,.08); font-size:10.5px; color:#a39a92 }
  .foot b { color:#e6dcd2; font-weight:500 }
`;
const Ring = ({ v, col, label }) => {
  const r = 27, C = 2 * Math.PI * r, f = Math.max(0, Math.min(100, v)) / 100;
  return (
    <div>
      <div className="ring">
        <svg width="64" height="64" viewBox="0 0 64 64">
          <circle cx="32" cy="32" r={r} fill="none" stroke="rgba(255,214,170,.08)" strokeWidth="5" />
          <circle cx="32" cy="32" r={r} fill="none" stroke={col} strokeWidth="5" strokeLinecap="round"
            strokeDasharray={`${C * f} ${C}`} transform="rotate(-90 32 32)" style={{ filter: `drop-shadow(0 0 4px ${col})` }} />
        </svg>
        <b className="num">{Math.round(v)}<small>%</small></b>
      </div>
      <div className="lbl rl">{label}</div>
    </div>
  );
};
const heat = v => v > 85 ? "#f87171" : v > 65 ? "#ffb35c" : null;
export const render = ({ output }) => {
  let s = null; try { s = JSON.parse(output); } catch (e) {}
  return (
    <div>
      <header><span style={{ color: "#ffb35c" }}>⌁</span><h1>SYSTEM</h1><span className="sub">MACBOOK · <b>{s ? "NOMINAL" : "…"}</b></span></header>
      {s && <div className="rings">
        <Ring v={s.cpu} col={heat(s.cpu) || "#7fdcff"} label="CPU" />
        <Ring v={s.mem} col={heat(s.mem) || "#a78bfa"} label="MEMORY" />
        <Ring v={s.disk} col={heat(s.disk) || "#ffb35c"} label="DISK" />
        <Ring v={s.batt} col={s.batt < 20 ? "#f87171" : "#4ade80"} label={s.charging ? "⚡ POWER" : "BATTERY"} />
      </div>}
      {s && <div className="foot num"><span>Uptime <b>{s.uptime}</b></span><span>Processes <b>{s.procs}</b></span><span>Free <b>{s.diskFree}</b></span></div>}
    </div>
  );
};''')

# ───────────────────────── CONNECTIONS ─────────────────────────
widget("connections", r'''// Connections, two views (toggle in the header, remembered):
// LIVE = throughput and latency to the services you use; LINK = Wi-Fi link, VPN + public IP, last speed test.
import { run } from "uebersicht";
export const command = "~/.stark/network.sh";
export const refreshFrequency = 30 * 1000;
export const className = `
  %%POS%%%%SHARED%%
  .body { display:flex; align-items:center; padding:4px 10px 0 6px }
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
  .rates { margin-left:auto; text-align:right; padding-right:8px }
  .rate { font: 200 25px -apple-system, sans-serif; line-height:1.15 } .rate small { font-size:10px; color:#8c8178; margin-left:3px }
  .rl { font-size:9.5px; letter-spacing:.16em; color:#8c8178; font-weight:600; margin-top:8px }
  .lip { font-size:9.5px; color:#6f665f; margin-top:9px; letter-spacing:.04em }
  .seg { display:inline-flex; gap:2px; padding:2px; border-radius:7px; background:rgba(0,0,0,.18); vertical-align:middle }
  .seg span { padding:2px 7px; border-radius:5px; font-size:8.5px; font-weight:700; letter-spacing:.12em; color:#8c8178; cursor:pointer }
  .seg span:hover { color:#e6dcd2 } .seg .on { background:rgba(255,255,255,.08); color:#fff7ee }
  .vpn { font-size:8.5px; font-weight:700; letter-spacing:.1em; padding:2px 6px; border-radius:5px; margin-right:6px; vertical-align:middle;
         color:#4ade80; background:rgba(74,222,128,.12) }
  .link { padding:2px 20px 0 }
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
  : ev.type === "SPEED" ? { ...prev, speed: ev.speed, testing: ev.testing } : { ...prev, output: ev.output, error: ev.error };
const problem = n => (window.__offline = n.ip === "offline" || n.services.every(x => !x.ms)) ? "No internet" : null;
const weak = ms => !ms || ms >= 150;   // amber, red or down: the link flickers and throws sparks
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
const col = ms => !ms ? "#6f665f" : ms < 150 ? "#4ade80" : ms < 450 ? "#ffb35c" : "#f87171";
const rate = b => b > 1048576 ? [(b / 1048576).toFixed(1), "MB/s"] : [(b / 1024).toFixed(0), "KB/s"];
const mbps = b => b >= 1e8 ? Math.round(b / 1e6) : (b / 1e6).toFixed(b >= 1e7 ? 0 : 1);
const hm = t => new Date(t * 1000).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" });
// signal: 4 bars ≥ -55 dBm, 3 ≥ -65, 2 ≥ -75, else 1
const bars = rssi => rssi >= -55 ? 4 : rssi >= -65 ? 3 : rssi >= -75 ? 2 : 1;
const sigCol = n => n >= 3 ? "#4ade80" : n === 2 ? "#ffb35c" : "#f87171";

const Live = ({ n }) => {
  const svcs = n ? n.services : [];
  // the hub pulses green when every link is fast, grey when exactly one service is down; a weak link turns it amber
  // and speeds it up, two or more down turn it red, any down service burns, and if everything is down the whole panel goes red
  const down = svcs.filter(s => !s.ms).length, dead = svcs.length > 0 && (down === svcs.length || n.ip === "offline");
  const alert = svcs.some(s => s.ms && weak(s.ms)) || down > 1, ok = svcs.length > 0 && !alert && down <= 1;
  const hub = dead || down > 1 ? "#f87171" : ok ? (down ? "#a39a92" : "#4ade80") : "#ffb35c", c = ms => dead ? "#f87171" : col(ms);
  const [dv, du] = n ? rate(n.down) : ["—", ""], [uv, uu] = n ? rate(n.up) : ["—", ""];
  return (
    <div className="body">
      <svg width="200" height="140" viewBox="0 0 200 140" style={{ overflow: "visible" }}>
        <defs><linearGradient id="flame" x1="0" y1="1" x2="0" y2="0">
          <stop offset="0" stopColor="#fff1b0" /><stop offset=".35" stopColor="#ffb340" /><stop offset=".7" stopColor="#ff5a24" /><stop offset="1" stopColor="#d9261c" stopOpacity="0" />
        </linearGradient></defs>
        {svcs.slice(0, NODES.length).map((s, i) => !s.ms ? null : <line key={"l" + i} className={weak(s.ms) ? "flow weak" : "flow"} x1="100" y1="70" x2={NODES[i][0]} y2={NODES[i][1]} stroke={c(s.ms)} strokeWidth="1.3" strokeOpacity=".8" />)}
        {svcs.slice(0, NODES.length).map((s, i) => s.ms ? null : reach(NODES[i][0], NODES[i][1], dead ? "#f87171" : "#a39a92", i))}
        {svcs.slice(0, NODES.length).map((s, i) => weak(s.ms) ? sparks(NODES[i][0], NODES[i][1], c(s.ms), i) : null)}
        {dead && [8, 9, 10].map(k => sparks(100, 70, "#f87171", k))}
        <g className={"hub" + (alert || dead ? " alert" : ok ? " ok" : "")} style={{ "--hub": hub }}>
          <circle className="wave" cx="100" cy="70" r="16" fill="none" stroke={hub} strokeWidth="1" />
          <circle className="wave b" cx="100" cy="70" r="16" fill="none" stroke={hub} strokeWidth="1" />
          <circle className="ring" cx="100" cy="70" r="16" fill="rgba(36,27,22,1)" stroke={hub} strokeWidth="1.3" />
          <text x="100" y="73.5" textAnchor="middle" fontSize="7.5" fontWeight="700" fill={hub} letterSpacing=".8" fontFamily="Orbitron">HUB</text>
        </g>
        {svcs.map((s, i) => { const [x, y] = NODES[i], side = y === 70 ? (x < 100 ? -1 : 1) : 0; return (
          <g key={s.name}>
            <circle className={s.ms ? "pulse" : "char"} cx={x} cy={y} r="4.5" fill={s.ms ? c(s.ms) : "#2a1512"} stroke={s.ms ? "none" : "#ff5a24"} strokeWidth="1.2"
              style={{ filter: `drop-shadow(0 0 4px ${s.ms ? c(s.ms) : "#ff5a24"})` }} />
            {!s.ms && fire(x, y, i)}
            <text x={side ? x + side * 10 : x} y={y > 70 || side ? y + 16 : y - 9} textAnchor={side < 0 ? "start" : side > 0 ? "end" : "middle"} fontSize="9" fill={dead ? "#f87171" : "#d9cfc6"}>{s.name} <tspan fill={c(s.ms)}>{s.ms ? s.ms + "ms" : "down"}</tspan></text>
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

const Link = ({ n, speed, testing, test }) => {
  const w = (n && n.wifi) || {}, v = n && n.vpn, p = n && n.pub, onWifi = w.rssi !== undefined && w.rssi !== 0;
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
        <span className="v">{v ? <span><span className="up">●</span> {v.name}<small>{v.full ? "all traffic" : "split tunnel"}</small></span>
          : <span><span className="dim">●</span> <span className="muted">Off</span></span>}</span>
        <span className="r num">{n && n.ip !== "offline" ? <span><span className="dim">LAN </span>{n.ip}</span> : ""}</span>
        <span className="d num">{p ? (v ? "Exit " : "Public ") + p.ip + " · " + [p.city, p.cc].filter(Boolean).join(", ") + (p.isp ? " · " + p.isp : "") : "Public IP unknown"}</span>
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

export const render = ({ output, view, speed: mine, testing: busy }, dispatch) => {
  let n = null; try { n = JSON.parse(output); } catch (e) {}
  const pick = v => { try { localStorage.setItem("conn-view", v); } catch (e) {} dispatch({ type: "VIEW", view: v }); };
  // a test started from the button wins until the regular refresh has a newer result
  const speed = mine && (!n || !n.speed || mine.at >= n.speed.at) ? mine : n && n.speed;
  const testing = busy || !!(n && n.testing);
  const test = () => { dispatch({ type: "SPEED", speed, testing: true });
    run("~/.stark/speedtest.sh now; cat ~/.stark/.speed.json").then(out => {
      let s = speed; try { s = JSON.parse(out); } catch (e) {} dispatch({ type: "SPEED", speed: s, testing: false }); }); };
  return (
    <div>
      <header><span style={{ color: "#ffb35c" }}>⟡</span><h1>CONNECTIONS</h1>
        <span className="sub">{n && n.vpn && <span className="vpn" title={n.vpn.name}>VPN</span>}
          <span className="seg">{["LIVE", "LINK"].map(v => <span key={v} className={view === v ? "on" : ""} onClick={() => pick(v)}>{v}</span>)}</span></span></header>
      {view === "LINK" ? <Link n={n} speed={speed} testing={testing} test={test} /> : <Live n={n} />}
    </div>
  );
};''')

# ───────────────────────── MARKETS ─────────────────────────
widget("markets", r'''// Tech markets: NASDAQ hero chart + the 6 biggest tech names by market cap, with 5-day charts. Edit symbols in ~/.stark/market.py (SPARK).
import { run } from "uebersicht";
export const command = "%%PY%% ~/.stark/market.py json quotes";
export const refreshFrequency = 5 * 60 * 1000;
export const className = `
  %%POS%%%%SHARED%%
  .pill { margin-left:10px; font-size:10px; letter-spacing:.1em; padding:3px 9px; border-radius:20px; font-weight:600 }
  .hero { padding:14px 18px 0; cursor:pointer }
  .hrow { display:flex; align-items:flex-end; gap:12px }
  .hname { font-size:10px; letter-spacing:.2em; color:#8c8178; font-weight:600 }
  .hp { font: 200 44px -apple-system, "SF Pro Display", sans-serif; letter-spacing:-.02em; line-height:1.05; color:#ffffff }
  .hc { font-size:15px; font-weight:500; padding-bottom:5px }
  .range { margin-left:auto; text-align:right; font-size:10.5px; color:#a39a92; line-height:1.6; padding-bottom:4px }
  .range b { color:#e6dcd2; font-weight:500 }
  .chart { margin-top:8px }
  .pulse { transform-box: fill-box; transform-origin: center; animation: pulse 2.4s ease-out infinite }
  @keyframes pulse { 0% { transform: scale(.5); opacity:.45 } 100% { transform: scale(1.6); opacity:0 } }
  .idx { display:grid; grid-template-columns: repeat(3, 1fr); gap:10px; padding:14px 16px 0 }
  .grid { display:grid; grid-template-columns: repeat(3, 1fr); gap:10px; padding:12px 16px 0 }
  .tile { background:rgba(255,214,170,.035); border:1px solid rgba(255,214,170,.05); border-radius:14px; padding:10px 12px; cursor:pointer; transition: all .25s; position:relative }
  .tile:hover { background:rgba(255,255,255,.07); border-color: rgba(255,255,255,.14) }
  .tile .top { display:flex; justify-content:space-between; align-items:baseline }
  .tile .s { font-size:11px; font-weight:700; letter-spacing:.06em; color:#e6dcd2 }
  .tile .c { font-size:10.5px; font-weight:600 }
  .tile .p { font-size:16px; font-weight:400; margin:2px 0 5px }
  .rk { font-style:normal; color:#ffb35c; font-size:9.5px; font-weight:700; margin-right:5px }
  .cap { margin-left:6px; font-size:9.5px; font-weight:600; color:#8c8178; letter-spacing:.02em }
  .tcap { float:right; font-size:9.5px; color:#8c8178; font-weight:500; margin-top:5px }
  .idx .tile { display:flex; align-items:center; gap:8px; padding:8px 11px; min-width:0 }
  .idx .tile > div { min-width:0 }
  .idx .tile .p { margin:1px 0 0; font-size:14px }
`;
%%FMT%%
%%SPARK%%
const nyOpen = () => {
  const p = Object.fromEntries(new Intl.DateTimeFormat("en-US", { timeZone: "America/New_York", hour12: false, weekday: "short", hour: "2-digit", minute: "2-digit" })
    .formatToParts(new Date()).map(x => [x.type, x.value]));
  const m = (+p.hour % 24) * 60 + +p.minute;
  return p.weekday !== "Sat" && p.weekday !== "Sun" && m >= 570 && m < 960;
};
const cap = c => !c ? "" : c >= 1e12 ? `$${(c / 1e12).toFixed(2)}T` : `$${Math.round(c / 1e9)}B`;
const yahoo = s => run(`open "https://finance.yahoo.com/quote/${encodeURIComponent(s)}"`);
export const render = ({ output }) => {
  let q = []; try { q = JSON.parse(output); } catch (e) {}
  const by = Object.fromEntries(q.map(x => [x.sym, x])), hero = by["^IXIC"], open = nyOpen();
  // rank by market cap: top 3 featured, next 8 in the grid
  const ranked = q.filter(x => x.sym !== "^IXIC").sort((a, b) => (b.cap || 0) - (a.cap || 0));
  const top = ranked.slice(0, 6);
  return (
    <div>
      <header><span style={{ color: "#4ade80" }}>↗</span><h1>TECH MARKETS</h1>
        <span className="sub">RANKED BY MARKET CAP</span>
        <span className="pill" style={{ color: open ? "#4ade80" : "#ffb35c", background: open ? "rgba(74,222,128,.1)" : "rgba(255,179,92,.1)" }}>
          ● NYSE {open ? "OPEN" : "CLOSED"}</span></header>
      {!hero ? <div className="hero muted">Connecting to markets…</div> : <div>
        <div className="hero" onClick={() => yahoo("^IXIC")}>
          <div className="hname">NASDAQ COMPOSITE · 5 DAYS</div>
          <div className="hrow">
            <div className="hp num">{hero.p.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</div>
            <div className={"hc num " + (hero.c >= 0 ? "up" : "dn")}>{pct(hero.c)}</div>
            <div className="range num">Day high <b>{fmt(hero.hi)}</b><br />Day low <b>{fmt(hero.lo)}</b></div>
          </div>
          <div className="chart"><Spark d={hero.spark} ts={hero.ts} base={hero.prev} w={650} h={206} sw={2} axis /></div>
        </div>
        <div className="grid">
          {top.map((x, i) => (
            <div className="tile" key={x.sym} onClick={() => yahoo(x.sym)}>
              <div className="top"><span className="s"><em className="rk">#{i + 1}</em>{x.sym}</span>
                <span className={"c num " + (x.c >= 0 ? "up" : "dn")}>{pct(x.c)}</span></div>
              <div className="p num">{fmt(x.p)}<span className="tcap">{cap(x.cap)}</span></div>
              <Spark d={x.spark} base={x.prev} w={186} h={34} />
            </div>))}
        </div>
      </div>}
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
  .list { padding:6px 8px 0 }
  .row { display:grid; grid-template-columns: 10px 1fr auto 30px; align-items:center; gap:9px; height:33px; padding:0 9px; border-radius:8px; cursor:pointer }
  .row:hover { background:rgba(255,179,92,.08) } .row:hover .name { color:#ffb35c }
  .dot { width:7px; height:7px; border-radius:50% }
  .name { font-weight:600; font-size:12.5px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis }
  .name i { font-style:normal; color:#ffb35c; font-size:10px; margin-left:6px; font-weight:500 }
  .br { font:10px "SF Mono", Menlo, monospace; color:#d9b48a; background:rgba(255,179,92,.07); border:1px solid rgba(255,179,92,.14); border-radius:5px; padding:1px 6px; max-width:96px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis }
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

# ───────────────────────── AI & TECH WIRE ─────────────────────────
widget("ai-wire", r'''// Top 5 tech stories ranked for a software engineer in the job market (relevance x freshness, see market.py);
// layoff news is flagged red and pinned. Click to open.
import { run } from "uebersicht";
export const command = "%%PY%% ~/.stark/market.py json tech";
export const refreshFrequency = 15 * 60 * 1000;
export const className = `
  %%POS%%%%SHARED%%
  .list { padding:6px 8px }
  .row { display:flex; align-items:center; gap:10px; height:46px; padding:0 10px; border-radius:8px; cursor:pointer }
  .row:hover { background:rgba(127,220,255,.07) } .row:hover .t { color:#fff }
  .tag { flex:none; width:54px; text-align:center; font-size:8.5px; font-weight:800; letter-spacing:.08em; padding:2px 0; border-radius:4px }
  .src { flex:none; width:86px; white-space:nowrap; font-size:9px; font-weight:700; letter-spacing:.08em; color:#8c8178 }
  .t { flex:1; display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; overflow:hidden; color:#e6dcd2; font-size:12.5px; line-height:1.35 }
  .a { flex:none; width:30px; text-align:right; font-size:10.5px; color:#6f665f }
  /* layoff / job-cut headlines: pure red warning row, pinned to the top */
  .row.alert { background:rgba(255,59,48,.16); box-shadow: inset 3px 0 0 #ff3b30; animation: alertGlow 2.6s ease-in-out infinite }
  .row.alert:hover { background:rgba(255,59,48,.26) }
  .row.alert .t, .row.alert:hover .t { color:#ff453a; font-weight:700 }
  .row.alert .src, .row.alert .a { color:#ff8a80 }
  .row.alert .tag { color:#fff; background:#ff3b30 }
  @keyframes alertGlow { 50% { background:rgba(255,59,48,.24) } }
  .alertsub { color:#ff453a; font-weight:700; margin-right:8px }
`;
%%AGO%%
export const render = ({ output }) => {
  let n = []; try { n = JSON.parse(output); } catch (e) {}
  // market.py already ranks: layoff alerts first, then relevance to a software engineer x freshness
  const alerts = n.filter(h => h.alert).length;
  const TAGS = { JOBS: "#ffb35c", AI: "#7fdcff", DEV: "#c4a1ff", "BIG TECH": "#e6dcd2", STARTUPS: "#4ade80", TECH: "#8c8178" };
  return (
    <div>
      <header><span style={{ color: "#7fdcff" }}>✦</span><h1>AI &amp; TECH WIRE</h1><span className="sub">{alerts > 0 && <span className="alertsub">⚠ {alerts} LAYOFF ALERT{alerts > 1 ? "S" : ""}</span>}TOP 5 · <b style={{ color: "#7fdcff" }}>RANKED FOR SOFTWARE ENGINEERS</b></span></header>
      <div className="list">
        {n.slice(0, 5).map(h => (
          <div className={"row" + (h.alert ? " alert" : "")} key={h.l} onClick={() => run(`open "${h.l}"`)}>
            {h.alert ? <span className="tag">⚠ LAYOFFS</span>
              : <span className="tag" style={{ color: TAGS[h.tag] || "#8c8178", background: "rgba(255,255,255,.05)" }}>{h.tag || "TECH"}</span>}
            <span className="src">{h.src.toUpperCase()}</span>
            <span className="t">{h.t}</span><span className="a num">{ago(h.d)}</span>
          </div>))}
      </div>
    </div>
  );
};''')

# ───────────────────────── TECH MOVERS ─────────────────────────
widget("movers", r'''// Today's top 3 gainers and top 3 losers across the tech pool. Edit the pool in ~/.stark/market.py (MOVERS).
import { run } from "uebersicht";
export const command = "%%PY%% ~/.stark/market.py json movers";
export const refreshFrequency = 5 * 60 * 1000;
export const className = `
  %%POS%%%%SHARED%%
  .list { padding:5px 8px }
  .row { display:grid; grid-template-columns: 1fr 64px 66px 62px; align-items:center; gap:8px; height:31px; padding:0 9px; border-radius:8px; cursor:pointer }
  .grp { display:flex; align-items:center; gap:8px; padding:6px 9px 2px; font-size:9px; font-weight:700; letter-spacing:.14em }
  .grp i { flex:1; height:1px; background:rgba(255,255,255,.06) }
  .none { padding:6px 9px; font-size:11px; color:#6f665f }
  .row:hover { background:rgba(255,179,92,.08) }
  .s { font-size:11.5px; font-weight:700; letter-spacing:.04em; color:#e6dcd2 }
  .s small { display:block; font-size:8.5px; font-weight:600; letter-spacing:.1em; color:#6f665f; margin-top:-1px }
  .p { text-align:right; font-size:12px }
  .c { text-align:right; font-size:10.5px; font-weight:600; padding:2px 0; border-radius:5px }
`;
%%FMT%%
%%SPARK%%
export const render = ({ output }) => {
  let q = []; try { q = JSON.parse(output); } catch (e) {}
  const gain = q.filter(x => x.c > 0).sort((a, b) => b.c - a.c).slice(0, 3);
  const lose = q.filter(x => x.c < 0).sort((a, b) => a.c - b.c).slice(0, 3);
  const up = q.filter(x => x.c >= 0).length;
  const Row = x => (
    <div className="row" key={x.sym} onClick={() => run(`open "https://finance.yahoo.com/quote/${x.sym}"`)}>
      <span className="s">{x.sym}{x.name !== x.sym && <small>{x.name}</small>}</span>
      <Spark d={x.spark} base={x.prev} w={64} h={18} fill={false} sw={1.4} />
      <span className="p num">{fmt(x.p)}</span>
      <span className={"c num " + (x.c >= 0 ? "up" : "dn")} style={{ background: x.c >= 0 ? "rgba(74,222,128,.08)" : "rgba(248,113,113,.08)" }}>{x.c >= 0 ? "+" : ""}{x.c.toFixed(2)}%</span>
    </div>);
  return (
    <div>
      <header><span style={{ color: "#4ade80" }}>⇅</span><h1>TECH MOVERS</h1><span className="sub"><b style={{ color: "#4ade80" }}>{up}</b> UP · <b style={{ color: "#f87171" }}>{q.length - up}</b> DOWN · OF {q.length}</span></header>
      <div className="list">
        <div className="grp up">▲ TOP GAINERS<i /></div>
        {gain.length ? gain.map(Row) : <div className="none">Nothing up today</div>}
        <div className="grp dn">▼ TOP LOSERS<i /></div>
        {lose.length ? lose.map(Row) : <div className="none">Nothing down today</div>}
      </div>
    </div>
  );
};''')

# ───────────────────────── MAIL ─────────────────────────
widget("mail", r'''// Unread email: Gmail's Primary tab + iCloud inbox as is (see mail.sh / mail_direct.py). Click to open in Mail.
import { run } from "uebersicht";
export const command = "~/.stark/mail.sh";
export const refreshFrequency = 30 * 1000;
export const className = `
  %%POS%%%%SHARED%%
  .list { padding:4px 8px }
  .it { display:grid; grid-template-columns: 8px 1fr auto; column-gap:9px; align-items:center; height:46px; padding:0 9px; border-radius:9px; cursor:pointer }
  .it:hover { background:rgba(255,179,92,.08) }
  .dot { width:7px; height:7px; border-radius:50%; grid-row: 1 / span 2 }
  .from { font-size:12.5px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; color:#e6dcd2 }
  .subj { grid-column: 2 / span 2; font-size:11.5px; color:#8c8178; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; margin-top:2px }
  .unread .from { font-weight:700; color:#fff7ee } .unread .subj { color:#d9cfc6 }
  .t { font-size:10px; color:#6f665f; display:flex; align-items:center; gap:6px }
  .acc { font-size:8.5px; font-weight:700; letter-spacing:.08em; padding:1px 5px; border-radius:4px }
  .empty { padding:78px 20px 0; text-align:center; color:#8c8178; line-height:1.6 }
  .hint { position:absolute; left:0; right:0; bottom:14px; text-align:center; font-size:10px; color:#6f665f }
  .hint b { color:#f87171; font-weight:600 }
  .empty b { color:#ffb35c; font-weight:600 }
  .sec { display:flex; align-items:center; gap:7px; padding:7px 9px 3px; font-size:9.5px; font-weight:700; letter-spacing:.12em }
  .sec .line { flex:1; height:1px; background:rgba(255,255,255,.07) }
  .sec .n { color:#8c8178; font-weight:600; letter-spacing:.06em }
  .none { padding:6px 9px 8px; font-size:11px; color:#6f665f }
  .tabs { display:flex; gap:4px; margin:0 14px 2px; padding:3px; border-radius:9px; background:rgba(0,0,0,.18) }
  .tab { flex:1; display:flex; justify-content:center; align-items:center; gap:6px; height:22px; border-radius:6px; cursor:pointer;
         font-size:9.5px; font-weight:700; letter-spacing:.1em; color:#8c8178 }
  .tab:hover { color:#e6dcd2 } .tab.on { background:rgba(255,255,255,.08); color:#fff7ee }
  .tab i { font-style:normal; font-weight:600; color:#6f665f } .tab.on i { color:#ffb35c }
`;
// Account picker (Gmail / iCloud) — kept in widget state and remembered across restarts.
const savedPick = () => { try { return localStorage.getItem("mail-pick") || "Gmail"; } catch (e) { return "Gmail"; } };
export const initialState = { output: "", pick: savedPick() };
export const updateState = (ev, prev) => ev.type === "PICK" ? { ...prev, pick: ev.pick } : { ...prev, output: ev.output, error: ev.error };
// iCloud only depends on the Mail app until its app password is in the Keychain (then mail_direct.py reads it)
const viaApp = m => !(m.direct || []).includes("iCloud");
const problem = m => { const e = m.errors || {}, late = m.icloud_synced ? Date.now() / 1000 - m.icloud_synced : 0;
  return e.Gmail ? "Gmail not syncing" : e.iCloud ? "iCloud not syncing"
    : viaApp(m) && m.mail_app === false && m.running ? "Mail closed · iCloud paused"
    : viaApp(m) && m.mail_app && late > 25 * 60 ? "iCloud late " + Math.round(late / 60) + "m" : null; };
const ACC = a => /gmail|google/i.test(a) ? ["GMAIL", "#f87171", "rgba(248,113,113,.12)"] : /icloud/i.test(a) ? ["ICLOUD", "#7fdcff", "rgba(127,220,255,.1)"] : [a.toUpperCase().slice(0, 8), "#ffb35c", "rgba(255,179,92,.1)"];
const name = f => (f || "").replace(/\s*<.*>\s*$/, "").replace(/^"|"$/g, "") || f;
const when = d => { const t = new Date(d), now = new Date();
  return t.toDateString() === now.toDateString() ? t.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" })
    : (now - t) < 6 * 864e5 ? t.toLocaleDateString("en-GB", { weekday: "short" }) : t.toLocaleDateString("en-GB", { day: "numeric", month: "short" }); };
export const render = ({ output, pick }, dispatch) => {
  let m = null; try { m = JSON.parse(output); } catch (e) {}
  const choose = p => { try { localStorage.setItem("mail-pick", p); } catch (e) {} dispatch({ type: "PICK", pick: p }); };
  const mail = m ? m.mail.filter(x => !x.read).sort((a, b) => new Date(b.d) - new Date(a.d)) : [];
  const accs = m ? m.accounts || [] : [];
  const unread = m ? m.unread || 0 : 0;
  const shown = accs.includes(pick) ? [pick] : accs.slice(0, 1);
  return (
    <div>
      <header><span style={{ color: "#ffb35c" }}>✉</span><h1>MAIL</h1>
        <span className="sub"><b>{unread}{m && m.more ? "+" : ""}</b> UNREAD</span></header>
      {!m ? <div className="empty">Checking Mail…</div>
        : !m.running ? <div className="empty">Open the <b>Mail</b> app to see your latest emails here.</div>
        : <div>
        {accs.length > 1 && <div className="tabs">
          {accs.map(p => <span key={p} className={"tab" + (shown[0] === p ? " on" : "")} onClick={() => choose(p)}>
            {ACC(p)[0]}<i>{(m.counts || {})[p] ?? 0}</i></span>)}
        </div>}
        <div className="list">
          {shown.map(a => { const [tag, c, bg] = ACC(a), items = mail.filter(x => x.acc === a), n = (m.counts || {})[a] ?? items.length;
            return <div key={a}>
              <div className="sec"><span className="acc" style={{ color: c, background: bg }}>{tag}</span>
                <span className="n">{n} UNREAD</span><span className="line" /></div>
              {(m.errors || {})[a] ? <div className="none" style={{ color: "#ff6b6b" }}>⚠ Can't reach {a} right now. Retrying every 30 s.</div>
                : !items.length ? <div className="none">✓ {a === "Gmail" ? "Nothing new in Primary" : "No unread email"}</div>
                : items.slice(0, 4).map(x => (
                <div className={"it" + (x.read ? "" : " unread")} key={x.id + x.acc}
                     onClick={() => run(`open "message://%3c${encodeURIComponent(x.id)}%3e"`)}>
                  <span className="dot" style={{ background: x.read ? "transparent" : c, boxShadow: x.read ? "none" : `0 0 6px ${c}` }} />
                  <span className="from">{name(x.from)}</span>
                  <span className="t num">{when(x.d)}</span>
                  <span className="subj">{x.subj || "(no subject)"}</span>
                </div>))}
            </div>; })}
        </div></div>}
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
h(372, 392, 156); h(372, 392, 389); h(372, 392, 622); h(372, 392, 837)   # left column ↔ centre
h(1078, 1098, 182); h(1078, 1098, 472); h(1078, 1098, 784)              # centre ↔ right column
for y in (256, 502, 722): v(120, y, y + 20); v(284, y, y + 20)          # left stack
v(560, 616, 636); v(910, 616, 636)                                      # markets ↔ news
v(1180, 308, 328); v(1356, 308, 328)
v(1180, 616, 636); v(1356, 616, 636)                                    # batcave ↔ ai
POS["aa-links"] = (0, 0, 0, 0)
widget("aa-links", '''// Glowing connectors between panels (file name sorts first so it draws behind them).
export const command = "true";
export const refreshFrequency = 2000;
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
    tx = e.clientX; ty = e.clientY; ring.classList.add("on");
    aim.style.transform = `translate(${tx}px, ${ty}px)`; aim.classList.toggle("on", !!(e.target.closest && e.target.closest(".widget")));
    const t = e.target.closest ? e.target.closest(".row,.tile,.it,.hero,header") : null;
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
  const loop = () => { x += (tx - x) * 0.24; y += (ty - y) * 0.24; ring.style.transform = `translate(${x}px, ${y}px)`; if (window.__hudCursor === "%%BUILD%%") requestAnimationFrame(loop); };
  loop();
};
const PAIRS = [["clock", "weather"], ["weather", "system"], ["system", "connections"], ["markets", "ai-wire"],
  ["batcave", "mail"], ["mail", "movers"], ["clock", "markets"], ["weather", "markets"], ["system", "ai-wire"],
  ["connections", "ai-wire"], ["markets", "batcave"], ["markets", "mail"], ["ai-wire", "movers"]];
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
    if (window.__hudLinks === "%%BUILD%%") requestAnimationFrame(tick); };
  tick();
};
export const className = `
  left: 0; top: 0; width: 100%; height: 100%; pointer-events: none;
  .flow { stroke-dasharray: 3 4; animation: f 1.6s linear infinite } @keyframes f { to { stroke-dashoffset: -14 } }
  circle { animation: p 2.6s ease-in-out infinite } @keyframes p { 50% { opacity:.4 } }
`;
const FONTS = "@import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@500;600;700&family=Rajdhani:wght@500;600;700&family=Share+Tech+Mono&display=swap');";
export const render = () => { installCursor(); installLinks(); return (
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
