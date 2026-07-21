@echo off
rem Ballcar PDF - เปิดจากซอร์สโค้ด (ตัวติดตั้งจริงคือ dist\Ballcar PDF.exe)
cd /d "%~dp0"
start "" ".venv\Scripts\pythonw.exe" -m app.main
