"""ธีมของโปรแกรม (2.0) — สีทั้งหมดอยู่ที่นี่ที่เดียว

โหมด: "system" (ตาม Windows) / "light" / "dark"
สีหลัก (accent): เลือกจาก ACCENTS หรือรหัสสีเอง เช่น "#e63329"
เก็บค่าใน settings.json (คีย์ theme_mode, theme_accent) เหมือนภาษา

วิดเจ็ตในโปรแกรมไม่ต้องกำหนดสีเอง ให้ตั้ง property "role" แล้วสไตล์กลางจัดให้
    label.setProperty("role", "hint")       ข้อความอธิบายตัวเล็กสีจาง
    bar.setProperty("role", "modebar-info")  แถบโหมดแก้ไข (info/warn/success/danger/note)
"""
from __future__ import annotations

from dataclasses import dataclass

from . import i18n

MODES = ("system", "light", "dark")

# สีหลักให้เลือก — คีย์คือชื่อที่เก็บใน settings (ชื่อที่แสดงอยู่ใน i18n: theme.accent.<คีย์>)
ACCENTS = {
    "ballcar": "#e63329",     # แดงประจำโปรแกรม (สีเดียวกับโลโก้)
    "blue": "#2f6fde",
    "green": "#1f9d55",
    "purple": "#7c4dff",
    "orange": "#f08c00",
    "teal": "#0f9ba8",
}
DEFAULT_MODE = "system"
DEFAULT_ACCENT = "ballcar"


@dataclass(frozen=True)
class Palette:
    dark: bool
    window: str        # พื้นหน้าต่าง
    surface: str       # แผง/แถบเครื่องมือ
    surface_alt: str   # แถวสลับ / ช่องกรอก
    text: str
    text_muted: str    # ข้อความอธิบาย
    border: str
    viewer_bg: str     # พื้นหลังรอบหน้ากระดาษ
    accent: str
    accent_text: str   # ตัวหนังสือบนพื้นสีหลัก
    # แถบโหมดแก้ไข (พื้น, ขอบ, ตัวหนังสือ)
    info: tuple[str, str, str]
    warn: tuple[str, str, str]
    success: tuple[str, str, str]
    danger: tuple[str, str, str]
    note: tuple[str, str, str]


def _readable_on(color: str) -> str:
    """ตัวหนังสือขาวหรือดำ ให้อ่านออกบนพื้นสีนี้"""
    r, g, b = (int(color[i:i + 2], 16) for i in (1, 3, 5))
    return "#1a1a1a" if (0.299 * r + 0.587 * g + 0.114 * b) > 160 else "#ffffff"


def _mix(a: str, b: str, amount: float) -> str:
    """ผสมสี a เข้าหา b ตามสัดส่วน amount (0 = a ล้วน, 1 = b ล้วน)"""
    ca = [int(a[i:i + 2], 16) for i in (1, 3, 5)]
    cb = [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * amount):02x}" for x, y in zip(ca, cb))


def resolve_accent(accent: str | None) -> str:
    if accent in ACCENTS:
        return ACCENTS[accent]
    if isinstance(accent, str) and len(accent) == 7 and accent.startswith("#"):
        try:
            int(accent[1:], 16)
            return accent.lower()
        except ValueError:
            pass
    return ACCENTS[DEFAULT_ACCENT]


def build_palette(dark: bool, accent: str | None = None) -> Palette:
    acc = resolve_accent(accent)
    if dark:
        return Palette(
            dark=True, window="#1f2124", surface="#2a2d31", surface_alt="#33373c",
            text="#e8e8e8", text_muted="#9aa0a6", border="#454a50", viewer_bg="#3a3d41",
            accent=acc, accent_text=_readable_on(acc),
            info=("#1d2f4a", "#2f5a96", "#9cc3ff"),
            warn=("#3d3418", "#7a6420", "#f2d27a"),
            success=("#18382a", "#2c6e4f", "#8fe0b4"),
            danger=("#3f1f1f", "#7d3535", "#ffb0b0"),
            note=("#1e3247", "#2f5880", "#a8d0f5"),
        )
    return Palette(
        dark=False, window="#f3f4f6", surface="#ffffff", surface_alt="#f7f8fa",
        text="#1f2328", text_muted="#6b7280", border="#d4d7dc", viewer_bg="#7c8187",
        accent=acc, accent_text=_readable_on(acc),
        info=("#e7f0ff", "#9bbcf0", "#0a58ca"),
        warn=("#fff4d6", "#e6c46a", "#664d03"),
        success=("#e3f6ec", "#8fd0ad", "#0f5132"),
        danger=("#fde8e8", "#e6a3a3", "#8a2f2f"),
        note=("#e6f1fb", "#9cc4ea", "#1f5c99"),
    )


def system_is_dark() -> bool:
    """Windows ตั้งโหมดมืดอยู่ไหม (อ่านจาก Qt — ไม่มีข้อมูลถือว่าสว่าง)"""
    try:
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QGuiApplication
        return QGuiApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark
    except Exception:
        return False


def saved_mode() -> str:
    mode = i18n.get_setting("theme_mode", DEFAULT_MODE)
    return mode if mode in MODES else DEFAULT_MODE


def saved_accent() -> str:
    return i18n.get_setting("theme_accent", DEFAULT_ACCENT) or DEFAULT_ACCENT


def colored_icons() -> bool:
    return bool(i18n.get_setting("theme_colored_icons", True))


def save(mode: str | None = None, accent: str | None = None,
         colored: bool | None = None) -> None:
    if colored is not None:
        i18n.set_setting("theme_colored_icons", bool(colored))
    if mode in MODES:
        i18n.set_setting("theme_mode", mode)
    if accent is not None:
        i18n.set_setting("theme_accent", accent)


def current_palette() -> Palette:
    mode = saved_mode()
    dark = system_is_dark() if mode == "system" else mode == "dark"
    return build_palette(dark, saved_accent())


def stylesheet(p: Palette) -> str:
    """สไตล์กลางทั้งโปรแกรม — วิดเจ็ตเลือกหน้าตาด้วย property role / objectName"""
    hover = _mix(p.surface, p.accent, 0.12)
    pressed = _mix(p.surface, p.accent, 0.22)
    bars = ""
    for role, (bg, border, fg) in (("info", p.info), ("warn", p.warn), ("success", p.success),
                                   ("danger", p.danger), ("note", p.note)):
        bars += f"""
        QWidget[role="modebar-{role}"] {{ background:{bg}; border-bottom:1px solid {border}; }}
        QWidget[role="modebar-{role}"] QLabel {{ background:transparent; color:{fg}; font-weight:bold; }}
        QWidget[role="modebar-{role}"] QPushButton {{
            background:{p.surface}; color:{p.text}; border:1px solid {border};
            border-radius:4px; padding:4px 12px; font-weight:500; }}
        QWidget[role="modebar-{role}"] QPushButton:hover {{ background:{hover}; border-color:{p.accent}; }}
        QWidget[role="modebar-{role}"] QPushButton:pressed {{ background:{pressed}; }}
        """
    return f"""
        QToolTip {{ background:{p.surface}; color:{p.text}; border:1px solid {p.border}; padding:4px; }}
        QMenuBar {{ background:{p.surface}; color:{p.text}; font-size:13px; }}
        QMenuBar::item:selected {{ background:{hover}; border-radius:4px; }}
        QMenu {{ background:{p.surface}; color:{p.text}; border:1px solid {p.border}; padding:4px;
                 font-size:13px; }}
        QMenu::item {{ padding:6px 24px 6px 28px; border-radius:4px; }}
        QMenu::item:selected {{ background:{p.accent}; color:{p.accent_text}; }}
        QMenu::separator {{ height:1px; background:{p.border}; margin:4px 8px; }}
        QToolBar {{ background:{p.surface}; border:none; border-bottom:1px solid {p.border};
                    spacing:2px; padding:3px; }}
        QToolButton {{ border-radius:5px; padding:3px; }}
        QToolButton:hover {{ background:{hover}; }}
        QToolButton:pressed, QToolButton:checked {{ background:{pressed}; }}
        QToolButton#toolsButton {{ font-weight:bold; padding:3px 10px; }}
        QToolButton#toolsButton::menu-indicator {{ subcontrol-position:right center; }}
        QPushButton[role="primary"] {{ background:{p.accent}; color:{p.accent_text};
            border:none; border-radius:5px; font-weight:bold; padding:6px 16px; }}
        QPushButton[role="primary"]:hover {{ background:{_mix(p.accent, '#000000', 0.12)}; }}
        QPushButton[role="primary"]:disabled {{ background:{p.border}; color:{p.text_muted}; }}
        QLineEdit:focus, QSpinBox:focus, QComboBox:focus {{ border:1px solid {p.accent}; }}
        QLineEdit[invalid="true"] {{ border:1px solid {p.danger[1]}; }}
        QLabel[role="hint"] {{ color:{p.text_muted}; font-size:11px; }}
        QLabel[role="title"] {{ font-size:17px; font-weight:bold; }}
        QLabel[role="header"] {{ font-weight:bold; padding:2px; }}
        QFrame[role="divider"] {{ color:{p.border}; background:{p.border}; max-height:1px; border:none; }}
        QSplitter::handle:horizontal {{ background:{p.border}; margin:0 1px; }}
        QSplitter::handle:horizontal:hover {{ background:{p.accent}; }}
        QStatusBar {{ background:{p.surface}; color:{p.text_muted}; border-top:1px solid {p.border}; }}
        #viewerArea, #printPreview {{ background:{p.viewer_bg}; }}
        #selPopup {{ background:{'#2b2f33' if not p.dark else p.surface_alt};
                    border:1px solid {p.border}; border-radius:6px; }}
        #selPopup QPushButton {{ color:#f0f0f0; background:transparent; border:none; padding:4px 10px; }}
        #selPopup QPushButton:hover {{ background:{p.accent}; color:{p.accent_text}; border-radius:4px; }}
        #toolPanel {{ background:{p.surface}; border-right:1px solid {p.border}; }}
        #toolPanelBody {{ background:transparent; }}
        #toolPanel QScrollArea {{ background:transparent; }}
        QLabel[role="panelTitle"] {{ font-size:16px; font-weight:bold; padding:2px 2px 4px 2px; }}
        #toolSearch {{ border:1px solid {p.border}; border-radius:6px; padding:6px 8px; font-size:13px;
                       background:{p.surface_alt}; color:{p.text}; }}
        #toolSearch:focus {{ border:1px solid {p.accent}; }}
        QLabel[role="toolGroup"] {{ color:{p.text_muted}; font-size:12px; font-weight:bold;
                                    padding:10px 4px 3px 4px; }}
        QLabel[role="toolGroup"][collapsed="true"] {{ padding:0; margin:6px 6px;
            max-height:1px; min-height:1px; background:{p.border}; }}
        #collapseButton {{ font-size:15px; font-weight:bold; padding:0 6px; border-radius:5px;
                           color:{p.text_muted}; }}
        #collapseButton:hover {{ background:{hover}; color:{p.text}; }}
        QToolButton[role="tool"] {{ text-align:left; padding:5px 8px; border:none;
                                    border-radius:5px; color:{p.text}; font-size:14px; }}
        QToolButton[role="tool"]:hover {{ background:{hover}; }}
        QToolButton[role="tool"]:pressed {{ background:{pressed}; }}
        QToolButton[role="tool"]:disabled {{ color:{p.text_muted}; }}
        #homePage {{ background:{p.window}; }}
        QLabel[role="homeTitle"] {{ font-size:26px; font-weight:bold; color:{p.text}; }}
        QPushButton[role="card"] {{ background:{p.surface}; color:{p.text}; text-align:left;
            border:1px solid {p.border}; border-radius:8px; padding:10px 14px; }}
        QPushButton[role="card"]:hover {{ border-color:{p.accent}; background:{hover}; }}
        QPushButton[role="card"]:pressed {{ background:{pressed}; }}
        #recentList {{ background:{p.surface}; border:1px solid {p.border}; border-radius:8px;
                       padding:4px; color:{p.text}; }}
        #recentList::item {{ padding:6px 8px; border-radius:6px; }}
        #recentList::item:hover {{ background:{hover}; }}
        #linkButton {{ color:{p.accent}; border:none; }}
        #linkButton:hover {{ text-decoration:underline; }}
        QListWidget::item:selected, QTreeWidget::item:selected {{
            background:{_mix(p.surface, p.accent, 0.35)}; color:{p.text}; }}
        {bars}
    """


def qpalette(p: Palette):
    """QPalette ตามธีม — ให้วิดเจ็ตพื้นฐานของ Qt (ช่องกรอก ปุ่ม รายการ) เปลี่ยนสีตามด้วย"""
    from PySide6.QtGui import QColor, QPalette

    pal = QPalette()
    roles = {
        QPalette.Window: p.window, QPalette.WindowText: p.text,
        QPalette.Base: p.surface, QPalette.AlternateBase: p.surface_alt,
        QPalette.Text: p.text, QPalette.Button: p.surface, QPalette.ButtonText: p.text,
        QPalette.ToolTipBase: p.surface, QPalette.ToolTipText: p.text,
        QPalette.PlaceholderText: p.text_muted, QPalette.Highlight: p.accent,
        QPalette.HighlightedText: p.accent_text, QPalette.Link: p.accent,
        QPalette.Mid: p.border, QPalette.Midlight: p.surface_alt, QPalette.Dark: p.border,
    }
    for role, color in roles.items():
        pal.setColor(role, QColor(color))
    for role in (QPalette.WindowText, QPalette.Text, QPalette.ButtonText):
        pal.setColor(QPalette.Disabled, role, QColor(p.text_muted))
    return pal


def swatch_icon(color: str, selected: bool, size: int = 16):
    """ไอคอนช่องสีในเมนูสีหลัก — สีที่เลือกอยู่มีเครื่องหมายถูกบนช่องสี

    (Qt ไม่แสดงเครื่องหมายถูกของเมนูที่มีไอคอน ผู้ใช้เลยไม่รู้ว่าเลือกสีไหนอยู่)
    """
    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap

    pix = QPixmap(size, size)
    pix.fill(Qt.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor(color))
    painter.drawRoundedRect(1, 1, size - 2, size - 2, 3, 3)
    if selected:
        pen = QPen(QColor(_readable_on(color)), 2.2)
        pen.setCapStyle(Qt.RoundCap)
        painter.setPen(pen)
        painter.drawPolyline([QPointF(size * 0.25, size * 0.52), QPointF(size * 0.43, size * 0.7),
                              QPointF(size * 0.76, size * 0.32)])
    painter.end()
    return QIcon(pix)


def apply(app, palette: Palette | None = None) -> Palette:
    """ใช้ธีมกับทั้งโปรแกรม (เรียกตอนเปิด และทุกครั้งที่ผู้ใช้เปลี่ยนธีม/สี)"""
    p = palette or current_palette()
    from . import icons
    # ไอคอนสี (ค่าเริ่มต้น) หรือขาวดำสีเดียวกับตัวหนังสือ — ธีมมืดทำสีให้สว่างขึ้นเอง
    icons.set_color(p.text, dark=p.dark, colored=colored_icons())
    app.setStyle("Fusion")       # Fusion เปลี่ยนสีตาม palette ได้ครบ (สไตล์ Windows ไม่ยอม)
    app.setPalette(qpalette(p))
    app.setStyleSheet(stylesheet(p))
    return p
