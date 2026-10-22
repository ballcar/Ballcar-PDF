# แพ็กโปรแกรมเป็นโฟลเดอร์ (onedir) -> dist\Ballcar PDF\Ballcar PDF.exe
# ใช้ onedir แทน onefile เพราะ onefile ต้องแตก python312.dll ลง %TEMP% ทุกครั้งที่เปิด
# บนเครื่องลูกมักโดนแอนตี้ไวรัสลบ/ล็อก dll ระหว่างแตก -> "Failed to load Python DLL"
# onedir ติดตั้งไฟล์ลงเครื่องจริง ไม่ต้องแตก temp -> เสถียรกว่าและเปิดเร็วกว่า
Set-Location $PSScriptRoot

# เพิ่มเลขเวอร์ชันก่อน build (1.0.1 -> 1.0.2 -> ... -> 1.0.99 -> 1.1.0)
$version = & .\.venv\Scripts\python.exe bump_version.py
Write-Host "เวอร์ชันใหม่: $version" -ForegroundColor Cyan

# รูป QR สนับสนุน (ไม่มีไฟล์ก็ข้ามไป โปรแกรมจะไม่แสดงรูปแต่ยังใช้งานได้)
$qrArgs = @()
# ลำดับต้องตรงกับ QR_CANDIDATES ใน app\main.py (ไม่งั้นแพ็กคนละรูปกับที่โปรแกรมมองหา)
$qrFiles = @("qr_code\promptpay2.png", "qr_code\promptpay.png", "qr_code\promptpay.jpg",
             "logo\promptpay.png", "logo\promptpay.jpg")
foreach ($q in $qrFiles) {
    if (Test-Path ".\$q") {
        $folder = Split-Path $q -Parent
        $qrArgs = @("--add-data", "$q;$folder")
        Write-Host "ใส่รูป QR สนับสนุน: $q" -ForegroundColor Green
        break
    }
}
if (-not $qrArgs) { Write-Host "ไม่พบรูป QR - หน้าต่างเกี่ยวกับจะไม่แสดงรูป" -ForegroundColor Yellow }

# ฝังข้อมูลลิขสิทธิ์/เวอร์ชันลงไฟล์ .exe (คลิกขวา -> Properties -> Details จะเห็น)
& .\.venv\Scripts\python.exe scripts\make-version-info.py

& .\.venv\Scripts\python.exe -m PyInstaller `
    --noconfirm --clean `
    --onedir --windowed `
    --name "Ballcar PDF" `
    --icon "logo\Ballcar PDF.ico" `
    --version-file "version_info.txt" `
    --splash "logo\splash.png" `
    --add-data "logo\Ballcar PDF.ico;logo" `
    --add-data "version.json;." `
    --add-data "tessdata;tessdata" `
    @qrArgs `
    --exclude-module PySide6.QtQuick `
    --exclude-module PySide6.QtQml `
    --exclude-module PySide6.Qt3DCore `
    --exclude-module PySide6.QtWebEngineCore `
    --exclude-module PySide6.QtMultimedia `
    --exclude-module tkinter `
    app\main.py

if ($LASTEXITCODE -eq 0) {
    Write-Host "`nเสร็จแล้ว -> dist\Ballcar PDF\Ballcar PDF.exe (เวอร์ชัน $version)" -ForegroundColor Green
}
