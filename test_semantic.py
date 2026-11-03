"""ทดสอบ AI จับความหมายของผู้ช่วย (โมเดลในเครื่อง) — ไม่มีไฟล์โมเดลจะข้ามส่วนที่ต้องใช้โมเดล"""
import os, sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from app import assistant as A
from app import semantic

# ---- แม่แบบของ AI ต้องเป็นคำสั่งที่กฎเข้าใจ (AI เลือกงาน -> กฎทำงานต่อ) ----
for template in semantic.EXAMPLES:
    assert template in A.TEMPLATES, f"แม่แบบ {template!r} ต้องอยู่ใน assistant.TEMPLATES"
    assert A._parse_rules(template) is not None, f"กฎต้องเข้าใจแม่แบบ {template!r}"
print(f"OK  แม่แบบ {len(semantic.EXAMPLES)} งานของ AI กฎเข้าใจครบ")

# ---- ไม่มีโมเดล -> ใช้กฎอย่างเดียว ไม่พัง ----
saved = semantic._candidates
semantic._candidates = lambda: [Path(tempfile.mkdtemp())]
assert not semantic.available() and semantic.model_dir() is None
semantic._candidates = saved
A.set_matcher(None)
assert A.parse("ลบหน้าว่างทั้งหมด").action == "delete_blank" and not A.has_matcher()
print("OK  ไม่มีไฟล์โมเดล ผู้ช่วยใช้กฎได้ปกติ")

if not semantic.available():
    print("ข้าม: ไม่มีไฟล์โมเดลในเครื่องนี้")
    print("\nผ่านทั้งหมด")
    sys.exit(0)

m = semantic.load()
A.set_matcher(m)

# ---- ประโยคที่กฎไม่รู้จัก แต่ AI เข้าใจ ----
cases = {
    "เอาแผ่นที่ไม่มีอะไรทิ้งไป": "delete_blank",
    "ไฟล์ใหญ่ ส่งไลน์ไม่ได้": ("open_tool", "compress_dialog"),
    "ทำให้ค้นหาคำในไฟล์สแกนได้": "ocr",
    "เอาตารางไปใส่ excel": ("open_tool", "export_excel"),
    "อยากเอาไปแก้ในเวิร์ด": ("open_tool", "export_word"),
    "กระดาษตั้งอยู่ อยากให้เป็นแนวนอน": "orientation",
}
for text, want in cases.items():
    it = A.parse(text)
    assert it is not None, f"AI ควรเข้าใจ {text!r}"
    got = it.action if isinstance(want, str) else (it.action, it.params.get("method"))
    assert got == want, f"{text!r}: ได้ {got} ต้องการ {want}"
print(f"OK  AI เข้าใจประโยคภาษาพูด {len(cases)} แบบที่กฎไม่รู้จัก")

# ---- เลขหน้ามาจากคำสั่งจริง ไม่ใช่จากแม่แบบ ----
it = A.parse("หน้า 4 เอียงอยู่ หมุนให้หน่อย")
assert it.action == "rotate" and it.params["pages"] == "4"
print("OK  เลขหน้าอ่านจากคำสั่งจริงเสมอ")

# ---- คำที่ไม่เกี่ยวกับงานเอกสาร ต้องไม่ทำอะไร และไม่เสนอมั่ว ----
for text in ("อยากกินข้าว", "วันนี้ฝนตก", "เปิดเพลงหน่อย", "ขอบคุณครับ", "ส่งอีเมลหาลูกค้า"):
    assert A.parse(text) is None, f"{text!r} ต้องไม่ถูกตีความเป็นคำสั่ง"
assert A.suggest("อยากกินข้าว") == []
print("OK  คำที่ไม่เกี่ยวไม่ถูกตีความเป็นคำสั่ง และไม่เสนอมั่ว")

# ---- ไม่มั่นใจ -> ไม่ทำเอง แต่เสนอตัวเลือกที่ถูกไว้ต้นๆ ----
assert A.parse("เอกสารกลับหัว") is None
assert A.suggest("เอกสารกลับหัว")[0] == "หมุนทุกหน้า 180"
print("OK  AI ไม่มั่นใจ -> เสนอเป็นตัวเลือก (ตัวที่ถูกอยู่อันดับแรก)")

# ---- เร็วพอพิมพ์ไปเห็นผลไป ----
import time
t0 = time.perf_counter()
for _ in range(20):
    m("ไฟล์ใหญ่ ส่งไลน์ไม่ได้")
per = (time.perf_counter() - t0) / 20 * 1000
assert per < 100, f"ช้าเกินไป {per:.0f} ms ต่อคำสั่ง"
print(f"OK  ตีความ {per:.0f} ms ต่อคำสั่ง")

print("\nผ่านทั้งหมด")
