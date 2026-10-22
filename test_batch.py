"""ทดสอบ Batch Processing (ประมวลผลหลายไฟล์)"""
import sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import fitz
from app import batch
from app.pdfops import PdfDocument, find_thai_font

tmp = Path(tempfile.mkdtemp())
srcdir = tmp / "in"; srcdir.mkdir()
outdir = tmp / "out"


def make(name, pages=2, with_table=False, locked=None):
    doc = fitz.open()
    for i in range(pages):
        p = doc.new_page(width=595, height=842)
        p.insert_text((72, 100), f"{name} page {i+1}", fontsize=12)
        if with_table:
            for r in range(2):
                for c in range(2):
                    rect = fitz.Rect(60+c*120, 150+r*30, 60+(c+1)*120, 150+(r+1)*30)
                    p.draw_rect(rect, width=0.8)
                    p.insert_textbox(rect, f"{r}{c}", fontsize=9)
    path = srcdir / f"{name}.pdf"
    if locked:
        doc.save(str(path), encryption=fitz.PDF_ENCRYPT_AES_256, user_pw=locked, owner_pw=locked)
    else:
        doc.save(str(path))
    doc.close()
    return path


f1 = make("doc1", with_table=True)
f2 = make("doc2", with_table=True)
f3 = make("doc3")
files = [f1, f2, f3]

progress_calls = []
def prog(done, total, name):
    progress_calls.append((done, total))


# ---- ลายน้ำ batch ----
res = batch.run_batch(files, outdir, "watermark_text", {"text": "สำเนา"}, progress=prog)
assert all(r["ok"] for r in res), res
assert len(list(outdir.glob("*-watermark.pdf"))) == 3
# ลายน้ำไทยติดจริง
with fitz.open(outdir / "doc1-watermark.pdf") as v:
    assert "สำเนา" in v.load_page(0).get_text()
assert progress_calls[0] == (0, 3) and progress_calls[-1] == (3, 3)
print("OK  ลายน้ำ batch 3 ไฟล์ (ไทยติด, progress ครบ)")

# ---- เพิ่มเลขหน้า batch ----
res = batch.run_batch(files, outdir, "page_numbers", {})
assert all(r["ok"] for r in res)
assert len(list(outdir.glob("*-numbered.pdf"))) == 3
print("OK  เพิ่มเลขหน้า batch")

# ---- แปลง Word batch ----
res = batch.run_batch(files, outdir, "to_word", {})
assert all(r["ok"] for r in res), res
assert len(list(outdir.glob("*.docx"))) == 3
print("OK  แปลง Word batch")

# ---- แปลงรูป batch (โฟลเดอร์ต่อไฟล์) ----
res = batch.run_batch(files, outdir, "to_images", {"dpi": 80})
assert all(r["ok"] for r in res)
assert (outdir / "doc1").is_dir() and list((outdir / "doc1").glob("*.jpg"))
print("OK  แปลงรูป batch")

# ---- Excel batch: บางไฟล์ไม่มีตาราง -> รายงาน error รายไฟล์ ไม่ล้มทั้งชุด ----
res = batch.run_batch(files, outdir, "to_excel", {})
ok = [r for r in res if r["ok"]]
fail = [r for r in res if not r["ok"]]
assert len(ok) == 2 and len(fail) == 1, (ok, fail)
assert fail[0]["file"].stem == "doc3"   # doc3 ไม่มีตาราง
print("OK  Excel batch: ไฟล์ไม่มีตารางถูกข้าม รายงานแยก ไม่ล้มทั้งชุด")

# ---- ตั้งรหัส batch ----
res = batch.run_batch(files, outdir, "set_password", {"password": "pass123"})
assert all(r["ok"] for r in res)
locked = outdir / "doc1-locked.pdf"
from app.pdfops import PasswordRequired
try:
    PdfDocument(locked)
except PasswordRequired:
    pass
else:
    raise AssertionError("ควรมีรหัส")
assert PdfDocument(locked, password="pass123").page_count == 2
print("OK  ตั้งรหัส batch")

# ---- ลบรหัส batch (ไฟล์ที่ล็อก) ----
lockdir = tmp / "locked_in"; lockdir.mkdir()
import shutil
for f in outdir.glob("*-locked.pdf"):
    shutil.copy(f, lockdir / f.name.replace("-locked", ""))
lfiles = list(lockdir.glob("*.pdf"))
res = batch.run_batch(lfiles, tmp / "unlocked", "remove_password",
                      {"open_password": "pass123"})
assert all(r["ok"] for r in res), res
assert PdfDocument(next((tmp / "unlocked").glob("*-unlocked.pdf"))).page_count == 2
print("OK  ลบรหัส batch")

# ---- ไฟล์ล็อกแต่ไม่ให้รหัส -> ข้าม รายงาน error ----
lock = make("secret", locked="zzz")
res = batch.run_batch([lock], tmp / "o2", "watermark_text", {"text": "x"})
assert not res[0]["ok"] and "รหัส" in res[0]["error"]
print("OK  ไฟล์ล็อกไม่มีรหัส -> ข้าม ไม่พัง")

# ---- รวมไฟล์ ----
merged = batch.run_merge(files, tmp / "merged.pdf")
with fitz.open(merged) as v:
    assert v.page_count == 6   # 2+2+2
print("OK  รวมไฟล์ batch")

# ---- งานที่ไม่รู้จัก ----
try:
    batch.run_batch(files, outdir, "unknown_op", {})
except ValueError:
    print("OK  งานที่ไม่รู้จักแจ้ง error")
else:
    raise AssertionError("ควร error")

print("\nผ่านทั้งหมด")
