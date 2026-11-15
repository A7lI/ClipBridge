import SwiftUI
import Vision
import VisionKit

@MainActor
struct QRScanner: UIViewControllerRepresentable {
    let onPairing: (Pairing) -> Void
    let onUnavailable: () -> Void

    func makeCoordinator() -> Coordinator {
        Coordinator(onPairing: onPairing, onUnavailable: onUnavailable)
    }

    func makeUIViewController(context: Context) -> DataScannerViewController {
        let scanner = DataScannerViewController(
            recognizedDataTypes: [.barcode(symbologies: [.qr])],
            qualityLevel: .balanced,
            recognizesMultipleItems: true,
            isHighFrameRateTrackingEnabled: false,
            isHighlightingEnabled: true
        )
        scanner.delegate = context.coordinator
        do {
            try scanner.startScanning()
        } catch {
            let coordinator = context.coordinator
            Task { coordinator.unavailable() }
        }
        return scanner
    }

    func updateUIViewController(_ scanner: DataScannerViewController, context: Context) {}

    static func dismantleUIViewController(_ scanner: DataScannerViewController, coordinator: Coordinator) {
        scanner.stopScanning()
    }

    @MainActor
    final class Coordinator: NSObject, DataScannerViewControllerDelegate {
        private let onPairing: (Pairing) -> Void
        private let onUnavailable: () -> Void
        private var finished = false

        init(onPairing: @escaping (Pairing) -> Void, onUnavailable: @escaping () -> Void) {
            self.onPairing = onPairing
            self.onUnavailable = onUnavailable
        }

        func dataScanner(_ scanner: DataScannerViewController, didAdd addedItems: [RecognizedItem],
                         allItems: [RecognizedItem]) {
            guard !finished else { return }
            for item in addedItems {
                guard case .barcode(let barcode) = item, let link = barcode.payloadStringValue,
                      let pairing = try? Pairing(link: link) else { continue }
                finished = true
                scanner.stopScanning()
                onPairing(pairing)
                return
            }
        }

        func dataScanner(_ scanner: DataScannerViewController,
                         becameUnavailableWithError error: DataScannerViewController.ScanningUnavailable) {
            unavailable()
        }

        func unavailable() {
            guard !finished else { return }
            finished = true
            onUnavailable()
        }
    }
}
