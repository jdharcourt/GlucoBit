import Foundation
import HealthKit

/// Writes glucose readings to Apple Health as bloodGlucose samples.
/// Dedupes via HKMetadataKeySyncIdentifier (the reading timestamp), so
/// re-exporting overlapping history is safe.
final class HealthKitExporter {
    private let healthStore = HKHealthStore()
    private let glucoseType = HKQuantityType(.bloodGlucose)
    private var authorized = false

    func requestAuthorization() async -> Bool {
        guard HKHealthStore.isHealthDataAvailable() else { return false }
        do {
            try await healthStore.requestAuthorization(toShare: [glucoseType], read: [])
            authorized = healthStore.authorizationStatus(for: glucoseType) == .sharingAuthorized
        } catch {
            authorized = false
        }
        return authorized
    }

    func export(_ readings: [GlucoseReading]) async {
        guard HKHealthStore.isHealthDataAvailable() else { return }
        if !authorized {
            guard await requestAuthorization() else { return }
        }

        let unit = HKUnit.gramUnit(with: .milli).unitDivided(by: .literUnit(with: .deci))
        let samples = readings.map { reading in
            HKQuantitySample(
                type: glucoseType,
                quantity: HKQuantity(unit: unit, doubleValue: Double(reading.valueMgdl)),
                start: reading.date,
                end: reading.date,
                metadata: [
                    HKMetadataKeySyncIdentifier: "glucobit-\(Int(reading.date.timeIntervalSince1970))",
                    HKMetadataKeySyncVersion: 1,
                ]
            )
        }
        guard !samples.isEmpty else { return }
        do {
            try await healthStore.save(samples)
        } catch {
            print("HealthKit export failed: \(error)")
        }
    }
}
