# ปล่อยอัปเดต Ballcar PDF ผ่าน HTTP บนเครื่องนี้ (เครื่องพี่)
# วิธีใช้: build installer ล่าสุดก่อน (.\build-installer.ps1) แล้วรันสคริปต์นี้
#   เครื่องลูกตั้งที่อยู่เซิร์ฟเวอร์เป็น http://<ip เครื่องนี้>:8000
#
# หมายเหตุ: ใช้โฟลเดอร์ปล่อยอัปเดต "ร่วมกัน" กับ Ballcar Diagram
# เพราะทั้งสองโปรแกรมใช้พอร์ต 8000 เหมือนกัน ถ้าต่างคนต่างเปิดเซิร์ฟเวอร์จะแย่งพอร์ตกัน
# แล้วเครื่องลูกได้ของผิดตัว (PDF ขอ /latest.json แต่ได้ 404 จากเซิร์ฟเวอร์ของ Diagram)
# ชื่อไฟล์สองโปรแกรมไม่ชนกัน (PDF=latest.json, Diagram=latest.yml) จึงวางรวมโฟลเดอร์เดียวได้
Set-Location $PSScriptRoot

$port = 8000
$installer = ".\dist\Ballcar PDF Installer.exe"
if (-not (Test-Path $installer)) {
    Write-Host "ยังไม่มี installer — รัน .\build-installer.ps1 ก่อน" -ForegroundColor Red
    exit 1
}

# โฟลเดอร์ปล่อยอัปเดตร่วม (ใช้ร่วมกับ Ballcar Diagram) -> D:\Project\_update-server
$pub = Join-Path (Split-Path $PSScriptRoot -Parent) '_update-server'
New-Item -ItemType Directory -Force -Path $pub | Out-Null

# เวอร์ชันที่ประกาศ ต้องมาจาก "ไฟล์จริงที่จะแจก" ไม่ใช่จาก version.json
# เพราะ build-exe.ps1 เพิ่มเลขเวอร์ชันตั้งแต่ก่อนเริ่ม build ถ้า build ไม่จบ
# version.json จะเดินไปข้างหน้าโดยไม่มีไฟล์จริงรองรับ แล้วเราจะประกาศเวอร์ชันลอยๆ
# ผลคือเครื่องลูกโหลดมาติดตั้งแล้วได้ของเก่า -> เด้งถามอัปเดตวนไม่รู้จบ
$builtExe = ".\dist\Ballcar PDF\Ballcar PDF.exe"
if (-not (Test-Path $builtExe)) {
    Write-Host "ไม่พบโปรแกรมที่ build ไว้ - รัน .\build-exe.ps1 ก่อน" -ForegroundColor Red
    exit 1
}
$version = (Get-Item $builtExe).VersionInfo.FileVersion.Trim()
$declared = (Get-Content ".\version.json" -Raw | ConvertFrom-Json).version

if ($version -ne $declared) {
    Write-Host ""
    Write-Host "  หยุด - เวอร์ชันไม่ตรงกัน ยังไม่ปล่อยอะไรขึ้นเซิร์ฟเวอร์" -ForegroundColor Red
    Write-Host "    version.json บอกว่า : $declared" -ForegroundColor Yellow
    Write-Host "    แต่ไฟล์ที่ build ไว้ : $version" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "  แปลว่า build รอบล่าสุดไม่จบ (เลขเวอร์ชันเดินไปแล้วแต่ไม่มีไฟล์จริง)" -ForegroundColor Yellow
    Write-Host "  ถ้าปล่อยไป เครื่องลูกจะโหลดมาติดตั้งแล้วได้ของเก่า เด้งถามอัปเดตวนไม่จบ" -ForegroundColor Yellow
    Write-Host "  วิธีแก้: รัน .\release.ps1 ใหม่ให้ build จบก่อน" -ForegroundColor Cyan
    exit 1
}

# ตัวติดตั้งต้องใหม่กว่าโปรแกรมที่ build เสมอ ไม่งั้นแปลว่าห่อของเก่าอยู่
if ((Get-Item $installer).LastWriteTime -lt (Get-Item $builtExe).LastWriteTime) {
    Write-Host ""
    Write-Host "  หยุด - ตัวติดตั้งเก่ากว่าโปรแกรมที่ build ไว้" -ForegroundColor Red
    Write-Host "  แปลว่ายังไม่ได้สร้างตัวติดตั้งใหม่ - รัน .\build-installer.ps1 ก่อน" -ForegroundColor Yellow
    exit 1
}

Copy-Item $installer $pub -Force
$latest = [ordered]@{
    version = $version
    file    = "Ballcar PDF Installer.exe"
    notes   = "เวอร์ชัน $version"
}
# เขียนแบบ UTF-8 ไม่มี BOM (BOM ทำให้ json.loads ฝั่งโปรแกรมพัง -> มองว่าต่อไม่ได้)
[System.IO.File]::WriteAllText("$pub\latest.json", ($latest | ConvertTo-Json), (New-Object System.Text.UTF8Encoding($false)))
Write-Host "ปล่อยเวอร์ชัน $version" -ForegroundColor Green

# หา IP วง LAN ของเครื่องนี้ (โชว์ให้ตั้งที่เครื่องลูก)
$ips = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
    Where-Object { $_.IPAddress -notlike "127.*" -and $_.IPAddress -notlike "169.254.*" }
Write-Host "`nที่เครื่องลูก ตั้งค่าเซิร์ฟเวอร์อัปเดตเป็น:" -ForegroundColor Cyan
foreach ($ip in $ips) { Write-Host "    http://$($ip.IPAddress):$port" -ForegroundColor Yellow }

# เปิด firewall ขาเข้าพอร์ตนี้ (ครั้งแรกอาจต้องสิทธิ์แอดมิน)
$ruleName = "Ballcar PDF Update ($port)"
if (-not (Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue)) {
    try {
        New-NetFirewallRule -DisplayName $ruleName -Direction Inbound -Action Allow `
            -Protocol TCP -LocalPort $port -ErrorAction Stop | Out-Null
        Write-Host "เปิด firewall พอร์ต $port แล้ว" -ForegroundColor Green
    } catch {
        Write-Host "เปิด firewall ไม่ได้ (ลองรัน PowerShell แบบ Run as administrator)" -ForegroundColor Yellow
    }
}

# มีเซิร์ฟเวอร์รันอยู่แล้วไหม (เช่นของ Ballcar Diagram ที่เปิดเองตอน logon)
# ถ้ามี ไม่ต้องเปิดซ้ำให้แย่งพอร์ตกัน - แค่วางไฟล์ลงโฟลเดอร์ร่วมก็พอ
$busy = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
if ($busy) {
    $owner = Get-Process -Id $busy.OwningProcess -ErrorAction SilentlyContinue
    # ยิงถามเซิร์ฟเวอร์จริงว่าตอนนี้ปล่อยเวอร์ชันอะไร - จะได้รู้แน่ว่าสำเร็จหรือไม่
    $served = ""
    try {
        $r = Invoke-RestMethod -Uri "http://localhost:$port/latest.json" -TimeoutSec 5
        $served = "$($r.version)"
    } catch { }

    if ($served -eq $version) {
        Write-Host ""
        Write-Host "  +---------------------------------------------+" -ForegroundColor Green
        Write-Host "  |  ปล่อยอัปเดตสำเร็จแล้ว - เครื่องลูกกดอัปเดตได้เลย  |" -ForegroundColor Green
        Write-Host "  +---------------------------------------------+" -ForegroundColor Green
        Write-Host "  เวอร์ชันที่เซิร์ฟเวอร์ปล่อยอยู่: $served" -ForegroundColor Green
        Write-Host "  (ใช้เซิร์ฟเวอร์ตัวที่เปิดค้างไว้อยู่แล้ว PID $($busy.OwningProcess) - ไม่ต้องเปิดซ้ำ)" -ForegroundColor DarkGray
        exit 0
    }

    Write-Host "`n  ยังไม่สำเร็จ - เซิร์ฟเวอร์บนพอร์ต $port ตอบว่าเวอร์ชัน '$served' (ควรเป็น $version)" -ForegroundColor Red
    Write-Host "  แปลว่ามีเซิร์ฟเวอร์ตัวอื่นเสิร์ฟคนละโฟลเดอร์อยู่ (PID $($busy.OwningProcess) $($owner.ProcessName))" -ForegroundColor Yellow
    Write-Host "  วิธีแก้: ปิดตัวนั้นก่อน  ->  Stop-Process -Id $($busy.OwningProcess) -Force" -ForegroundColor Yellow
    Write-Host "  แล้วรัน .\serve-update.ps1 ใหม่อีกครั้ง" -ForegroundColor Yellow
    exit 1
}

Write-Host "`nกำลังปล่อยอัปเดต... (กด Ctrl+C เพื่อหยุด)" -ForegroundColor Cyan
& .\.venv\Scripts\python.exe -m http.server $port --directory $pub
