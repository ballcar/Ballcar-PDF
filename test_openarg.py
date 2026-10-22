"""ทดสอบการเปิดไฟล์จาก argument (ตั้งเป็นโปรแกรมเปิด PDF หลัก)"""
import os, sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ["APPDATA"] = tempfile.mkdtemp()

import fitz
from PySide6.QtWidgets import QApplication
from app.main import MainWindow, initial_file_from_argv
from app.pdfops import PdfDocument

tmp = Path(tempfile.mkdtemp())
doc = fitz.open(); doc.new_page().insert_text((72, 72), "ARGFILE"); src = tmp / "doc.pdf"
doc.save(str(src)); doc.close()
other = tmp / "not.txt"; other.write_text("x")

# ---- เลือกไฟล์จาก argv ----
assert initial_file_from_argv(["app.exe", str(src)]) == str(src)
print("OK  รับ path .pdf จาก argument")

assert initial_file_from_argv(["app.exe"]) is None
print("OK  ไม่มี argument คืน None (เปิดหน้าต่างเปล่า)")

assert initial_file_from_argv(["app.exe", str(other)]) is None
print("OK  ไฟล์ไม่ใช่ .pdf ข้าม")

assert initial_file_from_argv(["app.exe", str(tmp / "missing.pdf")]) is None
print("OK  ไฟล์ไม่มีอยู่จริง ข้าม")

# เลือกไฟล์ .pdf ตัวแรกที่มีจริง
assert initial_file_from_argv(["app.exe", str(other), str(src)]) == str(src)
print("OK  เลือก .pdf ตัวแรกที่มีจริง")

# path มีช่องว่าง (ชื่อไฟล์ไทย/เว้นวรรค)
spaced = tmp / "ใบเสนอ ราคา.pdf"
fitz.open().save(str(spaced)) if False else None
d = fitz.open(); d.new_page(); d.save(str(spaced)); d.close()
assert initial_file_from_argv(["app.exe", str(spaced)]) == str(spaced)
print("OK  path ที่มีช่องว่าง/ภาษาไทยใช้ได้")

# ---- เปิดจริงผ่าน window._open_path ----
app = QApplication(sys.argv)
w = MainWindow()
w._open_path(str(src))
assert w.doc is not None and w.doc.page_count == 1
assert "ARGFILE" in w.doc.page_text(0)
print("OK  เปิดไฟล์จาก argument ขึ้นจริง (ไม่ใช่หน้าต่างเปล่า)")

print("\nผ่านทั้งหมด")
