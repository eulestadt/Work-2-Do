import SwiftUI

struct SettingsView: View {
    @StateObject private var store = LocalStore()
    @State private var baseURL: String = ""
    @State private var apiKey: String = ""

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                GlassCard {
                    VStack(alignment: .leading, spacing: 12) {
                        Text("API")
                            .font(.headline)
                        TextField("Backend URL (e.g. https://your-portal.railway.app)", text: $baseURL)
                            .textFieldStyle(.roundedBorder)
                            .textInputAutocapitalization(.never)
                            .autocorrectionDisabled()
                        SecureField("API key (optional for portal)", text: $apiKey)
                            .textFieldStyle(.roundedBorder)
                            .textInputAutocapitalization(.never)
                            .autocorrectionDisabled()
                        Text("Set the base URL of your deployed backend. For the Homework Portal, generate an API key in Settings → App connection and paste it here.")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                }

                if !store.hiddenIds.isEmpty {
                    GlassCard {
                        VStack(alignment: .leading, spacing: 12) {
                            Text("Hidden items")
                                .font(.headline)
                            Text("\(store.hiddenIds.count) schedule item(s) hidden from Tasks. Restore to show them again.")
                                .font(.caption)
                                .foregroundStyle(.secondary)
                            Button("Restore all hidden") {
                                let ids = store.hiddenIds
                                for id in ids {
                                    store.unhideItem(id: id)
                                }
                            }
                            .buttonStyle(.bordered)
                        }
                    }
                }

                GlassCard {
                    VStack(alignment: .leading, spacing: 12) {
                        Button("Save") {
                            let url = baseURL.trimmingCharacters(in: .whitespacesAndNewlines)
                            ScheduleService.shared.setBaseURL(url)
                            ScheduleService.shared.setApiKey(apiKey.isEmpty ? nil : apiKey)
                        }
                        .buttonStyle(.borderedProminent)
                        .frame(maxWidth: .infinity)
                    }
                }
            }
            .padding()
        }
        .navigationTitle("Settings")
        .onAppear {
            baseURL = ScheduleService.shared.baseURL()
            apiKey = ScheduleService.shared.apiKey() ?? ""
        }
    }
}

#Preview {
    NavigationStack {
        SettingsView()
    }
}
