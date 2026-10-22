"""ตัวจับ error กลาง + เขียน log — สำหรับตอนแจกให้คนอื่นทดลองใช้

ถ้าเกิดข้อผิดพลาดที่ไม่ได้ดักไว้ จะ:
1. เขียนรายละเอียดลงไฟล์ log (%APPDATA%\\BallcarPDF\\logs\\)
2. เด้งกล่องบอกผู้ใช้แบบเข้าใจง่าย (งานถูกสำรองไว้แล้ว) แทนที่จะปิดหายเงียบๆ
"""
from __future__ import annotations

import logging
import os
import sys
import traceback
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path


def log_dir() -> Path:
    base = Path(os.environ.get("APPDATA") or Path.home())
    folder = base / "BallcarPDF" / "logs"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


_logger: logging.Logger | None = None


def setup_logging(version: str = "") -> logging.Logger:
    """ตั้งค่า log ไฟล์ (หมุนไฟล์เก็บ 5 ไฟล์ล่าสุด กันโตไม่จบ)"""
    global _logger
    if _logger is not None:
        return _logger
    logger = logging.getLogger("BallcarPDF")
    logger.setLevel(logging.INFO)
    try:
        handler = RotatingFileHandler(
            log_dir() / "ballcar-pdf.log", maxBytes=512_000, backupCount=5, encoding="utf-8")
        handler.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(message)s", "%Y-%m-%d %H:%M:%S"))
        logger.addHandler(handler)
    except Exception:
        pass   # เขียน log ไม่ได้ก็ยังใช้โปรแกรมต่อได้
    logger.info("===== เปิดโปรแกรม Ballcar PDF %s =====", version)
    _logger = logger
    return logger


def install_excepthook(app=None, on_crash=None) -> None:
    """ดัก error ที่หลุดออกมาทั้งหมด — เขียน log + เด้งกล่องบอกผู้ใช้"""
    logger = setup_logging()

    def hook(exc_type, exc_value, exc_tb):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return
        detail = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        logger.error("ข้อผิดพลาดที่ไม่ได้ดัก:\n%s", detail)
        if on_crash is not None:
            try:
                on_crash()   # เช่น เซฟงานกู้คืนก่อน
            except Exception:
                pass
        _show_dialog(detail)

    sys.excepthook = hook


def _show_dialog(detail: str) -> None:
    try:
        from PySide6.QtWidgets import QApplication, QMessageBox
        if QApplication.instance() is None:
            return
        box = QMessageBox()
        box.setIcon(QMessageBox.Warning)
        box.setWindowTitle("เกิดข้อผิดพลาด")
        box.setText("โปรแกรมเจอข้อผิดพลาดที่ไม่คาดคิด\n\n"
                    "งานของคุณถูกสำรองไว้แล้ว — เปิดโปรแกรมใหม่แล้วเลือก \"กู้คืน\" ได้\n"
                    f"บันทึกรายละเอียดไว้ที่:\n{log_dir()}")
        box.setDetailedText(detail)
        box.setStandardButtons(QMessageBox.Ok)
        box.exec()
    except Exception:
        pass   # แม้แต่กล่อง error ยังเด้งไม่ได้ ก็อย่าให้พังซ้ำ


def log_info(msg: str, *args) -> None:
    setup_logging().info(msg, *args)
