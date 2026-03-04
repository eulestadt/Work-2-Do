import SwiftUI
import MarkdownUI

struct GameplanView: View {
    @State private var latest: LatestResponse?
    @State private var isLoading = false
    @State private var errorMessage: String?

    var body: some View {
        ScrollView {
            if isLoading {
                ProgressView("Loading...")
                    .padding()
            } else if let err = errorMessage {
                Text(err)
                    .foregroundStyle(.red)
                    .padding()
            } else if let latest = latest {
                VStack(alignment: .leading, spacing: 16) {
                    if let gp = latest.gameplanMd, !gp.isEmpty {
                        GlassCard {
                            VStack(alignment: .leading, spacing: 8) {
                                Text("Today's Gameplan")
                                    .font(.headline)
                                Markdown(gp)
                            }
                        }
                    }
                    if let gpTomorrow = latest.gameplanTomorrowMd, !gpTomorrow.isEmpty {
                        GlassCard {
                            VStack(alignment: .leading, spacing: 8) {
                                Text("Tomorrow's Gameplan")
                                    .font(.headline)
                                Markdown(gpTomorrow)
                            }
                        }
                    }
                    if (latest.gameplanMd?.isEmpty ?? true) && (latest.gameplanTomorrowMd?.isEmpty ?? true) {
                        GlassCard {
                            Group {
                                if let digest = latest.digestMd, !digest.isEmpty {
                                    Markdown(digest)
                                } else {
                                    Text("No gameplan available. Run the pipeline with --gameplan.")
                                        .foregroundStyle(.secondary)
                                }
                            }
                        }
                    }
                }
                .padding()
            }
        }
        .navigationTitle("Gameplan")
        .task { await load() }
        .refreshable { await load() }
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
}

#Preview {
    NavigationStack {
        GameplanView()
    }
}
