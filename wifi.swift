// Prints the current Wi-Fi link as JSON (CoreWLAN: instant, unlike system_profiler).
// macOS only reveals the network name to apps with Location access, so "ssid" is often null.
import CoreWLAN
import Foundation
guard let i = CWWiFiClient.shared().interface(), i.powerOn() else { print("{}"); exit(0) }
var o: [String: Any] = ["rssi": i.rssiValue(), "noise": i.noiseMeasurement(), "rate": Int(i.transmitRate())]
if let s = i.ssid() { o["ssid"] = s }
if let c = i.wlanChannel() {
  o["ch"] = c.channelNumber
  o["band"] = [CWChannelBand.band2GHz: "2.4", .band5GHz: "5", .band6GHz: "6"][c.channelBand] ?? ""
  o["width"] = [CWChannelWidth.width20MHz: 20, .width40MHz: 40, .width80MHz: 80, .width160MHz: 160][c.channelWidth] ?? 0
}
o["phy"] = [CWPHYMode.mode11a: "a", .mode11b: "b", .mode11g: "g", .mode11n: "4", .mode11ac: "5", .mode11ax: "6"][i.activePHYMode()] ?? ""
print(String(data: try! JSONSerialization.data(withJSONObject: o), encoding: .utf8)!)
