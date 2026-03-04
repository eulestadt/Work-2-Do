import SwiftUI

struct TaskListView: View {
    @StateObject private var store = LocalStore()
    @State private var latest: LatestResponse?
    @State private var isLoading = false
    @State private var errorMessage: String?
    @State private var showAddManual = false
    @State private var itemToEdit: ManualItem?

    private var allItems: [TaskRowItem] {
        var items: [TaskRowItem] = []
        for it in latest?.items ?? [] {
            if !store.isHidden(id: it.id) {
                items.append(.schedule(it))
            }
        }
        for it in store.manualItems {
            items.append(.manual(it))
        }
        return items.sorted { a, b in
            let d1 = a.date
            let d2 = b.date
            if d1 != d2 { return d1 < d2 }
            return a.title < b.title
        }
    }

    private var itemsByDate: [(date: String, items: [TaskRowItem])] {
        Dictionary(grouping: allItems) { $0.date.isEmpty ? "No date" : $0.date }
            .map { (date: $0.key, items: $0.value.sorted { $0.title < $1.title }) }
            .sorted { $0.date < $1.date }
    }

    var body: some View {
        List {
            if isLoading {
                HStack {
                    Spacer()
                    ProgressView()
                    Spacer()
                }
            } else if let err = errorMessage {
                Text(err)
                    .foregroundStyle(.red)
            }

            ForEach(itemsByDate, id: \.date) { group in
                Section {
                    ForEach(group.items) { item in
                        TaskRowView(
                            item: item,
                            isCompleted: isCompleted(for: item),
                            totalTime: store.totalTime(for: item.id),
                            isTiming: store.activeTimer?.itemId == item.id,
                            showDate: false,
                            onToggleComplete: { Task { await toggleComplete(for: item) } },
                            onStartTimer: { store.startTimer(itemId: item.id) },
                            onStopTimer: { store.stopTimer(course: item.course, date: item.date) },
                            onEdit: item.isManual ? { editManualItem(item) } : nil,
                            onRemove: { removeItem(item) }
                        )
                    }
                } header: {
                    Text(formatDateHeader(group.date))
                        .font(.subheadline)
                        .fontWeight(.semibold)
                }
                .listRowInsets(EdgeInsets(top: 2, leading: 12, bottom: 2, trailing: 12))
            }
        }
        .listStyle(.plain)
        .navigationTitle("Tasks")
        .toolbar {
            ToolbarItem(placement: .primaryAction) {
                Button {
                    showAddManual = true
                } label: {
                    Image(systemName: "plus.circle")
                }
            }
        }
        .task { await load() }
        .refreshable { await load() }
        .sheet(isPresented: $showAddManual) {
            ManualItemForm { item in
                store.addManualItem(item)
                showAddManual = false
            }
        }
        .sheet(item: $itemToEdit) { item in
            ManualItemForm(existing: item) { updated in
                store.updateManualItem(updated)
                itemToEdit = nil
            }
        }
    }

    private func formatDateHeader(_ dateStr: String) -> String {
        guard dateStr != "No date" else { return "No date" }
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd"
        formatter.locale = Locale(identifier: "en_US_POSIX")
        guard let date = formatter.date(from: dateStr) else { return dateStr }
        let display = DateFormatter()
        display.dateFormat = "EEEE, MMM d"
        return display.string(from: date)
    }

    private func editManualItem(_ item: TaskRowItem) {
        if case .manual(let m) = item {
            itemToEdit = m
        }
    }

    private func removeItem(_ item: TaskRowItem) {
        if item.isManual {
            store.removeManualItem(id: item.id)
        } else {
            store.hideItem(id: item.id)
        }
    }

    private func load() async {
        isLoading = true
        errorMessage = nil
        defer { isLoading = false }
        do {
            latest = try await ScheduleService.shared.fetchLatest()
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    private func isCompleted(for item: TaskRowItem) -> Bool {
        if item.isManual {
            return store.isCompleted(id: item.id)
        }
        if let scheduleItem = latest?.items?.first(where: { $0.id == item.id }),
           let completed = scheduleItem.completed {
            return completed
        }
        return store.isCompleted(id: item.id)
    }

    private func toggleComplete(for item: TaskRowItem) async {
        if item.isManual {
            store.toggleCompleted(id: item.id)
            return
        }
        let base = ScheduleService.shared.baseURL()
        let key = ScheduleService.shared.apiKey()
        if !base.isEmpty, let k = key, !k.isEmpty {
            do {
                _ = try await ScheduleService.shared.toggleComplete(assignmentId: item.id)
                await load()
            } catch {
                store.toggleCompleted(id: item.id)
            }
        } else {
            store.toggleCompleted(id: item.id)
        }
    }
}

enum TaskRowItem: Identifiable {
    case schedule(ScheduleItem)
    case manual(ManualItem)

    var id: String {
        switch self {
        case .schedule(let s): return s.id
        case .manual(let m): return m.id
        }
    }

    var title: String {
        switch self {
        case .schedule(let s): return s.title
        case .manual(let m): return m.title
        }
    }

    var date: String {
        switch self {
        case .schedule(let s): return s.date
        case .manual(let m): return m.date ?? ""
        }
    }

    var course: String {
        switch self {
        case .schedule(let s): return s.course
        case .manual(let m): return m.course
        }
    }

    var isManual: Bool {
        if case .manual = self { return true }
        return false
    }
}

struct TaskRowView: View {
    let item: TaskRowItem
    let isCompleted: Bool
    let totalTime: TimeInterval
    let isTiming: Bool
    var showDate: Bool = true
    let onToggleComplete: () -> Void
    let onStartTimer: () -> Void
    let onStopTimer: () -> Void
    var onEdit: (() -> Void)?
    var onRemove: () -> Void

    var body: some View {
        HStack(alignment: .center, spacing: 8) {
            Button {
                onToggleComplete()
            } label: {
                Image(systemName: isCompleted ? "checkmark.circle.fill" : "circle")
                    .font(.body)
                    .foregroundStyle(isCompleted ? .green : .secondary)
            }
            .buttonStyle(.plain)

            VStack(alignment: .leading, spacing: 1) {
                Text(item.title)
                    .font(.subheadline)
                    .strikethrough(isCompleted)
                    .lineLimit(1)
                if !item.course.isEmpty || (showDate && !item.date.isEmpty) {
                    HStack(spacing: 4) {
                        if !item.course.isEmpty {
                            Text(item.course)
                                .font(.caption2)
                                .foregroundStyle(.secondary)
                        }
                        if showDate && !item.date.isEmpty {
                            Text("·")
                                .font(.caption2)
                                .foregroundStyle(.secondary)
                            Text(item.date)
                                .font(.caption2)
                                .foregroundStyle(.secondary)
                        }
                    }
                }
                if totalTime > 0 {
                    Text(formatDuration(totalTime))
                        .font(.caption2)
                        .foregroundStyle(.tertiary)
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)

            if isTiming {
                Button("Stop") { onStopTimer() }
                    .font(.caption)
                    .buttonStyle(.borderedProminent)
            } else {
                Button("Start") { onStartTimer() }
                    .font(.caption)
                    .buttonStyle(.bordered)
            }
        }
        .padding(.vertical, 4)
        .swipeActions(edge: .trailing, allowsFullSwipe: false) {
            if let onEdit = onEdit {
                Button {
                    onEdit()
                } label: {
                    Label("Edit", systemImage: "pencil")
                }
            }
            Button(role: .destructive) { onRemove() } label: {
                Label(item.isManual ? "Delete" : "Hide", systemImage: "trash")
            }
        }
    }

    private func formatDuration(_ duration: TimeInterval) -> String {
        let m = Int(duration) / 60
        let h = m / 60
        return h > 0 ? "\(h)h \(m % 60)m" : "\(m)m"
    }
}

#Preview {
    NavigationStack {
        TaskListView()
    }
}
