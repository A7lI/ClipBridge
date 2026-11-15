# ClipBridge Preview (Android 0.6.5)

Share text, photos, files, new screenshots and scanned QR text between your Windows PC and Android phone on the same local network. The Android companion includes a keyboard for background clipboard access. File, camera, QR and screenshot transfer also work with your usual keyboard. PC sharing is local and needs no account. Phone-to-phone sharing adds offline nearby and encrypted online modes.

**Early public preview for Windows x64 and Android 11+.** Some phone-specific behaviors still need real-device validation.

The [iPhone web preview](web/README.md) pairs by QR and transfers text, photos, and files with the updated Windows companion. Open [ClipBridge in Safari](https://www.a7li.dev/apps/clipbridge/web/) and add it to the Home Screen. Photos and files support up to 300 MB per batch.

[Website and setup](https://www.a7li.dev/apps/clipbridge/) · [Downloads](https://github.com/A7lI/ClipBridge/releases/tag/v0.6.5-preview)

## Phone to phone

Android **0.6.5** adds **Phone-to-phone sharing**. On iPhone open [the phone sharing screen](https://www.a7li.dev/apps/clipbridge/web/phone). Share text, photos and files between Android and iPhone or two phones of the same type, without a PC. Up to 20 files / 300 MB total per batch; text up to 4 KB. Both sharing screens stay open and incoming transfers need acceptance.

Choose **Online** for different Wi-Fi/mobile networks: create an invitation and scan or share its private link. Choose **Offline nearby** on the same Wi-Fi/hotspot: one phone creates an invitation, the second scans it and shows a return QR, and the first scans that return QR. Open the web screen online once first and wait until it is ready for offline sharing. Offline transfers are direct; online transfers pass through an encrypted relay without server file storage. Check the code on both phones.

On Android save received files to Downloads/ClipBridge or copy photos/files for pasting. On iPhone use Copy photo, Download, or Share; save documents to Files to copy them. Keep received files before closing. Windows remains **0.6.4**. See [web setup and limits](web/README.md).

## Set up

1. On your PC, open **ClipBridge-PC.exe**. Keep this window running.
2. If Windows asks about firewall access, allow the finished **ClipBridge-PC** app on your trusted private home network. It uses TCP port **48721** and UDP port **48722** for discovery of an already-paired PC. The earlier Python development preview can be cancelled; it is not needed to run this executable. Do not enable router port forwarding.
3. Copy **ClipBridge-Android.apk** to your Android phone using a USB cable or your usual file-transfer method, then install it. Android will ask you to allow installation from the app you used to open the APK.
4. Open ClipBridge on the phone and tap **Scan QR code**. Allow camera access and scan the PC window's QR code: pairing is saved automatically. Alternatively, paste the pairing link and press **Save pairing**.
5. For automatic sharing of clipboard items copied in other phone apps, press **Enable keyboard**, enable **ClipBridge Keyboard**, then press **Select keyboard** and choose it. Android shows its standard keyboard trust warning. File sharing, camera, QR and screenshot transfer do not require changing keyboards.
6. Press **Allow microphone for voice typing** if you want dictation. This is optional for clipboard sync.
7. Press **Start syncing** on the phone. The PC now starts syncing automatically; its button reads **Pause syncing** while enabled. Wait for the connected status, then copy something new on either device and paste it on the other. Existing clipboard contents are not uploaded when you first enable sync.

The Wi-Fi address in the PC window must belong to the network your phone uses. VPN/virtual adapter addresses can be wrong; use the address selector if necessary. A guest network's device isolation can prevent a connection.

## Everyday use

- **File Explorer:** select local files, right-click, choose **Show more options → Send to → Share to My Phone (ClipBridge)**. Keep ClipBridge running and connected on both devices. Android **0.4.0 or later** saves received files automatically in **Downloads/ClipBridge**. The PC confirms success after the phone acknowledges saving them. Up to **20 files / 300 MB total** can be sent at once. Closing the sender popup does not cancel an already-started transfer.
- **Install Explorer sharing.cmd** installs or repairs the **Send to** shortcut for your Windows account; **Remove Explorer sharing.cmd** removes it. Keep **ClipBridge-PC.exe** in its current location or rerun installation after moving it. The main Windows **Send to My Phone** entry still belongs to Microsoft Phone Link. Use the explicitly named **ClipBridge** entry. No code-signing certificate, MSIX package, administrator access or Phone Link removal is needed.

- Copy text or **Copy image** in an app; the other device's clipboard updates automatically while connected. Normal transfer latency should be short on a healthy LAN, but image size and device scheduling affect it; it is not a guaranteed instant transfer.
- In an Android file manager or other app, select a file and tap **Share → ClipBridge**. The app also accepts multiple selected files, shared text and shared images. A single shared image is copied as image data for pasting into PC image-capable apps; other selections transfer as files. ClipBridge opens with transfer progress and confirms when the PC has accepted the item. Pair first and keep PC syncing enabled. Manual sharing does not need the phone's background sync service.
- Use **Send files** in either app to choose files. The PC's **Send files** button also saves to the phone's **Downloads/ClipBridge** folder and waits for acknowledgement. Copying files in Windows Explorer continues to sync via the clipboard while connected. Up to **20 files / 300 MB total** can be sent at once, including PDFs, documents and ZIPs. Folders must be zipped first. Received phone files are saved in `%LOCALAPPDATA%\ClipBridge\Received` and placed on the PC clipboard: **Ctrl+V** in Explorer pastes the files. **Received files** opens that folder. Android's **Received files** screen shows downloaded files and older cached clipboard files. Downloaded files persist in shared storage; save important cached files because Android may clear its cache.
- Tap **Take photo → PC**, take a photo and confirm it in the camera. The full capture is read, orientation is corrected and image data is sent to the PC clipboard, ready for **Ctrl+V** in an image-capable app. Very large captures are reduced to fit the 24 megapixel limit. The photo stays in private cache; this feature does not add a gallery photo.
- Tap **Scan QR code** to scan text, a URL or a code. Its text is copied to the PC clipboard as soon as decoding and transfer succeed; links are not opened automatically and text is not typed into another app. A ClipBridge pairing QR is recognized and saves pairing instead. Scanning runs offline on the phone.
- Enable **Automatically copy new screenshots to PC**, grant **all photos** access, and keep **Start syncing** enabled on the phone and PC. Newly saved images identified by a screenshot filename or folder are copied to the PC as image data and to the phone clipboard. Existing gallery screenshots are ignored. Detection uses MediaStore notifications with a two-second fallback; captures must be saved by Android before they can transfer. Partial/selected-photo access cannot include future screenshots. Paused, disconnected or stale captures are skipped, with no offline screenshot queue. HyperOS background restrictions and localized/custom screenshot folder names can affect detection; **Share → ClipBridge** is the manual alternative.
- The **Paste** key pastes the clipboard into the current field, including images where the destination supports them. You can also use Android's normal Paste menu or Ctrl+V on Windows.
- The globe/language key switches English and Arabic. Hold it to select a different keyboard. Hold Shift for caps lock. Hold Backspace to repeat deletion. Numeric fields get a number layout.
- Version **0.3.1** raises the keyboard with **20 dp** of extra bottom spacing and reserves the system navigation/cutout area so the spacebar row stays above Android's navigation controls. The bottom bar and divider use the keyboard's dark background. Android still owns its navigation/gesture controls.
- Android **0.6.2** adds frequency-ranked offline Arabic/English completions from over 96,000 entries, spelling alternatives, phrase-based next-word hints and optional local personalization. Vibration controls, all Arabic letters and long-press forms are included. See [Android 0.6.2 notes](ANDROID-0.6.2.md). Suggestions are inserted by tapping; swipe typing and a full emoji picker are not available. Password-manager autofill suggestions retain priority.
- **Pause syncing** on the PC stops clipboard transfers in both directions. **Stop syncing** on the phone stops its background connection. The PC's clipboard pause control does not disable the separately triggered voice-typing feature.
- **Reset pairing** in the PC app disconnects devices and creates a new secret. Pair the phone again afterward.
- To start ClipBridge at Windows sign-in, add a shortcut to its executable in your Windows Startup folder. Keep the executable in that location. The selected voice model and pairing key are restored automatically. **Start syncing automatically when ClipBridge opens** is enabled by default. Pause is temporary for the current session; uncheck that option if you want later launches to remain paused.
- Keep the phone companion enabled. Android retries the connection automatically when the PC returns. Version **0.2.0** also finds the already-paired PC if its address changes, using authenticated local discovery, and requests background-service startup after phone reboot or app update. This requires both devices on the same local network and permission for ClipBridge to run in the background. Install updates signed with the same key over the existing app to retain pairing. The public 0.5.1-keyboard build uses a different key; see the Android 0.6.1 installation notes. A guest network that blocks device broadcasts or peer traffic can prevent discovery.

## Voice typing — one click to install Canary

Open the Windows app and click **Download Canary model** under **Voice Typing**. The app downloads the **218 MB** Canary 180M Flash Q8 model directly from the model publisher's Hugging Face repository, shows progress, verifies its pinned SHA-256, and activates it automatically. You never need to move a file or choose a folder. Internet is required for this one-time download; cancellation and retry are available.

The speech engine, its Python runtime and voice-activity detector are already inside **ClipBridge-PC.exe**. **Cipher, Handy, Python and a separate engine installation are not required.** The phone APK contains no Canary weights. After setup, speech recordings and transcripts travel only over the encrypted local PC connection; there is no transcription account, cloud backend or API key.

Tap **Mic** on ClipBridge Keyboard, speak, then tap **Stop**. The Windows app transcribes the recording and returns text to the field you were editing. Recordings are limited to **60 seconds**; the first request can be slower while the model loads. Both devices must be connected, and the PC app must stay running. This release transcribes **English**; the keyboard itself can also type Arabic.

The model is stored automatically in `%LOCALAPPDATA%\ClipBridge\Models`, separate from the executable so it survives app updates and works without administrator access. It is app-managed storage; users do not browse this folder during setup. **Use an existing model…** remains an optional shortcut for users who already have a compatible Canary GGUF. Existing saved selections are preserved.

The download is pinned to publisher revision `8b01fc77ac169a0a05c5c0332bbfe54acf65c26f`, file `canary-180m-flash-Q8_0.gguf`, **218,447,648 bytes**, SHA-256 `f942ab746040b531a29ab78ca3afc8dc9564efd8e4c942b5541e53644be9c408`. Source: https://huggingface.co/handy-computer/canary-180m-flash-gguf . Attribution and CC BY 4.0 terms are in `licenses/canary/`. The app only installs a complete, verified model; failed downloads leave any previous model intact.

Voice typing is disabled in password fields. Changing fields during recording cancels it; if you change fields during transcription, the result remains in memory and you can deliberately insert it using **Paste**. Without the PC connection, normal keyboard typing still works.

## Saved passwords

Keep your current Android autofill/password manager selected. Passwords remain there; they are not imported into ClipBridge. The keyboard requests and displays Android's protected inline suggestions. Exact appearance and matching depend on your password manager and the app/website you are using. This integration still needs validation on a physical phone. Autofilling a password is not a clipboard copy and does not trigger sync.

## POCO / HyperOS

If Android stops the connection in the background or after reboot, allow ClipBridge's background activity/autostart and choose unrestricted battery use in its app settings. Menu names depend on your exact HyperOS release. If HyperOS blocks the boot receiver, opening ClipBridge restores an enabled connection. The keyboard route does not use USB debugging, Shizuku, root, accessibility services, or your existing keyboard's private data.

## Privacy and limits

- Pairing uses a random 256-bit key. Clipboard items, voice audio, and responses are encrypted and authenticated with AES-256-GCM, including request replay protection. This is an initial implementation, not an independently audited product.
- The pairing link grants access; keep it private. The PC stores its key protected by Windows DPAPI, and Android stores it in the app's private settings with backup disabled.
- Normal typed keystrokes are not sent to the PC. Optional keyboard personalization stores bounded word/pair counts only on the phone and can be cleared in settings. New clipboard changes, explicitly shared/selected files, captured photos, scanned QR text, enabled screenshot transfers and recordings deliberately started through the microphone button can be transferred.
- Clipboard text and recordings are not written to history or diagnostic logs by ClipBridge. Received images use Android's private cache because other apps need a content URI to paste them. Older received images are pruned after a day when another image arrives; Android can clear cache sooner. Windows and your phone/password manager may have their own clipboard histories outside ClipBridge.
- Received files on Windows remain in the **Received files** folder until you delete them. Explicit PC file deliveries on Android are written to shared **Downloads/ClipBridge**, where your file manager and apps with appropriate access can find them. Files received through clipboard sync and camera captures use private cache; save/export cached files you want to retain. Files are never opened or executed automatically. Filenames are validated; Windows caches use separate folders and Android Downloads handles duplicate names. Only the particular content URI being shared is granted to another Android app.
- Android clipboard items explicitly marked sensitive are skipped. Windows sensitivity flags and unmarked sensitive content are not automatically identified: copied text may include passwords or verification codes. Pause syncing when you do not want copied content shared.
- Supported: plain text up to **1 MB**, a single image up to **12 MB** in normalized PNG form and **24 megapixels**, and **1–20 files totaling up to 300 MB**. Multiple selected images can transfer as files. Rich text formatting and clipboard history do not sync.
- Copying a photo file in Windows Explorer transfers it as a file. Use Copy image in a browser/photo editor, a screenshot, or **Take photo → PC** for image-data pasting. Image pasting depends on the receiving app; a text-only field cannot accept an image.
- There is no offline transfer queue or conflict history. Use while the devices show connected; concurrent copies are handled in arrival order at the PC, with guards against obvious echo loops. The latest clipboard item can replace the previous one. Explicit PC file sends use a separate queue of at most four active deliveries and expire after 40 seconds; they survive unrelated clipboard changes. A missing response can mean the phone saved files but its acknowledgement was lost, so check **Downloads/ClipBridge** before retrying a timed-out send.

## Validation

The signed APK compiles against the installed Android SDK. Backend checks cover authenticated encryption, replay/path binding, invalid image/text rejection, pause behavior, direction routing, local HTTP transfers, and Windows-protected pairing storage. The standalone engine transcribed a generated 16 kHz test recording correctly. See `VALIDATION.md` for the final recorded results.

**This preview has not completed physical-phone validation.** Background syncing, Android microphone access, real password-manager suggestions, and image pasting in your chosen apps still require a phone test. This is a functional first build, not a claim of complete device validation.

## Source and rebuilding

`desktop/` contains the Python Windows app; `android/` contains the native Java keyboard and companion. Python clipboard syncing needs the packages in `desktop/requirements.txt`; the bundled Windows executable already includes them.

Build Android with `python build_android.py --work <absolute-build-directory>` using an installed Android SDK and Java. Keep that build directory's signing key and password safe for future APK updates. A different signing key requires uninstalling the old APK, which removes its pairing settings.

Build Windows using `build_windows.py --voice-python <voice-build-python.exe> --work <absolute-build-directory> --output <absolute-output-directory>`. The main build interpreter needs `desktop/requirements.txt` and PyInstaller 6.22.3. The voice build interpreter must be Python 3.12 x64 with `desktop/requirements-voice.txt` and PyInstaller 6.22.3. This builds a standalone voice worker and embeds it in the single Windows executable. Model weights, pairing settings and Android signing keys are never bundled. `--preview` starts an isolated loopback listener on a temporary port for UI checks.

The native Explorer DLL is experimental and is not registered or used by the Send to integration. Build it with `python build_shell.py --compiler <absolute-path-to-tcc.exe>`. The tested portable TinyCC 0.9.27 x64 compiler archive comes from `https://download.savannah.gnu.org/releases/tinycc/tcc-0.9.27-win64-bin.zip` (SHA-256 `34a721949a2583fdff725312da092fa0f5f1f284b702e6f811c6954714faabb2`). Build while the DLL is not loaded by Explorer, or use `--output` to stage a new DLL. `tests/check_shell.py --compiler <path>` exercises the COM implementation against real Windows shell item arrays without registering it or transferring files. `desktop/explorer_menu.py install` and `restore` provide the source-level equivalent of the installer/restore shortcuts.


ClipBridge 0.6.0 supports 300 MB total per file batch (up to 20 files), in either direction. Install the updated Android APK as well as the PC app. Files use encrypted 192 KB chunks; the photo clipboard limit remains 12 MB. Transfers may take up to 15 minutes on slow Wi-Fi.

The PC app has a ClipBridge icon in the Windows system tray (including the hidden icons menu). Close the window to keep syncing in the background. Double-click the tray icon, or right-click and select **Open ClipBridge**, to reopen it. The menu also offers **Pause / resume sync** and **Quit ClipBridge**. Windows Startup launches it with `--tray` so it stays in the tray.
