import SwiftUI

struct ContentView: View {
    @State private var selectedTab = 0

    var body: some View {
        TabView(selection: $selectedTab) {
            NavigationStack {
                GameplanView()
            }
            .tabItem { Label("Gameplan", systemImage: "list.bullet.clipboard") }
            .tag(0)

            NavigationStack {
                TaskListView()
            }
            .tabItem { Label("Tasks", systemImage: "checklist") }
            .tag(1)

            NavigationStack {
                TimeAnalyticsView()
            }
            .tabItem { Label("Time", systemImage: "clock") }
            .tag(2)
            
            NavigationStack {
                AskGeminiView()
            }
            .tabItem { Label("Ask Gemini", systemImage: "bubble.left.and.bubble.right") }
            .tag(3)

            NavigationStack {
                SettingsView()
            }
            .tabItem { Label("Settings", systemImage: "gear") }
            .tag(4)
        }
        .onOpenURL { url in
            guard url.scheme == "getworktodo" else { return }
            if url.host == "ask-gemini" {
                selectedTab = 3
            } else if url.host == "toggle" {
                let path = url.path.hasPrefix("/") ? String(url.path.dropFirst()) : url.path
                let itemId = path.removingPercentEncoding ?? path
                if !itemId.isEmpty {
                    LocalStore.shared.toggleCompleted(id: itemId)
                    selectedTab = 1
                }
            }
        }
    }
}

#Preview {
    ContentView()
}
