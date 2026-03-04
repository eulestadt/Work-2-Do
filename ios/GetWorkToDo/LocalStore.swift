import Foundation

final class LocalStore: ObservableObject {
    static let shared = LocalStore()

    private let suite = UserDefaults(suiteName: "group.com.getworktodo.app")
    private let completedKey = "completed_ids"
    private let timerSessionsKey = "timer_sessions"
    private let manualItemsKey = "manual_items"
    private let activeTimerKey = "active_timer"
    private let hiddenIdsKey = "hidden_ids"

    @Published var completedIds: Set<String> = []
    @Published var hiddenIds: Set<String> = []
    @Published var timerSessions: [TimerSession] = []
    @Published var manualItems: [ManualItem] = []
    @Published var activeTimer: (itemId: String, startedAt: Date)?

    init() {
        load()
    }

    private func load() {
        if let arr = suite?.stringArray(forKey: completedKey) {
            completedIds = Set(arr)
        }
        if let data = suite?.data(forKey: timerSessionsKey),
           let decoded = try? JSONDecoder().decode([TimerSession].self, from: data) {
            timerSessions = decoded
        }
        if let data = suite?.data(forKey: manualItemsKey),
           let decoded = try? JSONDecoder().decode([ManualItem].self, from: data) {
            manualItems = decoded
        }
        if let dict = suite?.dictionary(forKey: activeTimerKey),
           let itemId = dict["itemId"] as? String,
           let ts = dict["startedAt"] as? Double {
            activeTimer = (itemId, Date(timeIntervalSince1970: ts))
        }
        if let arr = suite?.stringArray(forKey: hiddenIdsKey) {
            hiddenIds = Set(arr)
        }
    }

    func save() {
        suite?.set(Array(completedIds), forKey: completedKey)
        if let data = try? JSONEncoder().encode(timerSessions) {
            suite?.set(data, forKey: timerSessionsKey)
        }
        if let data = try? JSONEncoder().encode(manualItems) {
            suite?.set(data, forKey: manualItemsKey)
        }
        if let at = activeTimer {
            suite?.set(["itemId": at.itemId, "startedAt": at.startedAt.timeIntervalSince1970], forKey: activeTimerKey)
        } else {
            suite?.removeObject(forKey: activeTimerKey)
        }
        suite?.set(Array(hiddenIds), forKey: hiddenIdsKey)
    }

    func toggleCompleted(id: String) {
        if completedIds.contains(id) {
            completedIds.remove(id)
        } else {
            completedIds.insert(id)
        }
        save()
    }

    func isCompleted(id: String) -> Bool {
        completedIds.contains(id)
    }

    func totalTime(for itemId: String) -> TimeInterval {
        let sessions = timerSessions.filter { $0.itemId == itemId }
        let total = sessions.reduce(0.0) { $0 + $1.duration }
        if let at = activeTimer, at.itemId == itemId {
            return total + Date().timeIntervalSince(at.startedAt)
        }
        return total
    }

    func startTimer(itemId: String) {
        activeTimer = (itemId, Date())
        save()
    }

    func stopTimer(course: String = "", date: String = "") {
        guard let at = activeTimer else { return }
        let session = TimerSession(itemId: at.itemId, startedAt: at.startedAt, endedAt: Date(), course: course.isEmpty ? nil : course, date: date.isEmpty ? nil : date)
        timerSessions.append(session)
        activeTimer = nil
        save()
    }

    func addManualItem(_ item: ManualItem) {
        manualItems.append(item)
        save()
    }

    func removeManualItem(id: String) {
        manualItems.removeAll { $0.id == id }
        save()
    }

    func updateManualItem(_ item: ManualItem) {
        if let idx = manualItems.firstIndex(where: { $0.id == item.id }) {
            manualItems[idx] = item
            save()
        }
    }

    func hideItem(id: String) {
        hiddenIds.insert(id)
        save()
    }

    func unhideItem(id: String) {
        hiddenIds.remove(id)
        save()
    }

    func isHidden(id: String) -> Bool {
        hiddenIds.contains(id)
    }
}
