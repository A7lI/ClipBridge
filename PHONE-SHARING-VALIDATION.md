# Phone sharing validation — 2026-11-15

Android APK: 0.6.5 (versionCode 10), unchanged signing certificate from 0.6.2. Windows remains 0.6.4. Hosted web cache build: clipbridge-mobile-0.6.5-v2.

- Published at https://www.a7li.dev/apps/clipbridge/web/phone. Production assets matched the tested source; website download buttons point to Android 0.6.5 and Windows 0.6.4. GitHub APK/source/checksum uploads were verified against local SHA-256 digests.
- Complete 300 MB transfers passed SHA-256 verification in both directions through the production Cloudflare WebSocket relay. Each receiver explicitly accepted the transfer, downloaded the received file, and compared its SHA-256 to the sender's bytes.
- Complete 300 MB nearby WebRTC transfers passed in both directions. Two isolated browser contexts reopened the app offline, decoded the invitation and return QR images, then transferred without HTTP access or internet signaling. DevTools offline disables LAN sockets as well, so LAN sockets were restored while HTTP and service-worker network fetches were blocked for the transfer portion.
- The production cached app also reopened in a fresh tab with the browser offline and navigated from the main screen into phone sharing.
- Text including Arabic and symbols, multiple files and PNG photos passed both ways. Opening an invitation link in an already-open sharing page worked and removed the secret fragment from browser history.
- Consent/decline, oversized batches, cancellation after data started, continued use after cancellation, disconnect reporting, and retaining completed received files after disconnect passed.
- Local relay checks rejected wrong origins, duplicate roles, guests without hosts, and invalid frames. Encrypted frames did not contain the private plaintext; replaying a captured frame was rejected without a duplicate delivery.
- Android's browser-to-native file adapter delivered exact bytes in bounded chunks. The native companion compiled and its APK signature verified; package metadata reports version 0.6.5. Existing Android checks passed: 85 keyboard checks and 12 QR decoding cases.
- Existing PC transfers still passed, including Get from PC after closing/reopening, text/photos/files, pause, cancellation, and size checks. All 41 Windows/protocol regression tests passed. The Windows executable was not changed.
- Website checks passed: 10 HTML pages, 253 local references, accessible labels, metadata, navigation, motion preferences, and a static asset budget below 1 MB. The Cloudflare Worker dry-run bundle passed using the existing Durable Object binding; no paid resource or storage bucket was added.

Physical iPhone Safari and Android WebView testing remains pending. These tests used desktop Chromium browser contexts representing phones, not physical devices on separate carrier networks. Verify native camera/file-picker/Downloads integration, clipboard compatibility in destination apps, hotspot isolation, and phone memory behavior on the actual devices. Both sharing screens must stay open, and the web screen must be opened online once before offline use. Online availability remains subject to Cloudflare's free quotas.
