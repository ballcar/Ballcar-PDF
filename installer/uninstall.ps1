# ถอนการติดตั้ง Ballcar PDF (ย้อนกลับทุกอย่างที่ install.ps1 ทำ)
# ไม่ลบ Tesseract (ใช้ร่วมกับโปรแกรมอื่น) และไม่ลบข้อมูลผู้ใช้ %APPDATA%\BallcarPDF
$ProgId = "BallcarPDF.Document"
$cls = "HKCU:\Software\Classes"

Write-Host "=== ถอนการติดตั้ง Ballcar PDF ===" -ForegroundColor Cyan

# ลบ shortcut
foreach ($lnk in @(
    (Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\Ballcar PDF.lnk"),
    (Join-Path ([Environment]::GetFolderPath('Desktop')) "Ballcar PDF.lnk")
)) {
    if (Test-Path $lnk) { Remove-Item $lnk -Force }
}

# ลบ ProgID / Applications / รายการใน OpenWithProgids
Remove-Item -Recurse -Force "$cls\$ProgId" -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force "$cls\Applications\Ballcar PDF.exe" -ErrorAction SilentlyContinue
Remove-ItemProperty -Path "$cls\.pdf\OpenWithProgids" -Name $ProgId -ErrorAction SilentlyContinue

# ลบโฟลเดอร์โปรแกรม
$target = Join-Path $env:LOCALAPPDATA "Programs\Ballcar PDF"
if (Test-Path $target) { Remove-Item -Recurse -Force $target -ErrorAction SilentlyContinue }

# แจ้ง Windows
Add-Type -Namespace Win32 -Name Shell -MemberDefinition @'
[System.Runtime.InteropServices.DllImport("shell32.dll")]
public static extern void SHChangeNotify(int eventId, uint flags, IntPtr item1, IntPtr item2);
'@
[Win32.Shell]::SHChangeNotify(0x08000000, 0, [IntPtr]::Zero, [IntPtr]::Zero)

Write-Host "ถอนการติดตั้งเสร็จแล้ว" -ForegroundColor Green
Write-Host "(Tesseract และไฟล์ตั้งค่า/ลายเซ็นของคุณยังอยู่ ถ้าต้องการลบเพิ่มเอง)" -ForegroundColor Gray
