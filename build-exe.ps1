# แพ็กโปรแกรมเป็น .exe ไฟล์เดียว -> dist\Ballcar PDF.exe
Set-Location $PSScriptRoot

# เพิ่มเลขเวอร์ชันก่อน build (1.0.1 -> 1.0.2 -> ... -> 1.0.99 -> 1.1.0)
$version = & .\.venv\Scripts\python.exe bump_version.py
Write-Host "เวอร์ชันใหม่: $version" -ForegroundColor Cyan

& .\.venv\Scripts\python.exe -m PyInstaller `
    --noconfirm --clean `
    --onefile --windowed `
    --name "Ballcar PDF" `
    --icon "logo\Ballcar PDF.ico" `
    --add-data "logo\Ballcar PDF.ico;logo" `
    --add-data "version.json;." `
    --exclude-module PySide6.QtQuick `
    --exclude-module PySide6.QtQml `
    --exclude-module PySide6.Qt3DCore `
    --exclude-module PySide6.QtWebEngineCore `
    --exclude-module PySide6.QtMultimedia `
    --exclude-module tkinter `
    app\main.py

if ($LASTEXITCODE -eq 0) {
    Write-Host "`nเสร็จแล้ว -> dist\Ballcar PDF.exe (เวอร์ชัน $version)" -ForegroundColor Green
}
