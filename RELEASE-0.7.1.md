# ClipBridge 0.7.1

Faster iPhone–PC files and clearer Android controls.

- Windows and the iPhone web app negotiate buffered binary transfers. Groups of 16 KB frames fill blocks up to 1 MB before waiting for a reply, avoiding a round trip and text encoding for every tiny piece.
- Transfer commands and block digests are authenticated with the pairing key. File bytes use the encrypted direct WebRTC connection. Both sides verify SHA-256 before accepting a block. Receive queues and send buffers are bounded.
- Older Windows builds use the original file method automatically. Older web clients also work with Windows 0.7.1. Text, pairing, copy/paste, cancellation and the 20-file / 300 MB limit are retained.
- Android: Camera is now **Take & send photo**. The duplicate scanner on Share is removed; use **Connect → Scan pairing code**. Existing pairing, keyboard and screenshot settings remain compatible.
- The website download buttons now point to 0.7.1. The web app retains the startup loading/retry feedback and real sharing links.

## Install

Windows: quit ClipBridge from its tray menu, extract the new ZIP, and open ClipBridge-PC.exe. Update Windows to enable the faster iPhone transfers.

Android: install the APK over the existing app. Version code 12 uses the same signing certificate as 0.7.0, 0.6.5 and 0.6.2.

iPhone: reopen https://www.a7li.dev/apps/clipbridge/web/ online to load the update. Pairing is retained. Safari → Share → Add to Home Screen installs the web app.

## Validation

- 42 Windows/protocol tests, including block integrity, bounds, offsets, pause and compatibility.
- Direct browser–Windows transfers: full 300 MB upload and download verified by SHA-256; text, multiple files, image clipboard, reopen/Get from PC, oversize rejection and cancellation passed.
- Corrupted binary block rejected before publishing; cancellation after the first block preserved the clipboard; a subsequent retry succeeded.
- 20 MB comparison on this Windows test machine: old Windows fallback 9.11 s upload / 9.03 s download; binary mode 3.73 s / 2.77 s. Old web client with new Windows also passed (9.27 s / 9.15 s). These are local automated results, not a guarantee of physical iPhone throughput.
- Chromium and WebKit startup, control activation and failed-load retry checks passed. Nearby phone transfers reopened offline and exchanged text, files and photos both ways.
- Signed APK build and 12 actual QR decoding cases passed. Windows executable version 0.7.1 and packaged startup check passed.
- Website build, labels, links, responsive layout and static-size checks passed. Physical iPhone Safari and Android interface checks still need user testing.

Windows retains the same embedded voice engine and third-party notices. FFmpeg corresponding source is included with this release under LGPL v3 or later.
