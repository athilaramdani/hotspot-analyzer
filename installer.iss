[Setup]
; Basic app info
AppName=HotspotAnalyzer
AppVersion=1.0.0
AppPublisher=Medical AI Solutions
AppPublisherURL=https://github.com/athilaramdani/hotspot-analyzer
AppSupportURL=https://github.com/athilaramdani/hotspot-analyzer/issues
AppUpdatesURL=https://github.com/athilaramdani/hotspot-analyzer/releases
DefaultDirName={autopf}\HotspotAnalyzer
DefaultGroupName=HotspotAnalyzer
AllowNoIcons=yes

; Output settings
OutputDir=installer_output
OutputBaseFilename=HotspotAnalyzer_Setup_v1.0.0_SingleFile

; Remove disk spanning:
; DiskSpanning=yes

; Use external compressor:
Compression=lzma2/max
SolidCompression=yes

; Installer appearance
WizardStyle=modern
DisableWelcomePage=no

; Requirements
MinVersion=6.1sp1
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Files]
; Main executable
Source: "dist\HotspotAnalyzer\HotspotAnalyzer.exe"; DestDir: "{app}"; Flags: ignoreversion

; All directories and subdirectories
Source: "dist\HotspotAnalyzer\assets\*"; DestDir: "{app}\assets"; Flags: ignoreversion recursesubdirs createallsubdirs; Check: DirExists('dist\HotspotAnalyzer\assets')
Source: "dist\HotspotAnalyzer\config\*"; DestDir: "{app}\config"; Flags: ignoreversion recursesubdirs createallsubdirs; Check: DirExists('dist\HotspotAnalyzer\config')
Source: "dist\HotspotAnalyzer\data\*"; DestDir: "{app}\data"; Flags: ignoreversion recursesubdirs createallsubdirs; Check: DirExists('dist\HotspotAnalyzer\data')
Source: "dist\HotspotAnalyzer\logs\*"; DestDir: "{app}\logs"; Flags: ignoreversion recursesubdirs createallsubdirs; Check: DirExists('dist\HotspotAnalyzer\logs')
Source: "dist\HotspotAnalyzer\models\*"; DestDir: "{app}\models"; Flags: ignoreversion recursesubdirs createallsubdirs; Check: DirExists('dist\HotspotAnalyzer\models')
Source: "dist\HotspotAnalyzer\temp\*"; DestDir: "{app}\temp"; Flags: ignoreversion recursesubdirs createallsubdirs; Check: DirExists('dist\HotspotAnalyzer\temp')
Source: "dist\HotspotAnalyzer\_internal\*"; DestDir: "{app}\_internal"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\HotspotAnalyzer"; Filename: "{app}\HotspotAnalyzer.exe"; WorkingDir: "{app}"
Name: "{group}\{cm:UninstallProgram,HotspotAnalyzer}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\HotspotAnalyzer"; Filename: "{app}\HotspotAnalyzer.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\HotspotAnalyzer.exe"; Description: "Launch HotspotAnalyzer"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}\logs"
Type: filesandordirs; Name: "{app}\temp"

[Code]
function DirExists(const DirName: String): Boolean;
begin
  Result := DirExists(ExpandConstant(DirName));
end;