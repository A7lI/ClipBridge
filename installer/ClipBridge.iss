; Build with build_installer.py and Inno Setup 6.7.4 or newer.
#ifndef AppVersion
  #error AppVersion must be supplied by the build script
#endif

[Setup]
AppId={{C76D5B54-78B0-4C5C-962E-C56DACF1F657}
AppName=ClipBridge
AppVersion={#AppVersion}
AppPublisher=A7li
AppPublisherURL=https://www.a7li.dev/apps/clipbridge/
AppSupportURL=https://github.com/A7lI/ClipBridge/issues
AppUpdatesURL=https://www.a7li.dev/apps/clipbridge/
DefaultDirName={localappdata}\Programs\ClipBridge
DefaultGroupName=ClipBridge
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir={#OutputDir}
OutputBaseFilename=ClipBridge-Setup-{#AppVersion}
SetupIconFile={#ProjectDir}\desktop\assets\clipbridge.ico
UninstallDisplayIcon={app}\ClipBridge-PC.exe
Compression=lzma2/fast
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no
SetupMutex=ClipBridgeSetupInstaller
VersionInfoVersion={#AppVersion}

[Tasks]
Name: desktopicon; Description: "Create a desktop shortcut"; Flags: unchecked
Name: sendto; Description: "Add Share to My Phone to Explorer's Send to menu"; Flags: unchecked

[Files]
Source: "{#PayloadDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\ClipBridge"; Filename: "{app}\ClipBridge-PC.exe"; WorkingDir: "{app}"; AppUserModelID: "A7li.ClipBridge"
Name: "{autodesktop}\ClipBridge"; Filename: "{app}\ClipBridge-PC.exe"; WorkingDir: "{app}"; Tasks: desktopicon
; Preserve a shortcut later redirected by a portable copy. Remove it ourselves
; at uninstall only when its target still belongs to this installation.
Name: "{userappdata}\Microsoft\Windows\SendTo\Share to My Phone (ClipBridge)"; Filename: "{app}\ClipBridge-PC.exe"; Parameters: "--send-files --"; IconFilename: "{app}\shell\ClipBridge-Phone.ico"; Tasks: sendto; Flags: uninsneveruninstall

[Run]
Filename: "{app}\ClipBridge-PC.exe"; Description: "Open ClipBridge"; WorkingDir: "{app}"; Flags: nowait postinstall skipifsilent; Check: CanLaunchClipBridge

[Code]
function CanLaunchClipBridge: Boolean;
begin
  Result := FindWindowByWindowName('ClipBridge') = 0;
end;

procedure CurPageChanged(CurPageID: Integer);
begin
  if (CurPageID = wpFinished) and not CanLaunchClipBridge then
    WizardForm.FinishedLabel.Caption := 'ClipBridge is installed. Quit the older ClipBridge from its system tray menu, then open ClipBridge from Start.';
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  Shell, Link: Variant;
  Shortcut: String;
begin
  if CurUninstallStep <> usUninstall then exit;
  Shortcut := ExpandConstant('{userappdata}\Microsoft\Windows\SendTo\Share to My Phone (ClipBridge).lnk');
  if not FileExists(Shortcut) then exit;
  try
    Shell := CreateOleObject('WScript.Shell');
    Link := Shell.CreateShortcut(Shortcut);
    if CompareText(Link.TargetPath, ExpandConstant('{app}\ClipBridge-PC.exe')) = 0 then
      DeleteFile(Shortcut);
  except
    Log('Left the Send to shortcut in place because its owner could not be verified.');
  end;
end;
