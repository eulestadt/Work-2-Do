import WidgetKit
import SwiftUI
import AppIntents

struct WidgetItem: Identifiable {
    let id: String
    let title: String
    let date: String
    let isCompleted: Bool
}

private struct WidgetManualItem: Codable {
    let id: String
    let title: String
    let date: String?
}

struct Provider: TimelineProvider {
    func placeholder(in context: Context) -> SimpleEntry {
        SimpleEntry(date: Date(), summary: "Loading...", itemCount: 0, todayItems: [], tomorrowItems: [], apiDate: "")
    }

    func getSnapshot(in context: Context, completion: @escaping (SimpleEntry) -> Void) {
        Task {
            let entry = await loadEntry()
            completion(entry)
        }
    }

    func getTimeline(in context: Context, completion: @escaping (Timeline<SimpleEntry>) -> Void) {
        Task {
            let entry = await loadEntry()
            let timeline = Timeline(entries: [entry], policy: .atEnd)
            completion(timeline)
        }
    }

    private func loadEntry() async -> SimpleEntry {
        let suite = UserDefaults(suiteName: "group.com.getworktodo.app")
        let baseURL = suite?.string(forKey: "baseURL") ?? ""
        guard !baseURL.isEmpty,
              let url = URL(string: baseURL.hasSuffix("/") ? baseURL + "api/latest" : baseURL + "/api/latest") else {
            return SimpleEntry(date: Date(), summary: "Set backend URL in Settings", itemCount: 0, todayItems: [], tomorrowItems: [], apiDate: "")
        }

        var request = URLRequest(url: url)
        if let apiKey = suite?.string(forKey: "apiKey"), !apiKey.isEmpty {
            request.setValue("Bearer \(apiKey)", forHTTPHeaderField: "Authorization")
        }

        let completedIds = Set(suite?.stringArray(forKey: "completed_ids") ?? [])

        do {
            let (data, _) = try await URLSession.shared.data(for: request)
            let json = try JSONSerialization.jsonObject(with: data) as? [String: Any]
            let apiDateStr = json?["date"] as? String ?? ""
            let itemsRaw = json?["items"] as? [[String: Any]] ?? []
            let digestMd = json?["digest_md"] as? String ?? ""

            let todayStr = apiDateStr
            let tomorrowStr = Self.tomorrowDate(from: apiDateStr)

            var todayItems: [WidgetItem] = []
            var tomorrowItems: [WidgetItem] = []

            for it in itemsRaw {
                guard let id = it["id"] as? String,
                      let title = it["title"] as? String,
                      let date = it["date"] as? String else { continue }
                let completed = (it["completed"] as? Bool) ?? completedIds.contains(id)
                let item = WidgetItem(id: id, title: title, date: date, isCompleted: completed)
                if date == todayStr {
                    todayItems.append(item)
                } else if date == tomorrowStr {
                    tomorrowItems.append(item)
                }
            }

            if let manualData = suite?.data(forKey: "manual_items"),
               let manualArr = try? JSONDecoder().decode([WidgetManualItem].self, from: manualData) {
                for m in manualArr {
                    let date = m.date ?? todayStr
                    let completed = completedIds.contains(m.id)
                    let item = WidgetItem(id: m.id, title: m.title, date: date, isCompleted: completed)
                    if date == todayStr {
                        todayItems.append(item)
                    } else if date == tomorrowStr {
                        tomorrowItems.append(item)
                    }
                }
            }

            todayItems.sort { $0.title < $1.title }
            tomorrowItems.sort { $0.title < $1.title }

            var summary: String
            if !todayItems.isEmpty {
                summary = todayItems.prefix(2).map(\.title).joined(separator: ", ")
            } else if !tomorrowItems.isEmpty {
                summary = tomorrowItems.prefix(2).map(\.title).joined(separator: ", ")
            } else if !itemsRaw.isEmpty {
                summary = itemsRaw.prefix(2).compactMap { $0["title"] as? String }.joined(separator: ", ")
            } else if !digestMd.isEmpty, let first = digestMd.split(separator: "\n").first {
                summary = String(first).replacingOccurrences(of: "#", with: "").trimmingCharacters(in: .whitespaces)
            } else {
                summary = "No schedule"
            }

            return SimpleEntry(
                date: Date(),
                summary: String(summary.prefix(80)),
                itemCount: todayItems.count + tomorrowItems.count,
                todayItems: todayItems,
                tomorrowItems: tomorrowItems,
                apiDate: apiDateStr
            )
        } catch {
            return SimpleEntry(date: Date(), summary: "Error loading", itemCount: 0, todayItems: [], tomorrowItems: [], apiDate: "")
        }
    }

    private static func tomorrowDate(from dateStr: String) -> String {
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd"
        formatter.locale = Locale(identifier: "en_US_POSIX")
        guard let date = formatter.date(from: dateStr),
              let tomorrow = Calendar.current.date(byAdding: .day, value: 1, to: date) else {
            return dateStr
        }
        return formatter.string(from: tomorrow)
    }
}

struct SimpleEntry: TimelineEntry {
    let date: Date
    let summary: String
    let itemCount: Int
    let todayItems: [WidgetItem]
    let tomorrowItems: [WidgetItem]
    let apiDate: String
}

struct GetWorkToDoWidgetEntryView: View {
    var entry: Provider.Entry
    @Environment(\.widgetFamily) var family

    var body: some View {
        switch family {
        case .accessoryCircular:
            CircularWidgetView(entry: entry)
        case .accessoryRectangular:
            RectangularWidgetView(entry: entry)
        case .accessoryInline:
            InlineWidgetView(entry: entry)
        case .systemSmall:
            SmallWidgetView(entry: entry)
        case .systemMedium:
            MediumWidgetView(entry: entry)
        default:
            StandardWidgetView(entry: entry)
        }
    }
}

struct CircularWidgetView: View {
    let entry: Provider.Entry

    var body: some View {
        ZStack {
            AccessoryWidgetBackground()
            Link(destination: URL(string: "getworktodo://ask-gemini")!) {
                VStack(spacing: 2) {
                    Text("\(entry.itemCount)")
                        .font(.headline)
                    Text("to do")
                        .font(.caption2)
                }
            }
            .widgetAccentable()
        }
    }
}

struct RectangularWidgetView: View {
    let entry: Provider.Entry

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Link(destination: URL(string: "getworktodo://ask-gemini")!) {
                Text("Ask Gemini")
                    .font(.caption2)
                    .foregroundStyle(.blue)
            }
            .widgetAccentable()

            ForEach(entry.todayItems.prefix(3) + entry.tomorrowItems.prefix(2)) { item in
                if #available(iOS 17.0, *) {
                    Link(destination: URL(string: "getworktodo://toggle/\(item.id.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed) ?? item.id)")!) {
                        HStack(spacing: 4) {
                            Image(systemName: item.isCompleted ? "checkmark.circle.fill" : "circle")
                                .font(.caption2)
                            Text(item.title)
                                .font(.caption2)
                                .lineLimit(1)
                                .strikethrough(item.isCompleted)
                        }
                    }
                } else {
                    HStack(spacing: 4) {
                        Image(systemName: item.isCompleted ? "checkmark.circle.fill" : "circle")
                            .font(.caption2)
                        Text(item.title)
                            .font(.caption2)
                            .lineLimit(1)
                            .strikethrough(item.isCompleted)
                    }
                }
            }
        }
        .containerBackground(for: .widget) {
            AccessoryWidgetBackground()
        }
    }
}

struct InlineWidgetView: View {
    let entry: Provider.Entry

    var body: some View {
        let done = entry.todayItems.filter(\.isCompleted).count + entry.tomorrowItems.filter(\.isCompleted).count
        let total = entry.itemCount
        Link(destination: URL(string: "getworktodo://ask-gemini")!) {
            Text(total > 0 ? "\(done) of \(total) done · Tap to open" : "Tap to ask Gemini")
        }
    }
}

struct SmallWidgetView: View {
    let entry: Provider.Entry

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Today")
                .font(.headline)
                .widgetAccentable()

            ForEach(entry.todayItems.prefix(5)) { item in
                if #available(iOS 17.0, *) {
                    Link(destination: URL(string: "getworktodo://toggle/\(item.id.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed) ?? item.id)")!) {
                        HStack(spacing: 6) {
                            Image(systemName: item.isCompleted ? "checkmark.circle.fill" : "circle")
                                .font(.caption)
                            Text(item.title)
                                .font(.caption)
                                .lineLimit(1)
                                .strikethrough(item.isCompleted)
                        }
                    }
                } else {
                    HStack(spacing: 6) {
                        Image(systemName: item.isCompleted ? "checkmark.circle.fill" : "circle")
                            .font(.caption)
                        Text(item.title)
                            .font(.caption)
                            .lineLimit(1)
                            .strikethrough(item.isCompleted)
                    }
                }
            }

            Link(destination: URL(string: "getworktodo://ask-gemini")!) {
                Text("Ask Gemini")
                    .font(.caption)
                    .foregroundStyle(.blue)
            }
            .widgetAccentable()
        }
        .padding()
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
        .containerBackground(for: .widget) {
            Color(.systemBackground)
        }
    }
}

struct MediumWidgetView: View {
    let entry: Provider.Entry

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Link(destination: URL(string: "getworktodo://ask-gemini")!) {
                Text("Ask Gemini")
                    .font(.caption)
                    .foregroundStyle(.blue)
            }
            .widgetAccentable()

            HStack(alignment: .top, spacing: 16) {
                VStack(alignment: .leading, spacing: 6) {
                    Text("Today")
                        .font(.headline)
                        .widgetAccentable()
                ForEach(entry.todayItems.prefix(6)) { item in
                    if #available(iOS 17.0, *) {
                        Link(destination: URL(string: "getworktodo://toggle/\(item.id.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed) ?? item.id)")!) {
                            HStack(spacing: 6) {
                                Image(systemName: item.isCompleted ? "checkmark.circle.fill" : "circle")
                                    .font(.caption)
                                Text(item.title)
                                    .font(.caption)
                                    .lineLimit(1)
                                    .strikethrough(item.isCompleted)
                            }
                        }
                    } else {
                        HStack(spacing: 6) {
                            Image(systemName: item.isCompleted ? "checkmark.circle.fill" : "circle")
                                .font(.caption)
                            Text(item.title)
                                .font(.caption)
                                .lineLimit(1)
                                .strikethrough(item.isCompleted)
                        }
                    }
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)

            VStack(alignment: .leading, spacing: 6) {
                Text("Tomorrow")
                    .font(.headline)
                    .widgetAccentable()
                ForEach(entry.tomorrowItems.prefix(6)) { item in
                    if #available(iOS 17.0, *) {
                        Link(destination: URL(string: "getworktodo://toggle/\(item.id.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed) ?? item.id)")!) {
                            HStack(spacing: 6) {
                                Image(systemName: item.isCompleted ? "checkmark.circle.fill" : "circle")
                                    .font(.caption)
                                Text(item.title)
                                    .font(.caption)
                                    .lineLimit(1)
                                    .strikethrough(item.isCompleted)
                            }
                        }
                    } else {
                        HStack(spacing: 6) {
                            Image(systemName: item.isCompleted ? "checkmark.circle.fill" : "circle")
                                .font(.caption)
                            Text(item.title)
                                .font(.caption)
                                .lineLimit(1)
                                .strikethrough(item.isCompleted)
                        }
                    }
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            }
        }
        .padding()
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
        .containerBackground(for: .widget) {
            Color(.systemBackground)
        }
    }
}

struct StandardWidgetView: View {
    let entry: Provider.Entry

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Link(destination: URL(string: "getworktodo://ask-gemini")!) {
                Text("Ask Gemini")
                    .font(.headline)
            }
            .widgetAccentable()
            Text(entry.summary)
                .font(.caption)
                .lineLimit(4)
        }
        .padding()
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
        .containerBackground(for: .widget) {
            Color(.systemBackground)
        }
    }
}

@main
struct GetWorkToDoWidget: Widget {
    let kind: String = "GetWorkToDoWidget"

    var body: some WidgetConfiguration {
        StaticConfiguration(kind: kind, provider: Provider()) { entry in
            GetWorkToDoWidgetEntryView(entry: entry)
        }
        .configurationDisplayName("Get Work To Do")
        .description("View your schedule. Tap to ask Gemini about it.")
        .supportedFamilies([
            .systemSmall,
            .systemMedium,
            .accessoryCircular,
            .accessoryRectangular,
            .accessoryInline
        ])
    }
}

#Preview(as: .accessoryRectangular) {
    GetWorkToDoWidget()
} timeline: {
    SimpleEntry(
        date: Date(),
        summary: "Read Chapter 5, Essay Draft",
        itemCount: 2,
        todayItems: [
            WidgetItem(id: "1", title: "Read Chapter 5", date: "2025-03-02", isCompleted: false),
            WidgetItem(id: "2", title: "Essay Draft", date: "2025-03-02", isCompleted: true)
        ],
        tomorrowItems: [],
        apiDate: "2025-03-02"
    )
}
