; yazıt — Inno Setup 6 kurulum betiği (tamga ailesi; uygulamanın eski adı delta)
; Doğrudan değil, packaging\build.ps1 üzerinden derleyin (önce PyInstaller çıktısı gerekir).
; Yönetici izni istemez: varsayılan olarak %LOCALAPPDATA%\Programs\yazit klasörüne kurulur.
; Kullanıcı verileri (%LOCALAPPDATA%\yazit: tercihler, önbellek; notlar Resimler\yazit) kaldırmada SİLİNMEZ.
;
; delta'dan yükseltme: AppId aynı (delta'nın kurulumu yerinde güncellenir, Programlar listesinde tek kayıt kalır)
; ama klasör yeni (UsePreviousAppDir=no → {autopf}\yazit). Kurulum bitince eski klasördeki delta dosyaları silinir,
; eski kısayollar / App Paths / Run değeri kaldırılır. .delta türü kayıtlı kalır (ProgID adı "delta.Note" değişmez:
; Windows'un varsayılan uygulama seçimi (UserChoice) bu ada bağlı; adı değişirse Windows güvenlik uyarısı sorar),
; yalnızca komutu ve simgesi yazit.exe'ye çevrilir. Yeni notlar .yazit (ProgID "yazit.Note").

#include "version.iss"
#define AppName "yazıt"
#define AppDir "yazit"
#define AppExe "yazit.exe"
#define AppUserModelID "tamga.yazit"
#define OldExe "delta.exe"
#define AppGuid "{274E63FA-2C5A-402B-BC02-3F663C51EDA8}"

[Setup]
; AppId delta ile aynı: yükseltme. DEĞİŞTİRME.
AppId={{274E63FA-2C5A-402B-BC02-3F663C51EDA8}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=tamga
DefaultDirName={autopf}\{#AppDir}
DefaultGroupName={#AppName}
; delta'nın klasörü / Başlat grubu yeniden kullanılmasın
UsePreviousAppDir=no
UsePreviousGroup=no
DisableProgramGroupPage=yes
DisableDirPage=auto
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\build\installer
OutputBaseFilename=yazit-setup-{#AppVersion}
SetupIconFile=..\yazit\assets\logo.ico
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName}
LicenseFile=..\LICENSE
VersionInfoDescription={#AppName} kurulumu
VersionInfoProductName={#AppName}
VersionInfoVersion={#AppVersion}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
; yazıt tepside çalışır; kapatma işini aşağıda "yazit.exe --quit" ile kendimiz yapıyoruz
CloseApplications=no
RestartApplications=no
; .yazit / .delta not dosyaları yazıt ile açılır (Gezgin simgeleri yenilensin)
ChangesAssociations=yes

[Languages]
Name: "turkish"; MessagesFile: "compiler:Languages\Turkish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[CustomMessages]
turkish.StartGroup=Başlangıç:
english.StartGroup=Startup:
turkish.TaskAutostart=Windows ile başlat (tepside sessizce bekler, kısayollar hep hazır)
english.TaskAutostart=Start with Windows (waits quietly in the tray, shortcuts always ready)
turkish.Desc=Not, çizim tahtası, ekran alıntısı, ekran videosu ve araştırma
english.Desc=Notes, whiteboard, screen snip, screen recording and research
turkish.SnipName=yazıt alıntı
english.SnipName=yazıt snip
turkish.SnipDesc=Ekran alıntısı al (yazıt kapalıysa tepside açılır)
english.SnipDesc=Take a screen snip (starts yazıt in the tray if it is not running)
turkish.NoteType=yazıt notu
english.NoteType=yazıt note
turkish.OldNoteType=yazıt notu (eski delta)
english.OldNoteType=yazıt note (old delta)
turkish.LaunchApp=yazıt'ı aç
english.LaunchApp=Open yazıt

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "autostart"; Description: "{cm:TaskAutostart}"; GroupDescription: "{cm:StartGroup}"

[Files]
Source: "..\build\dist\{#AppDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[InstallDelete]
; güncellemede eski sürümden kalan Python / Qt dosyaları karışmasın
Type: filesandordirs; Name: "{app}\_internal"
; delta'nın kısayolları (Başlat grubu "delta", masaüstü; alıntı kısayolu Türkçe / İngilizce adla)
Type: files; Name: "{autoprograms}\delta\delta.lnk"
Type: files; Name: "{autoprograms}\delta\delta alıntı.lnk"
Type: files; Name: "{autoprograms}\delta\delta snip.lnk"
Type: dirifempty; Name: "{autoprograms}\delta"
Type: files; Name: "{autodesktop}\delta.lnk"
Type: files; Name: "{autodesktop}\delta alıntı.lnk"
Type: files; Name: "{autodesktop}\delta snip.lnk"

[Icons]
; alıntı kısayolunun kendi kimliği var: aynı kimlikte Windows onu yazıt sayar, görev çubuğuna ayrıca sabitlenmez
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"; Comment: "{cm:Desc}"; AppUserModelID: "{#AppUserModelID}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Comment: "{cm:Desc}"; AppUserModelID: "{#AppUserModelID}"; Tasks: desktopicon
Name: "{group}\{cm:SnipName}"; Filename: "{app}\{#AppExe}"; Parameters: "--snip"; IconFilename: "{app}\_internal\yazit\assets\snip.ico"; Comment: "{cm:SnipDesc}"; AppUserModelID: "{#AppUserModelID}.snip"
Name: "{autodesktop}\{cm:SnipName}"; Filename: "{app}\{#AppExe}"; Parameters: "--snip"; IconFilename: "{app}\_internal\yazit\assets\snip.ico"; Comment: "{cm:SnipDesc}"; AppUserModelID: "{#AppUserModelID}.snip"; Tasks: desktopicon

[Registry]
; "Windows ile başlat" — uygulamanın Seçenekler'deki anahtarıyla aynı kayıt (HKCU Run → yazit)
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "yazit"; ValueData: """{app}\{#AppExe}"" --tray"; Tasks: autostart; Flags: uninsdeletevalue
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueName: "yazit"; ValueType: none; Flags: deletevalue uninsdeletevalue; Tasks: not autostart
; delta'nın eski kayıtları: Run değeri, App Paths, "Birlikte aç" listesinde Windows'un açtığı Applications\delta.exe
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueName: "delta"; ValueType: none; Flags: deletevalue
Root: HKA; Subkey: "Software\Microsoft\Windows\CurrentVersion\App Paths\{#OldExe}"; Flags: deletekey
Root: HKCU; Subkey: "Software\Classes\Applications\{#OldExe}"; Flags: deletekey
Root: HKA; Subkey: "Software\Microsoft\Windows\CurrentVersion\App Paths\{#AppExe}"; ValueType: string; ValueData: "{app}\{#AppExe}"; Flags: uninsdeletekey
; .yazit: yazıt notu (çizimler, yazılar, görseller, katmanlar) — çift tıkla yazıt'ta düzenlenebilir açılır
Root: HKA; Subkey: "Software\Classes\.yazit"; ValueType: string; ValueName: ""; ValueData: "yazit.Note"; Flags: uninsdeletevalue
Root: HKA; Subkey: "Software\Classes\yazit.Note"; ValueType: string; ValueName: ""; ValueData: "{cm:NoteType}"; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Classes\yazit.Note\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\_internal\yazit\assets\logo.ico"
Root: HKA; Subkey: "Software\Classes\yazit.Note\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExe}"" ""%1"""
; .delta: eski notlar. ProgID adı "delta.Note" BİLEREK aynı kalır (UserChoice bu ada bağlı olabilir); komut / simge yazıt'a
Root: HKA; Subkey: "Software\Classes\.delta"; ValueType: string; ValueName: ""; ValueData: "delta.Note"; Flags: uninsdeletevalue
Root: HKA; Subkey: "Software\Classes\delta.Note"; ValueType: string; ValueName: ""; ValueData: "{cm:OldNoteType}"; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Classes\delta.Note\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\_internal\yazit\assets\logo.ico"
Root: HKA; Subkey: "Software\Classes\delta.Note\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExe}"" ""%1"""

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchApp}"; Flags: nowait postinstall skipifsilent

[Code]
var
  OldAppDir: String;   // delta'nın kurulu olduğu klasör (yükseltmede; yoksa boş)

// /NOQUIT parametresi: test kurulumu çalışan yazıt'a dokunmasın
function ShouldQuitRunning(): Boolean;
begin
  Result := ExpandConstant('{param:NOQUIT|0}') = '0';
end;

// Önceki kurulumun klasörü (aynı AppId'nin kaldırma kaydından): delta'dan yükseltmede eski klasör
function PreviousAppDir(): String;
var
  Key: String;
begin
  Result := '';
  Key := 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{#AppGuid}_is1';
  if not RegQueryStringValue(HKA, Key, 'Inno Setup: App Path', Result) then
    if not RegQueryStringValue(HKCU, Key, 'Inno Setup: App Path', Result) then
      if not RegQueryStringValue(HKLM, Key, 'Inno Setup: App Path', Result) then
        Result := '';
end;

function InitializeSetup(): Boolean;
begin
  OldAppDir := PreviousAppDir();
  Result := True;
end;

function IsOldDirToClean(): Boolean;
begin
  Result := (OldAppDir <> '') and
            (CompareText(RemoveBackslashUnlessRoot(OldAppDir), RemoveBackslashUnlessRoot(ExpandConstant('{app}'))) <> 0) and
            FileExists(AddBackslash(OldAppDir) + '{#OldExe}');
end;

// Çalışan uygulamayı notlarını kaydettirerek kapat ("<exe> --quit"); 2,5 sn'de kapanmazsa zorla.
// --quit beklenmez: kurulu kopya bozuksa (yarım kalmış kurulum) exe hata kutusunda takılır, kurulum da kilitlenirdi;
// taskkill onu da kapatır.
procedure QuitRunning(Exe, ImageName: String);
var
  Code: Integer;
begin
  if not ShouldQuitRunning() then Exit;
  if FileExists(Exe) then
  begin
    Exec(Exe, '--quit', '', SW_HIDE, ewNoWait, Code);
    Sleep(2500);
  end;
  Exec(ExpandConstant('{sys}\taskkill.exe'), '/IM ' + ImageName + ' /F', '', SW_HIDE, ewWaitUntilTerminated, Code);
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  QuitRunning(ExpandConstant('{app}\{#AppExe}'), '{#AppExe}');
  if IsOldDirToClean() then
    QuitRunning(AddBackslash(OldAppDir) + '{#OldExe}', '{#OldExe}');   // delta'dan yükseltme: eski delta kapansın
  Result := '';
end;

// delta'nın eski kurulum klasörünü kaldırır. Varsayılan adlı klasör ("delta") tümüyle silinir; kullanıcı başka bir
// klasör seçtiyse yalnızca kurulumun koyduğu dosyalar silinir, klasör boşsa kaldırılır (başka dosyalara dokunulmaz).
procedure CleanOldAppDir();
var
  D: String;
begin
  if not IsOldDirToClean() then Exit;
  D := RemoveBackslashUnlessRoot(OldAppDir);
  if CompareText(ExtractFileName(D), 'delta') = 0 then
    DelTree(D, True, True, True)
  else
  begin
    DeleteFile(D + '\{#OldExe}');
    DeleteFile(D + '\LICENSE.txt');
    DeleteFile(D + '\unins000.exe');
    DeleteFile(D + '\unins000.dat');
    DeleteFile(D + '\unins000.msg');
    DelTree(D + '\_internal', True, True, True);
    RemoveDir(D);
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
    CleanOldAppDir();
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usUninstall then
    QuitRunning(ExpandConstant('{app}\{#AppExe}'), '{#AppExe}');
end;
