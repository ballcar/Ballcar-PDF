"""ทดสอบตัวเลือกการพิมพ์ — เลือกหน้า (คี่/คู่/ย้อนลำดับ/หน้าปัจจุบัน) และขนาด/หลายหน้าต่อแผ่น"""
import os, sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ["APPDATA"] = tempfile.mkdtemp()
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import fitz
from PySide6.QtGui import QPageSize, QPainter
from PySide6.QtPrintSupport import QPrinter
from PySide6.QtWidgets import QApplication
from app.main import MainWindow, PrintDialog
from app.pdfops import PdfDocument

tmp = Path(tempfile.mkdtemp())
d = fitz.open()
for i in range(6):
    d.new_page(width=595, height=842).insert_text((60, 80), f"PAGE {i+1}", fontsize=30)
src = tmp / "six.pdf"
d.save(str(src)); d.close()

app = QApplication.instance() or QApplication(sys.argv)
w = MainWindow()
w.doc = PdfDocument(src)
w.viewer.set_document(w.doc)
w._refresh_all(keep_row=0)

dlg = PrintDialog(w)

# ================= เลือกหน้าที่จะพิมพ์ =================

assert dlg.selected_pages() == [0, 1, 2, 3, 4, 5], "ค่าเริ่มต้น = ทุกหน้า"
print("OK  ค่าเริ่มต้นพิมพ์ทุกหน้า")

# หน้าปัจจุบัน
w.viewer.index = 3
dlg2 = PrintDialog(w)
dlg2.r_current.setChecked(True)
assert dlg2.selected_pages() == [3], f"ควรได้หน้า 4 ได้ {dlg2.selected_pages()}"
print("OK  เลือก 'หน้าปัจจุบัน' ได้หน้าที่กำลังดูอยู่")

# ระบุช่วงหน้าแบบข้ามหน้า
dlg.r_range.setChecked(True)
dlg.range_edit.setText("1-3,5")
assert dlg.selected_pages() == [0, 1, 2, 4], dlg.selected_pages()
print("OK  ระบุช่วงข้ามหน้า 1-3,5 ได้ถูกต้อง")

# ช่วงหน้าผิด -> ปุ่มพิมพ์ถูกปิด
dlg.range_edit.setText("abc")
assert dlg.selected_pages() == []
assert not dlg.print_btn.isEnabled(), "ช่วงหน้าผิด ต้องกดพิมพ์ไม่ได้"
dlg.range_edit.setText("1-3,5")
assert dlg.print_btn.isEnabled()
print("OK  ช่วงหน้าผิด -> กดพิมพ์ไม่ได้ (แก้แล้วกลับมากดได้)")

# คี่/คู่ (นับตามเลขหน้าที่ผู้ใช้เห็น)
dlg.r_all.setChecked(True)
dlg.oddeven.setCurrentIndex(dlg.oddeven.findData("odd"))
assert dlg.selected_pages() == [0, 2, 4], f"หน้าคี่ 1,3,5 ได้ {dlg.selected_pages()}"
dlg.oddeven.setCurrentIndex(dlg.oddeven.findData("even"))
assert dlg.selected_pages() == [1, 3, 5], f"หน้าคู่ 2,4,6 ได้ {dlg.selected_pages()}"
print("OK  กรองเฉพาะหน้าคี่ / หน้าคู่ ถูกต้อง")

# คี่/คู่ ต้องทำงานร่วมกับช่วงหน้า
dlg.r_range.setChecked(True)
dlg.range_edit.setText("1-4")
dlg.oddeven.setCurrentIndex(dlg.oddeven.findData("odd"))
assert dlg.selected_pages() == [0, 2], f"1-4 เอาเฉพาะคี่ = 1,3 ได้ {dlg.selected_pages()}"
print("OK  คี่/คู่ ใช้ร่วมกับช่วงหน้าได้")

# ย้อนลำดับ
dlg.oddeven.setCurrentIndex(dlg.oddeven.findData("all"))
dlg.r_all.setChecked(True)
dlg.reverse.setChecked(True)
assert dlg.selected_pages() == [5, 4, 3, 2, 1, 0], dlg.selected_pages()
dlg.reverse.setChecked(False)
print("OK  พิมพ์ย้อนลำดับได้")

# ย้อนลำดับ + คี่
dlg.oddeven.setCurrentIndex(dlg.oddeven.findData("odd"))
dlg.reverse.setChecked(True)
assert dlg.selected_pages() == [4, 2, 0], dlg.selected_pages()
dlg.reverse.setChecked(False)
dlg.oddeven.setCurrentIndex(dlg.oddeven.findData("all"))
print("OK  ย้อนลำดับใช้ร่วมกับคี่/คู่ได้")

# ลำดับที่เลือกต้องส่งถึงตัววาดจริง (fromTo บอกลำดับย้อนไม่ได้)
dlg.reverse.setChecked(True)
dlg._apply_settings()
assert w._print_only_pages == [5, 4, 3, 2, 1, 0], w._print_only_pages
dlg.reverse.setChecked(False)
dlg._apply_settings()
assert w._print_only_pages is None, "ทุกหน้าเรียงปกติ = ไม่ต้องระบุรายการ"
print("OK  ลำดับหน้าที่เลือกส่งถึงตัววาดจริง")

# ================= ขนาด / หลายหน้าต่อแผ่น =================

dlg.size_mode.setCurrentIndex(dlg.size_mode.findData("custom"))
assert dlg.scale_spin.isEnabled(), "เลือก 'กำหนดเอง' แล้วช่อง % ต้องกรอกได้"
dlg.size_mode.setCurrentIndex(dlg.size_mode.findData("fit"))
assert not dlg.scale_spin.isEnabled(), "โหมดอื่นต้องปิดช่อง %"
print("OK  ช่องเปอร์เซ็นต์เปิด/ปิดตามโหมดขนาด")

dlg.size_mode.setCurrentIndex(dlg.size_mode.findData("shrink"))
dlg.per_sheet.setCurrentIndex(dlg.per_sheet.findData(4))
dlg._apply_settings()
opts = w._print_opts
assert opts["size_mode"] == "shrink" and opts["per_sheet"] == 4, opts
assert opts["auto_rotate"] is True
print("OK  ส่งค่าขนาด/จำนวนหน้าต่อแผ่นให้ตัววาดถูกต้อง")


# ---- วาดจริงลงไฟล์ PDF แล้วนับจำนวนแผ่นที่ออกมา ----
def sheets_for(pages, per_sheet, size_mode="fit", scale=100, auto_rotate=True):
    w._print_only_pages = pages
    w._print_opts = {"size_mode": size_mode, "scale": scale,
                     "per_sheet": per_sheet, "auto_rotate": auto_rotate}
    out = tmp / f"o_{per_sheet}_{size_mode}_{scale}_{len(pages)}.pdf"
    pr = QPrinter(QPrinter.ScreenResolution)
    pr.setOutputFormat(QPrinter.PdfFormat)
    pr.setOutputFileName(str(out))
    pr.setPageSize(QPageSize(QPageSize.A4))
    w.render_print(pr)
    with fitz.open(str(out)) as v:
        return v.page_count, out


n, _ = sheets_for([0, 1, 2, 3, 4, 5], 1)
assert n == 6, f"1 หน้า/แผ่น จาก 6 หน้า ควรได้ 6 แผ่น ได้ {n}"
n, _ = sheets_for([0, 1, 2, 3, 4, 5], 2)
assert n == 3, f"2 หน้า/แผ่น ควรได้ 3 แผ่น ได้ {n}"
n, _ = sheets_for([0, 1, 2, 3, 4, 5], 4)
assert n == 2, f"4 หน้า/แผ่น ควรได้ 2 แผ่น ได้ {n}"
n, _ = sheets_for([0, 1, 2, 3, 4, 5], 9)
assert n == 1, f"9 หน้า/แผ่น ควรได้ 1 แผ่น ได้ {n}"
n, _ = sheets_for([0, 1, 2], 2)
assert n == 2, f"3 หน้า @2 ต่อแผ่น ควรได้ 2 แผ่น (แผ่นหลังมีหน้าเดียว) ได้ {n}"
print("OK  หลายหน้าต่อแผ่น 1/2/4/9 ได้จำนวนแผ่นถูกต้อง")

# พิมพ์เฉพาะหน้าที่เลือก ต้องได้เท่าที่เลือกจริง
n, out = sheets_for([0, 2, 4], 1)
assert n == 3, f"เลือก 3 หน้า ควรได้ 3 แผ่น ได้ {n}"
with fitz.open(str(out)) as v:
    assert v.page_count == 3
print("OK  พิมพ์เฉพาะหน้าที่เลือก ได้เท่าที่เลือก")

# ย้อนลำดับ: แผ่นแรกต้องเป็นหน้าสุดท้าย (เทียบด้วยภาพ)
def first_sheet_image(pages, **kw):
    _, path = sheets_for(pages, 1, **kw)
    with fitz.open(str(path)) as v:
        return v.load_page(0).get_pixmap(dpi=40).tobytes("png")


img_last = first_sheet_image([5])
img_rev_first = first_sheet_image([5, 4, 3, 2, 1, 0])
assert img_last == img_rev_first, "ย้อนลำดับ แผ่นแรกต้องเป็นหน้า 6"
print("OK  ย้อนลำดับ — แผ่นแรกคือหน้าสุดท้ายจริง")

# โหมดขนาดต่างๆ ต้องวาดได้และให้ผลต่างกันจริง
imgs = {}
for mode, sc in (("fit", 100), ("actual", 100), ("shrink", 100), ("custom", 50)):
    _, path = sheets_for([0], 1, size_mode=mode, scale=sc)
    with fitz.open(str(path)) as v:
        imgs[mode] = v.load_page(0).get_pixmap(dpi=40).tobytes("png")
assert imgs["custom"] != imgs["fit"], "ย่อ 50% ต้องต่างจากพอดีหน้า"
print("OK  โหมดขนาด fit/actual/shrink/custom วาดได้ และ 50% ต่างจริง")

# หน้าแนวนอนกับการหมุนอัตโนมัติ
land = fitz.open()
land.new_page(width=842, height=595).insert_text((60, 80), "WIDE", fontsize=40)
lp = tmp / "land.pdf"; land.save(str(lp)); land.close()
w2 = MainWindow()
w2.doc = PdfDocument(lp)
w2.viewer.set_document(w2.doc)
w2._refresh_all(keep_row=0)


def render_land(auto):
    w2._print_only_pages = [0]
    w2._print_opts = {"size_mode": "fit", "scale": 100, "per_sheet": 1,
                      "auto_rotate": auto}
    out = tmp / f"land_{auto}.pdf"
    pr = QPrinter(QPrinter.ScreenResolution)
    pr.setOutputFormat(QPrinter.PdfFormat)
    pr.setOutputFileName(str(out))
    pr.setPageSize(QPageSize(QPageSize.A4))
    w2.render_print(pr)
    with fitz.open(str(out)) as v:
        page = v.load_page(0)
        pix = page.get_pixmap(dpi=50)
        # หากล่องเนื้อหา (ส่วนที่ไม่ใช่ขาว) เพื่อดูว่าเต็มกระดาษแค่ไหน
        xs, ys = [], []
        for y in range(pix.height):
            for x in range(pix.width):
                if sum(pix.pixel(x, y)) < 700:
                    xs.append(x); ys.append(y)
        return (max(xs) - min(xs)) * (max(ys) - min(ys)) if xs else 0


area_on = render_land(True)
area_off = render_land(False)
assert area_on > area_off * 1.3, \
    f"หมุนอัตโนมัติควรได้เนื้อหาใหญ่กว่ามาก ({area_on} vs {area_off})"
print(f"OK  หมุนอัตโนมัติ — หน้าแนวนอนเต็มกระดาษกว่าเดิม ({area_on/area_off:.1f} เท่า)")

print("\nผ่านทั้งหมด")
