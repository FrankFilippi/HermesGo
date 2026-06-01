; HermesWebUI.iss — Inno Setup script for the one-click Hermes desktop installer.
;
; Design goals:
;   * No administrator rights required — installs per-user so a "normal user" can
;     just double-click and go. (PrivilegesRequired=lowest)
;   * Bundles everything: the frozen HermesWebUI.exe + _internal, portable Node,
;     PortableGit, the WebView2 Fixed Version runtime, and a provisioned Hermes
;     venv. The user installs no Python, Node, WebView2 or dev tools.
;   * Seeds the bundled skills into the Hermes home on first install.
;
; Compiled by build\make-installer.ps1 which passes /DAppVersion and /DStageDir.
; Requires Inno Setup 6+ (ISCC.exe).

#ifndef AppVersion
  #define AppVersion "0.1.0"
#endif
#ifndef StageDir
  #define StageDir "..\..\build\.stage"
#endif
#ifndef OutputDir
  #define OutputDir "..\..\dist"
#endif

#define AppName "Hermes"
#define AppExeName "HermesWebUI.exe"
#define AppPublisher "HermesWebUI"

[Setup]
AppId={{B5E6F0A2-7E2E-4A2B-9C1D-HERMESWEBUI01}}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
; Per-user install — no UAC prompt, no admin needed.
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
DefaultDirName={localappdata}\Programs\HermesWebUI
DefaultGroupName=Hermes
DisableProgramGroupPage=yes
UninstallDisplayIcon={app}\{#AppExeName}
OutputDir={#OutputDir}
OutputBaseFilename=HermesGo-Setup-{#AppVersion}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
; Long paths inside the bundled venv/node_modules — keep the install dir short
; (we already use a short DefaultDirName) and enable LZMA solid compression.
DisableDirPage=auto

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional icons:"

[Files]
; The entire staged payload (frozen exe + _internal + runtime\*) goes to {app}.
Source: "{#StageDir}\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion
; Seed bundled skills into the user's Hermes home, but never clobber skills the
; user already has. (onlyifdoesntexist + skipifsourcedoesntexist make this safe.)
Source: "{#StageDir}\runtime\hermes\default-skills\*"; DestDir: "{localappdata}\hermes\skills"; \
    Flags: recursesubdirs createallsubdirs onlyifdoesntexist skipifsourcedoesntexist

[Dirs]
; Make sure the Hermes home + logs exist so first-run logging never fails.
Name: "{localappdata}\hermes"
Name: "{localappdata}\hermes\logs\hermeswebui"
Name: "{localappdata}\hermes\skills"

[Icons]
Name: "{group}\Hermes"; Filename: "{app}\{#AppExeName}"
Name: "{group}\Hermes logs"; Filename: "{localappdata}\hermes\logs\hermeswebui"
Name: "{group}\Uninstall Hermes"; Filename: "{uninstallexe}"
Name: "{userdesktop}\Hermes"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
; Offer to launch right after install.
Filename: "{app}\{#AppExeName}"; Description: "Launch Hermes"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Remove our log folder on uninstall; leave the rest of %LOCALAPPDATA%\hermes
; (sessions, memories, user skills) intact so a reinstall keeps the user's data.
Type: filesandordirs; Name: "{localappdata}\hermes\logs\hermeswebui"
