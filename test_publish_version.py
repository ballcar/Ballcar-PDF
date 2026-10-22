"""กันเคส "ป้ายเวอร์ชันไม่ตรงกับไฟล์จริง" ที่ทำให้เครื่องลูกอัปเดตวนไม่จบ

เคยเกิดจริง: เซิร์ฟเวอร์ประกาศ 1.0.72 แต่ไฟล์ติดตั้งที่แจกเป็นตัว 1.0.71
เครื่องลูกจึงโหลดมาติดตั้งแล้วได้ของเก่า เปิดโปรแกรมมาก็ยัง 1.0.71 แล้วเด้งถามอัปเดตอีก
วนแบบนี้ไม่รู้จบ

ต้นเหตุ: build-exe.ps1 เพิ่มเลขเวอร์ชันใน version.json ตั้งแต่ "ก่อน" เริ่ม build
ถ้า build ไม่จบ (พัง/ถูกกด Ctrl+C) เลขจะเดินไปข้างหน้าโดยไม่มีไฟล์จริงรองรับ
แล้ว serve-update.ps1 ไปอ่านเวอร์ชันจาก version.json จึงประกาศเวอร์ชันลอยๆ ออกไป

ทางแก้: serve-update.ps1 ต้องอ่านเวอร์ชันจากไฟล์ .exe ที่ build ไว้จริง
และต้องหยุดถ้าไม่ตรงกับ version.json
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
serve = (ROOT / "serve-update.ps1").read_text(encoding="utf-8-sig")

# ---- ต้องอ่านเวอร์ชันจากไฟล์ที่ build จริง ----
assert "VersionInfo.FileVersion" in serve, (
    "serve-update.ps1 ต้องอ่านเวอร์ชันจาก .exe ที่ build ไว้จริง "
    "(VersionInfo.FileVersion) ไม่ใช่เชื่อ version.json อย่างเดียว")
print("OK  อ่านเวอร์ชันจากไฟล์ .exe ตัวจริงที่จะแจก")

# ---- ต้องมีการเทียบกับ version.json แล้วหยุดถ้าไม่ตรง ----
assert re.search(r"\$version\s+-ne\s+\$declared", serve), \
    "ต้องเทียบเวอร์ชันของไฟล์จริงกับ version.json"
mismatch = serve[serve.index("-ne $declared"):]
assert "exit 1" in mismatch.split("}")[0] + "exit 1" or "exit 1" in mismatch[:1200], \
    "ถ้าเวอร์ชันไม่ตรงกัน ต้อง exit 1 (ห้ามปล่อยขึ้นเซิร์ฟเวอร์)"
print("OK  เวอร์ชันไม่ตรงกับ version.json -> หยุด ไม่ปล่อยขึ้นเซิร์ฟเวอร์")

# ---- ต้องกันเคสห่อตัวติดตั้งจากของเก่า ----
assert "LastWriteTime" in serve, \
    "ต้องตรวจว่าตัวติดตั้งใหม่กว่าโปรแกรมที่ build ไว้ (กันการห่อของเก่า)"
print("OK  ตัวติดตั้งเก่ากว่าโปรแกรมที่ build -> หยุด (กันห่อของเก่า)")

# ---- ต้องคัดลอกไฟล์ "หลัง" ตรวจผ่านแล้วเท่านั้น ----
copy_at = serve.index("Copy-Item $installer $pub")
check_at = serve.index("-ne $declared")
assert check_at < copy_at, (
    "ต้องตรวจเวอร์ชันให้ผ่านก่อน แล้วค่อยคัดลอกไฟล์ขึ้นโฟลเดอร์ปล่อยอัปเดต "
    "ไม่งั้นของผิดขึ้นไปวางแล้วถึงจะรู้")
print("OK  ตรวจผ่านก่อน แล้วค่อยวางไฟล์ขึ้นเซิร์ฟเวอร์")

# ---- ถ้ามีของ build อยู่จริง ให้ตรวจว่าตรงกันจริง ----
built = ROOT / "dist" / "Ballcar PDF" / "Ballcar PDF.exe"
version_json = ROOT / "version.json"
if built.exists() and version_json.exists():
    import json
    declared = json.loads(version_json.read_text(encoding="utf-8-sig"))["version"]

    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes

        ver = ctypes.windll.version
        path = str(built)
        size = ver.GetFileVersionInfoSizeW(path, None)
        actual = ""
        if size:
            buf = ctypes.create_string_buffer(size)
            if ver.GetFileVersionInfoW(path, 0, size, buf):
                block = ctypes.c_void_p()
                length = wintypes.UINT()
                if ver.VerQueryValueW(buf, "\\", ctypes.byref(block),
                                      ctypes.byref(length)):
                    ffi = ctypes.cast(
                        block, ctypes.POINTER(ctypes.c_uint32 * 13)).contents
                    ms, ls = ffi[2], ffi[3]
                    actual = "{}.{}.{}".format(
                        ms >> 16, ms & 0xFFFF, ls >> 16)
        if actual:
            assert actual == declared, (
                f"ของที่ build ไว้เป็น {actual} แต่ version.json บอก {declared} "
                "- ถ้าปล่อยตอนนี้ เครื่องลูกจะอัปเดตวนไม่จบ ให้ build ใหม่ให้จบก่อน")
            print(f"OK  ของที่ build ไว้ ({actual}) ตรงกับ version.json")

print("")
print("ผ่านทั้งหมด")
