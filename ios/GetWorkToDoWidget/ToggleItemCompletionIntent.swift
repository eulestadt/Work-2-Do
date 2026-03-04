import AppIntents
import WidgetKit

struct ToggleItemCompletionIntent: AppIntent {
    static var title: LocalizedStringResource = "Toggle item completion"
    static var description = IntentDescription("Marks a task as complete or incomplete.")

    @Parameter(title: "Item ID")
    var itemId: String

    static var parameterSummary: some ParameterSummary {
        Summary("Toggle completion for \(\.$itemId)")
    }

    func perform() async throws -> some IntentResult {
        let suite = UserDefaults(suiteName: "group.com.getworktodo.app")
        let key = "completed_ids"
        var ids = Set(suite?.stringArray(forKey: key) ?? [])

        if ids.contains(itemId) {
            ids.remove(itemId)
        } else {
            ids.insert(itemId)
        }
        suite?.set(Array(ids), forKey: key)
        WidgetCenter.shared.reloadAllTimelines()
        return .result()
    }
}
