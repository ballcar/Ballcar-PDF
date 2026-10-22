# ติดตั้ง Ballcar PDF แบบ per-user (ไม่ต้องสิทธิ์แอดมิน ยกเว้นตอนลง Tesseract)
$ErrorActionPreference = "Stop"
$ProgId  = "BallcarPDF.Document"
$AppName = "Ballcar PDF"
$here    = Split-Path -Parent $MyInvocation.MyCommand.Path
$srcExe  = Join-Path $here "Ballcar PDF.exe"

Write-Host "=== ติดตั้ง Ballcar PDF ===" -ForegroundColor Cyan

if (-not (Test-Path $srcExe)) {
    Write-Host "ไม่พบไฟล์ 'Ballcar PDF.exe' ในโฟลเดอร์นี้" -ForegroundColor Red
    exit 1
}

# 1) ก๊อป .exe ไปโฟลเดอร์ถาวร
$target = Join-Path $env:LOCALAPPDATA "Programs\Ballcar PDF"
New-Item -ItemType Directory -Force -Path $target | Out-Null
$exe = Join-Path $target "Ballcar PDF.exe"
Copy-Item $srcExe $exe -Force
Write-Host "ก๊อปโปรแกรมไปที่: $target" -ForegroundColor Green

# 2) ลงทะเบียน ProgID + ไอคอน + คำสั่งเปิด (HKCU)
$cls = "HKCU:\Software\Classes"
New-Item -Force -Path "$cls\$ProgId" | Out-Null
Set-ItemProperty -Path "$cls\$ProgId" -Name "(default)" -Value "เอกสาร PDF (Ballcar PDF)"
New-Item -Force -Path "$cls\$ProgId\DefaultIcon" | Out-Null
Set-ItemProperty -Path "$cls\$ProgId\DefaultIcon" -Name "(default)" -Value "$exe,0"
New-Item -Force -Path "$cls\$ProgId\shell\open\command" | Out-Null
Set-ItemProperty -Path "$cls\$ProgId\shell\open\command" -Name "(default)" -Value "`"$exe`" `"%1`""

# 3) ทำให้โผล่ในรายการ "Open with" ของ .pdf
New-Item -Force -Path "$cls\.pdf\OpenWithProgids" | Out-Null
Set-ItemProperty -Path "$cls\.pdf\OpenWithProgids" -Name $ProgId -Value ([byte[]]@()) -Type Binary

# 4) รายการแอปใน "Open with" (Applications)
$appKey = "$cls\Applications\Ballcar PDF.exe"
New-Item -Force -Path "$appKey\shell\open\command" | Out-Null
Set-ItemProperty -Path "$appKey\shell\open\command" -Name "(default)" -Value "`"$exe`" `"%1`""
Set-ItemProperty -Path $appKey -Name "FriendlyAppName" -Value $AppName
New-Item -Force -Path "$appKey\SupportedTypes" | Out-Null
Set-ItemProperty -Path "$appKey\SupportedTypes" -Name ".pdf" -Value ""
Write-Host "ลงทะเบียนโปรแกรมกับไฟล์ .pdf แล้ว" -ForegroundColor Green

# 5) สร้าง shortcut (Start Menu + Desktop)
$sh = New-Object -ComObject WScript.Shell
foreach ($lnkPath in @(
    (Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\Ballcar PDF.lnk"),
    (Join-Path ([Environment]::GetFolderPath('Desktop')) "Ballcar PDF.lnk")
)) {
    $lnk = $sh.CreateShortcut($lnkPath)
    $lnk.TargetPath = $exe
    $lnk.IconLocation = "$exe,0"
    $lnk.WorkingDirectory = $target
    $lnk.Description = "โปรแกรมจัดการ PDF Ballcar PDF"
    $lnk.Save()
}
Write-Host "สร้าง shortcut ที่ Start Menu และ Desktop แล้ว" -ForegroundColor Green

# 6) แจ้ง Windows ว่า association เปลี่ยน
Add-Type -Namespace Win32 -Name Shell -MemberDefinition @'
[System.Runtime.InteropServices.DllImport("shell32.dll")]
public static extern void SHChangeNotify(int eventId, uint flags, IntPtr item1, IntPtr item2);
'@
[Win32.Shell]::SHChangeNotify(0x08000000, 0, [IntPtr]::Zero, [IntPtr]::Zero)

# 7) ลง Tesseract (OCR) + ภาษาไทย
$tess = "C:\Program Files\Tesseract-OCR\tesseract.exe"
if (Test-Path $tess) {
    Write-Host "พบ Tesseract อยู่แล้ว ข้ามการติดตั้ง" -ForegroundColor Green
} else {
    Write-Host "`nกำลังลง Tesseract (OCR) — จะมีหน้าต่าง UAC เด้ง กด Yes ได้เลย..." -ForegroundColor Yellow
    try {
        winget install -e --id UB-Mannheim.TesseractOCR --accept-source-agreements --accept-package-agreements
    } catch {
        Write-Host "ลง Tesseract ไม่สำเร็จ (ข้าม OCR ไปก่อนได้ ค่อยลงทีหลัง)" -ForegroundColor Yellow
    }
}
$tha = "C:\Program Files\Tesseract-OCR\tessdata\tha.traineddata"
if ((Test-Path (Split-Path $tha)) -and -not (Test-Path $tha)) {
    Write-Host "ดาวน์โหลดชุดภาษาไทยสำหรับ OCR..." -ForegroundColor Yellow
    try {
        Invoke-WebRequest -UseBasicParsing `
            -Uri "https://github.com/tesseract-ocr/tessdata/raw/main/tha.traineddata" `
            -OutFile $tha
        Write-Host "ลงชุดภาษาไทยแล้ว" -ForegroundColor Green
    } catch {
        Write-Host "ดาวน์โหลดภาษาไทยไม่สำเร็จ (OCR ไทยจะยังไม่ได้ ค่อยลงทีหลัง)" -ForegroundColor Yellow
    }
}

Write-Host "`n=====================================================" -ForegroundColor Cyan
Write-Host " ติดตั้งเสร็จแล้ว!" -ForegroundColor Green
Write-Host " เหลืออีกขั้นเดียว — ตั้งให้เป็นโปรแกรมเปิด PDF หลัก:" -ForegroundColor Cyan
Write-Host "   1) คลิกขวาที่ไฟล์ PDF ไฟล์ไหนก็ได้"
Write-Host "   2) เลือก 'เปิดด้วย (Open with)' > 'เลือกแอปอื่น (Choose another app)'"
Write-Host "   3) เลือก 'Ballcar PDF' แล้วติ๊ก 'ใช้เสมอ (Always)'"
Write-Host "   (อ่านละเอียดใน วิธีใช้.txt)" -ForegroundColor Gray
Write-Host "=====================================================" -ForegroundColor Cyan
