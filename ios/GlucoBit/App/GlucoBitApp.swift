import SwiftUI
import CoreHaptics

@main
struct GlucoBitApp: App {
    @UIApplicationDelegateAdaptor(AppDelegate.self) private var appDelegate
    @Environment(\.scenePhase) private var scenePhase
    

    var body: some Scene {
        WindowGroup {
            RootView(container: appDelegate.container)
                .preferredColorScheme(.dark)
        }
        .onChange(of: scenePhase) { _, phase in
            switch phase {
            case .active:
                appDelegate.container.sync.startForegroundPolling()
            case .background:
                appDelegate.container.sync.stopForegroundPolling()
                BackgroundRefreshScheduler.schedule()
            default:
                break
            }
        }
    }
}

struct RootView: View {
    let container: AppContainer
    @State private var showSetupWizard = false
    @State private var engine: CHHapticEngine?

    var body: some View {
        NavigationStack {
            HomeView(
                settings: container.settings,
                sync: container.sync,
                device: container.device,
                relay: container.relay
            )
            .navigationTitle("GlucoBit")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    NavigationLink {
                        SettingsView(
                            settings: container.settings,
                            device: container.device,
                            sync: container.sync,
                            notifications: container.notifications,
                            healthKit: container.healthKit
                        )
                    } label: {
                        Image(systemName: "gearshape")
                    }
                }
            }
        }
        .tint(AppTheme.accent)
        .background(AppTheme.background)
        .onAppear {
            if !container.settings.deviceConfigured && KeychainStore.dexcomCredentials == nil {
                showSetupWizard = true
            }
            prepareHaptics()
        }
        .sheet(isPresented: $showSetupWizard) {
            SetupWizardView(
                device: container.device,
                settings: container.settings,
                sync: container.sync
            )
        }
    }
    func prepareHaptics() {
        print("Preparing Haptics")
        guard CHHapticEngine.capabilitiesForHardware().supportsHaptics else {
            print("Haptics not supported on this device.")
            return
        }
        
        do {
            engine = try CHHapticEngine()
            engine?.stoppedHandler = { reason in
                print("Haptic engine stopped: \(reason.rawValue)")
                do {
                    try self.engine?.start()
                } catch {
                    print("Failed to restart engine: \(error.localizedDescription)")
                }
            }
            engine?.resetHandler = {
                do {
                    try self.engine?.start()
                } catch {
                    print("Failed to restart engine after reset: \(error.localizedDescription)")
                }
            }
            try engine?.start()
        } catch {
            print("Error creating haptic engine: \(error.localizedDescription)")
        }
    }
}
