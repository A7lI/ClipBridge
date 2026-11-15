# ClipBridge iPhone web preview

Pair with Windows by QR, then send text, photos, and files in either direction on the same Wi-Fi. Photos and files share a 300 MB total limit per batch of up to 20 files. Text supports up to 4 KB per transfer. Tap **Get from PC** to read the current Windows clipboard, including items copied while ClipBridge was closed on the iPhone.

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
