# ออกเวอร์ชันใหม่ของ Ballcar PDF แบบครบจบในคำสั่งเดียว
#   1) build โปรแกรม (เพิ่มเลขเวอร์ชันให้อัตโนมัติ)
#   2) สร้างตัวติดตั้ง + เก็บเข้าคลัง dist\release (ไม่ลบของเก่า)
#   3) ปล่อยขึ้นเซิร์ฟเวอร์อัปเดต แล้วยืนยันว่าเครื่องลูกเห็นเวอร์ชันใหม่จริง
#
# วิธีใช้:  cd D:\Project\PDF  แล้วรัน  .\release.ps1
#
# หมายเหตุ: เครื่องนี้เสิร์ฟไฟล์อัปเดตจากโฟลเดอร์รวม D:\Project\_update-server
# ซึ่งมีทั้ง Ballcar PDF (latest.json) และ Ballcar Diagram (latest.yml) อยู่ด้วยกัน
# เซิร์ฟเวอร์เปิดค้างไว้อยู่แล้ว สคริปต์นี้จึงแค่วางไฟล์ลงไป ไม่ไปแย่งพอร์ตกับใคร

Set-Location $PSScriptRoot
$ErrorActionPreference = 'Stop'

function Step($n, $text) {
    Write-Host ""
    Write-Host "===== [$n/3] $text =====" -ForegroundColor Cyan
}

function Fail($text) {
    Write-Host ""
    Write-Host "  $text" -ForegroundColor Red
    Write-Host "  หยุดไว้ก่อน - ยังไม่ได้ปล่อยอะไรขึ้นเซิร์ฟเวอร์" -ForegroundColor Red
    exit 1
}

Step 1 "build โปรแกรม"
& (Join-Path $PSScriptRoot 'build-exe.ps1')
if ($LASTEXITCODE -ne 0) { Fail "build โปรแกรมไม่ผ่าน" }

Step 2 "สร้างตัวติดตั้ง"
& (Join-Path $PSScriptRoot 'build-installer.ps1')
if ($LASTEXITCODE -ne 0) { Fail "สร้างตัวติดตั้งไม่ผ่าน" }

Step 3 "ปล่อยขึ้นเซิร์ฟเวอร์อัปเดต"
& (Join-Path $PSScriptRoot 'serve-update.ps1')
if ($LASTEXITCODE -ne 0) { Fail "ปล่อยอัปเดตไม่สำเร็จ - ดูวิธีแก้ด้านบน" }

$versionFile = Join-Path $PSScriptRoot 'version.json'
$version = (Get-Content $versionFile -Raw | ConvertFrom-Json).version

Write-Host ""
Write-Host "เรียบร้อย! Ballcar PDF $version พร้อมให้เครื่องลูกกดอัปเดตแล้ว" -ForegroundColor Green
Write-Host "ไฟล์ติดตั้งเก็บไว้ที่: dist\release\Ballcar PDF Installer - $version.exe" -ForegroundColor DarkGray
