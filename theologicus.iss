; THEOLOGICUS Installer - Inno Setup 7
; Build: C:\Users\toshr\AppData\Local\Programs\Inno Setup 7\ISCC.exe theologicus.iss

#define MyAppName "THEOLOGICUS-AI"
#define MyAppVersion "1.0.15"
#define MyAppPublisher "Ambassadeur"
#define MyAppURL "https://github.com/jelliel/Theologicus-AI"

[Setup]
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
OutputDir=.
OutputBaseFilename=THEOLOGICUS-AI-v{#MyAppVersion}-Setup
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesInstallIn64BitMode=x64
LicenseFile=readme.md
InfoBeforeFile=readme.md
InfoAfterFile=readme.md

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "french"; MessagesFile: "compiler:Languages\French.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "quicklaunchicon"; Description: "{cm:CreateQuickLaunchIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "main.py"; DestDir: "{app}"
Source: "ui.py"; DestDir: "{app}"
Source: "ui_new.html"; DestDir: "{app}"
Source: "requirements.txt"; DestDir: "{app}"
Source: "readme.md"; DestDir: "{app}"
Source: "bump_version.py"; DestDir: "{app}"
Source: "THEOLOGICUS-Setup.bat"; DestDir: "{app}"
Source: "setup_theologicus.bat"; DestDir: "{app}"
Source: "dist\THEOLOGICUS.exe"; DestDir: "{app}\dist"
Source: "actions\*"; DestDir: "{app}\actions"; Flags: recursesubdirs
Source: "config\*"; DestDir: "{app}\config"; Flags: recursesubdirs
Source: "core\*"; DestDir: "{app}\core"; Flags: recursesubdirs
Source: "dashboard\*"; DestDir: "{app}\dashboard"; Flags: recursesubdirs
Source: "memory\*"; DestDir: "{app}\memory"; Flags: recursesubdirs
Source: "research\*"; DestDir: "{app}\research"; Flags: recursesubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\dist\THEOLOGICUS.exe"; IconFilename: "{app}\config\theologicus.ico"
Name: "{group}\{#MyAppName} (Uninstall)"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\dist\THEOLOGICUS.exe"; IconFilename: "{app}\config\theologicus.ico"; Tasks: desktopicon
Name: "{userappdata}\Microsoft\Internet Explorer\Quick Launch\{#MyAppName}"; Filename: "{app}\dist\THEOLOGICUS.exe"; IconFilename: "{app}\config\theologicus.ico"; Tasks: quicklaunchicon

[Code]
procedure CurPageChanged(CurPageID: Integer);
begin
  if CurPageID = wpReady then
  begin
    Log('Preparing installation');
  end;
end;
