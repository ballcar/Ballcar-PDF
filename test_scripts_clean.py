"""ตรวจว่าสคริปต์ .ps1 ทุกไฟล์ใช้งานได้จริง ไม่มีอักขระควบคุมแปลกปน

เคยพลาดมาแล้ว: ตอนสร้าง release.ps1 มีอักขระ backspace (0x08) กับ vertical tab (0x0B)
หลุดเข้าไปในไฟล์ เพราะเขียนไฟล์ผ่านสตริงที่ตีความ \\b (.\\build-exe.ps1) และ
\\v (.\\version.json) เป็นอักขระควบคุม ผลคือ PowerShell อ่านเป็น 'uild-exe.ps1'
กับ '.ersion.json' แล้วรันไม่ผ่านทั้งสคริปต์ — ตาเปล่ามองไม่เห็นเลย
"""
import io
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# อนุญาต: tab (9), LF (10), CR (13) เท่านั้น
ALLOWED = {9, 10, 13}
NAMES = {0x00: "NUL", 0x07: "BEL", 0x08: "BACKSPACE", 0x0B: "VERTICAL TAB",
         0x0C: "FORM FEED", 0x1B: "ESC"}

scripts = sorted(ROOT.glob("*.ps1"))
assert scripts, "ไม่พบไฟล์ .ps1 เลย - ตรวจ path ผิดหรือเปล่า"

problems = []
for path in scripts:
    raw = path.read_bytes()
    found = {}
    for byte in raw:
        if byte < 32 and byte not in ALLOWED:
            found[byte] = found.get(byte, 0) + 1
    if found:
        detail = ", ".join(
            f"{NAMES.get(b, hex(b))} x{n}" for b, n in sorted(found.items()))
        problems.append(f"{path.name}: {detail}")

if problems:
    print("พบอักขระควบคุมในสคริปต์ (สคริปต์จะรันไม่ผ่าน):")
    for line in problems:
        print("   " + line)
    raise AssertionError(
        "สคริปต์ .ps1 มีอักขระควบคุมปน - มักเกิดจากเขียนไฟล์แล้ว \\b \\v \\r "
        "ถูกตีความเป็นอักขระควบคุม ให้เขียนไฟล์แบบ raw string หรือ escape ให้ถูก")

print(f"OK  สคริปต์ .ps1 {len(scripts)} ไฟล์ ไม่มีอักขระควบคุมแปลกปน")

# ---- ต้องมี UTF-8 BOM ----
# Windows PowerShell 5.1 อ่านไฟล์ที่ไม่มี BOM เป็น ANSI (cp874) ภาษาไทยจะเพี้ยน
# จนสตริงหาตัวปิดไม่เจอ -> ทั้งสคริปต์รันไม่ได้เลย (เคยพลาดมาแล้วกับ release.ps1)
BOM = b"\xef\xbb\xbf"
missing_bom = [p.name for p in scripts if not p.read_bytes().startswith(BOM)]
assert not missing_bom, (
    "สคริปต์ต่อไปนี้ไม่มี UTF-8 BOM: " + ", ".join(missing_bom) +
    " - PowerShell 5.1 จะอ่านภาษาไทยเพี้ยนแล้วรันไม่ผ่าน")
print(f"OK  สคริปต์ .ps1 {len(scripts)} ไฟล์ มี UTF-8 BOM ครบ (PowerShell 5.1 อ่านภาษาไทยได้)")

# ---- สคริปต์หลักต้องมีอยู่จริง และอ้างถึงกันได้ถูกต้อง ----
required = ["build-exe.ps1", "build-installer.ps1", "serve-update.ps1", "release.ps1"]
for name in required:
    assert (ROOT / name).exists(), f"ขาดสคริปต์ {name}"
print("OK  สคริปต์หลักครบ " + ", ".join(required))

# release.ps1 ต้องเรียกครบทั้ง 3 ขั้น
release = (ROOT / "release.ps1").read_text(encoding="utf-8-sig")
for name in ["build-exe.ps1", "build-installer.ps1", "serve-update.ps1"]:
    assert name in release, f"release.ps1 ต้องเรียก {name}"
print("OK  release.ps1 เรียกครบทั้ง 3 ขั้น (build -> installer -> ปล่อยอัปเดต)")

# ---- ชื่อไฟล์ที่ทั้งสองฝั่งต้องตรงกัน ----
serve = (ROOT / "serve-update.ps1").read_text(encoding="utf-8-sig")
sys.path.insert(0, str(ROOT))
from app import updater  # noqa: E402

assert "latest.json" in serve, "serve-update.ps1 ต้องเขียนไฟล์ latest.json"
assert "latest.json" in Path(updater.__file__).read_text(encoding="utf-8"), \
    "ฝั่งโปรแกรมต้องอ่าน latest.json ชื่อเดียวกับที่เซิร์ฟเวอร์เขียน"
print("OK  ชื่อไฟล์ latest.json ตรงกันทั้งฝั่งปล่อยและฝั่งโปรแกรม")

print("")
print("ผ่านทั้งหมด")
