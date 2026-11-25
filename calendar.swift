// Calendar events for the clock's day timeline: today 00:00 → tomorrow 24:00, as JSON on stdout.
// Built by build_widgets.py into ~/.stark/calendar (git-ignored). Run by Übersicht, so macOS asks once whether
// Übersicht may read your calendars. Prints {"ok":false} when access isn't granted.
import EventKit
import Foundation

let store = EKEventStore()
func granted() -> Bool {
  let s = EKEventStore.authorizationStatus(for: .event)
  if s.rawValue == 3 { return true }   // fullAccess (= the old .authorized)
  if s != .notDetermined { return false }
  let sem = DispatchSemaphore(value: 0); var ok = false
  if #available(macOS 14.0, *) { store.requestFullAccessToEvents { g, _ in ok = g; sem.signal() } }
  else { store.requestAccess(to: .event) { g, _ in ok = g; sem.signal() } }
  _ = sem.wait(timeout: .now() + 60)
  return ok
}
guard granted() else { print("{\"ok\":false}"); exit(0) }

let start = Calendar.current.startOfDay(for: Date()), end = start.addingTimeInterval(2 * 86400)
let skip: Set<String> = ["Birthdays"]   // birthdays come through as all-day noise
var out: [[String: Any]] = []
for e in store.events(matching: store.predicateForEvents(withStart: start, end: end, calendars: nil)) {
  if skip.contains(e.calendar.title) || e.status == .canceled { continue }
  out.append(["t": e.title ?? "Event", "s": Int(e.startDate.timeIntervalSince1970), "e": Int(e.endDate.timeIntervalSince1970),
              "all": e.isAllDay, "cal": e.calendar.title, "loc": e.location ?? ""])
}
let data = try! JSONSerialization.data(withJSONObject: ["ok": true, "ev": out])
print(String(data: data, encoding: .utf8)!)
