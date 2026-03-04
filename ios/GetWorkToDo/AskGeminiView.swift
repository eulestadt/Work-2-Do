import SwiftUI
import MarkdownUI

struct AskGeminiView: View {
    @State private var question = ""
    @State private var answer: String?
    @State private var isLoading = false
    @State private var errorMessage: String?

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                GlassCard {
                    VStack(alignment: .leading, spacing: 12) {
                        TextField("Ask about your schedule...", text: $question, axis: .vertical)
                            .textFieldStyle(.roundedBorder)
                            .lineLimit(3...6)

                        Button {
                            Task { await ask() }
                        } label: {
                            if isLoading {
                                ProgressView()
                                    .frame(maxWidth: .infinity)
                            } else {
                                Text("Ask Gemini")
                                    .frame(maxWidth: .infinity)
                            }
                        }
                        .buttonStyle(.borderedProminent)
                        .disabled(question.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || isLoading)

                        if let err = errorMessage {
                            Text(err)
                                .foregroundStyle(.red)
                        }
                    }
                }

                if let answer = answer {
                    GlassCard {
                        VStack(alignment: .leading, spacing: 8) {
                            Text("Answer")
                                .font(.headline)
                            Markdown(answer)
                                .frame(maxWidth: .infinity, alignment: .leading)
                        }
                    }
                }
            }
            .padding()
        }
        .navigationTitle("Ask Gemini")
    }

    private func ask() async {
        let q = question.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !q.isEmpty else { return }
        isLoading = true
        errorMessage = nil
        answer = nil
        defer { isLoading = false }
        do {
            answer = try await ScheduleService.shared.askGemini(question: q)
        } catch {
            errorMessage = error.localizedDescription
        }
    }
}

#Preview {
    NavigationStack {
        AskGeminiView()
    }
}
