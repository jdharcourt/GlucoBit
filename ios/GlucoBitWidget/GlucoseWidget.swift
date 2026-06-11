import WidgetKit
import SwiftUI

struct GlucoseWidget: Widget {
    var body: some WidgetConfiguration {
        StaticConfiguration(kind: "GlucoseWidget", provider: GlucoseTimelineProvider()) { entry in
            GlucoseWidgetEntryView(entry: entry)
        }
        .configurationDisplayName("Glucose")
        .description("Current glucose reading and trend from GlucoBit.")
        .supportedFamilies([.systemSmall, .accessoryCircular, .accessoryRectangular])
    }
}

struct GlucoseWidgetEntryView: View {
    @Environment(\.widgetFamily) private var family
    let entry: GlucoseEntry

    var body: some View {
        switch family {
        case .accessoryCircular:
            CircularGlucoseView(entry: entry)
                .containerBackground(.clear, for: .widget)
        case .accessoryRectangular:
            RectangularGlucoseView(entry: entry)
                .containerBackground(.clear, for: .widget)
        default:
            SmallGlucoseView(entry: entry)
                .containerBackground(
                    DeviceTheme.backgroundColor(hexString: entry.backgroundColorHex),
                    for: .widget
                )
        }
    }
}
