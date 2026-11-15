import AVFoundation
import SwiftUI
import VisionKit

@MainActor
struct ContentView: View {
    @StateObject private var bridge = BridgeModel()
    @State private var showingScanner = false
    @State private var showingLink = false
    @State private var link = ""
    @State private var draft = ""

    private let ink = Color(red: 8/255, green: 9/255, blue: 17/255)
    private let panel = Color(red: 20/255, green: 20/255, blue: 32/255)
    private let accent = Color(red: 199/255, green: 181/255, blue: 255/255)

    private func card<Content: View>(_ title: String, @ViewBuilder content: () -> Content) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            if !title.isEmpty { Text(title).font(.headline) }
            content()
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(16)
        .background(panel, in: RoundedRectangle(cornerRadius: 18))
        .overlay(RoundedRectangle(cornerRadius: 18).stroke(accent.opacity(0.16)))
    }

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 12) {
                    HStack(spacing: 10) {
                        Image(systemName: "square.on.square").font(.title2).foregroundStyle(accent)
                        VStack(alignment: .leading, spacing: 2) {
                            Text("ClipBridge.").font(.title2.bold()).tracking(-0.6)
                            Text("Across your devices.").font(.caption).foregroundStyle(.secondary)
                        }
                        Spacer()
                    }.padding(.vertical, 8)
                    if let pairing = bridge.pairing {
                        card("") {
                            HStack {
                                Label(pairing.host, systemImage: "desktopcomputer").font(.subheadline)
                                Spacer()
                                Menu {
                                    Button("Scan new QR", action: openScanner)
                                    Button("Use pairing link") { showingLink = true }
                                    Button("Forget PC", role: .destructive) { bridge.forgetPC(); draft = "" }
                                } label: { Image(systemName: "ellipsis.circle") }
                            }
                        }.disabled(bridge.busy)
                        card("Send") {
                            TextField("Type or paste something…", text: $draft, axis: .vertical)
                                .lineLimit(2...5).padding(12).background(ink, in: RoundedRectangle(cornerRadius: 10))
                            HStack {
                                PasteButton(payloadType: String.self) { values in
                                    guard let text = values.first else { return }
                                    Task { await bridge.send(text) }
                                }.accessibilityLabel("Paste and send to PC")
                                Spacer()
                                Button("Send to PC", systemImage: "arrow.up.right") {
                                    let text = draft
                                    Task { await bridge.send(text) }
                                }.buttonStyle(.borderedProminent).disabled(draft.isEmpty)
                            }
                        }.disabled(bridge.busy)
                        card("Receive") {
                            Button("Get from PC", systemImage: "arrow.down.left") { Task { await bridge.getFromPC() } }
                                .buttonStyle(.borderedProminent)
                            if let text = bridge.receivedText {
                                Text(verbatim: text).font(.subheadline).textSelection(.enabled).lineLimit(8)
                                Button("Copy text", systemImage: "document.on.document", action: bridge.copyReceivedText)
                                    .buttonStyle(.bordered)
                            }
                        }.disabled(bridge.busy)
                    } else {
                        card("Connect your PC") {
                            Text("Same Wi-Fi. Scan the code in Windows.").font(.subheadline).foregroundStyle(.secondary)
                            Button("Scan QR", systemImage: "qrcode.viewfinder", action: openScanner).buttonStyle(.borderedProminent)
                            Button("Use pairing link") { showingLink = true }
                        }.disabled(bridge.busy)
                    }
                    if let error = bridge.error {
                        Label(error, systemImage: "exclamationmark.circle").font(.footnote).foregroundStyle(.red).padding(10)
                    } else if let status = bridge.status {
                        HStack { if bridge.busy { ProgressView() }; Text(status).font(.footnote).foregroundStyle(.secondary) }.padding(.horizontal, 4)
                    }
                    DisclosureGroup("Help") {
                        Text("Keep Windows running on the same Wi-Fi. Get from PC reads its current clipboard. Keep pairing links private.")
                            .font(.footnote).foregroundStyle(.secondary).padding(.top, 8)
                        Link("Photos, files & phone sharing in the web app", destination: URL(string: "https://www.a7li.dev/apps/clipbridge/web/")!)
                            .font(.footnote).padding(.top, 6)
                    }.font(.subheadline).padding(16).background(panel, in: RoundedRectangle(cornerRadius: 16))
                }.padding(16)
            }
            .background(ink)
            .tint(accent)
            .preferredColorScheme(.dark)
            .toolbar(.hidden, for: .navigationBar)
            .sheet(isPresented: $showingScanner) {
                NavigationStack {
                    QRScanner(onPairing: { pairing in
                        showingScanner = false
                        Task { await bridge.pair(pairing) }
                    }, onUnavailable: {
                        showingScanner = false
                        bridge.report("Camera unavailable. Allow camera access in Settings or enter the PC pairing link.")
                    })
                    .navigationTitle("Scan QR")
                    .navigationBarTitleDisplayMode(.inline)
                    .toolbar {
                        ToolbarItem(placement: .cancellationAction) {
                            Button("Cancel") { showingScanner = false }
                        }
                    }
                }
            }
            .alert("Enter pairing link", isPresented: $showingLink) {
                TextField("clipbridge://…", text: $link)
                    .keyboardType(.URL)
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled()
                Button("Pair") { pairFromLink() }
                Button("Cancel", role: .cancel) { link = "" }
            } message: {
                Text("Use the pairing link displayed in ClipBridge on Windows.")
            }
        }
    }

    private func openScanner() {
        guard DataScannerViewController.isSupported else {
            bridge.report("QR scanning is unavailable on this device. Enter the PC pairing link.")
            return
        }
        Task {
            let allowed = await AVCaptureDevice.requestAccess(for: .video)
            guard allowed, DataScannerViewController.isAvailable else {
                bridge.report("Camera unavailable. Allow camera access in Settings or enter the PC pairing link.")
                return
            }
            showingScanner = true
        }
    }

    private func pairFromLink() {
        defer { link = "" }
        do {
            let pairing = try Pairing(link: link)
            Task { await bridge.pair(pairing) }
        } catch {
            bridge.report(error.localizedDescription)
        }
    }
}
