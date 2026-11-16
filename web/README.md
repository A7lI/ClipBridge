# ClipBridge iPhone web preview

Pair with Windows by QR, then send text, photos, and files in either direction on the same Wi-Fi. Photos and files share a 300 MB total limit per batch of up to 20 files. Text supports up to 4 KB per transfer. Tap **Get from PC** to read the current Windows clipboard, including items copied while ClipBridge was closed on the iPhone.

Windows 0.7.1 and the updated web app negotiate binary file transfers: 16 KB frames are buffered into blocks of up to 1 MB, with an authenticated SHA-256 digest per block. File data stays on the encrypted direct WebRTC connection; Cloudflare handles setup only. Older Windows/web versions retain the 16 KB request/reply method. The batch limit remains 300 MB.

## Run locally on Windows

Requires Python with `desktop/requirements.txt` installed and a recent Node.js. From the ClipBridge folder, start the website and signaling Worker without deploying them:

```powershell
npx wrangler dev --config web/wrangler.jsonc --port 8787
```

In another terminal, run the updated Windows companion. Quit the regular ClipBridge instance from the tray first if it is already running.

```powershell
$env:CLIPBRIDGE_WEB_URL = 'http://localhost:8787/'
python desktop/app.py
```

You can also launch `web/windows/ClipBridge-PC.exe` from that terminal with the same environment variable and skip installing Python. Open **iPhone web pairing…** in the Windows app and click **Enable web pairing**. In a PC browser, paste the link shown in that window. Use this loopback setup to check the site and both transfer directions on the PC. For iPhone testing, use an HTTPS deployment as described below.

## Test on an iPhone

The Windows web preview defaults to [the page on a7li.dev](https://www.a7li.dev/apps/clipbridge/web/). The production site serves the app and runs its signaling Worker on Cloudflare. Run `web/windows/ClipBridge-PC.exe`, open **iPhone web pairing…**, and click **Enable web pairing**. If you set `CLIPBRIDGE_WEB_URL` for local testing, clear that variable or start the companion from a fresh terminal to use the live page.

For independent deployments, `web/wrangler.jsonc` can deploy the app and its `PAIRING_ROOMS` Durable Object as a separate Cloudflare Worker. Set `CLIPBRIDGE_WEB_URL` on the PC to that deployment’s HTTPS URL before launching the companion.

1. Connect the Windows PC and iPhone to the same Wi-Fi. Open the HTTPS web app in Safari. Use **Share → Add to Home Screen**, then open the new icon.
2. Tap **Scan pairing QR**, allow the camera, and point it at the QR displayed in **iPhone web pairing…** on Windows. **Choose QR photo** can read a saved photo. You can also use the iPhone Camera to open the pairing page in Safari or paste the pairing link into the web app.
3. In **Send**, choose documents or photos and tap **Send selected files**. Files are saved in the PC’s **Received files** folder and copied for pasting in Explorer. A compatible single photo is also copied as an image. You can paste a photo into the text field, or use **Paste & send** where the browser exposes image clipboard access.
4. In **Receive**, use **Get from PC** for text, files copied in Explorer, or an image copied in a Windows app. Alternatively, choose **Send files to iPhone…** in the PC’s web pairing window, then tap **Receive files** on the phone. Use **Download file** or **Save or share files** to retain received files. Use **Copy photo** to paste an image into another app. Safari supports copying PNG image data. For documents, save to Files and copy them there.
5. Pause sync on Windows and confirm that send and receive report the paused state. Resume sync to try again. Reset web pairing on Windows to revoke the old QR.

The Worker passes encrypted WebRTC setup messages between paired devices. It does not handle clipboard contents. Both devices need access to the signaling service, and the actual transfer uses a direct Wi-Fi connection. Guest network isolation, firewalls, and VPNs can prevent it. Keep the pairing link private. Pairing is saved in browser storage and the Windows key is protected with DPAPI. Use **Forget PC** to remove the phone’s saved pairing.

Keep the web app open during a transfer. Cancelled or disconnected uploads remove their temporary data. Completed files on Windows remain in Received files even if an acknowledgement is lost. Save received phone files before closing the app. Image clipboard conversion on Windows uses the existing 24 megapixel / 12 MB normalized PNG limit. Larger photos can transfer as files within the 300 MB batch limit.

The app uses [jsQR 1.4.0](https://www.npmjs.com/package/jsqr) to decode camera frames and photos on the phone. The bundled script is the upstream `dist/jsQR.js` minified with Terser 5.51.2. The Apache 2.0 license is included in `public/vendor/jsQR-LICENSE.txt`.

## Phone-to-phone sharing

Open **Phone-to-phone sharing** in Android or use [the phone sharing screen](https://www.a7li.dev/apps/clipbridge/web/phone) on iPhone. Supports Android ↔ iPhone and phones of the same type, with no PC. The current Windows and Android download is 0.7.1.

- **Online:** both phones need internet, including different Wi-Fi/mobile networks. One creates an invitation; the other scans its QR or opens the private link. Check the six-digit code on both screens. Transfers use AES-256-GCM with direction/sequence authentication. Cloudflare forwards bounded encrypted WebSocket frames without persisting transfer data.
- **Offline nearby:** open the screen online once on each phone and wait for **Ready for offline nearby sharing**. Join the same Wi-Fi/hotspot; internet is unnecessary. The first phone creates an offline invitation, the second scans it and shows a return QR, and the first scans that return QR. WebRTC uses local candidates with no STUN/TURN or internet signaling. The service worker caches app files only. Guest-network isolation can block a direct connection.
- Both phones keep the screen open. Explicitly accept each incoming transfer. Send text up to 4 KB, or 1–20 photos/files totaling 300 MB. Decline, cancel, and disconnect are supported. There is no background delivery queue. Online sessions expire after two hours.
- On Android, **Save to Downloads**, **Copy file**, and **Copy photo** write a complete file into Downloads/ClipBridge. Copy controls also place its content URI on the clipboard. Text has a native copy action. iPhone uses Download/Share and Copy photo; documents can be copied after saving to Files. Save received files before closing the sharing screen.
- Online relay usage counts against the existing Cloudflare Workers/Durable Objects free quotas. When service quotas are exhausted, online sharing may be unavailable until reset; offline nearby does not use the relay. No paid storage or TURN service is configured.

QR generation uses qrcode-generator 2.0.4 by Kazuhiko Arase (MIT), with the upstream module minified using Terser 5.51.2 in `public/vendor/qrcode.mjs` and its license alongside it.
