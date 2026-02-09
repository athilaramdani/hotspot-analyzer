; ==========================================
; Telplastina Installer
; Inno Setup 6.x
; ==========================================

; ==== APP METADATA ====
#define MyAppName       "Telplastina"
#define MyAppExeName    "telplastina.exe"
#define MyAppVersion    "1.7.7"
#define MyAppPublisher  "Telplastina Team"
#define MyAppURL        "https://example.com"   ; optional

; GUID TANPA KURUNG. Penting!
#define MyAppID         "E9F2C3B0-3F3A-4F7E-9D0E-7B7A5A3D1B75"

; ==== PATHS ====
#define MyDistRoot      "F:\projek dosen\prototype riset\hotspot-analyzer\dist\telplastina"
#define MyOutputDir     "F:\projek dosen\prototype riset\hotspot-analyzer\installer_output"
#define MySetupIcon     "F:\projek dosen\prototype riset\hotspot-analyzer\assets\icon.ico"

[Setup]
; Hasil expand -> {{E9F2...}} (dua kurung di awal, dua di akhir)
AppId={{{#MyAppID}}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppComments=Medical AI Metastasis Detection
VersionInfoProductName={#MyAppName}
VersionInfoVersion={#MyAppVersion}
VersionInfoTextVersion={#MyAppVersion}
VersionInfoDescription=Telplastina | Medical AI Metastasis Detection

; Default install dir (user bisa ganti)
DefaultDirName={sd}\Telplastina
UsePreviousAppDir=yes
DisableDirPage=no

; Start Menu group
DefaultGroupName=Telplastina

; Ikon installer & ikon Uninstaller
SetupIconFile={#MySetupIcon}
UninstallDisplayIcon={app}\assets\icon.ico

; Output file
OutputBaseFilename=Telplastina-Setup-{#MyAppVersion}
OutputDir={#MyOutputDir}

; 64-bit, admin
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
PrivilegesRequired=admin

; Kompresi
Compression=lzma2/ultra64
SolidCompression=yes

; UX
WizardStyle=modern
DisableProgramGroupPage=no
DisableReadyMemo=no

; Cegah install saat app jalan
AppMutex=TelplastinaMutex

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a Desktop icon"; GroupDescription: "Shortcuts:"; Flags: unchecked

[Files]
Source: "{#MyDistRoot}\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#MyDistRoot}\assets\*";     DestDir: "{app}\assets";     Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#MyDistRoot}\config\*";     DestDir: "{app}\config";     Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#MyDistRoot}\models\*";     DestDir: "{app}\models";     Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#MyDistRoot}\data\*";       DestDir: "{app}\data";       Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#MyDistRoot}\_internal\*";  DestDir: "{app}\_internal";  Flags: ignoreversion recursesubdirs createallsubdirs

; Opsional:
; Source: "{#MyDistRoot}\logs\*";     DestDir: "{app}\logs";  Flags: ignoreversion recursesubdirs createallsubdirs skipifsourcedoesntexist
; Source: "{#MyDistRoot}\temp\*";     DestDir: "{app}\temp";  Flags: ignoreversion recursesubdirs createallsubdirs skipifsourcedoesntexist

[Dirs]
Name: "{app}\logs"
Name: "{app}\temp"

[Icons]
Name: "{group}\Telplastina";           Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; IconFilename: "{app}\assets\icon.ico"
Name: "{group}\Uninstall Telplastina"; Filename: "{uninstallexe}"
Name: "{commondesktop}\Telplastina";   Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon; WorkingDir: "{app}"; IconFilename: "{app}\assets\icon.ico"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Run Telplastina now"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}\logs"
Type: filesandordirs; Name: "{app}\temp"
