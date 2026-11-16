# ClipBridge 0.7.1

Across your devices. Share text, photos and files between phones and Windows.

| Device | Get it |
| --- | --- |
| Windows x64 | [Install 0.7.1 EXE](https://github.com/A7lI/ClipBridge/releases/download/v0.7.1-preview/ClipBridge-Setup-0.7.1.exe) · [Full portable ZIP](https://github.com/A7lI/ClipBridge/releases/download/v0.7.1-preview/ClipBridge-Windows-0.7.1-preview.zip) |
| Android 11+ | [Download 0.7.1 APK](https://github.com/A7lI/ClipBridge/releases/download/v0.7.1-preview/ClipBridge-Android-0.7.1.apk) |
| iPhone | [Open the web app](https://www.a7li.dev/apps/clipbridge/web/) · Safari → Add to Home Screen |

[Website](https://www.a7li.dev/apps/clipbridge/) · [Release notes and checksums](https://github.com/A7lI/ClipBridge/releases/tag/v0.7.1-preview)

## Faster transfers, fewer buttons

- iPhone–PC transfers use buffered binary blocks with Windows 0.7.1. Older Windows builds remain compatible using the original transfer method.
- Android: **Take & send photo** captures a photo; **Connect → Scan pairing code** connects your PC. The duplicate scanner on Share is removed.

## A simpler design

- One dark and lavender design, with new icons across the apps.
- Android and Windows: **Share**, **Connect**, **Settings**.
- iPhone web: **Computer** or **Phone to phone**, with compact Send and Receive panels.
- Less text on the main screens. Setup, keyboard, voice and help are one tap away.

## Start sharing

**Phone ↔ PC:** open both apps on the same Wi-Fi. In Android, open **Connect** and scan the PC QR. In the iPhone web app, choose **Computer** and scan the QR from Windows **iPhone web pairing**. Use **Get from PC** to fetch copied Windows content, including content copied while the web app was closed.

**Phone ↔ Phone:** open **Phone-to-phone sharing** in Android or [the phone web screen](https://www.a7li.dev/apps/clipbridge/web/phone). Choose Online across networks, or Nearby on the same Wi-Fi/hotspot. Nearby needs one online opening to save the web app first. Create an invitation, scan it on the other phone, and scan the return QR for Nearby mode. Check the connection code and accept incoming transfers. Keep both screens open.

**Copy and save:** Windows receives files ready for Ctrl+V. Android offers Save, Copy and Share. On iPhone use Copy photo or Download/Share; save documents to Files to copy them. Save received web files before closing.

## Limits

- Files/photos: **20 items / 300 MB total** per batch.
- Mobile web text: **4 KB**. Android–PC text: **1 MB**.
- Image clipboard conversion: **24 MP / 12 MB normalized PNG**. Larger photos can transfer as files. Pasting depends on the destination app.
- Optional Android voice typing: English, **60 seconds**. Download the **218 MB** Canary model once in Windows Settings.

PC and Nearby transfers are encrypted local connections. Online phone sharing uses an encrypted Cloudflare relay without server file storage and is subject to its free quotas. Keep pairing links private. There is no background phone delivery queue.

Android 0.7.1 uses the same signing certificate as 0.6.2 and 0.6.5: install over those versions to keep settings. Run the Windows installer for an app in Start, or extract the portable ZIP. Quit the old tray instance before opening the new build.

## Source and testing

Source, build scripts, notices and checksums are included in the release. Third-party licenses are in `licenses/`, `android/assets/suggestions/`, and `web/public/vendor/`. Windows includes FFmpeg under LGPL v3 or later; its [corresponding source](https://github.com/A7lI/ClipBridge/releases/download/v0.7.1-preview/ffmpeg-9.0.2.tar.xz) is attached.

Transfer, encryption, startup, keyboard, QR and build checks pass. The Windows interface was visually reviewed; web layouts were checked at phone and desktop widths. Physical Android/iPhone testing remains pending. The archived SwiftUI prototype was restyled in source only; the supported iPhone distribution is the web app.

[Windows installer details](INSTALLER.md) · [Detailed web setup](web/README.md) · [Technical reference](docs/REFERENCE.md) · [Report an issue](https://github.com/A7lI/ClipBridge/issues)
