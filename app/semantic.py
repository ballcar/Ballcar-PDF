"""AI จับความหมายคำสั่ง (2.0) — ทำงานในเครื่อง ไม่ต้องต่อเน็ต

โมเดล: sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2 (Apache-2.0)
       รุ่น ONNX quint8 (AVX2) 118 MB + tokenizer.json 9 MB — รองรับภาษาไทย
ตำแหน่งไฟล์ (หาตามลำดับ):
    <โฟลเดอร์โปรแกรม>/models/paraphrase-multilingual-MiniLM-L12-v2/
    %LOCALAPPDATA%/BallcarPDF/models/paraphrase-multilingual-MiniLM-L12-v2/
ไม่มีไฟล์/ไลบรารี = available() เป็น False ผู้ช่วยใช้กฎอย่างเดียว ทำงานได้ปกติ

AI ทำหน้าที่เดียว: บอกว่าประโยคนี้ "อยากทำงานไหน" (เทียบความหมายกับประโยคตัวอย่างของแต่ละงาน)
เลขหน้า/ข้อความ/คำค้น ยังอ่านด้วยกฎจากคำสั่งจริงเสมอ (assistant._parse_with_matcher)
"""
from __future__ import annotations

import os
import sys
import threading
from pathlib import Path

MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"

# งาน (คำสั่งแม่แบบที่กฎเข้าใจ) -> ประโยคตัวอย่างหลายแบบ ทั้งภาษาเขียน/ภาษาพูด/อังกฤษ
# แม่แบบต้องอยู่ใน assistant.TEMPLATES (เทสต์ตรวจ)
EXAMPLES: dict[str, list[str]] = {
    "ลบหน้าว่างทั้งหมด": [
        "ลบหน้าว่างทั้งหมด", "เอาหน้าที่ไม่มีข้อความออก", "ลบแผ่นเปล่าทิ้ง",
        "หน้าที่ไม่มีอะไรเลยเอาออกให้หน่อย", "ตัดหน้าว่างออกจากไฟล์", "ไม่เอาหน้าขาวๆ",
        "remove blank pages", "delete empty pages",
    ],
    "ลบหน้า 3": [
        "ลบหน้านี้", "ลบหน้าที่ไม่ต้องการ", "เอาหน้านั้นออก", "ตัดหน้าทิ้ง", "delete page",
    ],
    "หมุนทุกหน้าแนวนอน": [
        "หมุนทุกหน้าแนวนอน", "ทำให้หน้ากระดาษเป็นแนวนอน", "ปรับเป็นแนวนอนทั้งหมด",
        "อยากให้กระดาษนอน", "หน้ากระดาษตั้งอยู่ อยากให้นอน", "แนวนอนทั้งไฟล์",
        "make pages landscape",
    ],
    "หมุนหน้า 2 ไปทางขวา": [
        "หมุนหน้าไปทางขวา", "หมุนตามเข็มนาฬิกา", "หน้ากลับด้าน หมุนให้ตรง", "หมุนหน้าให้ตรง",
        "เอกสารเอียงอยู่ หมุนให้หน่อย", "rotate page right",
    ],
    "หมุนทุกหน้า 180": [
        "หมุนกลับหัว", "หน้ากลับหัวอยู่", "เอกสารคว่ำ หมุนกลับ", "rotate upside down",
    ],
    "ย้ายหน้า 5 ไปหน้าแรก": [
        "ย้ายหน้าไปไว้หน้าแรก", "เอาหน้านี้ขึ้นไปไว้ข้างหน้า", "สลับลำดับหน้า", "เรียงหน้าใหม่",
        "move page to the front",
    ],
    "แทรกหน้าว่างหลังหน้า 3": [
        "เพิ่มหน้าว่าง", "แทรกแผ่นเปล่า", "ใส่หน้าขาวเพิ่ม", "insert a blank page",
    ],
    "แยกหน้า 1-3 เป็นไฟล์ใหม่": [
        "เอาบางหน้าออกมาเป็นอีกไฟล์", "บันทึกเฉพาะบางหน้า", "ตัดบางหน้าไปทำไฟล์ใหม่",
        "save some pages as a new file",
    ],
    "แยกไฟล์ทีละหน้า": [
        "แยกไฟล์ทีละหน้า", "แตกไฟล์ออกเป็นหน้าละไฟล์", "ทำให้แต่ละหน้าเป็นไฟล์แยก",
        "split every page into its own file",
    ],
    "ใส่เลขหน้า": [
        "ใส่เลขหน้า", "ใส่หมายเลขหน้ากระดาษ", "ทำเลขกำกับหน้า", "อยากให้มีเลขหน้าทุกแผ่น",
        "ใส่ตัวเลขกำกับแต่ละหน้า", "add page numbers", "number the pages",
    ],
    "ใส่เลขหน้าเป็นเลขโรมัน": ["ใส่เลขหน้าแบบโรมัน", "เลขหน้าตัวโรมัน", "roman page numbers"],
    "OCR ทุกหน้า": [
        "ทำให้ไฟล์สแกนค้นหาคำได้", "อ่านตัวหนังสือจากภาพสแกน", "ไฟล์สแกนคัดลอกข้อความไม่ได้",
        "แปลงภาพสแกนเป็นข้อความ", "recognize text in scanned pages",
    ],
    "ลบข้อมูลส่วนบุคคล": [
        "ปิดเบอร์โทรกับอีเมล", "ซ่อนเลขบัตรประชาชน", "ปิดข้อมูลลับก่อนส่งต่อ", "เซ็นเซอร์ข้อมูลส่วนตัว",
        "redact personal information",
    ],
    'ใส่ลายน้ำ "สำเนา"': [
        "ใส่ลายน้ำ", "ประทับคำว่าสำเนาทุกหน้า", "ใส่ตัวหนังสือจางๆ ทับเอกสาร", "add a watermark",
    ],
    "บีบอัดไฟล์": [
        "บีบอัดไฟล์", "ไฟล์ใหญ่เกิน ส่งเมลไม่ได้", "ทำให้ไฟล์เล็กลง", "ลดขนาด PDF",
        "ไฟล์หนักไป อยากให้เบาลง", "แนบไฟล์ไม่ได้เพราะใหญ่เกิน", "compress the pdf",
        "make the file smaller",
    ],
    "แปลงเป็น Word": [
        "แปลงเป็นไฟล์ Word", "อยากได้ไฟล์เวิร์ดไปแก้", "เอาไปแก้ใน Word", "เปลี่ยนเป็น docx",
        "ทำเป็นเอกสารที่แก้ข้อความได้", "convert to word",
    ],
    "ดึงตารางเป็น Excel": [
        "ดึงตารางไป Excel", "อยากได้ตัวเลขในตารางไปทำในเอ็กเซล", "เอาตารางออกมาเป็นสเปรดชีต",
        "export tables to excel",
    ],
    "บันทึกหน้าเป็นรูป": [
        "บันทึกหน้าเป็นรูป", "แปลงหน้าเป็น jpg", "เซฟหน้าเป็นภาพ", "export pages as images",
    ],
    "ดึงข้อความทั้งไฟล์": [
        "ดึงข้อความทั้งหมดออกมา", "คัดลอกตัวหนังสือทั้งไฟล์", "เอาข้อความไปวางที่อื่น",
        "extract all the text",
    ],
    "ตั้งรหัสผ่าน": [
        "ตั้งรหัสผ่าน", "กันคนอื่นเปิดไฟล์", "ล็อกเอกสารไม่ให้ใครเปิด", "ใส่พาสเวิร์ดให้ไฟล์",
        "ป้องกันไฟล์ด้วยรหัส", "password protect this pdf",
    ],
    "ลบรหัสผ่าน": [
        "ลบรหัสผ่าน", "ไม่อยากให้ต้องใส่รหัสทุกครั้ง", "ปลดล็อกไฟล์", "remove the password",
    ],
    "รวมไฟล์": [
        "รวมไฟล์", "เอาหลายไฟล์มาต่อกันเป็นไฟล์เดียว", "รวม PDF หลายไฟล์", "merge pdf files",
    ],
    "พิมพ์": ["พิมพ์เอกสาร", "ปริ้นท์", "ปริ้นไฟล์นี้", "สั่งปริ้น", "print this"],
    "ใส่ลายเซ็น": [
        "ใส่ลายเซ็น", "เซ็นชื่อในเอกสาร", "ประทับตราบริษัท", "แปะลายเซ็น", "sign the document",
    ],
    "กรอกแบบฟอร์ม": ["กรอกแบบฟอร์ม", "กรอกช่องในฟอร์ม", "fill in the form"],
}

# AI ตัดสินใจเองได้เฉพาะตอนมั่นใจ: คะแนนสูง และนำอันดับสองชัดเจน
# ไม่ถึงเกณฑ์ -> เสนอเป็นตัวเลือกให้ผู้ใช้กด (ไม่ทำเอง)
CONFIDENT = 0.80
MARGIN = 0.05


def _candidates() -> list[Path]:
    exe_dir = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    found = [exe_dir / "models" / MODEL_NAME]
    if getattr(sys, "frozen", False):
        found.append(Path(sys.executable).resolve().parent / "models" / MODEL_NAME)
    local = os.environ.get("LOCALAPPDATA")
    if local:
        found.append(Path(local) / "BallcarPDF" / "models" / MODEL_NAME)
    return found


def model_dir() -> Path | None:
    for folder in _candidates():
        if (folder / "model.onnx").is_file() and (folder / "tokenizer.json").is_file():
            return folder
    return None


def available() -> bool:
    if model_dir() is None:
        return False
    try:
        import onnxruntime  # noqa: F401
        import tokenizers  # noqa: F401
    except ImportError:
        return False
    return True


class Matcher:
    """เทียบความหมายคำสั่งกับประโยคตัวอย่างของแต่ละงาน — เรียกได้เหมือนฟังก์ชัน"""

    def __init__(self, folder: Path) -> None:
        import numpy as np
        import onnxruntime as ort
        from tokenizers import Tokenizer

        self._np = np
        options = ort.SessionOptions()
        options.intra_op_num_threads = 2      # ไม่แย่ง CPU งานอื่นของโปรแกรม
        self._session = ort.InferenceSession(str(folder / "model.onnx"), options,
                                             providers=["CPUExecutionProvider"])
        self._inputs = {i.name for i in self._session.get_inputs()}
        self._tokenizer = Tokenizer.from_file(str(folder / "tokenizer.json"))
        self._tokenizer.enable_padding()
        self._tokenizer.enable_truncation(128)
        self._labels: list[str] = []
        sentences: list[str] = []
        for template, phrases in EXAMPLES.items():
            for phrase in phrases:
                self._labels.append(template)
                sentences.append(phrase)
        self._bank = self.embed(sentences)

    def embed(self, texts: list[str]):
        np = self._np
        encoded = self._tokenizer.encode_batch(texts)
        ids = np.array([e.ids for e in encoded], dtype=np.int64)
        mask = np.array([e.attention_mask for e in encoded], dtype=np.int64)
        feed = {"input_ids": ids, "attention_mask": mask}
        if "token_type_ids" in self._inputs:
            feed["token_type_ids"] = np.zeros_like(ids)
        hidden = self._session.run(None, feed)[0]
        weights = mask[..., None].astype(np.float32)
        vectors = (hidden * weights).sum(1) / np.maximum(weights.sum(1), 1e-9)   # mean pooling
        return vectors / np.linalg.norm(vectors, axis=1, keepdims=True)

    def rank(self, text: str) -> list[tuple[str, float]]:
        """งานทั้งหมดเรียงตามความใกล้ [(แม่แบบ, คะแนน)] — คะแนนของงาน = ประโยคตัวอย่างที่ใกล้ที่สุด"""
        scores = self._bank @ self.embed([text])[0]
        best: dict[str, float] = {}
        for label, score in zip(self._labels, scores):
            if score > best.get(label, -1.0):
                best[label] = float(score)
        return sorted(best.items(), key=lambda kv: kv[1], reverse=True)

    def __call__(self, text: str) -> list[tuple[str, float]]:
        """สำหรับ assistant.set_matcher — คะแนนอันดับแรกถูกลดลงถ้านำอันดับสองไม่ชัด
        (assistant ใช้เกณฑ์เดียว ไม่ต้องรู้เรื่อง margin)"""
        ranked = self.rank(text)
        if len(ranked) >= 2 and ranked[0][1] - ranked[1][1] < MARGIN:
            ranked[0] = (ranked[0][0], min(ranked[0][1], CONFIDENT - 0.01))
        return ranked


_matcher: Matcher | None = None
_lock = threading.Lock()


def load() -> Matcher | None:
    """โหลดโมเดล (ครั้งแรก ~1 วินาที) — ไม่มีไฟล์/ไลบรารี หรือโหลดพัง คืน None"""
    global _matcher
    from . import errorlog
    with _lock:
        if _matcher is None and available():
            try:
                _matcher = Matcher(model_dir())
                errorlog.log_info("assistant AI: พร้อมใช้ (%s)", model_dir())
            except Exception as exc:
                # ไม่เด้งกล่องเตือน (ผู้ช่วยใช้กฎต่อได้) แต่บันทึกไว้ให้ตรวจเครื่องที่มีปัญหาได้
                errorlog.log_info("assistant AI: โหลดไม่สำเร็จ ใช้กฎแทน — %r", exc)
                _matcher = None
        elif _matcher is None:
            errorlog.log_info("assistant AI: ไม่มีไฟล์โมเดล/ไลบรารี ใช้กฎแทน (หาที่ %s)",
                              ", ".join(str(p) for p in _candidates()))
        return _matcher


def load_in_background(on_ready=None) -> None:
    """โหลดตอนเปิดโปรแกรมโดยไม่ทำให้หน้าต่างช้า — เสร็จแล้วต่อเข้ากับผู้ช่วยเอง"""
    def work():
        matcher = load()
        if matcher is not None:
            from . import assistant
            assistant.set_matcher(matcher)
            if on_ready:
                on_ready()
    if available():
        threading.Thread(target=work, daemon=True).start()
