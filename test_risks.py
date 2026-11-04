"""ทดสอบ 2.3 ความปลอดภัย: ตรวจ JavaScript / คำสั่งเปิดโปรแกรม / ไฟล์แนบ, แถบเตือน, ล้างออก"""
import os, sys, tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ["APPDATA"] = tempfile.mkdtemp()
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import fitz
from PySide6.QtWidgets import QApplication, QMessageBox
from app import i18n
from app.main import MainWindow
from app.pdfops import PdfDocument

i18n.load_language()
app = QApplication.instance() or QApplication(sys.argv)
tmp = Path(tempfile.mkdtemp())

# ไฟล์อันตรายจำลอง: สคริปต์รันตอนเปิด, สคริปต์ระดับเอกสาร, ลิงก์ที่สั่งรันโปรแกรม, ไฟล์แนบ 2 แบบ
evil = tmp / "invoice.pdf"
d = fitz.open()
p = d.new_page()
p.insert_text((72, 100), "Invoice 2026-001", fontsize=14)
cat = d.pdf_catalog()
js = d.get_new_xref(); d.update_object(js, "<< /S /JavaScript /JS (app.alert('x');) >>")
d.xref_set_key(cat, "OpenAction", f"{js} 0 R")
names_js = d.get_new_xref(); d.update_object(names_js, "<< /S /JavaScript /JS (this.print();) >>")
d.xref_set_key(cat, "Names", f"<< /JavaScript << /Names [(a) {names_js} 0 R] >> >>")
p.insert_link({"kind": fitz.LINK_URI, "from": fitz.Rect(72, 120, 220, 140), "uri": "https://example.com"})
launch = d.get_new_xref(); d.update_object(launch, "<< /S /Launch /F (cmd.exe) >>")
d.embfile_add("payload.exe", b"MZ fake")
p.add_file_annot((300, 300), b"x", "note.txt")
d.save(str(evil)); d.close()

clean = tmp / "clean.pdf"
c = fitz.open(); c.new_page().insert_text((72, 100), "Normal", fontsize=14); c.save(str(clean)); c.close()

# ---- ตรวจพบ ----
doc = PdfDocument(evil)
info = doc.risks()
assert info["javascript"] >= 2 and info["launch"] == 1 and info["attachments"] == 2, info
assert PdfDocument(clean).risks() == {"javascript": 0, "launch": 0, "attachments": 0}
print("OK  ตรวจเจอ JavaScript / คำสั่งเปิดโปรแกรม / ไฟล์แนบ · ไฟล์ปกติ = ไม่มี")

# ---- ล้างออก: เนื้อหาและลิงก์เว็บอยู่ครบ ย้อนกลับได้ บันทึกแล้วเปิดใหม่ยังสะอาด ----
doc.remove_risks()
assert doc.risks() == {"javascript": 0, "launch": 0, "attachments": 0} and doc.dirty
assert doc.undo() and doc.risks()["javascript"] >= 2
doc.redo()
out = tmp / "safe.pdf"
doc.save(out)
with fitz.open(str(out)) as saved:
    assert "Invoice 2026-001" in saved[0].get_text()
    assert [l.get("uri") for l in saved[0].get_links()] == ["https://example.com"]
    assert saved.embfile_count() == 0
assert PdfDocument(out).risks() == {"javascript": 0, "launch": 0, "attachments": 0}
print("OK  ล้างออกแล้ว: เนื้อหา/ลิงก์เว็บอยู่ครบ ย้อนกลับได้ บันทึกแล้วสะอาดจริง")

# ---- หน้าต่าง: เปิดไฟล์มีความเสี่ยง -> แถบเตือน; ไฟล์ปกติ -> ไม่มี ----
w = MainWindow(); w.resize(1200, 800); w.show(); app.processEvents()
w._open_path(str(evil)); app.processEvents(); app.processEvents()
assert w._risk_bar.isVisible(), "เปิดไฟล์ที่มีสคริปต์ ต้องมีแถบเตือน"
assert "JavaScript" in w._risk_label.text() and i18n.t("risk.attach", n=2) in w._risk_label.text()
w._open_path(str(clean)); app.processEvents(); app.processEvents()
assert not w._risk_bar.isVisible(), "ไฟล์ปกติไม่มีแถบเตือน"
w.tab_bar.setCurrentIndex(0); app.processEvents(); app.processEvents()
assert w._risk_bar.isVisible(), "สลับกลับมาไฟล์เสี่ยง แถบเตือนกลับมา"
print("OK  เปิดไฟล์ที่มีสคริปต์/ไฟล์แนบ = แถบเตือน · ไฟล์ปกติไม่มี · ตามแท็บที่ดูอยู่")

# ปุ่มล้างออก (ยืนยัน) -> แถบหาย ไฟล์รอบันทึก
with patch.object(QMessageBox, "question", return_value=QMessageBox.Yes):
    w._risk_clean.click()
app.processEvents()
assert not w._risk_bar.isVisible() and w.doc.dirty and not any(w.doc.risks().values())
assert w.tab_bar.tabText(0).endswith("*")
print("OK  กดล้างออก → สคริปต์/ไฟล์แนบหาย แถบเตือนหาย รอบันทึก")

# ซ่อนแถบ (×) ได้ ต่อไฟล์
w._open_path(str(evil.with_name("invoice.pdf"))); app.processEvents()
w2 = PdfDocument(evil)
w._add_tab(w2); app.processEvents(); app.processEvents()
assert w._risk_bar.isVisible()
w._risk_close.click()
assert not w._risk_bar.isVisible() and w2.risk_dismissed
assert i18n.t("risk.menu") in {a.text() for a in w.tool_actions}
with patch.object(QMessageBox, "information") as info_box:
    w.tab_bar.setCurrentIndex(1); app.processEvents()
    w.remove_risks()
    assert info_box.called, "ไฟล์ปกติ กดเมนูล้าง = บอกว่าไม่พบ"
print("OK  ปุ่ม × ซ่อนแถบได้ · เมนูเครื่องมือ → ล้างสคริปต์ ใช้กับไฟล์ไหนก็ได้")

for tab in w._tabs:
    tab["doc"].dirty = False
print("\nผ่านทั้งหมด")
