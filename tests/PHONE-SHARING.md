# Phone sharing checks

Start the local Worker with `npx wrangler dev --config web/wrangler.jsonc --port 8787`. Install Playwright in a separate Node tools folder and expose its node_modules through NODE_PATH. Set CLIPBRIDGE_BROWSER to a Chromium executable path if Brave is not installed in its default Windows location.

Run `node tests/check_phone_web.cjs` for online relay sharing, `node tests/check_phone_web.cjs --offline` for cached pages and QR-paired local sharing, and add `--large` for full 300 MB checks both ways. Optional CLIPBRIDGE_PHONE_URL points to the deployed sharing page. CLIPBRIDGE_ARTIFACTS sets an existing screenshot output directory. Tests create and remove an isolated temporary folder.

The offline check reopens both pages with the browser offline, then restores LAN sockets while blocking HTTP requests and the service worker network fetch function. DevTools offline emulation also disables LAN WebRTC, so it is not suitable for the direct-transfer portion. No signaling server is used for that handshake or transfer.

`python tests/check_phone_relay.py` checks origin restrictions, role exclusivity, missing hosts, invalid frames, and binary forwarding against the local Worker. Requires websockets from desktop/requirements.txt.

Run the existing Android SDK build and QR/keyboard checks for the native companion. A physical-device check is still required for Android WebView camera/file-picker/Downloads integration and iPhone Safari clipboard, hotspot, and memory behavior.
