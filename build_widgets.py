"""Builds the Übersicht desktop dashboard from one shared layout grid.
Run: python3 ~/.stark/build_widgets.py   (then Übersicht reloads automatically)"""
import os, re, shutil, urllib.parse

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
  -webkit-user-select: none; user-select: none; cursor: default; box-sizing: border-box;
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
  &.snap { border-color: rgba(245,177,76,.55) }
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
"""

AGO = """const ago = d => {
  const m = Math.round((Date.now() - new Date(d)) / 60000);
  return isNaN(m) ? "" : m < 60 ? `${m}m` : m < 1440 ? `${Math.round(m / 60)}h` : `${Math.round(m / 1440)}d`;
};"""

SPARK = """let _sid = 0;
const Spark = ({ d, w, h, up, fill = true, sw = 1.6 }) => {
  if (!d || d.length < 2) return <svg width={w} height={h} />;
  const mn = Math.min(...d), mx = Math.max(...d), r = (mx - mn) || 1;
  const pts = d.map((v, i) => [(i / (d.length - 1)) * w, h - 3 - ((v - mn) / r) * (h - 6)]);
  const line = pts.map((p, i) => (i ? "L" : "M") + p[0].toFixed(1) + " " + p[1].toFixed(1)).join(" ");
  const col = up ? "#4ade80" : "#f87171", id = "g" + (++_sid);
  return (
    <svg width={w} height={h} style={{ display: "block", overflow: "visible" }}>
      <defs><linearGradient id={id} x1="0" y1="0" x2="0" y2="1">
        <stop offset="0" stopColor={col} stopOpacity=".28" /><stop offset="1" stopColor={col} stopOpacity="0" />
      </linearGradient></defs>
      {fill && <path d={`${line} L ${w} ${h} L 0 ${h} Z`} fill={`url(#${id})`} />}
      <path d={line} fill="none" stroke={col} strokeWidth={sw} strokeLinejoin="round" strokeLinecap="round" />
      <circle cx={pts[pts.length - 1][0]} cy={pts[pts.length - 1][1]} r="2.6" fill={col} />
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


# ── Sci-fi HUD palette: holographic cyan, Stark gold, neon green/red ──
THEME = [
    ("rgba(255,179,92,", "rgba(245,177,76,"), ("rgba(255,214,170,", "rgba(255,255,255,"),
    ("rgba(74,222,128,", "rgba(79,209,139,"), ("rgba(248,113,113,", "rgba(255,107,107,"), ("rgba(36,27,22,1)", "rgba(24,20,18,1)"),
    ("#ffb35c", "#f5b14c"), ("#4ade80", "#4fd18b"), ("#f87171", "#ff6b6b"), ("#7fdcff", "#7cc8ff"),
    ("#fff7ee", "#ffffff"), ("#f3ece6", "#f2ede6"), ("#e6dcd2", "#ebe5dd"), ("#d9cfc6", "#d9d2c8"),
    ("#a39a92", "#9b938a"), ("#8c8178", "#857d75"), ("#6f665f", "#6b645d"), ("#4a403a", "#3e3934"),
    ("#d9b48a", "#e9c48e"), ("#a78bfa", "#b39cff"), ("#c4a1ff", "#b39cff"),
]

HUD = """// Drag a panel by its header: it snaps to neighbouring panels, the screen margins and its home slot.
// Released near home it glides back; double-click the header to send it home. Cursor light for the glass.
const hud = name => el => {
  if (!el) return; const box = el.parentElement; if (!box || box.__hud) return; box.__hud = true;
  box.dataset.hud = name;
  const key = "hud-pos:" + name, anywhere = name === "clock", GAP = 20, MAG = 16, HOME_R = 70;
  const home = { x: box.offsetLeft, y: box.offsetTop };
  const EASE = "cubic-bezier(.2,.9,.25,1.15)", BASE = "border-color .3s, box-shadow .3s, transform .3s";
  const place = (x, y, glide) => {
    box.style.transition = glide ? `left .45s ${EASE}, top .45s ${EASE}, ${BASE}` : BASE;
    box.style.left = x + "px"; box.style.top = y + "px"; };
  try { const p = JSON.parse(localStorage.getItem(key)); if (p) place(p.x, p.y, false); } catch (e) {}
  box.addEventListener("mousemove", e => { const r = box.getBoundingClientRect();
    box.style.setProperty("--mx", (e.clientX - r.left) + "px"); box.style.setProperty("--my", (e.clientY - r.top) + "px"); });
  box.addEventListener("mouseleave", () => box.style.setProperty("--mx", "-999px"));
  const nearest = (v, cands) => { let best = v, d = MAG; for (const c of cands) { const k = Math.abs(c - v); if (k < d) { d = k; best = c; } } return best; };
  box.addEventListener("mousedown", e => {
    if (e.button !== 0 || !(anywhere || e.target.closest("header"))) return;
    e.preventDefault();
    const sx = e.clientX, sy = e.clientY, ox = box.offsetLeft, oy = box.offsetTop, W = box.offsetWidth, H = box.offsetHeight;
    const xs = [32, window.innerWidth - W - 32, home.x], ys = [20, window.innerHeight - H - 20, home.y];
    document.querySelectorAll("[data-hud]").forEach(o => { if (o === box) return;
      const l = o.offsetLeft, t = o.offsetTop, r = l + o.offsetWidth, b = t + o.offsetHeight;
      xs.push(l, r - W, r + GAP, l - W - GAP); ys.push(t, b - H, b + GAP, t - H - GAP); });
    window.__hudZ = (window.__hudZ || 10) + 1; box.style.zIndex = window.__hudZ; box.classList.add("dragging");
    const mv = ev => {
      let x = ox + ev.clientX - sx, y = oy + ev.clientY - sy;
      const nx = nearest(x, xs), ny = nearest(y, ys);
      box.classList.toggle("snap", nx !== x || ny !== y);
      x = Math.max(0, Math.min(window.innerWidth - W, nx)); y = Math.max(0, Math.min(window.innerHeight - 40, ny));
      place(Math.round(x), Math.round(y), false); };
    const up = () => {
      document.removeEventListener("mousemove", mv); document.removeEventListener("mouseup", up);
      box.classList.remove("dragging", "snap");
      if (Math.hypot(box.offsetLeft - home.x, box.offsetTop - home.y) < HOME_R) { place(home.x, home.y, true); localStorage.removeItem(key); }
      else localStorage.setItem(key, JSON.stringify({ x: box.offsetLeft, y: box.offsetTop })); };
    document.addEventListener("mousemove", mv); document.addEventListener("mouseup", up);
  });
  box.addEventListener("dblclick", e => { if (!(anywhere || e.target.closest("header"))) return;
    localStorage.removeItem(key); place(home.x, home.y, true); });
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

# ── HUD cursors (SVG crosshairs) ──
def _cursor(color, size=28):
    c = size // 2
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}">'
           f'<g fill="none" stroke="{color}" stroke-width="1.6">'
           f'<circle cx="{c}" cy="{c}" r="5.5"/>'
           f'<path d="M{c} 1v6M{c} {size-7}v6M1 {c}h6M{size-7} {c}h6"/></g>'
           f'<circle cx="{c}" cy="{c}" r="1.6" fill="{color}"/></svg>')
    return f'url("data:image/svg+xml,{urllib.parse.quote(svg)}") {c} {c}'
CURSOR = _cursor("#f5b14c") + ", crosshair"
CURSOR_HOT = _cursor("#ffd696") + ", pointer"

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
    body = body.replace("cursor: default;", f"cursor: {CURSOR};").replace("cursor:pointer", f"cursor:{CURSOR_HOT}")
    if name != "aa-links":
        body = re.sub(r"(return \(\s*<div)>", lambda m: m.group(1) + ' ref={hud("' + name + '")}>', body)
        body = re.sub(r"(return <div)>", lambda m: m.group(1) + ' ref={hud("' + name + '")}>', body)
        body = body.replace("\nexport const render", "\n" + HUD + "\nexport const render", 1)
    with open(os.path.join(W, name + ".jsx"), "w") as f:
        f.write(body + "\n")


# ───────────────────────── CLOCK ─────────────────────────
widget("clock", r'''// Clock, greeting and world-market sessions.
export const command = "date +%s";
export const refreshFrequency = 1000;
export const className = `
  %%POS%%%%SHARED%%
  padding: 18px 18px 16px 20px; cursor: grab;
  .time { display:flex; align-items:baseline; gap:8px }
  .time b { font: 200 60px -apple-system, "SF Pro Display", sans-serif; letter-spacing:-.03em; line-height:1; color:#ffffff }
  .time span { font: 300 20px -apple-system, sans-serif; color:#f5b14c }
  .date { margin-top:8px; font: 500 14px -apple-system, sans-serif; color:#ebe5dd }
  .greet { margin-top:1px; font-size:12px; letter-spacing:.06em; color:#5f8a99 }
  .ex { display:grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap:7px; margin-top:12px }
  .cell { background:rgba(255,255,255,.04); border:1px solid rgba(255,255,255,.06); border-radius:12px; padding:6px 10px }
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
widget("connections", r'''// Live connections: throughput and latency to the services you use.
export const command = "~/.stark/network.sh";
export const refreshFrequency = 30 * 1000;
export const className = `
  %%POS%%%%SHARED%%
  .body { display:flex; align-items:center; padding:4px 10px 0 6px }
  .flow { stroke-dasharray: 3 5; animation: f 1.2s linear infinite } @keyframes f { to { stroke-dashoffset: -16 } }
  .pulse { animation: p 2.4s ease-in-out infinite } @keyframes p { 50% { opacity:.45 } }
  .rates { margin-left:auto; text-align:right; padding-right:8px }
  .rate { font: 200 25px -apple-system, sans-serif; line-height:1.15 } .rate small { font-size:10px; color:#8c8178; margin-left:3px }
  .rl { font-size:9.5px; letter-spacing:.16em; color:#8c8178; font-weight:600; margin-top:8px }
`;
const NODES = [[36, 28], [164, 28], [36, 112], [164, 112]];
const col = ms => !ms ? "#6f665f" : ms < 150 ? "#4ade80" : ms < 450 ? "#ffb35c" : "#f87171";
const rate = b => b > 1048576 ? [(b / 1048576).toFixed(1), "MB/s"] : [(b / 1024).toFixed(0), "KB/s"];
export const render = ({ output }) => {
  let n = null; try { n = JSON.parse(output); } catch (e) {}
  const svcs = n ? n.services : [];
  const [dv, du] = n ? rate(n.down) : ["—", ""], [uv, uu] = n ? rate(n.up) : ["—", ""];
  return (
    <div>
      <header><span style={{ color: "#ffb35c" }}>⟡</span><h1>CONNECTIONS</h1><span className="sub">{n ? <span>{n.dev.toUpperCase()} · <b>{n.ip}</b></span> : "…"}</span></header>
      <div className="body">
        <svg width="200" height="140" viewBox="0 0 200 140">
          {svcs.map((s, i) => <line key={"l" + i} className="flow" x1="100" y1="70" x2={NODES[i][0]} y2={NODES[i][1]} stroke={col(s.ms)} strokeWidth="1.3" strokeOpacity=".8" />)}
          <circle cx="100" cy="70" r="16" fill="rgba(36,27,22,1)" stroke="#ffb35c" strokeWidth="1.3" />
          <text x="100" y="73.5" textAnchor="middle" fontSize="7" fontWeight="700" fill="#ffb35c" letterSpacing=".5" fontFamily="Orbitron">CORE</text>
          {svcs.map((s, i) => { const [x, y] = NODES[i], below = y > 70; return (
            <g key={s.name}>
              <circle className="pulse" cx={x} cy={y} r="4.5" fill={col(s.ms)} style={{ filter: `drop-shadow(0 0 4px ${col(s.ms)})` }} />
              <text x={x} y={below ? y + 16 : y - 9} textAnchor="middle" fontSize="9" fill="#d9cfc6">{s.name} <tspan fill={col(s.ms)}>{s.ms ? s.ms + "ms" : "down"}</tspan></text>
            </g>); })}
        </svg>
        <div className="rates num">
          <div className="rl">DOWN</div><div className="rate up">↓ {dv}<small>{du}</small></div>
          <div className="rl">UP</div><div className="rate" style={{ color: "#7fdcff" }}>↑ {uv}<small>{uu}</small></div>
        </div>
      </div>
    </div>
  );
};''')

# ───────────────────────── MARKETS ─────────────────────────
widget("markets", r'''// Tech markets: NASDAQ hero chart, featured names and watchlist with 5-day sparklines. Edit symbols in ~/.stark/market.py (SPARK).
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
  .chart { margin-top:10px }
  .idx { display:grid; grid-template-columns: repeat(3, 1fr); gap:10px; padding:14px 16px 0 }
  .grid { display:grid; grid-template-columns: repeat(4, 1fr); gap:10px; padding:10px 16px 0 }
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
  const idx = ranked.slice(0, 3), watch = ranked.slice(3, 11);
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
          <div className="chart"><Spark d={hero.spark} w={650} h={136} up={hero.c >= 0} sw={2} /></div>
        </div>
        <div className="idx">
          {idx.map((x, i) => (
            <div className="tile" key={x.sym} onClick={() => yahoo(x.sym)}>
              <div style={{ flex: 1 }}><div className="s"><em className="rk">#{i + 1}</em>{x.name}<span className="cap">{cap(x.cap)}</span></div><div className="p num">{fmt(x.p)}</div>
                <div className={"c num " + (x.c >= 0 ? "up" : "dn")}>{pct(x.c)}</div></div>
              <Spark d={x.spark} w={64} h={36} up={x.c >= 0} />
            </div>))}
        </div>
        <div className="grid">
          {watch.map((x, i) => (
            <div className="tile" key={x.sym} onClick={() => yahoo(x.sym)}>
              <div className="top"><span className="s"><em className="rk">#{i + 4}</em>{x.sym}</span><span className={"c num " + (x.c >= 0 ? "up" : "dn")}>{pct(x.c)}</span></div>
              <div className="p num">{fmt(x.p)}<span className="tcap">{cap(x.cap)}</span></div>
              <Spark d={x.spark} w={128} h={30} up={x.c >= 0} />
            </div>))}
        </div>
      </div>}
    </div>
  );
};''')

# ───────────────────────── BATCAVE ─────────────────────────
widget("batcave", r'''// Batcave: git projects (click to open in VS Code) + 12-week commit activity.
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
        <h1>BATCAVE</h1><span className="sub"><b>{active}</b> ACTIVE · <b>{total}</b> COMMITS</span></header>
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
widget("ai-wire", r'''// AI & tech headlines, newest first (AI stories tagged). Click to open.
import { run } from "uebersicht";
export const command = "%%PY%% ~/.stark/market.py json tech";
export const refreshFrequency = 15 * 60 * 1000;
export const className = `
  %%POS%%%%SHARED%%
  .list { padding:6px 8px }
  .row { display:flex; align-items:center; gap:10px; height:29px; padding:0 10px; border-radius:8px; cursor:pointer }
  .row:hover { background:rgba(127,220,255,.07) } .row:hover .t { color:#fff }
  .tag { flex:none; width:24px; text-align:center; font-size:8.5px; font-weight:800; letter-spacing:.08em; padding:2px 0; border-radius:4px }
  .src { flex:none; width:66px; font-size:9px; font-weight:700; letter-spacing:.08em; color:#8c8178 }
  .t { flex:1; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; color:#e6dcd2; font-size:12.5px }
  .a { flex:none; width:30px; text-align:right; font-size:10.5px; color:#6f665f }
`;
%%AGO%%
export const render = ({ output }) => {
  let n = []; try { n = JSON.parse(output); } catch (e) {}
  n.sort((a, b) => new Date(b.d) - new Date(a.d));  // latest first
  return (
    <div>
      <header><span style={{ color: "#7fdcff" }}>✦</span><h1>AI &amp; TECH WIRE</h1><span className="sub">CNBC TECH · YAHOO · J.A.R.V.I.S. <b style={{ color: "#7fdcff" }}>BRIEFING</b></span></header>
      <div className="list">
        {n.slice(0, 8).map(h => (
          <div className="row" key={h.l} onClick={() => run(`open "${h.l}"`)}>
            <span className="tag" style={h.ai ? { color: "#7fdcff", background: "rgba(127,220,255,.12)" } : { color: "#6f665f", background: "rgba(255,214,170,.05)" }}>{h.ai ? "AI" : "TECH"}</span>
            <span className="src">{h.src.toUpperCase()}</span>
            <span className="t">{h.t}</span><span className="a num">{ago(h.d)}</span>
          </div>))}
      </div>
    </div>
  );
};''')

# ───────────────────────── TECH MOVERS ─────────────────────────
widget("movers", r'''// More tech stocks, ranked by today's move. Edit the list in ~/.stark/market.py (MOVERS).
import { run } from "uebersicht";
export const command = "%%PY%% ~/.stark/market.py json movers";
export const refreshFrequency = 5 * 60 * 1000;
export const className = `
  %%POS%%%%SHARED%%
  .list { padding:5px 8px }
  .row { display:grid; grid-template-columns: 1fr 64px 66px 62px; align-items:center; gap:8px; height:26px; padding:0 9px; border-radius:8px; cursor:pointer }
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
  q.sort((a, b) => b.c - a.c);
  const up = q.filter(x => x.c >= 0).length;
  return (
    <div>
      <header><span style={{ color: "#4ade80" }}>⇅</span><h1>TECH MOVERS</h1><span className="sub"><b style={{ color: "#4ade80" }}>{up}</b> UP · <b style={{ color: "#f87171" }}>{q.length - up}</b> DOWN</span></header>
      <div className="list">
        {q.slice(0, 9).map(x => (
          <div className="row" key={x.sym} onClick={() => run(`open "https://finance.yahoo.com/quote/${x.sym}"`)}>
            <span className="s">{x.sym}{x.name !== x.sym && <small>{x.name}</small>}</span>
            <Spark d={x.spark} w={64} h={18} up={x.c >= 0} fill={false} sw={1.3} />
            <span className="p num">{fmt(x.p)}</span>
            <span className={"c num " + (x.c >= 0 ? "up" : "dn")} style={{ background: x.c >= 0 ? "rgba(74,222,128,.08)" : "rgba(248,113,113,.08)" }}>{x.c >= 0 ? "+" : ""}{x.c.toFixed(2)}%</span>
          </div>))}
      </div>
    </div>
  );
};''')

# ───────────────────────── MAIL ─────────────────────────
widget("mail", r'''// Unread emails from every Mail.app account (iCloud, Gmail…). Click to open in Mail.
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
`;
const ACC = a => /gmail|google/i.test(a) ? ["GMAIL", "#f87171", "rgba(248,113,113,.12)"] : /icloud/i.test(a) ? ["ICLOUD", "#7fdcff", "rgba(127,220,255,.1)"] : [a.toUpperCase().slice(0, 8), "#ffb35c", "rgba(255,179,92,.1)"];
const name = f => (f || "").replace(/\s*<.*>\s*$/, "").replace(/^"|"$/g, "") || f;
const when = d => { const t = new Date(d), now = new Date();
  return t.toDateString() === now.toDateString() ? t.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" })
    : (now - t) < 6 * 864e5 ? t.toLocaleDateString("en-GB", { weekday: "short" }) : t.toLocaleDateString("en-GB", { day: "numeric", month: "short" }); };
export const render = ({ output }) => {
  let m = null; try { m = JSON.parse(output); } catch (e) {}
  const mail = m ? m.mail.filter(x => !x.read).sort((a, b) => new Date(b.d) - new Date(a.d)) : [];
  const accs = m ? m.accounts || [] : [];
  const unread = m ? m.unread || 0 : 0;
  const hasGmail = accs.some(a => /gmail|google/i.test(a));
  return (
    <div>
      <header><span style={{ color: "#ffb35c" }}>✉</span><h1>MAIL</h1>
        <span className="sub"><b>{unread}</b> UNREAD · {accs.map(a => ACC(a)[0]).join(" + ") || "MAIL"}</span></header>
      {!m ? <div className="empty">Checking Mail…</div>
        : !m.running ? <div className="empty">Open the <b>Mail</b> app to see your latest emails here.</div>
        : !mail.length ? <div className="empty">✓ Inbox zero<br /><span className="dim">No unread emails right now.</span></div>
        : <div className="list">
          {mail.slice(0, 5).map(x => { const [tag, c, bg] = ACC(x.acc); return (
            <div className={"it" + (x.read ? "" : " unread")} key={x.id + x.acc}
                 onClick={() => run(`open "message://%3c${encodeURIComponent(x.id)}%3e"`)}>
              <span className="dot" style={{ background: x.read ? "transparent" : "#ffb35c", boxShadow: x.read ? "none" : "0 0 6px #ffb35c" }} />
              <span className="from">{name(x.from)}</span>
              <span className="t num"><span className="acc" style={{ color: c, background: bg }}>{tag}</span>{when(x.d)}</span>
              <span className="subj">{x.subj || "(no subject)"}</span>
            </div>); })}
        </div>}
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
// Hidden once any panel has been dragged somewhere else (double-click headers to restore the default layout).
export const command = "true";
export const refreshFrequency = 2000;
const CURSOR_CSS = `
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
  if (window.__hudCursor) return; window.__hudCursor = true;
  const ring = document.createElement("div"); ring.id = "hud-ring"; ring.innerHTML = "<i></i><b></b>"; document.body.appendChild(ring);
  let x = -200, y = -200, tx = -200, ty = -200, hot = false;
  document.addEventListener("mousemove", e => {
    tx = e.clientX; ty = e.clientY; ring.classList.add("on");
    const t = e.target.closest ? e.target.closest(".row,.tile,.it,.hero,header") : null;
    hot = !!t && !t.matches("header");
    ring.classList.toggle("hot", hot); ring.classList.toggle("grab", !!t && t.matches("header"));
  });
  document.addEventListener("mouseout", e => { if (!e.relatedTarget) ring.classList.remove("on"); });
  document.addEventListener("mousedown", e => {
    ring.classList.add("down");
    const r = document.createElement("div"); r.className = "hud-ripple" + (hot ? " hot" : "");
    r.style.left = e.clientX + "px"; r.style.top = e.clientY + "px"; document.body.appendChild(r); setTimeout(() => r.remove(), 700);
  });
  document.addEventListener("mouseup", () => ring.classList.remove("down"));
  const loop = () => { x += (tx - x) * 0.24; y += (ty - y) * 0.24; ring.style.transform = `translate(${x}px, ${y}px)`; requestAnimationFrame(loop); };
  loop();
};
const PAIRS = [["clock", "weather"], ["weather", "system"], ["system", "connections"], ["markets", "ai-wire"],
  ["batcave", "mail"], ["mail", "movers"], ["clock", "markets"], ["weather", "markets"], ["system", "ai-wire"],
  ["connections", "ai-wire"], ["markets", "batcave"], ["markets", "mail"], ["ai-wire", "movers"]];
const LAYOUT_VERSION = "2";  // bump to send every panel back to its home slot once
const installLinks = () => {
  if (window.__hudLinks) return; window.__hudLinks = true;
  try { if (localStorage.getItem("hud-layout") !== LAYOUT_VERSION) {
    Object.keys(localStorage).filter(k => k.startsWith("hud-pos:")).forEach(k => localStorage.removeItem(k));
    localStorage.setItem("hud-layout", LAYOUT_VERSION); } } catch (e) {}
  const NS = "http://www.w3.org/2000/svg", svg = document.createElementNS(NS, "svg");
  svg.id = "hud-links";
  svg.style.cssText = "position:fixed;left:0;top:0;width:100%;height:100%;pointer-events:none;z-index:0;overflow:visible";
  document.body.prepend(svg);
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
    const now = Object.entries(boxes).map(([k, r]) => k + (r.left | 0) + "," + (r.top | 0)).join("|");
    if (now !== sig) { sig = now;
      PAIRS.forEach(([p, q], i) => { const g = els[i], a = boxes[p], b = boxes[q];
        if (!a || !b) { g.style.display = "none"; return; }
        const [x1, y1, x2, y2] = link(a, b), len = Math.hypot(x2 - x1, y2 - y1);
        if (len > 340 || len < 4) { g.style.display = "none"; return; }
        g.style.display = "";
        const straight = Math.abs(x1 - x2) < 1 || Math.abs(y1 - y2) < 1, mx = (x1 + x2) / 2;
        const d = straight ? `M${x1} ${y1}L${x2} ${y2}` : `M${x1} ${y1}C${mx} ${y1} ${mx} ${y2} ${x2} ${y2}`;
        g.children[0].setAttribute("d", d); g.children[1].setAttribute("d", d);
        g.children[2].setAttribute("cx", x1); g.children[2].setAttribute("cy", y1);
        g.children[3].setAttribute("cx", x2); g.children[3].setAttribute("cy", y2); }); }
    requestAnimationFrame(tick); };
  tick();
};
const moved = () => { try { return Object.keys(localStorage).some(k => k.startsWith("hud-pos:")); } catch (e) { return false; } };
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

print("wrote", sorted(f for f in os.listdir(W) if f.endswith(".jsx")))
