import SwiftUI

struct ManualItemForm: View {
    @State private var title = ""
    @State private var date = ""
    @State private var type = "other"
    @State private var course = ""
    @Environment(\.dismiss) private var dismiss

    var existing: ManualItem?
    let onSave: (ManualItem) -> Void

    private let types = ["reading", "homework", "assignment", "exam", "quiz", "other"]

    init(existing: ManualItem? = nil, onSave: @escaping (ManualItem) -> Void) {
        self.existing = existing
        self.onSave = onSave
    }

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    TextField("Title", text: $title)
                } header: {
                    Text("Required")
                }

                Section {
                    TextField("Date (YYYY-MM-DD)", text: $date)
                        .textInputAutocapitalization(.never)
                    Picker("Type", selection: $type) {
                        ForEach(types, id: \.self) { Text($0).tag($0) }
                    }
                    TextField("Course (optional)", text: $course)
                } header: {
                    Text("Optional")
                }
            }
            .navigationTitle(existing != nil ? "Edit Item" : "Add Item")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button(existing != nil ? "Save" : "Add") {
                        let item = ManualItem(
                            id: existing?.id ?? UUID().uuidString,
                            title: title.trimmingCharacters(in: .whitespacesAndNewlines),
                            date: date.isEmpty ? nil : date,
                            type: type,
                            course: course.trimmingCharacters(in: .whitespacesAndNewlines)
                        )
                        onSave(item)
                    }
                    .disabled(title.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                }
            }
            .onAppear {
                if let e = existing {
                    title = e.title
                    date = e.date ?? ""
                    type = e.type
                    course = e.course
                }
            }
        }
    }
}

#Preview {
    ManualItemForm(onSave: { _ in })
}
