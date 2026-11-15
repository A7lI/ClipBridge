# ClipBridge Android 0.6.5 — phone-to-phone sharing

Adds a Phone-to-phone sharing screen to Android and the iPhone web app. Windows remains version 0.6.4.

- iPhone ↔ Android, iPhone ↔ iPhone, and Android ↔ Android.
- Online sharing across different Wi-Fi/mobile networks, using an AES-GCM encrypted relay. Transfer files are not persisted by the server.
- Offline nearby on the same Wi-Fi/hotspot after one online opening to cache the web app. Exchange an invitation QR and a return QR; data then travels directly with no internet signaling.
- Text up to 4 KB; up to 20 files/photos totaling 300 MB per batch. Keep both sharing screens open. Each transfer requires acceptance. Decline, cancel, and disconnect are available.
- Android Save to Downloads, Copy file, Copy photo, and native Copy text. Received items are marked remote to avoid clipboard echo to the PC. iPhone offers Download/Share and Copy photo; save documents to Files to copy them there.

Install the APK over Android 0.6.2 to keep settings: the signing certificate is unchanged. Open Phone-to-phone sharing. On iPhone open https://www.a7li.dev/apps/clipbridge/web/phone in Safari. For offline use, wait for Ready for offline nearby sharing before disconnecting from the internet.

Validation: complete 300 MB transfers in both directions through both local WebRTC and the WebSocket relay, verified with SHA-256; offline page reloads; real QR decoding of the offline handshake; text and photos both ways; accept/decline; cancellation; size rejection; encryption/replay checks; relay-origin and role checks; native file-adapter checks; 41 Windows/protocol regression tests; 85 Android keyboard checks and 12 QR checks. Tests used desktop browser contexts representing phones. The APK compiles and its signature verifies. Physical iPhone and Android WebView validation remains pending.

Online service availability is subject to Cloudflare's free quotas. No paid plan, storage bucket, or TURN service is configured. Both phones must stay open; there is no background delivery queue. Some guest Wi-Fi or hotspot implementations can block local peer traffic.
