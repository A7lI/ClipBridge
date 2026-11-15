# ClipBridge

Copy here. Paste there.

ClipBridge shares clipboard text, photos and files between Windows and Android over your local network. The iPhone web app supports text, photo, and file transfers with Windows.

| Platform | Preview | Download |
| --- | --- | --- |
| Windows x64 | 0.6.4 web preview | [Download Windows ZIP](https://github.com/A7lI/ClipBridge/releases/download/v0.6.4-web-preview/ClipBridge-Windows-0.6.4-web-preview.zip) |
| Android 11+ | 0.6.2 | [Download Android APK](https://github.com/A7lI/ClipBridge/releases/download/v0.6.2-preview/ClipBridge-Android-0.6.2.apk) |
| iPhone | Home Screen web app | [Open ClipBridge in Safari](https://www.a7li.dev/apps/clipbridge/web/) |

[Website and setup](https://www.a7li.dev/apps/clipbridge/) · [Windows release and checksums](https://github.com/A7lI/ClipBridge/releases/tag/v0.6.4-web-preview) · [Android release and checksums](https://github.com/A7lI/ClipBridge/releases/tag/v0.6.2-preview)

## Windows

Extract the ZIP and run **ClipBridge-PC.exe**. If an older instance is running, quit it from the system tray first. Connect your phone and PC to the same Wi-Fi.

## iPhone web preview

1. On Windows, open **iPhone web pairing…** and click **Enable web pairing**.
2. Open the web app in Safari and use **Share → Add to Home Screen**.
3. Launch ClipBridge from your Home Screen and tap **Scan pairing QR**. Scan the QR shown on Windows.
4. Use **Send to PC** or **Get from PC**. The latter reads the Windows clipboard when you tap it. It also works for text copied while the web app was closed.

In **Send**, choose photos or files and tap **Send selected files**. In **Receive**, tap **Get from PC** for the current Windows clipboard, or **Receive files** for files selected with **Send files to iPhone…** on Windows.

Photos and files support up to **300 MB total per batch**, with up to 20 files. Text supports up to 4 KB per transfer. Received files are copied on Windows for Ctrl+V in Explorer. Compatible single photos are also copied as image data. On iPhone, use **Copy photo**, **Download file**, or **Save or share files**. Save documents to Files to copy and paste them in other apps. Keep the web app open during the transfer.

## Android

Install the Android APK, open ClipBridge, and scan the Android pairing QR shown on your PC. Enable and select ClipBridge Keyboard for automatic phone clipboard sharing and voice typing. Manual file, camera and QR sharing work with your usual keyboard.

**Updating from the public Android 0.5.1 preview:** Android requires a reinstall because the signing certificate changed. Save important app-private files, uninstall the older version, install 0.6.2, and pair again.

Android and Windows support text up to 1 MB, a normalized image up to 12 MB, and up to 20 files totaling 300 MB per batch. For optional offline English voice typing, click **Download Canary model** in the Windows app. The model downloads separately and stays on the PC.

## Privacy and source

Clipboard transfers use an authenticated, encrypted connection directly between your paired devices. The iPhone web app uses Cloudflare to set up the connection. Keep the pairing QR private and pause syncing whenever you want to stop sharing.

The [Windows release](https://github.com/A7lI/ClipBridge/releases/tag/v0.6.4-web-preview) includes the app source, SHA-256 checksums, and third-party notices. The Windows build uses FFmpeg under LGPL v3 or later. [FFmpeg source](https://github.com/A7lI/ClipBridge/releases/download/v0.6.4-web-preview/ffmpeg-9.0.2.tar.xz)

For help, include your ClipBridge version, Windows version, phone model, and steps to reproduce the issue. [Open an issue](https://github.com/A7lI/ClipBridge/issues) or email support@a7li.dev.
