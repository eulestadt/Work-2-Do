import Foundation

enum ScheduleServiceError: Error {
    case invalidURL
    case noData
    case decodingError
}

final class ScheduleService {
    static let shared = ScheduleService()

    private let decoder: JSONDecoder = {
        let d = JSONDecoder()
        return d
    }()

    func baseURL() -> String {
        UserDefaults(suiteName: "group.com.getworktodo.app")?.string(forKey: "baseURL") ?? ""
    }

    func setBaseURL(_ url: String) {
        UserDefaults(suiteName: "group.com.getworktodo.app")?.set(url, forKey: "baseURL")
    }

    func apiKey() -> String? {
        UserDefaults(suiteName: "group.com.getworktodo.app")?.string(forKey: "apiKey")
    }

    func setApiKey(_ key: String?) {
        UserDefaults(suiteName: "group.com.getworktodo.app")?.set(key, forKey: "apiKey")
    }

    private func addAuthHeaders(to request: inout URLRequest) {
        if let key = apiKey(), !key.isEmpty {
            request.setValue("Bearer \(key)", forHTTPHeaderField: "Authorization")
        }
    }

    func fetchLatest() async throws -> LatestResponse {
        let base = baseURL().trimmingCharacters(in: .whitespacesAndNewlines)
        guard !base.isEmpty else { throw ScheduleServiceError.invalidURL }
        let urlString = base.hasSuffix("/") ? base + "api/latest" : base + "/api/latest"
        guard let url = URL(string: urlString) else { throw ScheduleServiceError.invalidURL }

        var request = URLRequest(url: url)
        addAuthHeaders(to: &request)

        let (data, _) = try await URLSession.shared.data(for: request)
        let response = try decoder.decode(LatestResponse.self, from: data)
        return response
    }

    func askGemini(question: String) async throws -> String {
        let base = baseURL().trimmingCharacters(in: .whitespacesAndNewlines)
        guard !base.isEmpty else { throw ScheduleServiceError.invalidURL }
        let urlString = base.hasSuffix("/") ? base + "api/ask_gemini" : base + "/api/ask_gemini"
        guard let url = URL(string: urlString) else { throw ScheduleServiceError.invalidURL }

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONEncoder().encode(["question": question])
        addAuthHeaders(to: &request)

        let (data, _) = try await URLSession.shared.data(for: request)
        let json = try JSONSerialization.jsonObject(with: data) as? [String: Any]
        guard let answer = json?["answer"] as? String else {
            throw ScheduleServiceError.noData
        }
        return answer
    }

    func toggleComplete(assignmentId: String) async throws -> Bool {
        let base = baseURL().trimmingCharacters(in: .whitespacesAndNewlines)
        guard !base.isEmpty else { throw ScheduleServiceError.invalidURL }
        let urlString = base.hasSuffix("/")
            ? base + "api/assignments/\(assignmentId)/complete"
            : base + "/api/assignments/\(assignmentId)/complete"
        guard let url = URL(string: urlString) else { throw ScheduleServiceError.invalidURL }

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        addAuthHeaders(to: &request)

        let (data, _) = try await URLSession.shared.data(for: request)
        let json = try JSONSerialization.jsonObject(with: data) as? [String: Any]
        guard let completed = json?["completed"] as? Bool else {
            throw ScheduleServiceError.noData
        }
        return completed
    }
}
