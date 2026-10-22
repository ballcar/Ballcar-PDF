"""สร้างไฟล์ข้อมูลเวอร์ชัน/ลิขสิทธิ์ ให้ PyInstaller ฝังลง .exe

ผลลัพธ์: คลิกขวาที่ Ballcar PDF.exe -> Properties -> Details จะเห็นชื่อโปรแกรม
เวอร์ชัน เจ้าของลิขสิทธิ์ ครบ (เดิมว่างเปล่าทั้งหมด)

รันอัตโนมัติจาก build-exe.ps1 ก่อนเรียก PyInstaller
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OWNER = "ballcar"
PRODUCT = "Ballcar PDF"
YEAR = 2026


def main() -> None:
    version = json.loads((ROOT / "version.json").read_text(encoding="utf-8"))["version"]
    parts = [int(x) for x in version.split(".")]
    while len(parts) < 4:
        parts.append(0)
    quad = ", ".join(str(p) for p in parts[:4])

    copyright_text = f"Copyright (c) {YEAR} {OWNER} - MIT License"
    body = f"""# ไฟล์นี้ถูกสร้างอัตโนมัติโดย scripts/make-version-info.py -- อย่าแก้ด้วยมือ
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=({quad}),
    prodvers=({quad}),
    mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable('040E04B0', [
        StringStruct('CompanyName', {OWNER!r}),
        StringStruct('FileDescription', {PRODUCT + ' - โปรแกรมจัดการไฟล์ PDF'!r}),
        StringStruct('FileVersion', {version!r}),
        StringStruct('InternalName', {PRODUCT!r}),
        StringStruct('LegalCopyright', {copyright_text!r}),
        StringStruct('OriginalFilename', {PRODUCT + '.exe'!r}),
        StringStruct('ProductName', {PRODUCT!r}),
        StringStruct('ProductVersion', {version!r}),
      ])
    ]),
    # 0x040E = ไทย, 0x04B0 = Unicode
    VarFileInfo([VarStruct('Translation', [0x040E, 1200])])
  ]
)
"""
    out = ROOT / "version_info.txt"
    out.write_text(body, encoding="utf-8")
    print(f"สร้าง {out.name} (เวอร์ชัน {version} - {copyright_text})")


if __name__ == "__main__":
    sys.exit(main())
