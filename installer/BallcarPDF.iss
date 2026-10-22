; Inno Setup script — สร้าง Ballcar PDF Installer.exe (ติดตั้งแบบ per-user ไม่ต้องแอดมิน)
#define AppName "Ballcar PDF"
; เวอร์ชันส่งมาจาก build-installer.ps1 (/DAppVersion=x.y.z) — ถ้าไม่ส่งใช้ค่าสำรอง
#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
#define AppExe "Ballcar PDF.exe"
#define ProgId "BallcarPDF.Document"

[Setup]
AppId={{B7A1C3E2-9F4D-4A6B-8C10-BALLCARPDF01}}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=ballcar
AppCopyright=Copyright (c) 2026 ballcar - MIT License
DefaultDirName={localappdata}\Programs\{#AppName}
DisableProgramGroupPage=yes
DisableDirPage=yes
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=Ballcar PDF Installer
SetupIconFile=..\logo\Ballcar PDF.ico
UninstallDisplayIcon={app}\{#AppExe}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
; ถ้าโปรแกรมเปิดค้างอยู่ตอนอัปเดต ให้ตรวจเจอและปิดให้ (ไม่งั้นไฟล์ถูกล็อก ติดตั้งล้มเหลว)
CloseApplications=force
CloseApplicationsFilter=*.exe
RestartApplications=no
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "thai"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "สร้างไอคอนบนหน้าจอ (Desktop)"; GroupDescription: "ทางลัด:"
; ไม่มีตัวเลือกติดตั้ง OCR แล้ว — ไฟล์ภาษาไทย/อังกฤษถูกติดตั้งมาพร้อมโปรแกรม
; ใช้ OCR ได้ทันทีแม้เครื่องออกอินเทอร์เน็ตไม่ได้ และไม่ต้องมี UAC เด้ง

[Files]
; onedir: แพ็กทั้งโฟลเดอร์ (exe + _internal\python312.dll ฯลฯ) ลงเครื่อง
Source: "..\dist\Ballcar PDF\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Registry]
; ProgID + ไอคอน + คำสั่งเปิด
Root: HKCU; Subkey: "Software\Classes\{#ProgId}"; ValueType: string; ValueName: ""; ValueData: "เอกสาร PDF (Ballcar PDF)"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\{#ProgId}\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\{#AppExe},0"
Root: HKCU; Subkey: "Software\Classes\{#ProgId}\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExe}"" ""%1"""
; ทำให้โผล่ในรายการ "Open with" ของ .pdf
Root: HKCU; Subkey: "Software\Classes\.pdf\OpenWithProgids"; ValueType: string; ValueName: "{#ProgId}"; ValueData: ""; Flags: uninsdeletevalue
; รายการแอปใน Open with
Root: HKCU; Subkey: "Software\Classes\Applications\{#AppExe}\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExe}"" ""%1"""; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\Applications\{#AppExe}"; ValueType: string; ValueName: "FriendlyAppName"; ValueData: "{#AppName}"
Root: HKCU; Subkey: "Software\Classes\Applications\{#AppExe}\SupportedTypes"; ValueType: string; ValueName: ".pdf"; ValueData: ""
; ---- คลิกขวาไฟล์ PDF (เลือกหลายไฟล์ได้) -> "รวมไฟล์ด้วย Ballcar PDF" ----
; MultiSelectModel=Document = Windows เรียกโปรแกรมทีละไฟล์ (Player ส่งมาแค่ไฟล์แรก)
; ตัวแรกเป็น "ตัวรวบ" ตัวที่เหลือส่งชื่อไฟล์ไปให้แล้วปิดตัวเอง -> เห็นหน้าต่างเดียว
Root: HKCU; Subkey: "Software\Classes\SystemFileAssociations\.pdf\shell\BallcarPDFCombine"; ValueType: string; ValueName: ""; ValueData: "รวมไฟล์ด้วย Ballcar PDF"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\SystemFileAssociations\.pdf\shell\BallcarPDFCombine"; ValueType: string; ValueName: "Icon"; ValueData: "{app}\{#AppExe},0"
Root: HKCU; Subkey: "Software\Classes\SystemFileAssociations\.pdf\shell\BallcarPDFCombine"; ValueType: string; ValueName: "MultiSelectModel"; ValueData: "Document"
Root: HKCU; Subkey: "Software\Classes\SystemFileAssociations\.pdf\shell\BallcarPDFCombine\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExe}"" --combine ""%1"""
; ---- คลิกขวา -> "เปิดด้วย Ballcar PDF" (เปิดไฟล์เดียว ไม่ต้องตั้ง default) ----
Root: HKCU; Subkey: "Software\Classes\SystemFileAssociations\.pdf\shell\BallcarPDFOpen"; ValueType: string; ValueName: ""; ValueData: "เปิดด้วย Ballcar PDF"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\SystemFileAssociations\.pdf\shell\BallcarPDFOpen"; ValueType: string; ValueName: "Icon"; ValueData: "{app}\{#AppExe},0"
Root: HKCU; Subkey: "Software\Classes\SystemFileAssociations\.pdf\shell\BallcarPDFOpen\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExe}"" ""%1"""

[Run]
; เปิดโปรแกรมหลังติดตั้งเสร็จ (ถ้าผู้ใช้ติ๊ก)
Filename: "{app}\{#AppExe}"; Description: "เปิด Ballcar PDF เลย"; Flags: nowait postinstall skipifsilent

[Messages]
thai.WelcomeLabel2=โปรแกรมจะติดตั้ง [name] ลงในเครื่องของคุณ%n%n(ติดตั้งแบบส่วนตัว ไม่ต้องใช้สิทธิ์ผู้ดูแล)%n%nหลังติดตั้งเสร็จ ให้คลิกขวาไฟล์ PDF แล้วเลือก "เปิดด้วย > Ballcar PDF > ใช้เสมอ" เพื่อตั้งเป็นโปรแกรมเปิด PDF หลัก
