# ClipBridge

Copy here. Paste there.

An early preview by A7li for sharing clipboard text, images, files, camera photos and QR text between **Windows x64 and Android 11+** over the same local network.

[Website and setup](https://www.a7li.dev/apps/clipbridge/) · [Download preview 0.5.0](https://github.com/A7lI/ClipBridge/releases/tag/v0.5.0-preview)

## Get started

1. Download and extract the Windows ZIP, then open **ClipBridge-PC.exe**.
2. Install the Android APK and open ClipBridge on your phone.
3. Connect both devices to the same Wi-Fi. Scan the PC pairing QR from the phone app.
4. Enable and select ClipBridge Keyboard for automatic Android clipboard sharing and voice typing, then start syncing. Manual file, camera and QR sharing also work with your usual keyboard.
5. For voice typing, click **Download Canary model** in the PC app. The 218 MB model downloads directly from the publisher on Hugging Face and activates automatically. No file moving, folder selection, Cipher, Handy, Python installation or API key is required.

The Windows app includes its own speech engine. Canary stays on the PC; no speech weights are included in the phone APK. After the initial download, English voice typing runs locally while the paired PC is connected. English and Arabic keyboard layouts are included.

## Current limits

- Windows x64 and Android 11+ only. **No iPhone app is available.**
- Early preview: physical-phone clipboard, microphone, background execution and password-manager behavior still need broader testing.
- Voice typing is English only, up to 60 seconds per recording, and needs the PC running.
- Text up to 1 MB; images and file batches up to 12 MB; at most 20 files per batch.
- There is no offline transfer queue. Image pasting depends on the receiving app.

## Privacy

Transfers use an authenticated, encrypted local connection. No ClipBridge account or cloud transcription service is required. Hugging Face is contacted only for the optional model download; audio is not sent there. Keep your pairing QR private, and pause syncing when you do not want copied items shared. This preview has not had an independent security audit.

## Source and notices

The release includes the complete **ClipBridge-Source-0.5.0-preview.zip**, setup guide, checksums and third-party licenses. Model weights are downloaded separately. Canary is NVIDIA’s Canary 180M Flash, converted to GGUF/Q8_0 by handy-computer, under CC BY 4.0.

[Model publisher](https://huggingface.co/handy-computer/canary-180m-flash-gguf) · [Original NVIDIA model](https://huggingface.co/nvidia/canary-180m-flash)

For a problem report, include your app version, Windows version, phone model and steps to reproduce it. [Open an issue](https://github.com/A7lI/ClipBridge/issues) or email support@a7li.dev.
