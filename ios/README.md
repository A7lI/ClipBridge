# ClipBridge for iPhone · text prototype

Pair one iPhone to a Windows PC and send plain text (up to 1 MB) over the local network. **Get from PC** reads the Windows clipboard when you tap it, including text copied before the iPhone app opened. Choose **Copy** to put the result on the iPhone clipboard.

## Run on an iPhone

1. Quit any running Windows ClipBridge instance from its system tray menu. Open `windows/ClipBridge-PC.exe` from this folder, or run the updated `desktop/app.py` from the project root with `desktop/requirements.txt` installed. The existing pairing and settings are shared with the regular Windows build.
2. Allow Windows firewall access on the trusted private network if prompted. Connect the PC and iPhone to the same network. If the Windows button says **Start syncing**, press it before transferring text.
3. On a Mac, open `ClipBridge.xcodeproj` in Xcode. In the ClipBridge target’s **Signing & Capabilities**, choose your development team. If Xcode reports that the bundle ID is unavailable, choose a unique bundle ID there. Select your connected iPhone and run the ClipBridge scheme. The deployment target is iOS 17.
4. Tap **Scan PC pairing QR code** and allow Camera and Local Network access. Aim at the QR code in the Windows window. **Enter pairing link** also accepts the link shown on Windows. If the PC’s IP address changes, scan its new QR code.

## Check both directions

- **iPhone → Windows:** Copy a short line of text in another iPhone app. Open ClipBridge and tap **Paste**, then press **Ctrl+V** in Notepad. You can also type in ClipBridge and tap **Send**.
- **Windows → iPhone:** Close ClipBridge from the iPhone app switcher. Leave the PC app running and copy a new line in Notepad. Reopen ClipBridge, tap **Get from PC**, then **Copy**. Paste into Notes and compare the text. Try some Arabic, emoji, and line breaks.
- **Pause:** Click **Pause syncing** on Windows, then try sending or getting text. Both operations should report that the PC is paused. Resume syncing to retry.

The QR contains the Windows address and shared pairing key. The app verifies the pairing with the PC before saving it in Keychain. Requests and replies use the existing authenticated AES-GCM protocol over local HTTP, with local-network transport exceptions for private and link-local IPv4 addresses. Keep the QR code and pairing link private.

## Publish an iPhone install link

Use TestFlight for the preview. Visitors open the public invitation on their iPhone and install the build in TestFlight. Keep the matching Windows companion available on the ClipBridge page.

1. Commit the `ios/ClipBridge` and `ios/ClipBridge.xcodeproj` folders, `ios/upload-testflight.sh`, and `.github/workflows/ios-testflight.yml` to the ClipBridge repository. Run the **ClipBridge iPhone** workflow from the repository’s default branch with upload disabled for an unsigned simulator build.
2. In your Apple Developer team, register an explicit iOS bundle ID, create the App Store Connect app record, and create its Apple Distribution certificate and App Store Connect distribution provisioning profile. An App Store Connect team API key with build-upload access is needed for automated upload.
3. Configure the `testflight` GitHub Actions environment in that repository. Set `APPLE_TEAM_ID`, `IOS_BUNDLE_ID`, `APP_STORE_CONNECT_KEY_ID`, and `APP_STORE_CONNECT_ISSUER_ID` as environment variables. Set `IOS_DISTRIBUTION_P12`, `IOS_APP_STORE_PROFILE`, and `APP_STORE_CONNECT_KEY` to the base64 contents of the `.p12`, `.mobileprovision`, and `.p8` files as environment secrets. Set `IOS_DISTRIBUTION_PASSWORD` to the `.p12` export password as an environment secret. Keep the signing files in private storage.
4. Run the workflow from the default branch with upload enabled. In App Store Connect, complete the build’s export-compliance questions. Install the processed build on an iPhone through internal testing and verify QR pairing and text transfer with the Windows companion.
5. Add the build to an external TestFlight group and submit it for Apple’s beta review. Include the Windows companion download, pairing steps, and how to test both directions in the review information. Once Apple approves the build and testing is active, create the public link and use it for a **Try on iPhone** button. TestFlight builds expire after 90 days.

[Apple build uploads](https://developer.apple.com/help/app-store-connect/manage-builds/upload-builds/) · [Apple external TestFlight testing](https://developer.apple.com/help/app-store-connect/test-a-beta-version/invite-external-testers)
