import Foundation

/// Client for the Dexcom Share API — the same endpoints and applicationId the
/// GlucoBit firmware uses, so device and app see identical data.
actor DexcomShareClient {
    struct Credentials: Equatable {
        var username: String
        var password: String
        /// e.g. "shareous1.dexcom.com" (outside US) or "share2.dexcom.com" (US)
        var server: String
    }

    enum ClientError: LocalizedError {
        case notConfigured
        case loginFailed(status: Int)
        case fetchFailed(status: Int)
        case malformedResponse
        case throttled(retryAfter: TimeInterval)

        var errorDescription: String? {
            switch self {
            case .notConfigured:
                return "Dexcom account not configured."
            case .loginFailed(let status):
                return "Dexcom login failed (HTTP \(status)). Check your username, password and server region."
            case .fetchFailed(let status):
                return "Couldn't fetch glucose data (HTTP \(status))."
            case .malformedResponse:
                return "Unexpected response from Dexcom."
            case .throttled(let after):
                return "Too many requests — retry in \(Int(after))s."
            }
        }
    }

    private static let applicationId = "d89443d2-327c-4a6f-89e5-496bbb0317db"

    private var credentials: Credentials?
    private var sessionToken: String?
    private var lastFetchDate: Date?
    private var consecutiveAuthFailures = 0
    private var backoffUntil: Date?

    /// Minimum spacing between fetches, to stay well clear of Dexcom rate limits.
    private let minFetchInterval: TimeInterval = 30

    func configure(_ credentials: Credentials) {
        if credentials != self.credentials {
            self.credentials = credentials
            sessionToken = nil
            consecutiveAuthFailures = 0
            backoffUntil = nil
        }
    }

    var isConfigured: Bool { credentials != nil }

    /// Validate credentials by performing a login. Used by the setup wizard
    /// before credentials are sent to the device.
    func validateCredentials(_ creds: Credentials) async throws {
        _ = try await login(creds)
    }

    /// Fetch recent readings (most recent last). `maxCount` 288 covers 24h of
    /// 5-minute readings for the history chart.
    func fetchReadings(maxCount: Int = 288, force: Bool = false) async throws -> [GlucoseReading] {
        guard let credentials else { throw ClientError.notConfigured }

        if let backoffUntil, backoffUntil > Date() {
            throw ClientError.throttled(retryAfter: backoffUntil.timeIntervalSinceNow)
        }
        if !force, let last = lastFetchDate, Date().timeIntervalSince(last) < minFetchInterval {
            throw ClientError.throttled(retryAfter: minFetchInterval - Date().timeIntervalSince(last))
        }

        if sessionToken == nil {
            sessionToken = try await loginWithBackoff(credentials)
        }

        do {
            let readings = try await readLatest(maxCount: maxCount)
            lastFetchDate = Date()
            return readings
        } catch ClientError.fetchFailed {
            // Session likely expired — re-login once and retry.
            sessionToken = try await loginWithBackoff(credentials)
            let readings = try await readLatest(maxCount: maxCount)
            lastFetchDate = Date()
            return readings
        }
    }

    // MARK: - Private

    private func loginWithBackoff(_ creds: Credentials) async throws -> String {
        do {
            let token = try await login(creds)
            consecutiveAuthFailures = 0
            backoffUntil = nil
            return token
        } catch {
            // Repeated failed logins can lock a Dexcom Share account; back off
            // exponentially (2, 4, 8 … capped at 30 minutes).
            consecutiveAuthFailures += 1
            let delay = min(pow(2.0, Double(consecutiveAuthFailures)) * 60, 1800)
            backoffUntil = Date().addingTimeInterval(delay)
            throw error
        }
    }

    private func login(_ creds: Credentials) async throws -> String {
        let url = URL(string: "https://\(creds.server)/ShareWebServices/Services/General/LoginPublisherAccountByName")!
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONSerialization.data(withJSONObject: [
            "accountName": creds.username,
            "password": creds.password,
            "applicationId": Self.applicationId,
        ])

        let (data, response) = try await URLSession.shared.data(for: request)
        guard let http = response as? HTTPURLResponse else { throw ClientError.malformedResponse }
        guard http.statusCode == 200 else { throw ClientError.loginFailed(status: http.statusCode) }

        let token = String(decoding: data, as: UTF8.self)
            .trimmingCharacters(in: CharacterSet(charactersIn: "\" \n"))
        guard !token.isEmpty, token != "00000000-0000-0000-0000-000000000000" else {
            throw ClientError.loginFailed(status: http.statusCode)
        }
        return token
    }

    private func readLatest(maxCount: Int) async throws -> [GlucoseReading] {
        guard let credentials, let sessionToken else { throw ClientError.notConfigured }

        var components = URLComponents(string: "https://\(credentials.server)/ShareWebServices/Services/Publisher/ReadPublisherLatestGlucoseValues")!
        components.queryItems = [
            URLQueryItem(name: "sessionID", value: sessionToken),
            URLQueryItem(name: "minutes", value: "1440"),
            URLQueryItem(name: "maxCount", value: String(maxCount)),
        ]
        var request = URLRequest(url: components.url!)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = Data("{}".utf8)

        let (data, response) = try await URLSession.shared.data(for: request)
        guard let http = response as? HTTPURLResponse else { throw ClientError.malformedResponse }
        guard http.statusCode == 200 else {
            if http.statusCode == 500 { self.sessionToken = nil }
            throw ClientError.fetchFailed(status: http.statusCode)
        }

        struct ShareReading: Decodable {
            let Value: Int
            let Trend: TrendValue
            let WT: String

            // Older servers return trend as an int (4 = Flat), newer as a string.
            enum TrendValue: Decodable {
                case string(String)
                case int(Int)
                init(from decoder: Decoder) throws {
                    let c = try decoder.singleValueContainer()
                    if let s = try? c.decode(String.self) { self = .string(s) }
                    else { self = .int(try c.decode(Int.self)) }
                }
                var direction: TrendDirection {
                    switch self {
                    case .string(let s): return TrendDirection(dexcomString: s)
                    case .int(let i): return TrendDirection(code: UInt8(clamping: i))
                    }
                }
            }
        }

        let raw = try JSONDecoder().decode([ShareReading].self, from: data)
        return raw.compactMap { entry in
            guard let date = Self.parseWT(entry.WT) else { return nil }
            return GlucoseReading(valueMgdl: entry.Value, trend: entry.Trend.direction, date: date)
        }
        .sorted { $0.date < $1.date }
    }

    /// Dexcom timestamps look like "/Date(1718106000000)/" (ms since epoch).
    static func parseWT(_ wt: String) -> Date? {
        guard let start = wt.firstIndex(of: "("),
              let end = wt.lastIndex(of: ")") else { return nil }
        let inner = wt[wt.index(after: start)..<end]
        let digits = inner.prefix { $0.isNumber }
        guard let ms = Double(digits) else { return nil }
        return Date(timeIntervalSince1970: ms / 1000)
    }
}
