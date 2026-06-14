import WidgetKit
import Foundation

struct GlucoseEntry: TimelineEntry {
    let date: Date
    let reading: GlucoseReading?
    let deltaMgdl: Int?
    let useMmol: Bool
    let backgroundColorHex: String
    let alertLowMgdl: Int
    let alertHighMgdl: Int
}

struct GlucoseTimelineProvider: TimelineProvider {
    func placeholder(in context: Context) -> GlucoseEntry {
        GlucoseEntry(
            date: .now,
            reading: GlucoseReading(valueMgdl: 100, trend: .flat, date: .now),
            deltaMgdl: 2,
            useMmol: true,
            backgroundColorHex: DeviceTheme.defaultBackgroundHex,
            alertLowMgdl: 70,
            alertHighMgdl: 180
        )
    }

    func getSnapshot(in context: Context, completion: @escaping (GlucoseEntry) -> Void) {
        completion(currentEntry(at: .now))
    }

    /// Entries every 5 minutes for the next 30 minutes so the displayed
    /// reading age stays current, then iOS asks again. Fresh data arrives
    /// via WidgetCenter.reloadAllTimelines() from the app on each sync.
    func getTimeline(in context: Context, completion: @escaping (Timeline<GlucoseEntry>) -> Void) {
        let entries = (0..<6).map { i in
            currentEntry(at: Date().addingTimeInterval(Double(i) * 300))
        }
        completion(Timeline(entries: entries, policy: .atEnd))
    }

    private func currentEntry(at date: Date) -> GlucoseEntry {
        let readings = GlucoseStore.loadFromDisk()
        let prefs = AppSettings.widgetSnapshot()
        let latest = readings.last
        let delta: Int? = readings.count >= 2
            ? readings[readings.count - 1].valueMgdl - readings[readings.count - 2].valueMgdl
            : nil
        return GlucoseEntry(
            date: date,
            reading: latest,
            deltaMgdl: delta,
            useMmol: prefs.useMmol,
            backgroundColorHex: prefs.backgroundColorHex,
            alertLowMgdl: prefs.alertLowMgdl,
            alertHighMgdl: prefs.alertHighMgdl
        )
    }
}
