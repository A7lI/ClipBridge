# Windows installer

Download **ClipBridge-Setup-0.7.1.exe** from the website and run it. Setup installs the complete Windows app and adds ClipBridge to Start. A desktop shortcut and Explorer's Send to shortcut are optional. No ZIP extraction or Python installation is needed.

Installation is for the current Windows user, in `%LOCALAPPDATA%\Programs\ClipBridge`. Pairing, settings, downloaded voice models and received files remain in `%LOCALAPPDATA%\ClipBridge`. Updating or uninstalling the program leaves that data in place.

If a portable copy is running, quit it from its system tray menu before opening the installed copy. Updates to an installed copy use the same installation directory. Uninstall through Windows Settings → Apps → Installed apps → ClipBridge.

The full portable ZIP is still available on the GitHub release. Keep its files together when using the portable version.

The app and installer are currently unsigned. Windows may show an unknown-publisher or SmartScreen notice.

## Rebuild

Install or extract Inno Setup 6.7.4 or newer from https://jrsoftware.org/. From the source root, run:

```powershell
python build_installer.py --iscc "C:\Path\To\ISCC.exe" --portable "C:\Path\To\ClipBridge-Windows-0.7.1-preview.zip" --work "C:\Build\ClipBridge-installer" --output "C:\Build\release"
```

The builder packages the complete portable payload with its third-party notices, the Inno Setup license, a Windows uninstaller, and the shortcuts defined in `installer/ClipBridge.iss`. Application binaries are unchanged from the portable release. Inno Setup is by Jordan Russell and Martijn Laan; see `licenses/inno-setup/LICENSE.txt`.
