#define AppName "Move Coach"
#define AppVersion "12.0.0"
#define AppPublisher "Move Coach"
#define AppExeName "MoveCoach.exe"

[Setup]
AppId={{B6C2B8A3-8A96-4BB0-BE41-7F8C3A4B9E20}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={localappdata}\MoveCoach
DefaultGroupName={#AppName}
OutputDir=Output
OutputBaseFilename=MoveCoach-Setup-v13
Compression=lzma2/ultra64
SolidCompression=yes
PrivilegesRequired=lowest
ArchitecturesInstallIn64BitMode=x64compatible
DisableProgramGroupPage=yes
UninstallDisplayIcon={app}\{#AppExeName}

[Files]
Source: "..\dist\MoveCoach\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Start {#AppName}"; Flags: nowait postinstall skipifsilent
