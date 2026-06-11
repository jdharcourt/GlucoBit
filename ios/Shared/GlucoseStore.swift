import Foundation
import Observation

enum AppGroup {
    static let identifier = "group.com.jdharcourt.glucobit"

    static var containerURL: URL {
        FileManager.default.containerURL(forSecurityApplicationGroupIdentifier: identifier)
        // Personal-team provisioning can refuse App Groups; fall back so the
        // app still works (the widget will just show no data in that case).
            ?? FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
    }
}

/// Rolling 24h store of glucose readings, persisted as JSON in the App Group
/// container so the widget extension can read it.
@Observable
final class GlucoseStore {
    private(set) var readings: [GlucoseReading] = []

    var latest: GlucoseReading? { readings.last }
    var previous: GlucoseReading? { readings.count >= 2 ? readings[readings.count - 2] : nil }

    /// Delta in mg/dL between the two most recent readings.
    var deltaMgdl: Int? {
        guard let latest, let previous else { return nil }
        return latest.valueMgdl - previous.valueMgdl
    }

    private static var fileURL: URL {
        AppGroup.containerURL.appendingPathComponent("glucose-history.json")
    }

    init() {
        readings = Self.loadFromDisk()
    }

    /// Merge new readings (deduped by timestamp), trim to 24h, persist.
    func ingest(_ new: [GlucoseReading]) {
        var byDate = Dictionary(uniqueKeysWithValues: readings.map { ($0.date, $0) })
        for r in new { byDate[r.date] = r }
        let cutoff = Date().addingTimeInterval(-24 * 3600)
        readings = byDate.values
            .filter { $0.date >= cutoff }
            .sorted { $0.date < $1.date }
        persist()
    }

    func readings(inLast hours: Int) -> [GlucoseReading] {
        let cutoff = Date().addingTimeInterval(-Double(hours) * 3600)
        return readings.filter { $0.date >= cutoff }
    }

    private func persist() {
        do {
            let data = try JSONEncoder().encode(readings)
            try data.write(to: Self.fileURL, options: .atomic)
        } catch {
            print("GlucoseStore persist failed: \(error)")
        }
    }

    static func loadFromDisk() -> [GlucoseReading] {
        guard let data = try? Data(contentsOf: fileURL) else { return [] }
        return (try? JSONDecoder().decode([GlucoseReading].self, from: data)) ?? []
    }
}
