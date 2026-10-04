// Hides the system pointer while it is over an uncovered dashboard panel, so only the HUD aimer + ring
// (drawn by the aa-links widget) shows there. Übersicht's desktop-level web view can't hide it itself.
// Panel rects come from ~/.stark/.panels.json (written by build_widgets.py, in Übersicht canvas pixels).
import AppKit

// Lets a background process hide the cursor (same trick as Cursorcerer).
@_silgen_name("_CGSDefaultConnection") func _CGSDefaultConnection() -> Int32
@_silgen_name("CGSSetConnectionProperty")
func CGSSetConnectionProperty(_ cid: Int32, _ target: Int32, _ key: CFString, _ value: CFTypeRef) -> Int32
let cid = _CGSDefaultConnection()
_ = CGSSetConnectionProperty(cid, cid, "SetsCursorInBackground" as CFString, kCFBooleanTrue)

let panelsPath = NSHomeDirectory() + "/.stark/.panels.json"
var panels: [CGRect] = [], panelsMtime = Date.distantPast
var canvas = CGPoint.zero, canvasPid: Int32 = 0
var hidden = false, tick = 0, last = CGPoint(x: -1, y: -1)

func loadPanels() {
  guard let m = (try? FileManager.default.attributesOfItem(atPath: panelsPath))?[.modificationDate] as? Date,
        m != panelsMtime, let d = FileManager.default.contents(atPath: panelsPath),
        let a = try? JSONSerialization.jsonObject(with: d) as? [[Double]] else { return }
  panelsMtime = m
  panels = a.filter { $0.count == 4 }.map { CGRect(x: $0[0], y: $0[1], width: $0[2], height: $0[3]) }
}

// Windows in front-to-back order; the Übersicht canvas is its layer -1 window.
func windows() -> [[String: Any]] {
  (CGWindowListCopyWindowInfo([.optionOnScreenOnly, .excludeDesktopElements], kCGNullWindowID) as? [[String: Any]]) ?? []
}

func findCanvas(_ ws: [[String: Any]]) {
  for w in ws where (w[kCGWindowOwnerName as String] as? String ?? "").contains("bersicht")
                  && (w[kCGWindowLayer as String] as? Int) == -1 {
    if let b = w[kCGWindowBounds as String] as? NSDictionary, let r = CGRect(dictionaryRepresentation: b) {
      canvas = r.origin; canvasPid = w[kCGWindowOwnerPID as String] as? Int32 ?? 0; return }
  }
  canvasPid = 0
}

func covered(_ p: CGPoint, _ ws: [[String: Any]]) -> Bool {
  for w in ws {
    let layer = w[kCGWindowLayer as String] as? Int ?? 0, alpha = w[kCGWindowAlpha as String] as? Double ?? 1
    if layer < 0 || alpha < 0.05 || (w[kCGWindowOwnerPID as String] as? Int32) == canvasPid { continue }
    if let b = w[kCGWindowBounds as String] as? NSDictionary, let r = CGRect(dictionaryRepresentation: b), r.contains(p) { return true }
  }
  return false
}

func setHidden(_ h: Bool) {
  if h == hidden { return }
  hidden = h
  if h { CGDisplayHideCursor(CGMainDisplayID()) } else { CGDisplayShowCursor(CGMainDisplayID()) }
}

func step() {
  if tick % 60 == 0 { loadPanels() }
  tick += 1
  // CG coordinates: origin top-left of the main display.
  let m = NSEvent.mouseLocation, h = NSScreen.screens.first?.frame.height ?? 0
  let p = CGPoint(x: m.x, y: h - m.y)
  if p == last && tick % 15 != 0 { return }  // idle: re-check a few times a second for windows moving over it
  last = p
  let ws = windows()
  if tick % 30 == 1 { findCanvas(ws) }
  let local = CGPoint(x: p.x - canvas.x, y: p.y - canvas.y)
  let over = canvasPid != 0 && panels.contains { $0.contains(local) } && !covered(p, ws)
  setHidden(over)
}

signal(SIGTERM) { _ in CGDisplayShowCursor(CGMainDisplayID()); exit(0) }
signal(SIGINT) { _ in CGDisplayShowCursor(CGMainDisplayID()); exit(0) }
Timer.scheduledTimer(withTimeInterval: 1.0 / 60, repeats: true) { _ in step() }
RunLoop.main.run()
