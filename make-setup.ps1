# ประกอบชุดติดตั้ง -> dist\Ballcar PDF Setup\  (พร้อมก๊อปใส่ USB ไปเครื่องอื่น)
Set-Location $PSScriptRoot

$exe = ".\dist\Ballcar PDF.exe"
if (-not (Test-Path $exe)) {
    Write-Host "ยังไม่มี .exe — รัน .\build-exe.ps1 ก่อน" -ForegroundColor Red
    exit 1
}

$pkg = ".\dist\Ballcar PDF Setup"
if (Test-Path $pkg) { Remove-Item -Recurse -Force $pkg }
New-Item -ItemType Directory -Force -Path $pkg | Out-Null

Copy-Item $exe $pkg -Force
Copy-Item ".\installer\*" $pkg -Force

Write-Host "สร้างชุดติดตั้งแล้ว -> $pkg" -ForegroundColor Green
Get-ChildItem $pkg | Select-Object Name, @{n="MB";e={[math]::Round($_.Length/1MB,1)}}
