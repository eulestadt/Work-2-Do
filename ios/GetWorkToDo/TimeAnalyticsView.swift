import SwiftUI

struct TimeAnalyticsView: View {
    @StateObject private var store = LocalStore()

    private var sessionsByDate: [String: [TimerSession]] {
        Dictionary(grouping: store.timerSessions) { s in
            s.date ?? dateString(from: s.endedAt)
        }
    }

    private var sessionsByCourse: [String: [TimerSession]] {
        Dictionary(grouping: store.timerSessions) { s in
            s.course ?? "Other"
        }
    }

    private var todayStr: String {
        dateString(from: Date())
    }

    private var yesterdayStr: String {
        guard let yesterday = Calendar.current.date(byAdding: .day, value: -1, to: Date()) else { return "" }
        return dateString(from: yesterday)
    }

    private var weekDates: [String] {
        (0..<7).compactMap { offset in
            Calendar.current.date(byAdding: .day, value: -offset, to: Date())
        }.map { dateString(from: $0) }
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                Text("This week")
                    .font(.title2)
                    .fontWeight(.semibold)

                GlassCard {
                    VStack(alignment: .leading, spacing: 8) {
                        Text("Total")
                            .font(.headline)
                        Text(formatDuration(totalThisWeek))
                            .font(.title2)
                    }
                }

                Text("By day")
                    .font(.title2)
                    .fontWeight(.semibold)

                ForEach(weekDates, id: \.self) { dateStr in
                    if let sessions = sessionsByDate[dateStr], !sessions.isEmpty {
                        GlassCard {
                            VStack(alignment: .leading, spacing: 8) {
                                Text(dayLabel(for: dateStr))
                                    .font(.headline)
                                Text(formatDuration(sessions.reduce(0) { $0 + $1.duration }))
                                    .font(.subheadline)
                                Text(breakdownByCourse(sessions))
                                    .font(.caption)
                                    .foregroundStyle(.secondary)
                            }
                        }
                    }
                }

                Text("By class")
                    .font(.title2)
                    .fontWeight(.semibold)

                ForEach(Array(sessionsByCourse.keys).sorted(), id: \.self) { course in
                    if let sessions = sessionsByCourse[course], !sessions.isEmpty {
                        GlassCard {
                            VStack(alignment: .leading, spacing: 8) {
                                Text(course)
                                    .font(.headline)
                                Text(formatDuration(sessions.reduce(0) { $0 + $1.duration }))
                                    .font(.subheadline)
                                Text(breakdownByDay(sessions))
                                    .font(.caption)
                                    .foregroundStyle(.secondary)
                            }
                        }
                    }
                }

                if store.timerSessions.isEmpty {
                    GlassCard {
                        Text("No timer data yet. Start a timer on a task to track your study time.")
                            .font(.subheadline)
                            .foregroundStyle(.secondary)
                    }
                }
            }
            .padding()
        }
        .navigationTitle("Time")
    }

    private var totalThisWeek: TimeInterval {
        let weekStart = Calendar.current.date(byAdding: .day, value: -7, to: Date()) ?? Date()
        return store.timerSessions
            .filter { $0.endedAt >= weekStart }
            .reduce(0) { $0 + $1.duration }
    }

    private func dateString(from date: Date) -> String {
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd"
        formatter.locale = Locale(identifier: "en_US_POSIX")
        return formatter.string(from: date)
    }

    private func dayLabel(for dateStr: String) -> String {
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd"
        formatter.locale = Locale(identifier: "en_US_POSIX")
        guard let date = formatter.date(from: dateStr) else { return dateStr }
        let display = DateFormatter()
        display.dateFormat = "EEEE, MMM d"
        return display.string(from: date)
    }

    private func breakdownByCourse(_ sessions: [TimerSession]) -> String {
        let byCourse = Dictionary(grouping: sessions) { $0.course ?? "Other" }
        return byCourse
            .map { "\($0.key) \(formatDuration($0.value.reduce(0) { $0 + $1.duration }))" }
            .sorted()
            .joined(separator: ", ")
    }

    private func breakdownByDay(_ sessions: [TimerSession]) -> String {
        let byDate = Dictionary(grouping: sessions) { $0.date ?? dateString(from: $0.endedAt) }
        return byDate
            .map { "\(shortDay($0.key)) \(formatDuration($0.value.reduce(0) { $0 + $1.duration }))" }
            .sorted()
            .joined(separator: ", ")
    }

    private func shortDay(_ dateStr: String) -> String {
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd"
        formatter.locale = Locale(identifier: "en_US_POSIX")
        guard let date = formatter.date(from: dateStr) else { return dateStr }
        let display = DateFormatter()
        display.dateFormat = "EEE"
        return display.string(from: date)
    }

    private func formatDuration(_ duration: TimeInterval) -> String {
        let m = Int(duration) / 60
        let h = m / 60
        return h > 0 ? "\(h)h \(m % 60)m" : "\(m)m"
    }
}

#Preview {
    NavigationStack {
        TimeAnalyticsView()
    }
}
