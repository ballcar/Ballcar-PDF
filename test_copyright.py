"""ทดสอบว่าข้อมูลลิขสิทธิ์ถูกใส่ครบทุกที่ที่ผู้ใช้เห็นได้"""
import os, re, sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ["APPDATA"] = tempfile.mkdtemp()
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parent
OWNER = "ballcar"
YEAR = "2026"

# ---- ไฟล์ LICENSE ----
lic = (ROOT / "LICENSE").read_text(encoding="utf-8")
assert "MIT License" in lic, "ต้องเป็นสัญญาอนุญาต MIT"
assert f"Copyright (c) {YEAR} {OWNER}" in lic, "ชื่อเจ้าของลิขสิทธิ์ใน LICENSE ไม่ตรง"
print("OK  ไฟล์ LICENSE — MIT + ชื่อเจ้าของถูกต้อง")

# ---- หน้าต่าง "เกี่ยวกับโปรแกรม" ทั้งสองภาษา ----
from app import i18n

i18n.load_language()
th = i18n.t("help.about_body", version="9.9.9")
assert "สงวนลิขสิทธิ์" in th and OWNER in th and YEAR in th, th
assert "MIT" in th, "ต้องบอกสัญญาอนุญาตด้วย"
assert "9.9.9" in th, "ต้องแสดงเวอร์ชัน"

i18n._current = "en"
en = i18n.t("help.about_body", version="9.9.9")
assert "Copyright" in en and OWNER in en and YEAR in en, en
assert "MIT" in en
i18n._current = "th"
print("OK  หน้าต่างเกี่ยวกับโปรแกรม — มีลิขสิทธิ์ครบทั้งไทย/อังกฤษ")

# ---- ช่องทางแจ้งปัญหา + สนับสนุน (แสดงในหน้าต่างเกี่ยวกับ) ----
from app import main as M

assert "@" in M.SUPPORT_EMAIL and "." in M.SUPPORT_EMAIL, f"อีเมลไม่ถูกรูปแบบ: {M.SUPPORT_EMAIL}"
for lang in ("th", "en"):
    i18n._current = lang
    for key in ("about.contact", "about.support", "about.account",
                "about.version", "about.tagline", "about.copyright",
                "about.license", "about.warranty"):
        val = i18n.t(key, version="9.9.9")
        assert val and val != key, f"[{lang}] ขาดข้อความ {key}"
i18n._current = "th"
assert "{version}" not in i18n.t("about.version", version="9.9.9")
print(f"OK  ช่องทางแจ้งปัญหา ({M.SUPPORT_EMAIL}) + สนับสนุน — ข้อความครบ 2 ภาษา")

# ---- ปุ่ม/หน้าต่างสนับสนุน (QR ไม่โชว์ในหน้าเกี่ยวกับ แต่กดปุ่มแล้วเด้งขึ้นมา) ----
for lang in ("th", "en"):
    i18n._current = lang
    for key in ("about.support_btn", "support.title", "support.thanks",
                "support.promptpay", "support.close"):
        val = i18n.t(key)
        assert val and val != key, f"[{lang}] ขาดข้อความ {key}"
i18n._current = "th"
assert hasattr(M.MainWindow, "show_support"), "ต้องมีหน้าต่างสนับสนุนแยก"

# หน้าเกี่ยวกับต้องไม่ฝัง QR ไว้ (ให้กะทัดรัด) — QR อยู่ในหน้าสนับสนุนเท่านั้น
import inspect

about_src = inspect.getsource(M.MainWindow.show_about)
support_src = inspect.getsource(M.MainWindow.show_support)
assert "promptpay_qr_path" not in about_src, "หน้าเกี่ยวกับต้องไม่แสดง QR แล้ว"
assert "promptpay_qr_path" in support_src, "หน้าสนับสนุนต้องแสดง QR"
assert "show_support" in about_src, "หน้าเกี่ยวกับต้องมีปุ่มเปิดหน้าสนับสนุน"
print("OK  QR ย้ายไปหน้าสนับสนุน — หน้าเกี่ยวกับกะทัดรัด มีปุ่มเปิดให้")

# ---- ต้องหารูป QR เจอ ----
qr = M.promptpay_qr_path()
assert qr is not None and qr.exists(), "ต้องหารูป QR เจอ (วางที่ qr_code/promptpay2.png)"
print(f"OK  หารูป QR เจอ: {qr.name}")

# ---- build ต้องใส่รูป QR ให้ ถ้ามีไฟล์ ----
buildtxt = (ROOT / "build-exe.ps1").read_text(encoding="utf-8-sig")
assert "promptpay" in buildtxt, "build ต้องแพ็กรูป QR ไปด้วย (ถ้ามีไฟล์)"
assert "Test-Path" in buildtxt, "ต้องเช็คก่อนว่ามีไฟล์ QR ไหม ไม่งั้น build พังตอนไม่มีไฟล์"
print("OK  build แพ็กรูป QR แบบมีก็ใส่ ไม่มีก็ข้าม (build ไม่พัง)")

# ---- ตัวติดตั้ง ----
iss = (ROOT / "installer" / "BallcarPDF.iss").read_text(encoding="utf-8-sig")
assert re.search(r"^AppCopyright=.*ballcar", iss, re.M), "ตัวติดตั้งต้องมี AppCopyright"
assert re.search(r"^AppPublisher=ballcar", iss, re.M), "ตัวติดตั้งต้องมี AppPublisher"
print("OK  ตัวติดตั้ง — มีข้อมูลลิขสิทธิ์/ผู้เผยแพร่")

# ---- build ต้องฝังข้อมูลลงไฟล์ .exe ----
build = (ROOT / "build-exe.ps1").read_text(encoding="utf-8-sig")
assert "make-version-info.py" in build, "build ต้องสร้างไฟล์ข้อมูลเวอร์ชันก่อน"
assert "--version-file" in build, "build ต้องส่ง --version-file ให้ PyInstaller"
assert build.index("make-version-info.py") < build.index("-m PyInstaller"), \
    "ต้องสร้างไฟล์ข้อมูลเวอร์ชัน 'ก่อน' เรียก PyInstaller"
print("OK  build-exe.ps1 — ฝังข้อมูลลิขสิทธิ์ลง .exe")

# ---- ตัวสร้างไฟล์ข้อมูลเวอร์ชัน ทำงานได้และตรงกับ version.json ----
import json
import subprocess

version = json.loads((ROOT / "version.json").read_text(encoding="utf-8"))["version"]
env = dict(os.environ, PYTHONIOENCODING="utf-8")
r = subprocess.run([sys.executable, str(ROOT / "scripts" / "make-version-info.py")],
                   capture_output=True, text=True, env=env, cwd=str(ROOT),
                   encoding="utf-8", errors="replace")   # ผลลัพธ์เป็นภาษาไทย
assert r.returncode == 0, f"สร้างไฟล์ข้อมูลเวอร์ชันไม่สำเร็จ: {r.stderr}"

info = (ROOT / "version_info.txt").read_text(encoding="utf-8")
assert f"'{version}'" in info, f"เวอร์ชันใน version_info ไม่ตรงกับ version.json ({version})"
assert f"Copyright (c) {YEAR} {OWNER}" in info, "ต้องมีบรรทัดลิขสิทธิ์"
assert "'ballcar'" in info, "ต้องมีชื่อบริษัท/เจ้าของ"
assert "Ballcar PDF" in info, "ต้องมีชื่อผลิตภัณฑ์"
quad = tuple(int(x) for x in version.split(".")) + (0,)
assert f"filevers=({quad[0]}, {quad[1]}, {quad[2]}, {quad[3]})" in info, \
    f"เลขเวอร์ชัน 4 ท่อนไม่ตรง: {version}"
print(f"OK  ไฟล์ข้อมูลเวอร์ชัน — ตรงกับ version.json ({version}) และมีลิขสิทธิ์")

# ไฟล์นี้สร้างอัตโนมัติ ไม่ควรถูกแก้ด้วยมือ -> ต้องมีคำเตือน
assert "สร้างอัตโนมัติ" in info, "ควรมีหมายเหตุว่าไฟล์นี้สร้างอัตโนมัติ"
print("OK  มีหมายเหตุกันคนเผลอแก้ไฟล์ที่สร้างอัตโนมัติ")

print("\nผ่านทั้งหมด")
