"""ทดสอบ 2.3.2: แปลงเป็น Excel จากไฟล์ที่ทำมาจาก Excel (ตารางหลายอันเรียงกันในหน้าเดียว)

เคยมีปัญหา (MEP.pdf): ตาราง 4 อันถูกรวบเป็นตารางเดียว มีหมายเหตุปนเข้ามา หัวตารางหาย
และภาษาไทยเพี้ยน (สระล่างไปต่อท้ายคำ, วรรณยุกต์ตัวยกกลายเป็น Ŗ ŕ É Ê)
"""
import os, sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ["APPDATA"] = tempfile.mkdtemp()

import fitz
from openpyxl import load_workbook
from app.pdfops import PdfDocument, _fix_span, _tidy_thai

tmp = Path(tempfile.mkdtemp())
FONT = r"C:\Windows\Fonts\tahoma.ttf"

# หน้าแบบที่ Excel ส่งออก: เส้นแนวนอนยาวเท่ากันทุกตาราง, เส้นซ้าย/ขวาแยกตามตาราง
src = tmp / "stacked.pdf"
d = fitz.open()
page = d.new_page()
page.insert_font(fontname="th", fontfile=FONT)
X0, XM, X1 = 50, 200, 540


def table(top, title_inside, rows, title=None):
    y = top
    lines = [y]
    if title and not title_inside:
        page.insert_text((X0 + 120, top - 6), title, fontname="th", fontsize=11)
    if title and title_inside:
        page.insert_text((X0 + 120, y + 15), title, fontname="th", fontsize=11)
        y += 21
        lines.append(y)
    first_body = y
    for a, b in rows:
        page.insert_text((X0 + 4, y + 15), a, fontname="th", fontsize=10)
        page.insert_text((XM + 4, y + 15), b, fontname="th", fontsize=10)
        y += 21
        lines.append(y)
    for ly in lines:
        page.draw_rect(fitz.Rect(X0, ly - 0.6, X1, ly + 0.6), color=None, fill=(0, 0, 0))
    for x in (X0, X1):
        page.draw_rect(fitz.Rect(x - 0.6, top, x + 0.6, y), color=None, fill=(0, 0, 0))
    page.draw_rect(fitz.Rect(XM - 0.4, first_body, XM + 0.4, y), color=None, fill=(0, 0, 0))
    return y


end = table(120, False, [("ผู้สั่ง", "คุณเอกชัย"), ("ผู้อนุมัติ", "คุณภักดี"), ("ฝ่ายจัดซื้อ", "คุณอลิสรา")],
            title="ผู้มีอำนาจอนุมัติ ใบขอซื้อ RA/RS")
end = table(end + 20, True, [("ผู้รับมอบอำนาจ", "คุณโอภาส")], title="ใบสั่งซื้อ PA/PS")
page.insert_text((X0, end + 25), "หมายเหตุ : อำนาจอนุมัติยึดจากใบขอซื้อ", fontname="th", fontsize=10)
table(end + 60, True, [("ผู้สั่งสินค้า", "คุณภักดี"), ("ผู้รับมอบอำนาจ", "คุณโอภาส")], title="ใบสั่งซื้อ PO")
d.save(str(src)); d.close()

doc = PdfDocument(src)
tables = doc.find_tables(0)
assert len(tables) == 3, f"ตารางเรียงกัน 3 อัน ต้องแยกเป็น 3 ได้ {len(tables)}: {tables}"
assert tables[0][0][0] == "ผู้มีอำนาจอนุมัติ ใบขอซื้อ RA/RS", "หัวตารางที่อยู่เหนือกรอบต้องมาด้วย"
assert tables[0][1] == ["ผู้สั่ง", "คุณเอกชัย"] and len(tables[0]) == 4
assert tables[1] == [["ใบสั่งซื้อ PA/PS", ""], ["ผู้รับมอบอำนาจ", "คุณโอภาส"]], tables[1]
assert all("หมายเหตุ" not in c for t in tables for r in t for c in r), "หมายเหตุนอกกรอบต้องไม่ปนเข้าตาราง"
assert tables[2][-1] == ["ผู้รับมอบอำนาจ", "คุณโอภาส"]
print("OK  ตารางเรียงกันหลายอัน แยกถูก หัวตารางครบ หมายเหตุไม่ปน สระไม่เพี้ยน")

xlsx = tmp / "out.xlsx"
assert doc.to_excel(xlsx) == 3
book = load_workbook(xlsx)
assert book.sheetnames == ["หน้า1-ตาราง1", "หน้า1-ตาราง2", "หน้า1-ตาราง3"]
sheet = book["หน้า1-ตาราง2"]
assert [str(r) for r in sheet.merged_cells.ranges] == ["A1:B1"], "หัวตารางผสานช่องใน Excel"
assert sheet["A1"].value == "ใบสั่งซื้อ PA/PS" and sheet["A1"].font.bold
assert sheet["A2"].value == "ผู้รับมอบอำนาจ" and sheet["B2"].value == "คุณโอภาส"
print("OK  Excel: 1 ตาราง = 1 ชีต หัวตารางผสานช่อง ตัวหนา")

# ---- ทั้งเอกสาร (แบบ ABBYY): หัวเรื่อง/หมายเหตุ/ตาราง เรียงตามหน้า ชีตเดียว ----
whole = tmp / "whole.xlsx"
rows_written = doc.to_excel(whole, mode="document")
ws = load_workbook(whole).active
cells = [[c.value for c in row if c.value] for row in ws.iter_rows()]
cells = [r for r in cells if r]
flat = [v for r in cells for v in r]
assert ws.title == "เอกสาร" and rows_written >= 10
assert flat.index("ผู้มีอำนาจอนุมัติ ใบขอซื้อ RA/RS") < flat.index("ผู้สั่ง")     < flat.index("หมายเหตุ : อำนาจอนุมัติยึดจากใบขอซื้อ") < flat.index("ใบสั่งซื้อ PO"), "เรียงตามหน้า"
assert ["ผู้สั่ง", "คุณเอกชัย"] in cells, "ตารางยังอยู่เป็น 2 คอลัมน์"
assert flat.count("ผู้สั่ง") == 1, "ข้อความในตารางไม่ซ้ำเป็นย่อหน้าอีกรอบ"
note = [c for row in ws.iter_rows() for c in row if c.value and str(c.value).startswith("หมายเหตุ")][0]
assert note.font.size == 10
two = tmp / "pages.xlsx"
d2 = fitz.open(str(src)); d2.new_page().insert_text((72, 72), "หน้าสอง", fontname="th", fontfile=FONT)
d2.save(str(tmp / "two.pdf")); d2.close()
PdfDocument(tmp / "two.pdf").to_excel(two, mode="document", sheet_per_page=True)
assert load_workbook(two).sheetnames == ["หน้า 1", "หน้า 2"]
print("OK  ทั้งเอกสาร: ข้อความ + ตาราง เรียงตามหน้า ไม่ซ้ำ คงขนาดตัวอักษร · แยกชีตตามหน้าได้")

# ---- หน้าต่าง: เลือกแบบ -> จำแบบที่เลือกไว้ ----
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from unittest.mock import patch
from PySide6.QtWidgets import QApplication, QFileDialog, QInputDialog
from app import i18n
from app.main import MainWindow
i18n.load_language()
app = QApplication.instance() or QApplication(sys.argv)
w = MainWindow()
w._open_path(str(src)); app.processEvents()
out_ui = tmp / "ui.xlsx"
from PySide6.QtWidgets import QDialog
seen = []


def choose(index, pictures):
    def run(dialog):
        combo, pics = dialog._parts
        seen.append((combo.currentIndex(), pics.isChecked()))
        combo.setCurrentIndex(index)
        assert pics.isEnabled() == (index != 2), "ใส่รูปได้เฉพาะแบบทั้งเอกสาร"
        pics.setChecked(pictures)
        return QDialog.Accepted
    return run


with patch.object(w, "_ask_scope", return_value=[0]), \
        patch.object(QFileDialog, "getSaveFileName", return_value=(str(out_ui), "")):
    with patch.object(QDialog, "exec", choose(2, False)):
        w.export_excel()
    assert seen[0] == (0, True), "ครั้งแรก: ทั้งเอกสาร + ใส่รูป (แบบ ABBYY)"
    assert load_workbook(out_ui).sheetnames == ["หน้า1-ตาราง1", "หน้า1-ตาราง2", "หน้า1-ตาราง3"]
    with patch.object(QDialog, "exec", choose(0, True)):
        w.export_excel()
    assert seen[1] == (2, False), "จำแบบที่เลือกครั้งก่อน"
    assert load_workbook(out_ui).sheetnames == ["เอกสาร"]
    with patch.object(QDialog, "exec", lambda self: QDialog.Rejected):
        before = out_ui.stat().st_mtime_ns
        w.export_excel()
        assert out_ui.stat().st_mtime_ns == before, "กดยกเลิก = ไม่แปลง"
print("OK  เมนูแปลงเป็น Excel: เลือกแบบ + ใส่รูปได้ จำค่าล่าสุด ยกเลิกได้")

# ---- ใส่รูป: แผนผัง (กล่อง+ลูกศร) เป็นรูปแปะ ข้อความในแผนผังอยู่ข้างรูป ----
flow = tmp / "flow.pdf"
fd = fitz.open()
fp = fd.new_page()
fp.insert_font(fontname="th", fontfile=FONT)
fp.insert_text((72, 60), "ขั้นตอนการจัดซื้อ", fontname="th", fontsize=16)
for k, label in enumerate(["1. รับเรื่องขอซื้อ", "2. ติดต่อซัพพลายเออร์", "3. เปิดใบสั่งซื้อ"]):
    top = 100 + k * 90
    fp.draw_rect(fitz.Rect(150, top, 400, top + 50), color=(0.2, 0.4, 0.8), width=1.5)
    fp.insert_text((170, top + 30), label, fontname="th", fontsize=12)
    if k < 2:
        fp.draw_line((275, top + 50), (275, top + 90), color=(0.9, 0.5, 0.1), width=1.5)
fp.insert_text((72, 420), "หมายเหตุ ท้ายแผนผัง", fontname="th", fontsize=11)
fd.save(str(flow)); fd.close()
fx = tmp / "flow.xlsx"
PdfDocument(flow).to_excel(fx, mode="document", pictures=True)
ws = load_workbook(fx).active
assert len(ws._images) == 1, "กล่อง+ลูกศรที่ต่อกัน = รูปเดียว"
img_row = ws._images[0].anchor._from.row + 1
values = {c.value: (c.row, c.column) for row in ws.iter_rows() for c in row if c.value}
assert values["ขั้นตอนการจัดซื้อ"][0] < img_row < values["หมายเหตุ ท้ายแผนผัง"][0], "รูปอยู่ตามลำดับในหน้า"
assert values["1. รับเรื่องขอซื้อ"][0] == img_row and values["1. รับเรื่องขอซื้อ"][1] > 1, \
    "ข้อความในกล่องอยู่ข้างรูป แถวเดียวกัน"
assert values["3. เปิดใบสั่งซื้อ"][0] == img_row + 2
shown_px = ws._images[0].anchor.ext.height / 9525     # ขนาดที่แสดงใน Excel (EMU -> px)
assert 300 < shown_px < 330, "รูปขนาดเท่าบนกระดาษ (237pt ≈ 316px)"
height_rows = -(-int(shown_px) // 20)
assert values["หมายเหตุ ท้ายแผนผัง"][0] > img_row + height_rows - 1, "ข้อความถัดไปไม่ทับรูป"
PdfDocument(flow).to_excel(tmp / "nopics.xlsx", mode="document")
nop = load_workbook(tmp / "nopics.xlsx").active
assert not nop._images and any(c.value == "2. ติดต่อซัพพลายเออร์" for r in nop.iter_rows() for c in r)
# เส้นใต้/แถบไฮไลต์หลังหัวเรื่อง (ชิ้นเล็ก) และเส้นตาราง ไม่นับเป็นรูป
src_doc = PdfDocument(src)
zones = [t["rect"] + (-1, -1, 1, 1) for t in src_doc._tables_on(src_doc.doc[0])]
assert src_doc._picture_regions(src_doc.doc[0], zones) == []
print("OK  ใส่รูป: แผนผังเป็นรูปแปะตามลำดับ ข้อความอยู่ข้างรูป ไม่ทับกัน · ไม่ติ๊ก = ไม่มีรูป")

# ---- วรรณยุกต์ตัวยกที่โปรแกรมสร้าง PDF ไม่ได้บอกตัวจริง ----
fix = {"\u0156": "\u0e49", "\u0155": "\u0e48"}
assert _fix_span("ซื\u0156อ ชั\u0156น สั\u0155ง", fix) == "ซื้อ ชั้น สั่ง"
assert _fix_span("Ŗodo", fix) == "Ŗodo", "ตัวอักษรละตินจริง (ไม่ติดตัวไทย) ต้องไม่ถูกแก้"
assert _tidy_thai("อํานาจ") == "อำนาจ"
print("OK  แก้วรรณยุกต์ตัวยกเฉพาะที่ติดตัวไทย · ํา -> ำ")

real = Path(r"C:\Users\chayakul_b\Desktop\MEP.pdf")      # ไฟล์จริงจากออฟฟิศ (ไม่เอาเข้า repo)
if real.exists():
    mep = PdfDocument(real)
    tabs = mep.find_tables(0)
    assert [t[0][0] for t in tabs] == [
        "ผู้มีอำนาจอนุมัติ เอกสารใบขอซื้อ RA/RS", "ผู้มีอำนาจอนุมัติ เอกสารใบสั่งซื้อ PA/PS",
        "ผู้มีอำนาจอนุมัติ เอกสารใบขอซื้อ RO", "ผู้มีอำนาจอนุมัติ เอกสารใบสั่งซื้อ PO"], tabs
    assert tabs[0][1] == ["ผู้สั่ง", "คุณเอกชัย บุญศรี หรือผู้จัดทำเอกสาร"]
    import re
    for i in range(mep.page_count):
        odd = re.findall(r"[Ā-ɏÀ-ÿ]", mep.page_text(i))
        assert not odd, f"หน้า {i + 1}: ยังมีตัวเพี้ยน {odd}"
    assert "ขั้นตอนกระบวนการจัดซื้อ" in mep.page_text(1)
    print("OK  ไฟล์จริง MEP.pdf: 4 ตาราง หัวครบ ภาษาไทยถูก · ดึงข้อความหน้าแผนผังก็ถูก")

print("\nผ่านทั้งหมด")
