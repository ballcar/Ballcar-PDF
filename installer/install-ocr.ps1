# ลง Tesseract + ภาษาไทย (เรียกจาก installer เมื่อผู้ใช้ติ๊กเลือก OCR)
$tess = "C:\Program Files\Tesseract-OCR\tesseract.exe"
if (-not (Test-Path $tess)) {
    try {
        winget install -e --id UB-Mannheim.TesseractOCR --accept-source-agreements --accept-package-agreements
    } catch {}
}
$tha = "C:\Program Files\Tesseract-OCR\tessdata\tha.traineddata"
if ((Test-Path (Split-Path $tha)) -and -not (Test-Path $tha)) {
    try {
        Invoke-WebRequest -UseBasicParsing `
            -Uri "https://github.com/tesseract-ocr/tessdata/raw/main/tha.traineddata" `
            -OutFile $tha
    } catch {}
}
