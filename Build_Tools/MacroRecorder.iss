#ifndef AppSourceDir
  #error AppSourceDir is required
#endif
#ifndef OutputDir
  #error OutputDir is required
#endif

[Setup]
AppId={{31B415CE-725F-48A2-B27B-9583D11AE498}
AppName=Макро Рекордер
AppVersion=0.3.0
VersionInfoVersion=0.3.0
AppPublisher=Frommer-droid
DefaultDirName={code:DefaultAppDir}
DefaultGroupName=Макро Рекордер
UsePreviousAppDir=no
PrivilegesRequired=admin
OutputDir={#OutputDir}
OutputBaseFilename=MacroRecorder_v0.3.0_Setup
SetupIconFile=..\logo.ico
UninstallDisplayIcon={app}\logo.ico
LicenseFile=..\LICENSE
Compression=lzma2
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
LanguageDetectionMethod=none
ShowLanguageDialog=no
CloseApplications=yes

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"

[Tasks]
Name: "desktopicon"; Description: "Создать ярлык на рабочем столе"; GroupDescription: "Ярлыки:"

[Files]
Source: "{#AppSourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Макро Рекордер"; Filename: "{app}\MacroRecorder.exe"; WorkingDir: "{app}"
Name: "{autodesktop}\Макро Рекордер"; Filename: "{app}\MacroRecorder.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\MacroRecorder.exe"; Description: "Запустить приложение"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}"

[Code]
function DefaultAppDir(Param: String): String;
begin
  if DirExists('D:\') then
    Result := 'D:\Apps\Макро Рекордер'
  else
    Result := 'C:\Apps\Макро Рекордер';
end;
