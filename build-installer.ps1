# สร้างตัวติดตั้ง Ballcar PDF Installer.exe (ดึงเลขเวอร์ชันจาก version.json อัตโนมัติ)
# -Fast = ตัวทดสอบ: บีบอัดแบบเร็ว (~25 วินาที แทน ~3.5 นาที แต่ไฟล์ใหญ่ขึ้น ~30 MB)
#         ตัวจริงที่ส่งเครื่องลูก (release.ps1) ไม่ใส่ -Fast -> บีบอัดสูงสุดเหมือนเดิม
param([switch]$Fast)
Set-Location $PSScriptRoot

$exe = ".\dist\Ballcar PDF\Ballcar PDF.exe"
if (-not (Test-Path $exe)) {
    Write-Host "ยังไม่มีโฟลเดอร์ build — รัน .\build-exe.ps1 ก่อน" -ForegroundColor Red
    exit 1
}

$version = (Get-Content ".\version.json" -Raw | ConvertFrom-Json).version
Write-Host "เวอร์ชัน: $version" -ForegroundColor Cyan

$iscc = "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
if (-not (Test-Path $iscc)) {
    $iscc = (Get-ChildItem "C:\Program Files (x86)\Inno Setup*\ISCC.exe","C:\Program Files\Inno Setup*\ISCC.exe" -ErrorAction SilentlyContinue | Select-Object -First 1).FullName
}
if (-not $iscc -or -not (Test-Path $iscc)) {
    Write-Host "ไม่พบ Inno Setup (ISCC.exe) — ลงด้วย: winget install -e --id JRSoftware.InnoSetup" -ForegroundColor Red
    exit 1
}

$compress = if ($Fast) { "lzma2/fast" } else { "lzma2/max" }
Write-Host "บีบอัด: $compress" -ForegroundColor Cyan
& $iscc "/DAppVersion=$version" "/DCompress=$compress" ".\installer\BallcarPDF.iss"
if ($LASTEXITCODE -ne 0) {
    Write-Host "compile ไม่สำเร็จ" -ForegroundColor Red
    exit 1
}

$out = ".\dist\Ballcar PDF Installer.exe"

# เก็บสำเนาทุกเวอร์ชันไว้เปรียบเทียบ — ไม่ลบของเก่าเด็ดขาด
# (ไฟล์ชื่อกลาง "Ballcar PDF Installer.exe" ถูกเขียนทับทุกครั้งที่ build
#  ถ้าไม่เก็บสำเนาแยกชื่อตามเวอร์ชัน เวอร์ชันเก่าจะหายไปเงียบๆ)
$archive = ".\dist\release"
New-Item -ItemType Directory -Force -Path $archive | Out-Null
$keep = Join-Path $archive "Ballcar PDF Installer - $version.exe"
if (Test-Path $keep) {
    Write-Host "มี $version ในคลังอยู่แล้ว — ไม่เขียนทับ" -ForegroundColor Yellow
} else {
    Copy-Item $out $keep
    Write-Host "เก็บเข้าคลัง -> $keep" -ForegroundColor Green
}

Write-Host "`nเสร็จแล้ว -> $out (เวอร์ชัน $version)" -ForegroundColor Green
Get-ChildItem $out | Select-Object Name, @{n="MB";e={[math]::Round($_.Length/1MB)}}, LastWriteTime

Write-Host "`nคลังเวอร์ชันที่เก็บไว้ (dist\release):" -ForegroundColor Cyan
Get-ChildItem $archive -Filter "*.exe" | Sort-Object Name |
    ForEach-Object { "   {0,-45} {1,4} MB" -f $_.Name, [math]::Round($_.Length/1MB) }
