import SwiftUI

struct GlassCard<Content: View>: View {
    @ViewBuilder let content: () -> Content
    var padding: CGFloat = 16

    var body: some View {
        content()
            .padding(padding)
            .frame(maxWidth: .infinity, alignment: .leading)
            .modifier(GlassCardModifier())
    }
}

private struct GlassCardModifier: ViewModifier {
    func body(content: Content) -> some View {
        if #available(iOS 26, *) {
            content
                .glassEffect(in: .rect(cornerRadius: 16))
        } else {
            content
                .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 16))
        }
    }
}

#Preview {
    GlassCard {
        Text("Hello, Liquid Glass!")
            .font(.title)
    }
    .padding()
}
