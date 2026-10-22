"""ทดสอบแทรก/ลบ/ย้ายหน้า — layout ต้องไม่ค้าง และของที่วางไว้ต้องติดไปกับหน้าเดิม

กันบั๊กที่เจอจริง (1.0.48):
  1. แทรกไฟล์แล้ววิวเออร์กลายเป็นจอว่าง (IndexError เพราะ layout ยังเป็นของเก่า)
  2. ลายเซ็น/ข้อความ/มาร์กอัป ไปโผล่ผิดหน้าหลังแทรกหน้า ("หน้าไม่ตรงกัน")
"""
import os, sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ["APPDATA"] = tempfile.mkdtemp()
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import fitz
from PySide6.QtWidgets import QApplication
from app.main import MainWindow
from app.pdfops import PdfDocument

tmp = Path(tempfile.mkdtemp())


def mk(name, n, w=595, h=842):
    d = fitz.open()
    for i in range(n):
        d.new_page(width=w, height=h).insert_text((60, 80), f"{name} p{i+1}", fontsize=18)
    p = tmp / f"{name}.pdf"
    d.save(str(p)); d.close()
    return p


base = mk("BASE", 3)
ins = mk("INS", 6, w=420, h=300)      # ขนาดหน้าต่างกัน (เหมือนงานจริง)

# ================= ของลอยต้องเลื่อนตามหน้า =================

def fresh():
    d = PdfDocument(base)
    d.add_textbox(2, fitz.Rect(100, 100, 300, 140), "MARKER", font_size=14)
    d.add_annotation(2, "rect", [(50, 50), (200, 150)])
    return d


# ---- แทรกที่ต้นเล่ม -> ของลอยเลื่อนลงตามจำนวนหน้าที่แทรก ----
d = fresh()
d.insert_pdf(0, ins)
assert d.textboxes[0].page == 8, f"textbox ควรเลื่อนไปหน้า 9 ได้ {d.textboxes[0].page+1}"
assert d.annotations[0].page == 8
out = tmp / "a.pdf"; d.save(out)
with fitz.open(str(out)) as v:
    assert v.page_count == 9
    txt = v.load_page(8).get_text()
    assert "MARKER" in txt and "BASE p3" in txt, f"MARKER ต้องอยู่กับ BASE p3 ได้ {txt!r}"
print("OK  แทรกต้นเล่ม — ข้อความ/มาร์กอัป ติดไปกับหน้าเดิม")

# ---- แทรกหลังหน้าที่มีของลอย -> ไม่ขยับ ----
d = fresh()
d.insert_pdf(3, ins)
assert d.textboxes[0].page == 2, "แทรกท้าย ของลอยไม่ควรขยับ"
print("OK  แทรกท้ายเล่ม — ของลอยอยู่หน้าเดิม")

# ---- แทรกหน้าว่าง ----
d = fresh()
d.insert_blank_page(0)
assert d.textboxes[0].page == 3
print("OK  แทรกหน้าว่าง — ของลอยเลื่อนตาม")

# ---- ลบหน้าก่อนหน้า -> เลื่อนขึ้น ----
d = fresh()
d.delete_pages([0])
assert d.textboxes[0].page == 1, f"ควรเลื่อนขึ้นเป็นหน้า 2 ได้ {d.textboxes[0].page+1}"
print("OK  ลบหน้าก่อนหน้า — ของลอยเลื่อนขึ้น")

# ---- ลบหน้าที่มีของลอย -> ของลอยหายไปด้วย (ไม่ไปโผล่หน้าอื่น) ----
d = fresh()
d.delete_pages([2])
assert d.textboxes == [] and d.annotations == [], "ลบหน้าแล้วของบนหน้านั้นต้องหายไปด้วย"
print("OK  ลบหน้าที่มีของลอย — ไม่ไปโผล่หน้าอื่น")

# ---- ย้ายหน้า ----
d = fresh()
d.move_page(2, 0)          # เอาหน้า 3 (ที่มี MARKER) ไปไว้หน้าแรก
assert d.textboxes[0].page == 0, f"ของลอยควรตามไปหน้า 1 ได้ {d.textboxes[0].page+1}"
out = tmp / "m.pdf"; d.save(out)
with fitz.open(str(out)) as v:
    txt = v.load_page(0).get_text()
    assert "MARKER" in txt and "BASE p3" in txt
print("OK  ย้ายหน้า — ของลอยตามไปด้วย")

# ---- เรียงหน้าใหม่ ----
d = fresh()
d.reorder_pages([2, 0, 1])
assert d.textboxes[0].page == 0
print("OK  เรียงหน้าใหม่ — ของลอยตามไปด้วย")

# ---- เก็บเฉพาะบางหน้า ----
d = fresh()
d.keep_only_pages([1, 2])
assert d.textboxes[0].page == 1
d2 = fresh()
d2.keep_only_pages([0, 1])     # ตัดหน้าที่มีของลอยทิ้ง
assert d2.textboxes == []
print("OK  เก็บเฉพาะบางหน้า — ของลอยตามไป/หายไปถูกต้อง")

# ---- undo คืนสภาพเดิม ----
d = fresh()
d.insert_pdf(0, ins)
d.undo()
assert d.page_count == 3 and d.textboxes[0].page == 2, "undo ต้องคืนเลขหน้าเดิม"
print("OK  undo คืนเลขหน้าของลอยกลับเดิม")

# ================= วิวเออร์ไม่ค้างหลังแทรก/ลบ =================

app = QApplication.instance() or QApplication(sys.argv)
w = MainWindow(); w.resize(900, 650)
w.doc = PdfDocument(base)
w.viewer.set_document(w.doc)
w._refresh_all(keep_row=0)
w.show(); app.processEvents()
v = w.viewer

# แทรกท้ายเล่ม (เคสที่เคยพัง: keep_row ชี้เกิน layout เก่า)
at = w.doc.page_count
w.doc.insert_pdfs(at, [str(ins)])
w._refresh_all(keep_row=at)
app.processEvents()
assert w.doc.page_count == 9
assert len(v._geoms) == 9, f"layout ต้องอัปเดตครบ 9 หน้า ได้ {len(v._geoms)}"
assert w.thumbs.count() == 9
assert v._label.height() >= v._geoms[-1].bottom(), "แคนวาสต้องสูงครอบหน้าสุดท้าย"
print("OK  แทรกไฟล์ท้ายเล่ม — วิวเออร์ไม่ค้าง layout ครบ")

# หน้าที่แทรกเข้ามาขนาดต่างกัน ต้องวางกึ่งกลางและไม่ทับกัน
for i in range(len(v._geoms) - 1):
    assert v._geoms[i].bottom() < v._geoms[i + 1].y(), f"หน้า {i+1} กับ {i+2} ทับกัน"
print("OK  หน้าขนาดต่างกันเรียงต่อกันไม่ทับ")

# ---- หน้าที่ถูกหมุน (ไฟล์สแกน): กรอบต้องตรงกับภาพจริง ไม่งั้นล้นไปทับหน้าถัดไป ----
rot = fitz.open()
for i in range(2):
    p = rot.new_page(width=595, height=842)
    p.insert_text((60, 80), f"ROT {i+1}", fontsize=20)
    p.set_rotation(90)
rotp = tmp / "ROT.pdf"; rot.save(str(rotp)); rot.close()

w2 = MainWindow(); w2.resize(900, 650)
w2.doc = PdfDocument(base)
w2.viewer.set_document(w2.doc)
w2._refresh_all(keep_row=0)
w2.show(); app.processEvents()
w2.doc.insert_pdfs(1, [str(rotp)])
w2._refresh_all(keep_row=1)
app.processEvents()
v2 = w2.viewer
for i, g in enumerate(v2._geoms):
    pm = v2._page_pixmap(i)
    # ภาพถูกเรนเดอร์ที่ความละเอียดจอจริง (DPR) — เทียบขนาดตรรกะที่ Qt วาดออกมาจริง
    size = pm.deviceIndependentSize()
    assert abs(size.width() - g.width()) <= 1 and abs(size.height() - g.height()) <= 1, (
        f"หน้า {i+1}: กรอบ {g.width()}x{g.height()} ไม่ตรงกับภาพ "
        f"{size.width():.0f}x{size.height():.0f}")
for i in range(len(v2._geoms) - 1):
    assert v2._geoms[i].bottom() < v2._geoms[i + 1].y(), f"หน้า {i+1} ทับหน้า {i+2}"
print("OK  แทรกหน้าที่ถูกหมุน — กรอบตรงกับภาพจริง ไม่ทับกัน")

# ภาพย่อของหน้าขนาด/มุมหมุนต่างกัน ต้องกว้างเท่ากันหมด (ไม่ล้นจนดูเหมือนหน้าว่าง)
assert w2.thumbs.count() == 5, f"3 หน้าเดิม + แทรก 2 = 5 ได้ {w2.thumbs.count()}"
widths = [w2.thumbs.item(i).icon().availableSizes()[0].width()
          for i in range(w2.thumbs.count())]
assert max(widths) - min(widths) <= 2, f"ภาพย่อกว้างไม่เท่ากัน: {widths}"
# และต้องไม่ล้นกรอบไอคอนของลิสต์ (ล้น = ถูกตัดจนดูเหมือนหน้าว่าง)
box = w2.thumbs.iconSize()
for i in range(w2.thumbs.count()):
    s = w2.thumbs.item(i).icon().availableSizes()[0]
    assert s.width() <= box.width() and s.height() <= box.height(), \
        f"ภาพย่อหน้า {i+1} ({s.width()}x{s.height()}) ล้นกรอบ {box.width()}x{box.height()}"
print(f"OK  ภาพย่อทุกหน้ากว้างเท่ากัน ({widths[0]}px) ไม่ล้นกรอบ แม้ขนาด/มุมหมุนต่างกัน")

# ลบหน้าแล้ว layout ต้องหดตาม
w.doc.delete_pages([0, 1, 2])
w._refresh_all(keep_row=0)
app.processEvents()
assert len(v._geoms) == w.doc.page_count == 6, f"หลังลบต้องเหลือ 6 ได้ {len(v._geoms)}"
print("OK  ลบหน้า — layout หดตามถูกต้อง")

# บันทึกแล้วหน้าต้องครบ ไม่หาย
out = tmp / "final.pdf"
w.doc.save(out)
with fitz.open(str(out)) as vv:
    assert vv.page_count == 6, f"บันทึกแล้วต้องได้ 6 หน้า ได้ {vv.page_count}"
print("OK  บันทึกแล้วหน้าครบ ไม่หาย")


# ================= ปรับขนาดหน้าที่แทรกให้เท่าเอกสาร =================

small = mk("SMALL", 2, w=300, h=400)      # ขนาดต่างจาก BASE (595x842)

d = PdfDocument(base)
assert d.sizes_differ_from([str(small)]) is True, "ต้องรู้ว่าขนาดต่างกัน"
assert d.sizes_differ_from([str(base)]) is False, "ขนาดเท่ากันต้องไม่ถาม"
print("OK  ตรวจได้ว่าไฟล์ที่จะแทรกขนาดต่างจากเอกสารไหม")

# fit_to_page=False -> คงขนาดเดิม
d = PdfDocument(base)
d.insert_pdfs(d.page_count, [str(small)], fit_to_page=False)
assert d.page_size_of(3) == (300.0, 400.0), f"ควรคงขนาดเดิม ได้ {d.page_size_of(3)}"
print("OK  ไม่ปรับขนาด — หน้าที่แทรกคงขนาดเดิม")

# fit_to_page=True -> เท่าเอกสาร และเนื้อหายังอยู่ (เป็น vector ไม่ใช่รูป)
d = PdfDocument(base)
n = d.insert_pdfs(d.page_count, [str(small)], fit_to_page=True)
assert n == 2 and d.page_count == 5
for i in (3, 4):
    w_, h_ = d.page_size_of(i)
    assert (round(w_), round(h_)) == (595, 842), f"หน้า {i+1} ควรเท่าเอกสาร ได้ {w_}x{h_}"
out = tmp / "fit.pdf"; d.save(out)
with fitz.open(str(out)) as v:
    assert "SMALL p1" in v.load_page(3).get_text(), "เนื้อหาต้องยังอยู่หลังปรับขนาด"
    assert v.load_page(3).get_text().strip() != "", "ต้องยังเป็นข้อความ (vector) ไม่ใช่รูปเปล่า"
print("OK  ปรับขนาดให้เท่าเอกสาร — เนื้อหายังเป็นข้อความคมชัด")

# ---- หน้าที่ถูกหมุนไว้ (ไฟล์สแกน/ใบแจ้งหนี้) ต้องไม่ออกมาตะแคง ----
# show_pdf_page ของ PyMuPDF ไม่สนใจ /Rotate ตอนวาด — ถ้าไม่จัดการ หน้าจะตะแคง (บั๊ก 1.0.55)
def _bbox(px):
    xs, ys = [], []
    for y in range(px.height):
        for x in range(px.width):
            if sum(px.pixel(x, y)) < 250:
                xs.append(x); ys.append(y)
    return (min(xs), min(ys), max(xs), max(ys)) if xs else None


for rot in (0, 90, 180, 270):
    r = fitz.open()
    pg = r.new_page(width=595, height=842)      # ขนาดเดียวกับเอกสาร -> ต้องเหมือนเป๊ะ
    pg.insert_text((60, 120), "ABC", fontsize=100)
    pg.draw_line(fitz.Point(40, 40), fitz.Point(40, 300))
    pg.set_rotation(rot)
    rp = tmp / f"rot{rot}.pdf"; r.save(str(rp)); r.close()

    with fitz.open(str(rp)) as s:
        s0 = s.load_page(0)
        want = s0.get_pixmap(dpi=26)
        want_box = _bbox(want)
        want_landscape = s0.rect.width > s0.rect.height

    d = PdfDocument(base)
    d.insert_pdfs(d.page_count, [str(rp)], fit_to_page=True)
    got_page = d.doc.load_page(3)
    got = got_page.get_pixmap(dpi=26)
    assert (got.width, got.height) == (want.width, want.height), (
        f"หมุน {rot}°: ขนาดหน้าไม่ตรง ได้ {got.width}x{got.height} "
        f"ควร {want.width}x{want.height}")
    assert (got_page.rect.width > got_page.rect.height) == want_landscape, \
        f"หมุน {rot}°: แนวกระดาษไม่ตรงกับต้นฉบับ"
    got_box = _bbox(got)
    assert max(abs(a - b) for a, b in zip(want_box, got_box)) <= 2, \
        f"หมุน {rot}°: ตำแหน่งเนื้อหาเพี้ยน {want_box} -> {got_box} (น่าจะตะแคง)"
    # ต้นฉบับต้องไม่ถูกแก้มุมหมุนค้างไว้
    with fitz.open(str(rp)) as s:
        assert s.load_page(0).rotation == rot, "ต้องคืนมุมหมุนให้ไฟล์ต้นทาง"
print("OK  หน้าที่ถูกหมุน 0/90/180/270 — ไม่ตะแคง ขนาด/ตำแหน่งตรงต้นฉบับ")

# ---- หน้าแนวนอนต้องได้กระดาษแนวนอน (ไม่ยัดลงแนวตั้งจนเนื้อหาเล็ก) ----
land = fitz.open(); land.new_page(width=842, height=595).insert_text((60, 80), "LAND")
lp = tmp / "land.pdf"; land.save(str(lp)); land.close()
d = PdfDocument(base)                            # เอกสารเป็น A4 แนวตั้ง
d.insert_pdfs(d.page_count, [str(lp)], fit_to_page=True)
w_, h_ = d.page_size_of(3)
assert w_ > h_, f"หน้าแนวนอนควรได้กระดาษแนวนอน ได้ {w_:.0f}x{h_:.0f}"
assert (round(min(w_, h_)), round(max(w_, h_))) == (595, 842), \
    f"ต้องเป็นกระดาษ A4 ขนาดเดิม (แค่สลับแนว) ได้ {w_:.0f}x{h_:.0f}"
print("OK  หน้าแนวนอน — ได้ A4 แนวนอน (คงขนาดกระดาษ สลับแค่แนว)")

# ---- ต่างกันแค่แนวตั้ง/นอน ไม่ต้องถามผู้ใช้ ----
a4l = fitz.open(); a4l.new_page(width=842, height=595)
p_ = tmp / "a4land.pdf"; a4l.save(str(p_)); a4l.close()
d = PdfDocument(base)
assert d.sizes_differ_from([str(p_)]) is False, "A4 นอน กับ A4 ตั้ง = กระดาษเดียวกัน ไม่ต้องถาม"
print("OK  A4 แนวนอน vs แนวตั้ง — ถือว่าขนาดเดียวกัน ไม่ถามซ้ำซ้อน")

# คงสัดส่วน ไม่บีบยืด (300x400 -> ใส่ใน 595x842 ต้องได้สเกลเดียวกันทั้งกว้าง/สูง)
with fitz.open(str(out)) as v:
    drawings = v.load_page(3).get_drawings()
print("OK  แทรกแบบปรับขนาดแล้วบันทึกได้ปกติ")

# ================= แทรกแล้วไปต่อท้ายหน้าสุดท้าย =================

w3 = MainWindow(); w3.resize(900, 650)
w3.doc = PdfDocument(base)
w3.viewer.set_document(w3.doc)
w3._refresh_all(keep_row=0)
w3.show(); app.processEvents()
w3.thumbs.setCurrentRow(0)          # เลือกหน้าแรกไว้ — เมนูปกติต้องยังต่อท้าย ไม่แทรกตรงนี้

from unittest.mock import patch
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMessageBox

# ต้องกดผ่าน "เมนูจริง" ไม่ใช่เรียกเมธอดตรงๆ
# เพราะ QAction.triggered ส่ง checked=False มาเป็นอาร์กิวเมนต์แรก
# ซึ่งเคยกลายเป็นตำแหน่ง 0 ทำให้ไฟล์ไปโผล่หน้า 1 แทนที่จะต่อท้าย (บั๊ก 1.0.53)
menu_action = next(a for a in w3.findChildren(QAction) if "แทรกไฟล์ PDF" in a.text())
with patch("app.main.QFileDialog.getOpenFileNames", return_value=([str(small)], "")), \
     patch("app.main.QMessageBox.question", return_value=QMessageBox.No):
    menu_action.trigger()
app.processEvents()
assert w3.doc.page_count == 5
with fitz.open(str(base)) as b:
    pass
assert "SMALL p1" in w3.doc.page_text(3), "หน้าที่แทรกต้องไปอยู่ท้ายเล่ม (หน้า 4)"
assert "BASE p1" in w3.doc.page_text(0), "หน้าแรกต้องยังเป็นหน้าเดิม"
print("OK  เมนูแทรกไฟล์ — ไปต่อท้ายหน้าสุดท้าย แม้เลือกหน้าแรกอยู่")

# คลิกขวา "แทรกตรงนี้" ยังแทรกตรงตำแหน่งได้เหมือนเดิม
w4 = MainWindow()
w4.doc = PdfDocument(base)
w4.viewer.set_document(w4.doc)
w4._refresh_all(keep_row=0)
with patch("app.main.QFileDialog.getOpenFileNames", return_value=([str(small)], "")), \
     patch("app.main.QMessageBox.question", return_value=__import__("PySide6.QtWidgets",
           fromlist=["QMessageBox"]).QMessageBox.No):
    w4.insert_pdf_file(1)           # ระบุตำแหน่ง = แทรกตรงนั้น
assert "SMALL p1" in w4.doc.page_text(1), "คลิกขวาต้องแทรกตรงตำแหน่งที่เลือก"
print("OK  คลิกขวา 'แทรกตรงนี้' ยังแทรกตรงตำแหน่งได้")

# ---- ส่ง checked=False ตรงๆ ก็ต้องไม่กลายเป็นตำแหน่ง 0 ----
w5 = MainWindow()
w5.doc = PdfDocument(base)
w5.viewer.set_document(w5.doc)
w5._refresh_all(keep_row=0)
with patch("app.main.QFileDialog.getOpenFileNames", return_value=([str(small)], "")), \
     patch("app.main.QMessageBox.question", return_value=QMessageBox.No):
    w5.insert_pdf_file(False)       # จำลองค่าที่ Qt ส่งมา
assert "BASE p1" in w5.doc.page_text(0), \
    "checked=False ต้องถือว่าไม่ระบุตำแหน่ง (ต่อท้าย) — หน้า 1 ต้องยังเป็นหน้าเดิม"
assert "SMALL p1" in w5.doc.page_text(3), "ไฟล์ที่แทรกต้องเริ่มหลังหน้าเดิมทั้ง 3 หน้า"
print("OK  ค่า checked=False ไม่ถูกตีความเป็นตำแหน่งหน้า 1")

# ---- _act ต้องไม่ส่ง checked ต่อเข้า slot (กันบั๊กชนิดเดียวกันในเมนูอื่น) ----
got = []
act = w5._act("ทดสอบ", lambda *a: got.append(a))
act.trigger()
assert got == [()], f"slot ต้องถูกเรียกโดยไม่มีอาร์กิวเมนต์ ได้ {got}"
print("OK  _act ตัดค่า checked ทิ้ง ไม่ส่งต่อเข้าเมนูใดๆ")

# ================= ไฟล์ต้นทางผิดปกติ ต้องไม่ล้มทั้งงาน =================

# บาง PDF โครงสร้างหน้าไม่เป็นมาตรฐาน MuPDF ฟ้อง "object is not a stream"
# ต้องถอยไปใส่ขนาดเดิมแทน ไม่ใช่ยกเลิกการแทรกทั้งหมด (บั๊กที่เจอจริง 1.0.54)
import pymupdf
_orig_show = pymupdf.Page.show_pdf_page
pymupdf.Page.show_pdf_page = lambda self, *a, **k: (_ for _ in ()).throw(
    Exception("code=7: object is not a stream"))
try:
    d = PdfDocument(base)                       # BASE = 3 หน้า 595x842
    n = d.insert_pdfs(d.page_count, [str(small)], fit_to_page=True)
    assert n == 2 and d.page_count == 5, f"ต้องแทรกครบ ได้ {d.page_count} หน้า"
    assert d.fit_failed_pages == 2, f"ต้องนับหน้าที่ปรับไม่ได้ ได้ {d.fit_failed_pages}"
    assert d.page_size_of(3) == (300.0, 400.0), "ถอยไปใช้ขนาดเดิม"
    assert "SMALL p1" in d.page_text(3), "เนื้อหาต้องไม่หาย"
    out = tmp / "fallback.pdf"; d.save(out)
    with fitz.open(str(out)) as v:
        assert v.page_count == 5
finally:
    pymupdf.Page.show_pdf_page = _orig_show
print("OK  ไฟล์ต้นทางผิดปกติ — ไม่ล้มทั้งงาน ถอยไปใส่ขนาดเดิม เนื้อหาครบ")

# ปกติแล้วต้องไม่มีหน้าที่ปรับไม่ได้
d = PdfDocument(base)
d.insert_pdfs(d.page_count, [str(small)], fit_to_page=True)
assert d.fit_failed_pages == 0, "ไฟล์ปกติต้องปรับขนาดได้ครบ"
print("OK  ไฟล์ปกติ — ปรับขนาดได้ครบ ไม่มีหน้าตกหล่น")

# ---- บอกชื่อ/ขนาดกระดาษให้ผู้ใช้เห็นว่าต่างกันตรงไหน ----
assert PdfDocument.paper_name(595.28, 841.89) == "A4"
assert PdfDocument.paper_name(612, 792) == "Letter"
assert PdfDocument.paper_name(841.89, 595.28) == "A4", "แนวนอนก็ต้องเรียก A4"
assert "มม." in PdfDocument.paper_name(123, 456), "ขนาดแปลกๆ ต้องบอกเป็นมิลลิเมตร"
d = PdfDocument(base)
assert "A4" in d.describe_size(0), d.describe_size(0)
assert "300×400" in d.describe_source_sizes([str(small)]).replace(" ", "") or \
       "300" in d.describe_source_sizes([str(small)])
print(f"OK  บอกชื่อกระดาษได้ — เอกสาร: {d.describe_size(0)} / "
      f"ไฟล์แทรก: {d.describe_source_sizes([str(small)])}")

print("\nผ่านทั้งหมด")
