; Claudia Office for Windows: the installer (D740-D745). Built by packaging/windows/build.py, which stages the files
; and calls ISCC with the /D values below; see packaging/windows/README.md.
;
;   iscc /DAppVersion=0.4.0 /DNumericVersion=0.4.0.0 /DStageDir=C:\...\stage /DOutputDir=C:\...\dist claudia.iss
;
; What is installed (under {app}):
;   client\    the three desktop apps (Neutralino windows and their Node core), started by client\claudia-start.exe
;   node\      the Node.js that runs the launcher and the core
;   server\    claudia-server.exe: the server with its Python and its libraries inside
;   web\       the built web frontend the server serves
;   service\   (optional component) WinSW, which runs the server as the Windows service "ClaudiaServer"
;   icons\     the icons of the shortcuts
#ifndef AppVersion
  #error AppVersion is not defined: pass /DAppVersion=1.2.3
#endif
#ifndef NumericVersion
  #define NumericVersion "0.0.0.0"
#endif
#ifndef StageDir
  #error StageDir is not defined: pass /DStageDir=<the staged files>
#endif
#ifndef OutputDir
  #define OutputDir "."
#endif

#define AppName "Claudia Office"
#define ServiceId "ClaudiaServer"
#define WebView2Setup "MicrosoftEdgeWebview2Setup.exe"

[Setup]
; Never change the AppId: it is how an update finds the installation it replaces.
AppId={{6C1F2D0A-5B7E-4F0C-9A53-2D8E7B41C9A6}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=Claudia
AppPublisherURL=https://github.com/claudiaoffice/claudia
AppSupportURL=https://github.com/claudiaoffice/claudia/issues
VersionInfoVersion={#NumericVersion}
DefaultDirName={autopf}\Claudia Office
DefaultGroupName=Claudia Office
UninstallDisplayName={#AppName}
UninstallDisplayIcon={app}\icons\claudia.ico
SetupIconFile={#StageDir}\icons\claudia.ico
LicenseFile={#StageDir}\LICENSE.txt
OutputDir={#OutputDir}
OutputBaseFilename=claudia-office-{#AppVersion}-windows-x64
WizardStyle=modern
Compression=lzma2/max
SolidCompression=yes
; Windows 10 1809 and newer, on 64-bit processors (Windows on ARM runs the x64 files).
MinVersion=10.0.17763
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
; Per person without administrator rights, or for all people with them: the person is asked. The service needs them.
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=commandline dialog
DisableProgramGroupPage=yes
ChangesEnvironment=no
; A running server holds its files: Windows' Restart Manager closes what it can, PrepareToInstall ends the rest.
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "en"; MessagesFile: "compiler:Default.isl"
Name: "de"; MessagesFile: "compiler:Languages\German.isl"

[CustomMessages]
en.ComponentClient=Claudia Composes, Computes and Creates
en.ComponentService=Claudia server as a Windows service (for sharing documents on this computer's network)
en.TypeStandard=Standard (the three apps)
en.TypeFull=With the server as a Windows service
en.TaskDesktopIcons=Create icons on the desktop
en.StatusService=Setting up the Claudia server service...
en.StatusWebView2=Installing Microsoft's WebView2 Runtime, which shows the apps' windows...
en.RunComposes=Start Claudia Composes
en.DocumentsStay=Your documents were left where they are (%LOCALAPPDATA%\Claudia, and %ProgramData%\Claudia for the service). Delete those folders if you do not need them.
de.ComponentClient=Claudia Composes, Computes und Creates
de.ComponentService=Claudia-Server als Windows-Dienst (um Dokumente im Netzwerk dieses Computers zu teilen)
de.TypeStandard=Standard (die drei Programme)
de.TypeFull=Mit dem Server als Windows-Dienst
de.TaskDesktopIcons=Symbole auf dem Desktop anlegen
de.StatusService=Der Dienst des Claudia-Servers wird eingerichtet ...
de.StatusWebView2=Die WebView2-Runtime von Microsoft, die die Fenster der Programme anzeigt, wird installiert ...
de.RunComposes=Claudia Composes starten
de.DocumentsStay=Ihre Dokumente wurden dort belassen, wo sie liegen (%LOCALAPPDATA%\Claudia, und %ProgramData%\Claudia für den Dienst). Löschen Sie diese Ordner, wenn Sie sie nicht mehr brauchen.

[Types]
Name: "standard"; Description: "{cm:TypeStandard}"
Name: "full"; Description: "{cm:TypeFull}"
Name: "custom"; Description: "{code:CustomTypeName}"; Flags: iscustom

[Components]
Name: "client"; Description: "{cm:ComponentClient}"; Types: standard full custom; Flags: fixed
Name: "service"; Description: "{cm:ComponentService}"; Types: full

[Tasks]
Name: "desktopicons"; Description: "{cm:TaskDesktopIcons}"; Flags: unchecked

[Dirs]
; The service's own folders: it runs without anyone signed in, so it keeps its documents here (see claudia-service.xml).
Name: "{commonappdata}\Claudia\documents"; Components: service
Name: "{commonappdata}\Claudia\state\service"; Components: service

[Files]
Source: "{#StageDir}\client\*"; DestDir: "{app}\client"; Flags: recursesubdirs createallsubdirs ignoreversion; Components: client
Source: "{#StageDir}\node\*"; DestDir: "{app}\node"; Flags: recursesubdirs createallsubdirs ignoreversion; Components: client
Source: "{#StageDir}\server\*"; DestDir: "{app}\server"; Flags: recursesubdirs createallsubdirs ignoreversion; Components: client
Source: "{#StageDir}\web\*"; DestDir: "{app}\web"; Flags: recursesubdirs createallsubdirs ignoreversion; Components: client
Source: "{#StageDir}\icons\*"; DestDir: "{app}\icons"; Flags: ignoreversion; Components: client
Source: "{#StageDir}\LICENSE.txt"; DestDir: "{app}"; Flags: ignoreversion; Components: client
Source: "{#StageDir}\CHANGELOG.md"; DestDir: "{app}"; Flags: ignoreversion; Components: client
Source: "{#StageDir}\service\claudia-service.exe"; DestDir: "{app}\service"; Flags: ignoreversion; Components: service
; The configuration is the person's once installed: an update does not take a changed copy back.
Source: "{#StageDir}\service\claudia-service.xml"; DestDir: "{app}\service"; Flags: onlyifdoesntexist; Components: service
Source: "{#StageDir}\prerequisites\{#WebView2Setup}"; DestDir: "{tmp}"; Flags: deleteafterinstall; Check: NeedsWebView2

[Icons]
; The windows are those of Neutralino. claudia-start.exe starts node with the app's launcher, which starts the window and
; its core; it has no window of its own, hides node's, and keeps what they print in
; %LOCALAPPDATA%\Claudia\<app>\state\launcher.log (UX-78, D750).
Name: "{autoprograms}\Claudia Composes"; Filename: "{app}\client\claudia-start.exe"; Parameters: "composes"; WorkingDir: "{app}"; IconFilename: "{app}\icons\composes.ico"
Name: "{autoprograms}\Claudia Computes"; Filename: "{app}\client\claudia-start.exe"; Parameters: "computes"; WorkingDir: "{app}"; IconFilename: "{app}\icons\computes.ico"
Name: "{autoprograms}\Claudia Creates"; Filename: "{app}\client\claudia-start.exe"; Parameters: "creates"; WorkingDir: "{app}"; IconFilename: "{app}\icons\creates.ico"
Name: "{autodesktop}\Claudia Composes"; Filename: "{app}\client\claudia-start.exe"; Parameters: "composes"; WorkingDir: "{app}"; IconFilename: "{app}\icons\composes.ico"; Tasks: desktopicons
Name: "{autodesktop}\Claudia Computes"; Filename: "{app}\client\claudia-start.exe"; Parameters: "computes"; WorkingDir: "{app}"; IconFilename: "{app}\icons\computes.ico"; Tasks: desktopicons
Name: "{autodesktop}\Claudia Creates"; Filename: "{app}\client\claudia-start.exe"; Parameters: "creates"; WorkingDir: "{app}"; IconFilename: "{app}\icons\creates.ico"; Tasks: desktopicons

[Run]
Filename: "{tmp}\{#WebView2Setup}"; Parameters: "/silent /install"; StatusMsg: "{cm:StatusWebView2}"; Flags: waituntilterminated; Check: NeedsWebView2
; The service: WinSW registers it, Windows is told to run it as LocalService (it needs no more), which may write its folder.
Filename: "{app}\service\claudia-service.exe"; Parameters: "install"; StatusMsg: "{cm:StatusService}"; Flags: runhidden waituntilterminated; Components: service
Filename: "{sys}\sc.exe"; Parameters: "config {#ServiceId} obj= ""NT AUTHORITY\LocalService"""; Flags: runhidden waituntilterminated; Components: service
Filename: "{sys}\icacls.exe"; Parameters: """{commonappdata}\Claudia"" /grant ""*S-1-5-19:(OI)(CI)M"""; Flags: runhidden waituntilterminated; Components: service
Filename: "{app}\service\claudia-service.exe"; Parameters: "start"; Flags: runhidden waituntilterminated; Components: service
Filename: "{app}\client\claudia-start.exe"; Parameters: "composes"; Description: "{cm:RunComposes}"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{app}\service\claudia-service.exe"; Parameters: "stop"; RunOnceId: "StopService"; Flags: runhidden waituntilterminated; Components: service
Filename: "{app}\service\claudia-service.exe"; Parameters: "uninstall"; RunOnceId: "RemoveService"; Flags: runhidden waituntilterminated; Components: service

[UninstallDelete]
; What the launcher copies for a window (D741) goes with the program; the documents stay (see the message at the end).
Type: filesandordirs; Name: "{localappdata}\Claudia\run"

[Code]
const
  WebView2Key = 'SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}';

function CustomTypeName(Param: String): String;
begin
  Result := SetupMessage(msgCustomInstallation);
end;

function HasWebView2Version(RootKey: Integer; const SubKey: String): Boolean;
var
  Version: String;
begin
  Result := RegQueryStringValue(RootKey, SubKey, 'pv', Version) and (Version <> '') and (Version <> '0.0.0.0');
end;

{ The WebView2 Runtime comes with Windows 11 and with Microsoft Edge; where it is not there, the setup brings it. }
function NeedsWebView2: Boolean;
begin
  Result := not (HasWebView2Version(HKLM32, WebView2Key) or HasWebView2Version(HKCU, WebView2Key));
end;

{ The service needs administrator rights: where the installation is for this person only, its component is not offered. }
procedure CurPageChanged(CurPageID: Integer);
var
  Index: Integer;
begin
  if CurPageID = wpSelectComponents then
  begin
    Index := WizardForm.ComponentsList.Items.IndexOf(CustomMessage('ComponentService'));
    if (Index >= 0) and not IsAdminInstallMode then
    begin
      WizardForm.ComponentsList.Checked[Index] := False;
      WizardForm.ComponentsList.ItemEnabled[Index] := False;
    end;
  end;
end;

{ A running server (the service, or the one of a window) holds its files: it is ended before they are replaced or removed. }
procedure EndTheServer;
var
  Code: Integer;
  Service: String;
begin
  Service := ExpandConstant('{app}\service\claudia-service.exe');
  if FileExists(Service) then
    Exec(Service, 'stop', '', SW_HIDE, ewWaitUntilTerminated, Code);
  Exec(ExpandConstant('{sys}\taskkill.exe'), '/F /T /IM claudia-server.exe', '', SW_HIDE, ewWaitUntilTerminated, Code);
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  EndTheServer;
  Result := '';
end;

function InitializeUninstall: Boolean;
begin
  EndTheServer;
  Result := True;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if (CurUninstallStep = usPostUninstall) and not UninstallSilent then
    MsgBox(ExpandConstant('{cm:DocumentsStay}'), mbInformation, MB_OK);
end;
