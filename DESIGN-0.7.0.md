# ClipBridge 0.7.0 — a simpler design

A shared dark and lavender style inspired by a7li.dev, with new app, tray and Explorer icons.

- Android and Windows now have Share, Connect and Settings tabs. Keyboard preferences, screenshot sharing and voice setup stay in Settings.
- The iPhone web app has a compact Computer / Phone to phone switcher, paired Send and Receive cards, and Files / Photos buttons.
- Main-screen copy is shorter; connection, installation and privacy help is available on demand.
- Received-file cards and Android keyboard styling match the new design.
- The website has a shorter product page, clear device downloads and optional setup details.

Sharing behavior is retained: QR pairing, both-way text/photos/files, Get from PC after closing the web app, offline nearby and online phone sharing, and 20 files / 300 MB total per batch. No protocol or size-limit change.

Android: install over 0.6.2/0.6.5 to keep settings; the signing key is unchanged. Windows: quit the old tray instance, extract the ZIP and run ClipBridge-PC.exe. The Explorer sharing scripts and icon are included. iPhone: reopen https://www.a7li.dev/apps/clipbridge/web/ to load the new design. Open online once before Nearby offline use.

Validation: 41 Windows/protocol tests; 85 keyboard checks; 12 QR cases; PC and phone browser transfers both ways; offline cache and QR pairing; file/photo copying adapters; packaged Windows startup; signed Android build; mobile/desktop responsive and website checks. Transfer size remains 300 MB, previously verified end to end. Physical Android WebView and iPhone Safari checks remain pending. The archived SwiftUI view and icons were updated as source only and could not be built on this Windows environment.

This preview includes source, checksums and third-party notices. Windows uses FFmpeg under LGPL v3 or later; corresponding source is attached.
