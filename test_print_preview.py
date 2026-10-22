"""ทดสอบดูตัวอย่างก่อนพิมพ์ + การวาดลงเครื่องพิมพ์"""
import os, sys, tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
tmp = Path(tempfile.mkdtemp())
os.environ["APPDATA"] = str(tmp / "appdata")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import fitz
from PySide6.QtWidgets import QApplication
from PySide6.QtPrintSupport import QPrinter
from app.main import MainWindow
from app.pdfops import PdfDocument, find_thai_font

doc = fitz.open()
for i in range(5):
    doc.new_page(width=595, height=842).insert_text((72, 80), f"PRINTPAGE-{i+1}", fontsize=20)
src = tmp / "t.pdf"
doc.save(str(src)); doc.close()

app = QApplication.instance() or QApplication(sys.argv)


def fresh():
    w = MainWindow()
    w.doc = PdfDocument(src); w.viewer.set_document(w.doc); w._refresh_all(keep_row=0)
    return w


def pdf_printer(out: Path) -> QPrinter:
    """เครื่องพิมพ์ที่พิมพ์ลงไฟล์ PDF — ใช้ตรวจผลการพิมพ์ได้จริง"""
    p = QPrinter(QPrinter.HighResolution)
    p.setOutputFormat(QPrinter.PdfFormat)
    p.setOutputFileName(str(out))
    return p


# ---- พิมพ์ทุกหน้า ----
w = fresh()
out = tmp / "all.pdf"
pr = pdf_printer(out)
pr.setFromTo(1, 5)
w.render_print(pr)
assert out.exists() and out.stat().st_size > 0, "ต้องได้ไฟล์งานพิมพ์"
with fitz.open(out) as v:
    assert v.page_count == 5, f"ต้องพิมพ์ 5 หน้า ได้ {v.page_count}"
print("OK  พิมพ์ทุกหน้า (5 หน้า)")

# ---- พิมพ์เฉพาะช่วงหน้า ----
w = fresh()
out2 = tmp / "range.pdf"
pr = pdf_printer(out2)
pr.setPrintRange(QPrinter.PageRange)
pr.setFromTo(2, 4)
w.render_print(pr)
with fitz.open(out2) as v:
    assert v.page_count == 3, f"หน้า 2-4 = 3 หน้า ได้ {v.page_count}"
print("OK  พิมพ์เฉพาะช่วงหน้า (2-4 = 3 หน้า)")

# ---- _print_pages คำนวณหน้าถูก ----
w = fresh()
pr = pdf_printer(tmp / "x.pdf")
pr.setPrintRange(QPrinter.AllPages)
assert w._print_pages(pr) == [0, 1, 2, 3, 4]
pr.setPrintRange(QPrinter.PageRange); pr.setFromTo(3, 3)
assert w._print_pages(pr) == [2]
pr.setFromTo(4, 99)          # เกินจำนวนหน้า -> ต้องตัดให้พอดี
assert w._print_pages(pr) == [3, 4], w._print_pages(pr)
print("OK  คำนวณหน้าที่จะพิมพ์ถูก (รวมกรณีช่วงเกินจำนวนหน้า)")

# ---- งานพิมพ์รวมข้อความที่เพิ่มไว้ (ยังไม่บันทึก) ----
w = fresh()
w.doc.add_textbox(0, fitz.Rect(60, 300, 500, 340), "ข้อความก่อนพิมพ์", font_size=16)
w.doc.set_watermark("สำเนา")
out3 = tmp / "withextras.pdf"
pr = pdf_printer(out3)
pr.setFromTo(1, 1)
pr.setPrintRange(QPrinter.PageRange)
w.render_print(pr)
with fitz.open(out3) as v:
    # งานพิมพ์เป็นภาพ จึงเทียบด้วยปริมาณหมึกว่ามีของเพิ่มเข้ามา
    ink = v.load_page(0).get_pixmap(matrix=fitz.Matrix(0.5, 0.5))
    dark = sum(1 for i in range(0, len(ink.samples), 3) if ink.samples[i] < 200)
plain = fresh()
out4 = tmp / "plain.pdf"
pr2 = pdf_printer(out4)
pr2.setPrintRange(QPrinter.PageRange); pr2.setFromTo(1, 1)
plain.render_print(pr2)
with fitz.open(out4) as v:
    ink2 = v.load_page(0).get_pixmap(matrix=fitz.Matrix(0.5, 0.5))
    dark2 = sum(1 for i in range(0, len(ink2.samples), 3) if ink2.samples[i] < 200)
assert dark > dark2 + 50, f"งานพิมพ์ต้องมีข้อความ/ลายน้ำที่เพิ่มไว้ ({dark2} -> {dark})"
print(f"OK  งานพิมพ์รวมข้อความ+ลายน้ำที่ยังไม่บันทึก (หมึก {dark2} -> {dark})")
# ต้นฉบับไม่ถูกแตะ
assert len(w.doc.textboxes) == 1 and w.doc.watermark is not None
print("OK  พิมพ์แล้วของที่เพิ่มไว้ยังแก้ต่อได้ (ไม่ถูกฝัง)")

# ---- print_document เปิดหน้าต่างพิมพ์แบบรวม (ตั้งค่า+ตัวอย่าง) ----
from app.main import PrintDialog

w = fresh()
shown = {}
with patch.object(PrintDialog, "exec", lambda self: shown.update(dlg=self) or 0):
    w.print_document()
dlg = shown.get("dlg")
assert dlg is not None, "ต้องเปิดหน้าต่างพิมพ์"
assert "พิมพ์" in dlg.windowTitle(), dlg.windowTitle()
# ต้องมีทั้งส่วนตั้งค่าและตัวอย่างในหน้าต่างเดียว
from PySide6.QtPrintSupport import QPrintPreviewWidget
assert dlg.findChild(QPrintPreviewWidget) is not None, "ต้องมีตัวอย่างในหน้าต่างเดียวกัน"
assert dlg.printer_box.count() > 0, "ต้องมีรายชื่อเครื่องพิมพ์ให้เลือก"
# ตัวอย่างต้องไม่ผูกกับ driver จริง (กันค้างเมื่อเลือกเครื่องที่ปิดอยู่)
assert dlg.printer.outputFormat() == QPrinter.PdfFormat, "ตัวอย่างต้องเป็น PDF ไม่แตะ driver"
print(f"OK  หน้าต่างพิมพ์เดียวจบ (ตั้งค่า + ตัวอย่าง, เครื่องพิมพ์ {dlg.printer_box.count()} ตัว)")

# ค่าเริ่มต้น = ทุกหน้า
assert dlg.r_all.isChecked() and dlg.selected_pages() == [0, 1, 2, 3, 4]
assert not dlg.range_edit.isEnabled(), "ยังไม่เลือกช่วงหน้า ช่องต้องปิดอยู่"
print("OK  ค่าเริ่มต้นพิมพ์ทุกหน้า")

# เลือกช่วงหน้าแบบข้ามหน้า
dlg.r_range.setChecked(True)
assert dlg.range_edit.isEnabled()
dlg.range_edit.setText("1-2,5")
assert dlg.selected_pages() == [0, 1, 4], dlg.selected_pages()
assert dlg.print_btn.isEnabled()
print("OK  ระบุช่วงหน้าข้ามหน้าได้ (1-2,5)")

# ช่วงหน้าผิด -> ปิดปุ่มพิมพ์ ไม่ให้กด
dlg.range_edit.setText("99")
assert dlg.selected_pages() == []
assert not dlg.print_btn.isEnabled(), "ช่วงหน้าผิดต้องกดพิมพ์ไม่ได้"
print("OK  ช่วงหน้าผิด ปิดปุ่มพิมพ์ (กันพิมพ์พลาด)")

# เลือกเครื่องพิมพ์ = แค่จำชื่อไว้ ไม่ setPrinterName ใส่ตัวพรีวิว (กันค้าง)
dlg.r_all.setChecked(True)
dlg.printer_box.setCurrentIndex(0)
dlg._apply_settings()
assert dlg._target_printer == dlg.printer_box.currentText(), "ต้องจำชื่อเครื่องที่เลือก"
assert dlg.printer.printerName() != dlg._target_printer or dlg.printer.outputFormat() == QPrinter.PdfFormat,     "ตัวพรีวิวต้องไม่ถูกผูกกับเครื่องจริง"
print("OK  เลือกเครื่องพิมพ์แล้วตัวพรีวิวไม่แตะ driver (ไม่ค้าง)")

# กดพิมพ์ไปเครื่องที่ไม่มีในระบบ -> เตือน ไม่ค้าง
w_off = fresh()
with patch.object(PrintDialog, "exec", lambda self: None):
    d_off = PrintDialog(w_off)
d_off._target_printer = "เครื่องพิมพ์ที่ไม่มีจริง 999"
with patch("app.main.QMessageBox.warning") as warn:
    d_off._do_print()
    assert warn.called, "เครื่องพิมพ์ไม่มีในระบบต้องเตือน ไม่ค้าง"
print("OK  พิมพ์ไปเครื่องที่ปิด/ไม่มี -> เตือน ไม่ค้าง")

# พิมพ์เฉพาะหน้าที่ระบุแบบข้ามหน้า -> ได้จำนวนหน้าถูก
w2 = fresh()
w2._print_only_pages = [0, 2, 4]
out5 = tmp / "skip.pdf"
pr5 = pdf_printer(out5)
w2.render_print(pr5)
with fitz.open(out5) as v:
    assert v.page_count == 3, f"หน้า 1,3,5 = 3 หน้า ได้ {v.page_count}"
w2._print_only_pages = None
print("OK  พิมพ์หน้าข้ามหน้า (1,3,5) ได้ 3 หน้า")

# ---- ของจริง: สร้าง PrintDialog จริงได้ (คลาส Qt ที่ใช้มีอยู่ใน build) ----
w = fresh()
real = PrintDialog(w)
assert real.findChild(QPrintPreviewWidget) is not None
real.deleteLater()
print("OK  สร้างหน้าต่างพิมพ์จริงได้ (มีในโปรแกรมที่แพ็ก)")

print("\nผ่านทั้งหมด")


# ---- ชื่องานพิมพ์ = ชื่อไฟล์ (โชว์ในคิวเครื่องพิมพ์ ไม่ใช่ "document1") ----
import fitz as _fitz
named = tmp / "ใบเสนอราคา-2568.pdf"
_d = _fitz.open(); _d.new_page().insert_text((72, 80), "hi"); _d.save(str(named)); _d.close()
w = MainWindow(); w.doc = PdfDocument(named)
w.viewer.set_document(w.doc); w._refresh_all(keep_row=0)
with patch.object(PrintDialog, "exec", lambda self: None):
    dlg = PrintDialog(w)
# ตรวจ docName ที่ตั้งให้ printer จริง (ดักตอน setDocName)
captured = {}
real_setname = QPrinter.setDocName
with patch.object(QPrinter, "setDocName", lambda self, n: captured.update(name=n)):
    # ให้ผ่านด่านตรวจเครื่องพิมพ์: ใช้ชื่อเครื่องที่มีจริง
    from PySide6.QtPrintSupport import QPrinterInfo
    avail = [p.printerName() for p in QPrinterInfo.availablePrinters()]
    if avail:
        dlg._target_printer = avail[0]
        with patch.object(w, "render_print", lambda pr: None):
            dlg._do_print()
        assert captured.get("name") == "ใบเสนอราคา-2568.pdf", captured
        print(f"OK  ชื่องานพิมพ์ = ชื่อไฟล์ ({captured['name']})")
    else:
        print("SKIP ไม่มีเครื่องพิมพ์ในระบบ")

# ยังไม่ตั้งชื่อไฟล์ (เอกสารใหม่) -> ใช้ชื่อโปรแกรมแทน ไม่พัง
w2 = fresh(); w2.doc.path = None
with patch.object(PrintDialog, "exec", lambda self: None):
    dlg2 = PrintDialog(w2)
cap2 = {}
from PySide6.QtPrintSupport import QPrinterInfo as _QPI
_avail = [p.printerName() for p in _QPI.availablePrinters()]
if _avail:
    dlg2._target_printer = _avail[0]
    with patch.object(QPrinter, "setDocName", lambda self, n: cap2.update(name=n)), \
         patch.object(w2, "render_print", lambda pr: None):
        dlg2._do_print()
    assert cap2.get("name") == "Ballcar PDF", cap2
    print("OK  เอกสารยังไม่ตั้งชื่อ -> ใช้ชื่อโปรแกรม ไม่พัง")

print("\nผ่านทั้งหมด (รวมชื่องานพิมพ์)")
