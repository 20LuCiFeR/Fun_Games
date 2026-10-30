import math
import re
import sys

from PySide6.QtCore import Qt, QRect, QSize, Signal, QTimer, QPoint, QPointF
from PySide6.QtGui import (
    QPainter, QColor, QPen, QBrush, QFont, QFontMetrics, QFontDatabase,
    QImage, QPixmap, QIcon, QPolygonF, QAction, QActionGroup, QKeySequence,
    QCursor, QPainterPath
)
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QToolBar, QLabel, QSpinBox,
    QComboBox, QLineEdit, QPushButton, QPlainTextEdit, QTableWidget,
    QTableWidgetItem, QTabWidget, QVBoxLayout, QHBoxLayout,
    QScrollArea, QSplitter, QDialog, QDialogButtonBox,
    QRadioButton, QMessageBox, QFileDialog, QSizePolicy,
    QWidgetAction, QStatusBar, QGroupBox, QCheckBox, QSlider, QInputDialog
)

try:
    from deep_translator import GoogleTranslator
    TRANSLATOR_AVAILABLE = True
except ImportError:
    TRANSLATOR_AVAILABLE = False


# ------------------------------------------------------------------ theme --
BG_DARK = "#1b1e23"
PANEL_BG = "#22262d"
GUTTER_BG = "#191c21"
BTN_BG = "#2d3239"
BTN_ACTIVE = "#3a414a"
ACCENT = "#4d9de0"
TEXT_MAIN = "#e7ebef"
TEXT_MUTED = "#8b93a1"
GRID_COLOR = "#181818"
CANVAS_OFF = "#050505"

ON_COLOR = "#FFFFFF"

PIXEL_SIZE_DEFAULT = 9
PIXEL_SIZE_MIN = 2     # minimum zoom is now 2x2
PIXEL_SIZE_MAX = 32
MAX_UNDO = 60
GUTTER = 34
HANDLE_PX = 10

# Fonts that actually carry Devanagari glyphs (for Hindi rendering). We pick
# the first one installed on the machine; DejaVu Sans (the old default)
# cannot render Hindi at all.
DEVANAGARI_FONT_CANDIDATES = [
    "Noto Sans Devanagari", "Lohit Devanagari", "Mangal", "Nirmala UI",
    "Sarai", "FreeSans",
]
LATIN_FONT_DEFAULT = "DejaVu Sans"

# Common languages for the translate panel: Hindi & English pinned first.
LANGUAGE_CHOICES = [
    ("Hindi", "hi"), ("English", "en"),
    ("Spanish", "es"), ("French", "fr"), ("German", "de"), ("Italian", "it"),
    ("Portuguese", "pt"), ("Russian", "ru"), ("Chinese (Simplified)", "zh-CN"),
    ("Japanese", "ja"), ("Korean", "ko"), ("Arabic", "ar"),
    ("Bengali", "bn"), ("Tamil", "ta"), ("Telugu", "te"), ("Marathi", "mr"),
    ("Gujarati", "gu"), ("Punjabi", "pa"), ("Urdu", "ur"), ("Kannada", "kn"),
    ("Malayalam", "ml"), ("Nepali", "ne"), ("Turkish", "tr"),
    ("Vietnamese", "vi"), ("Thai", "th"), ("Indonesian", "id"),
    ("Dutch", "nl"), ("Polish", "pl"), ("Ukrainian", "uk"),
    ("Swahili", "sw"), ("Persian", "fa"), ("Greek", "el"), ("Hebrew", "iw"),
]

STYLE_SHEET = f"""
QMainWindow, QWidget {{ background: {BG_DARK}; color: {TEXT_MAIN}; font-size: 9pt; }}
QToolBar {{ background: {PANEL_BG}; border: none; spacing: 2px; padding: 3px; }}
QToolButton {{ background: {BTN_BG}; border: 1px solid transparent; border-radius: 5px; padding: 4px; }}
QToolButton:hover {{ background: {BTN_ACTIVE}; border: 1px solid {ACCENT}; }}
QToolButton:checked {{ background: #2a3f52; border: 1px solid {ACCENT}; }}
QPushButton {{ background: {BTN_BG}; border: 1px solid #3a3f47; border-radius: 5px; padding: 4px 8px; }}
QPushButton:hover {{ background: {BTN_ACTIVE}; border: 1px solid {ACCENT}; }}
QPushButton:pressed {{ background: #23272d; }}
#GenerateBtn {{ background: {ACCENT}; color: white; font-weight: 600; border: none; }}
#GenerateBtn:hover {{ background: #3f8ecf; }}
QComboBox, QLineEdit {{
    background: #14171b; border: 1px solid #3a3f47; border-radius: 4px; padding: 3px 5px;
}}
QSpinBox {{
    background: #14171b; border: 1px solid #3a3f47; border-radius: 4px;
    padding: 2px 2px 2px 5px;
}}
QSpinBox::up-button {{
    subcontrol-origin: border; subcontrol-position: top right;
    width: 15px; height: 10px;
    border-left: 1px solid #3a3f47; border-bottom: 1px solid #3a3f47;
    border-top-right-radius: 4px;
    background: #1c2026;
}}
QSpinBox::up-button:hover {{ background: {BTN_ACTIVE}; }}
QSpinBox::up-button:pressed {{ background: #14171b; }}
QSpinBox::down-button {{
    subcontrol-origin: border; subcontrol-position: bottom right;
    width: 15px; height: 10px;
    border-left: 1px solid #3a3f47;
    border-bottom-right-radius: 4px;
    background: #1c2026;
}}
QSpinBox::down-button:hover {{ background: {BTN_ACTIVE}; }}
QSpinBox::down-button:pressed {{ background: #14171b; }}
QSpinBox::up-arrow {{
    width: 0; height: 0;
    border-left: 3px solid transparent; border-right: 3px solid transparent;
    border-bottom: 5px solid {TEXT_MAIN};
}}
QSpinBox::down-arrow {{
    width: 0; height: 0;
    border-left: 3px solid transparent; border-right: 3px solid transparent;
    border-top: 5px solid {TEXT_MAIN};
}}
QGroupBox {{ border: 1px solid #3a3f47; border-radius: 6px; margin-top: 10px; padding-top: 8px; }}
QGroupBox::title {{ subcontrol-origin: margin; left: 8px; padding: 0 4px; color: {TEXT_MUTED}; }}
QTabWidget::pane {{ border: 1px solid #3a3f47; background: {PANEL_BG}; }}
QTabBar::tab {{ background: {BTN_BG}; padding: 6px 14px; border: 1px solid #3a3f47; border-bottom: none; }}
QTabBar::tab:selected {{ background: {PANEL_BG}; color: {ACCENT}; }}
QTableWidget {{ background: #101318; gridline-color: #262b32; border: none; }}
QHeaderView::section {{ background: {PANEL_BG}; color: {TEXT_MUTED}; padding: 3px; border: 1px solid #2a2e35; }}
QPlainTextEdit {{ background: #0a0d10; color: #bfe9ff; border: 1px solid #3a3f47; }}
QScrollArea {{ border: none; }}
QStatusBar {{ background: {PANEL_BG}; color: {TEXT_MUTED}; }}
QSplitter::handle {{ background: #14171b; }}
"""


# ------------------------------------------------------------- geometry ---
def bresenham_line(x0, y0, x1, y1):
    points = []
    dx = abs(x1 - x0)
    dy = -abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx + dy
    x, y = x0, y0
    while True:
        points.append((x, y))
        if x == x1 and y == y1:
            break
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x += sx
        if e2 <= dx:
            err += dx
            y += sy
    return points


def rect_points(x0, y0, x1, y1):
    """Outline only -- use the Fill Bucket tool if you want it filled."""
    x0, x1 = sorted((x0, x1))
    y0, y1 = sorted((y0, y1))
    pts = []
    for x in range(x0, x1 + 1):
        pts.append((x, y0))
        pts.append((x, y1))
    for y in range(y0, y1 + 1):
        pts.append((x0, y))
        pts.append((x1, y))
    return pts


def polygon_outline_points(vertices):
    pts = []
    n = len(vertices)
    for i in range(n):
        x0, y0 = vertices[i]
        x1, y1 = vertices[(i + 1) % n]
        pts.extend(bresenham_line(int(round(x0)), int(round(y0)),
                                   int(round(x1)), int(round(y1))))
    return pts


def ellipse_vertices(cx, cy, rx, ry, steps=None):
    if steps is None:
        steps = max(16, min(360, int(3 * max(rx, ry, 1))))
    verts = []
    for i in range(steps):
        a = 2 * math.pi * i / steps
        verts.append((cx + rx * math.cos(a), cy + ry * math.sin(a)))
    return verts


def triangle_vertices(x0, y0, x1, y1):
    x0, x1 = sorted((x0, x1))
    y0, y1 = sorted((y0, y1))
    return [((x0 + x1) / 2, y0), (x0, y1), (x1, y1)]


def star_vertices(cx, cy, r_outer, r_inner, points=5, rotation=-90):
    verts = []
    for i in range(points * 2):
        angle = math.radians(rotation + i * (360 / (points * 2)))
        r = r_outer if i % 2 == 0 else r_inner
        verts.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))
    return verts


def shape_points(kind, x0, y0, x1, y1):
    """Dispatch: returns list of (x,y) integer pixel points for a shape tool.
    Every shape is an OUTLINE -- fill it afterwards with the Fill Bucket."""
    if kind == "line":
        return bresenham_line(x0, y0, x1, y1)
    if kind == "rect":
        return rect_points(x0, y0, x1, y1)
    if kind == "circle":
        r = int(round(math.hypot(x1 - x0, y1 - y0)))
        return polygon_outline_points(ellipse_vertices(x0, y0, r, r))
    if kind == "ellipse":
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        rx, ry = abs(x1 - x0) / 2, abs(y1 - y0) / 2
        return polygon_outline_points(ellipse_vertices(cx, cy, rx, ry))
    if kind == "triangle":
        return polygon_outline_points(triangle_vertices(x0, y0, x1, y1))
    if kind == "star":
        r_outer = math.hypot(x1 - x0, y1 - y0)
        return polygon_outline_points(star_vertices(x0, y0, r_outer, r_outer * 0.45))
    return []


SHAPE_TOOLS = ("line", "rect", "circle", "ellipse", "triangle", "star")
PENDING_TOOLS = ("text", "image")   # tools that use the drag/resize pending-object flow


# --------------------------------------------------------- image -> mask --
def qimage_to_dithered_mask(qimg, target_w, target_h, invert=False,
                            brightness=0, contrast=0):
    """Scale `qimg` to target_w x target_h, apply brightness/contrast, then
    Floyd-Steinberg-style dither down to 1-bit (Qt's diffuse dither) and
    return a boolean mask (list of rows of bool)."""
    target_w = max(1, int(round(target_w)))
    target_h = max(1, int(round(target_h)))

    gray = qimg.convertToFormat(QImage.Format_Grayscale8)
    scaled = gray.scaled(target_w, target_h, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
    scaled = scaled.convertToFormat(QImage.Format_Grayscale8)

    if brightness or contrast:
        c = max(-100, min(100, contrast))
        factor = (259 * (c + 255)) / (255 * (259 - c)) if c else 1.0
        adjusted = QImage(scaled.size(), QImage.Format_Grayscale8)
        for y in range(target_h):
            for x in range(target_w):
                v = QColor(scaled.pixel(x, y)).red()
                v = factor * (v - 128) + 128 + brightness
                v = max(0, min(255, int(round(v))))
                adjusted.setPixel(x, y, QColor(v, v, v).rgb())
        scaled = adjusted

    mono = scaled.convertToFormat(QImage.Format_Mono, Qt.MonoOnly | Qt.DiffuseDither)

    mask = []
    for y in range(target_h):
        row = []
        for x in range(target_w):
            on = QColor(mono.pixel(x, y)).red() < 128   # dark pixel -> "on" for an OLED
            if invert:
                on = not on
            row.append(on)
        mask.append(row)
    return mask


def contains_devanagari(text):
    return any('\u0900' <= ch <= '\u097F' for ch in text)


def _font_can_render(family, sample="\u0915\u0916\u0917"):
    """Actually probe the font instead of trusting the family name alone --
    some systems register a family under a slightly different spelling
    (e.g. 'Nirmala UI Semilight') so a plain membership check can miss a
    font that is really installed."""
    font = QFont(family, 24)
    fm = QFontMetrics(font)
    if fm.horizontalAdvance(sample) <= 0:
        return False
    return all(fm.inFontUcs4(ord(ch)) for ch in sample)


def pick_font_family(text):
    """Pick a font that can actually render `text`. Returns (family, warning)."""
    if contains_devanagari(text):
        available = list(QFontDatabase.families())
        lower_map = {fam.lower(): fam for fam in available}

        for name in DEVANAGARI_FONT_CANDIDATES:
            if name in available and _font_can_render(name):
                return name, None
            match = lower_map.get(name.lower())
            if not match:
                match = next((fam for fam in available
                              if name.lower() in fam.lower()), None)
            if match and _font_can_render(match):
                return match, None

        for fam in available:
            if _font_can_render(fam):
                return fam, None

        return LATIN_FONT_DEFAULT, (
            "No Devanagari-capable font (e.g. Noto Sans Devanagari, Nirmala UI, "
            "Mangal) was found on this system -- the Hindi text would render as "
            "empty boxes, so nothing will show up on the canvas. Install a "
            "Devanagari font and restart the app."
        )
    return LATIN_FONT_DEFAULT, None


# ------------------------------------------------------------------ icons --
def _draw_bold_arrow_arc(p, cx, cy, r_outer, band, a_start_deg, a_end_deg, fg,
                          arrow_w=None, steps=48):
    """Draw a THICK, FILLED circular-arc arrow (a ring segment ending in a
    solid triangular arrowhead) -- the bold "undo/redo badge" style, instead
    of a thin stroked arc. a_start_deg -> a_end_deg, 0deg = 3 o'clock,
    increasing = clockwise on screen."""
    r_inner = r_outer - band
    if arrow_w is None:
        arrow_w = band * 1.9

    a0 = math.radians(a_start_deg)
    a1 = math.radians(a_end_deg)
    sign = 1 if a1 >= a0 else -1
    # pull the ring back a bit short of the true end angle so the arrowhead
    # (drawn separately) tucks in flush against it instead of overlapping.
    head_len_ang = arrow_w * 1.05 / ((r_outer + r_inner) / 2)
    a1_ring = a1 - sign * head_len_ang

    outer_pts = []
    inner_pts = []
    for i in range(steps + 1):
        t = a0 + (a1_ring - a0) * i / steps
        outer_pts.append(QPointF(cx + r_outer * math.cos(t), cy + r_outer * math.sin(t)))
        inner_pts.append(QPointF(cx + r_inner * math.cos(t), cy + r_inner * math.sin(t)))

    path = QPainterPath()
    path.moveTo(outer_pts[0])
    for pt in outer_pts[1:]:
        path.lineTo(pt)
    for pt in reversed(inner_pts):
        path.lineTo(pt)
    path.closeSubpath()

    # rounded start cap so the tail doesn't look chopped off
    start_mid_r = (r_outer + r_inner) / 2
    cap_r = band / 2
    cap_cx = cx + start_mid_r * math.cos(a0)
    cap_cy = cy + start_mid_r * math.sin(a0)
    path.addEllipse(QPointF(cap_cx, cap_cy), cap_r, cap_r)

    p.setPen(Qt.NoPen)
    p.setBrush(fg)
    p.drawPath(path)

    # arrowhead: solid triangle, tangent to the curve at the true end angle
    tx = -math.sin(a1) * sign
    ty = math.cos(a1) * sign
    px, py = -ty, tx
    mid_r = (r_outer + r_inner) / 2
    tip = QPointF(cx + (mid_r + arrow_w * 0.62) * math.cos(a1),
                  cy + (mid_r + arrow_w * 0.62) * math.sin(a1))
    base_c = QPointF(cx + (mid_r - arrow_w * 0.62) * math.cos(a1) - tx * arrow_w * 0.15,
                      cy + (mid_r - arrow_w * 0.62) * math.sin(a1) - ty * arrow_w * 0.15)
    left = QPointF(base_c.x() + px * arrow_w * 0.95, base_c.y() + py * arrow_w * 0.95)
    right = QPointF(base_c.x() - px * arrow_w * 0.95, base_c.y() - py * arrow_w * 0.95)
    p.drawPolygon(QPolygonF([tip, left, right]))


def make_qicon(kind, size=26, color=TEXT_MAIN):
    """Draw a small, clean vector icon with QPainter and wrap it as a QIcon."""
    pix = QPixmap(size, size)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing, True)
    fg = QColor(color)
    pen = QPen(fg)
    pen.setWidthF(1.8)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    pad = size * 0.16
    w = h = size

    def poly(pts):
        return QPolygonF([QPointF(x, y) for x, y in pts])

    if kind == "pencil":
        p.drawLine(pad, h - pad, w - pad, pad)
        p.setBrush(fg)
        p.drawPolygon(poly([(w - pad, pad), (w - pad - 7, pad), (w - pad, pad + 7)]))
    elif kind == "eraser":
        p.save()
        p.translate(w / 2, h / 2 + h * 0.03)
        p.rotate(-30)
        rect_w, rect_h = w * 0.62, h * 0.36
        p.drawRoundedRect(-rect_w / 2, -rect_h / 2, rect_w, rect_h, 5, 5)
        p.drawLine(-rect_w / 2 + rect_w * 0.4, -rect_h / 2, -rect_w / 2 + rect_w * 0.4, rect_h / 2)
        p.restore()
    elif kind == "fill":
        p.drawPolygon(poly([(w * 0.32, h * 0.85), (w * 0.68, h * 0.85), (w * 0.82, h * 0.48),
                             (w * 0.5, pad), (w * 0.18, h * 0.48)]))
        p.setBrush(fg)
        p.drawEllipse(w * 0.4, h * 0.66, w * 0.2, h * 0.2)
    elif kind == "line":
        p.drawLine(pad, h - pad, w - pad, pad)
    elif kind == "rect":
        p.drawRect(pad, pad, w - 2 * pad, h - 2 * pad)
    elif kind == "circle":
        p.drawEllipse(pad, pad, w - 2 * pad, h - 2 * pad)
    elif kind == "ellipse":
        p.drawEllipse(pad, h * 0.28, w - 2 * pad, h * 0.44)
    elif kind == "triangle":
        p.drawPolygon(poly([(w / 2, pad), (pad, h - pad), (w - pad, h - pad)]))
    elif kind == "star":
        pts = star_vertices(w / 2, h / 2, w / 2 - pad, (w / 2 - pad) * 0.42)
        p.drawPolygon(poly(pts))
    elif kind == "text":
        font = QFont("DejaVu Sans", max(1, int(size * 0.55)))
        font.setBold(True)
        p.setFont(font)
        p.drawText(pix.rect(), Qt.AlignCenter, "A")
    elif kind == "image":
        p.drawRect(pad, pad * 1.3, w - 2 * pad, h - 2.3 * pad)
        p.drawEllipse(w * 0.24, h * 0.28, w * 0.14, h * 0.14)
        p.drawPolygon(poly([(pad, h - pad * 1.3), (w * 0.42, h * 0.5),
                             (w * 0.62, h * 0.68), (w * 0.78, h * 0.42),
                             (w - pad, h - pad * 1.3)]))
    elif kind == "translate":
        p.drawEllipse(pad, pad, w - 2 * pad, h - 2 * pad)
        p.drawLine(pad, h / 2, w - pad, h / 2)
        p.drawEllipse(w * 0.5 - (w * 0.18), pad, w * 0.36, h - 2 * pad)
        p.drawArc(pad, h * 0.28, w - 2 * pad, h * 0.2, 0, 180 * 16)
        p.drawArc(pad, h * 0.52, w - 2 * pad, h * 0.2, 180 * 16, 180 * 16)
    elif kind == "invert":
        p.drawEllipse(pad, pad, w - 2 * pad, h - 2 * pad)
        p.setBrush(fg)
        p.setPen(Qt.NoPen)
        p.setClipRect(w / 2, 0, w / 2, h)
        p.drawEllipse(pad, pad, w - 2 * pad, h - 2 * pad)
        p.setClipping(False)
    elif kind == "flip_h":
        p.drawLine(w / 2, pad, w / 2, h - pad)
        p.setBrush(fg)
        p.drawPolygon(poly([(w * 0.62, h * 0.3), (w - pad, h / 2), (w * 0.62, h * 0.7)]))
        p.setBrush(Qt.NoBrush)
        p.drawPolygon(poly([(w * 0.38, h * 0.3), (pad, h / 2), (w * 0.38, h * 0.7)]))
    elif kind == "flip_v":
        p.drawLine(pad, h / 2, w - pad, h / 2)
        p.setBrush(fg)
        p.drawPolygon(poly([(w * 0.3, h * 0.62), (w / 2, h - pad), (w * 0.7, h * 0.62)]))
        p.setBrush(Qt.NoBrush)
        p.drawPolygon(poly([(w * 0.3, h * 0.38), (w / 2, pad), (w * 0.7, h * 0.38)]))
    elif kind == "undo":
        # plain left arrow -- simple, no circle, no extras.
        p.drawLine(pad, h / 2, w - pad, h / 2)
        p.setBrush(fg)
        p.drawPolygon(poly([(pad, h / 2), (pad + 9, h / 2 - 6), (pad + 9, h / 2 + 6)]))
    elif kind == "redo":
        # plain right arrow -- simple, no circle, no extras.
        p.drawLine(pad, h / 2, w - pad, h / 2)
        p.setBrush(fg)
        p.drawPolygon(poly([(w - pad, h / 2), (w - pad - 9, h / 2 - 6), (w - pad - 9, h / 2 + 6)]))
    elif kind == "zoom_in" or kind == "zoom_out":
        p.drawEllipse(pad, pad, w * 0.55, h * 0.55)
        p.drawLine(w * 0.62, h * 0.62, w - pad, h - pad)
        cx, cy = pad + w * 0.275, pad + h * 0.275
        p.drawLine(cx - 4, cy, cx + 4, cy)
        if kind == "zoom_in":
            p.drawLine(cx, cy - 4, cx, cy + 4)
    elif kind == "new":
        p.drawRect(pad, pad, w - 2 * pad, h - 2 * pad)
        p.drawLine(w * 0.5, h * 0.32, w * 0.5, h * 0.68)
        p.drawLine(w * 0.32, h * 0.5, w * 0.68, h * 0.5)
    elif kind == "save":
        p.drawRect(pad, pad, w - 2 * pad, h - 2 * pad)
        p.setBrush(fg)
        p.drawRect(w * 0.32, pad, w * 0.36, h * 0.3)
    elif kind == "open":
        # a proper folder glyph: back tab + front pocket, outlined so it
        # reads clearly at toolbar size (was previously an odd zig-zag shape).
        p.setBrush(Qt.NoBrush)
        tab_w = w * 0.34
        body_top = h * 0.34
        path = QPainterPath()
        path.moveTo(pad, body_top)
        path.lineTo(pad, h * 0.28)
        path.lineTo(pad + tab_w, h * 0.28)
        path.lineTo(pad + tab_w + h * 0.07, body_top)
        path.lineTo(w - pad, body_top)
        path.lineTo(w - pad, h - pad)
        path.lineTo(pad, h - pad)
        path.closeSubpath()
        p.drawPath(path)
    elif kind == "clear":
        p.drawRect(w * 0.3, h * 0.32, w * 0.4, h * 0.56)
        p.drawLine(w * 0.22, h * 0.28, w * 0.78, h * 0.28)
        p.drawLine(w * 0.42, h * 0.2, w * 0.58, h * 0.2)
    p.end()
    return QIcon(pix)


# -------------------------------------------------------------- dialogs ---
class ResolutionDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Choose OLED resolution")
        self._result = (128, 64)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Select OLED resolution:"))
        self.r1 = QRadioButton("128 x 64 (most common)")
        self.r2 = QRadioButton("128 x 32")
        self.r1.setChecked(True)
        layout.addWidget(self.r1)
        layout.addWidget(self.r2)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def result_size(self):
        return (128, 64) if self.r1.isChecked() else (128, 32)


# ---------------------------------------------------------- pixel canvas --
class PixelCanvas(QWidget):
    """The drawing surface. Owns the pixel grid, undo/redo, shape preview,
    and the "pending object" (text / image) placement system."""

    cursorMoved = Signal(int, int)
    pixelsChanged = Signal()
    pendingChanged = Signal()
    textToolClicked = Signal(int, int)

    def __init__(self, width, height, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)

        self.width_cells = width
        self.height_cells = height
        self.pixel_size = PIXEL_SIZE_DEFAULT
        self.eraser_size = 1
        self.pencil_size = 1
        self.pixels = [[0] * width for _ in range(height)]
        self.on_color = ON_COLOR
        self.byte_order = "vertical"

        self.tool = "pencil"

        self.undo_stack = []
        self.redo_stack = []

        self.drawing = False
        self.shape_base = None
        self.start_cell = None
        self.last_cell = None

        # pending object (text / image) placement state
        self._pending = None
        self._drag_mode = None
        self._drag_anchor = None
        self._orig_pos = None
        self.last_font_warning = None

        self._recompute_size()

    # -------------------------------------------------- geometry helpers --
    @property
    def origin_x(self):
        return GUTTER if self.byte_order == "vertical" else 0

    @property
    def origin_y(self):
        return GUTTER if self.byte_order == "horizontal" else 0

    def _recompute_size(self):
        ps = self.pixel_size
        w = self.origin_x + self.width_cells * ps + 2
        h = self.origin_y + self.height_cells * ps + 2
        self.setFixedSize(w, h)
        self.update()

    def set_byte_order(self, order):
        self.byte_order = order
        self._recompute_size()

    def set_pixel_size(self, size):
        self.pixel_size = max(PIXEL_SIZE_MIN, min(PIXEL_SIZE_MAX, size))
        self._recompute_size()

    def set_tool(self, tool):
        self.tool = tool
        self.update()

    # ------------------------------------------------------- new canvas ---
    def load_pixels(self, width, height, pixels):
        self.width_cells = width
        self.height_cells = height
        self.pixels = pixels
        self.undo_stack.clear()
        self.redo_stack.clear()
        self._pending = None
        self._recompute_size()
        self.pixelsChanged.emit()
        self.pendingChanged.emit()

    def clear_all(self):
        self.push_undo()
        self.pixels = [[0] * self.width_cells for _ in range(self.height_cells)]
        self.pixelsChanged.emit()
        self.update()

    def invert_all(self):
        self.push_undo()
        self.pixels = [[1 - v for v in row] for row in self.pixels]
        self.pixelsChanged.emit()
        self.update()

    def flip_horizontal(self):
        self.push_undo()
        self.pixels = [row[::-1] for row in self.pixels]
        self.pixelsChanged.emit()
        self.update()

    def flip_vertical(self):
        self.push_undo()
        self.pixels = self.pixels[::-1]
        self.pixelsChanged.emit()
        self.update()

    # ------------------------------------------------------- undo / redo --
    def push_undo(self):
        self.undo_stack.append([row[:] for row in self.pixels])
        if len(self.undo_stack) > MAX_UNDO:
            self.undo_stack.pop(0)
        self.redo_stack.clear()

    def undo(self):
        if not self.undo_stack:
            return
        self.redo_stack.append([row[:] for row in self.pixels])
        self.pixels = self.undo_stack.pop()
        self.pixelsChanged.emit()
        self.update()

    def redo(self):
        if not self.redo_stack:
            return
        self.undo_stack.append([row[:] for row in self.pixels])
        self.pixels = self.redo_stack.pop()
        self.pixelsChanged.emit()
        self.update()

    # ------------------------------------------------------------ pixels --
    def _in_bounds(self, x, y):
        return 0 <= x < self.width_cells and 0 <= y < self.height_cells

    def _set_pixel(self, x, y, val):
        if self._in_bounds(x, y):
            self.pixels[y][x] = val

    def _paint_area(self, x, y, size, val):
        half = size // 2
        for dy in range(size):
            for dx in range(size):
                self._set_pixel(x - half + dx, y - half + dy, val)

    def _erase_area(self, x, y, size):
        self._paint_area(x, y, size, 0)

    def _draw_area(self, x, y, size):
        self._paint_area(x, y, size, 1)

    def set_eraser_size(self, size):
        self.eraser_size = max(1, min(20, size))

    def set_pencil_size(self, size):
        self.pencil_size = max(1, min(20, size))

    def flood_fill(self, x, y):
        if not self._in_bounds(x, y):
            return
        target = self.pixels[y][x]
        new_val = 1 - target
        if target == new_val:
            return
        stack = [(x, y)]
        seen = set()
        while stack:
            cx, cy = stack.pop()
            if (cx, cy) in seen or not self._in_bounds(cx, cy):
                continue
            if self.pixels[cy][cx] != target:
                continue
            seen.add((cx, cy))
            self.pixels[cy][cx] = new_val
            stack.extend([(cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)])

    # ------------------------------------------------------- coordinates --
    def _pos_to_cell(self, pos):
        x = (pos.x() - self.origin_x) / self.pixel_size
        y = (pos.y() - self.origin_y) / self.pixel_size
        return x, y

    def _clamped_cell(self, pos):
        x, y = self._pos_to_cell(pos)
        x = max(0, min(self.width_cells - 1, int(x)))
        y = max(0, min(self.height_cells - 1, int(y)))
        return x, y

    # -------------------------------------------------- text mask render --
    def _render_text_mask(self, text, target_w, target_h):
        """Render `text` and stretch it to EXACTLY target_w x target_h pixels,
        then threshold to a monochrome mask. Picks a Devanagari-capable font
        automatically if the text contains Hindi characters."""
        target_w = max(1, int(round(target_w)))
        target_h = max(1, int(round(target_h)))

        family, warning = pick_font_family(text)
        self.last_font_warning = warning

        render_size = max(24, int(target_h * 6))
        font = QFont(family, render_size)
        font.setStyleStrategy(QFont.PreferAntialias)
        fm = QFontMetrics(font)
        br = fm.boundingRect(text)
        src_w = max(1, br.width() + 3)
        src_h = max(1, br.height() + 3)
        img = QImage(src_w, src_h, QImage.Format_Grayscale8)
        img.fill(0)
        p = QPainter(img)
        p.setFont(font)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setPen(QColor(255, 255, 255))
        p.drawText(-br.x() + 1, -br.y() + 1, text)
        p.end()

        scaled = img.scaled(target_w, target_h, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
        mask = [[QColor(scaled.pixel(x, y)).red() > 110 for x in range(target_w)]
                for y in range(target_h)]
        return mask, target_w, target_h

    def natural_text_size(self, text, height_hint=16):
        """A reasonable starting Width for a given Height, based on the
        font's natural aspect ratio -- just a default; fully overridable."""
        family, _ = pick_font_family(text)
        probe = QFont(family, 16)
        fm = QFontMetrics(probe)
        natural_w = max(1, fm.horizontalAdvance(text))
        natural_h = max(1, fm.height())
        h = max(1, height_hint)
        w = max(4, round(natural_w * h / natural_h))
        return w, h

    # ------------------------------------------------------ pending object -
    def _new_pending(self, kind, cell_x, cell_y, w, h, **extra):
        self._pending = {"kind": kind, "x": float(cell_x), "y": float(cell_y),
                          "w": int(w), "h": int(h)}
        self._pending.update(extra)
        self._recompute_pending_mask()
        self.pendingChanged.emit()
        self.update()

    def _recompute_pending_mask(self):
        p = self._pending
        if p is None:
            return
        if p["kind"] == "text":
            mask, w, h = self._render_text_mask(p["text"], p["w"], p["h"])
            p["mask"], p["w"], p["h"] = mask, w, h
        elif p["kind"] == "image":
            mask = qimage_to_dithered_mask(
                p["source_image"], p["w"], p["h"],
                invert=p.get("invert", False),
                brightness=p.get("brightness", 0),
                contrast=p.get("contrast", 0))
            p["mask"] = mask

    def set_pending_text(self, text):
        if not self._pending or self._pending["kind"] != "text":
            return
        self._pending["text"] = text
        self._recompute_pending_mask()
        self.pendingChanged.emit()
        self.update()

    def set_pending_image_options(self, invert=None, brightness=None, contrast=None):
        if not self._pending or self._pending["kind"] != "image":
            return
        if invert is not None:
            self._pending["invert"] = invert
        if brightness is not None:
            self._pending["brightness"] = brightness
        if contrast is not None:
            self._pending["contrast"] = contrast
        self._recompute_pending_mask()
        self.pendingChanged.emit()
        self.update()

    def set_pending_size(self, w, h, lock_aspect=False):
        if not self._pending:
            return
        w = max(1, min(500, int(w)))
        h = max(1, min(500, int(h)))
        if lock_aspect and self._pending.get("aspect_ratio"):
            ar = self._pending["aspect_ratio"]
            h = max(1, round(w / ar))
        self._pending["w"], self._pending["h"] = w, h
        self._recompute_pending_mask()
        self.pendingChanged.emit()
        self.update()

    def set_pending_pos(self, x, y):
        if not self._pending:
            return
        self._pending["x"] = float(x)
        self._pending["y"] = float(y)
        self.update()

    def commit_pending(self):
        if not self._pending:
            return
        self.push_undo()
        x0, y0 = int(round(self._pending["x"])), int(round(self._pending["y"]))
        for ty, row in enumerate(self._pending["mask"]):
            for tx, v in enumerate(row):
                if v:
                    self._set_pixel(x0 + tx, y0 + ty, 1)
        self._pending = None
        self.pendingChanged.emit()
        self.pixelsChanged.emit()
        self.update()

    def cancel_pending(self):
        if not self._pending:
            return
        self._pending = None
        self.pendingChanged.emit()
        self.update()

    def _pending_body_rect(self):
        p = self._pending
        ps = self.pixel_size
        bx = self.origin_x + p["x"] * ps
        by = self.origin_y + p["y"] * ps
        return QRect(int(bx), int(by), int(p["w"] * ps), int(p["h"] * ps))

    def _pending_handle_rect(self):
        body = self._pending_body_rect()
        return QRect(body.right() - HANDLE_PX // 2, body.bottom() - HANDLE_PX // 2,
                     HANDLE_PX, HANDLE_PX)

    # ------------------------------------------------------------- paint --
    def paintEvent(self, event):
        painter = QPainter(self)
        ps = self.pixel_size
        ox, oy = self.origin_x, self.origin_y

        painter.fillRect(self.rect(), QColor(GUTTER_BG))
        if self.byte_order == "vertical":
            painter.fillRect(QRect(0, 0, ox, self.height()), QColor(PANEL_BG))
        else:
            painter.fillRect(QRect(0, 0, self.width(), oy), QColor(PANEL_BG))

        area = QRect(ox, oy, self.width_cells * ps, self.height_cells * ps)
        painter.fillRect(area, QColor(CANVAS_OFF))

        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(self.on_color))
        for y in range(self.height_cells):
            row = self.pixels[y]
            for x in range(self.width_cells):
                if row[x]:
                    painter.drawRect(ox + x * ps, oy + y * ps, ps, ps)

        if ps >= 4:
            painter.setPen(QPen(QColor(GRID_COLOR), 1))
            for gx in range(self.width_cells + 1):
                xx = ox + gx * ps
                painter.drawLine(xx, oy, xx, oy + self.height_cells * ps)
            for gy in range(self.height_cells + 1):
                yy = oy + gy * ps
                painter.drawLine(ox, yy, ox + self.width_cells * ps, yy)

        painter.setRenderHint(QPainter.Antialiasing, True)
        font = QFont("Segoe UI", 8)
        painter.setFont(font)
        sep_color = QColor(TEXT_MUTED)
        sep_color.setAlpha(130)
        sep_pen = QPen(sep_color)
        sep_pen.setWidth(1)
        sep_pen.setStyle(Qt.DotLine)

        if self.byte_order == "vertical":
            pages = math.ceil(self.height_cells / 8)
            if ps >= 4:
                painter.setPen(sep_pen)
                for k in range(1, pages):
                    yy = oy + k * 8 * ps
                    painter.drawLine(ox, yy, ox + self.width_cells * ps, yy)
            painter.setPen(QColor(TEXT_MUTED))
            label_h = 20
            canvas_top = oy
            canvas_bottom = oy + self.height_cells * ps
            for pnum in range(pages):
                band_top = oy + pnum * 8 * ps
                band_h = min(8, self.height_cells - pnum * 8) * ps
                yc = band_top + band_h // 2
                rect_top = yc - label_h // 2
                # P0 must always start fully visible right at the canvas top --
                # never let its label box get pushed above y=0 by the centering
                # math (this was clipping "P0" off at low zoom levels).
                rect_top = max(rect_top, canvas_top)
                rect_top = min(rect_top, canvas_bottom - label_h)
                painter.drawText(QRect(0, rect_top, ox - 4, label_h),
                                  Qt.AlignRight | Qt.AlignVCenter, f"P{pnum}")
        else:
            bcols = math.ceil(self.width_cells / 8)
            if ps >= 4:
                painter.setPen(sep_pen)
                for k in range(1, bcols):
                    xx = ox + k * 8 * ps
                    painter.drawLine(xx, oy, xx, oy + self.height_cells * ps)
            painter.setPen(QColor(TEXT_MUTED))
            for bnum in range(bcols):
                band_w = min(8, self.width_cells - bnum * 8) * ps
                xc = ox + bnum * 8 * ps + band_w // 2
                painter.drawText(QRect(xc - 20, 2, 40, oy - 4),
                                  Qt.AlignHCenter | Qt.AlignVCenter, f"B{bnum}")

        if self._pending:
            body = self._pending_body_rect()
            painter.setBrush(QColor(ACCENT))
            painter.setOpacity(0.55)
            for ty, row in enumerate(self._pending["mask"]):
                for tx, v in enumerate(row):
                    if v:
                        painter.drawRect(body.x() + tx * ps, body.y() + ty * ps, ps, ps)
            painter.setOpacity(1.0)
            pen = QPen(QColor(ACCENT))
            pen.setStyle(Qt.DashLine)
            pen.setWidth(1)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(body)
            handle = self._pending_handle_rect()
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(ACCENT))
            painter.drawRect(handle)

        painter.end()

    # ------------------------------------------------------------- mouse --
    def mousePressEvent(self, event):
        self.setFocus()
        if event.button() != Qt.LeftButton:
            return
        pos = event.position().toPoint()

        if self.tool in PENDING_TOOLS and self._pending:
            if self._pending_handle_rect().contains(pos):
                self._drag_mode = "resize"
                self._drag_anchor = pos
                return
            if self._pending_body_rect().contains(pos):
                self._drag_mode = "move"
                self._drag_anchor = pos
                self._orig_pos = (self._pending["x"], self._pending["y"])
                return
            self.commit_pending()

        if self.tool == "text" and not self._pending:
            x, y = self._clamped_cell(pos)
            self.textToolClicked.emit(x, y)
            return

        if self.tool == "image":
            return  # images are placed via the "Import image" action, not by clicking

        x, y = self._clamped_cell(pos)
        self.push_undo()
        self.start_cell = (x, y)
        self.last_cell = (x, y)

        if self.tool in ("pencil", "eraser"):
            self.drawing = True
            if self.tool == "pencil":
                self._draw_area(x, y, self.pencil_size)
            else:
                self._erase_area(x, y, self.eraser_size)
            self.pixelsChanged.emit()
            self.update()
        elif self.tool == "fill":
            self.flood_fill(x, y)
            self.pixelsChanged.emit()
            self.update()
        elif self.tool in SHAPE_TOOLS:
            self.shape_base = [row[:] for row in self.pixels]

    def mouseMoveEvent(self, event):
        pos = event.position().toPoint()
        fx, fy = self._pos_to_cell(pos)
        self.cursorMoved.emit(int(fx), int(fy))

        if self.tool in PENDING_TOOLS and self._pending and self._drag_mode:
            ps = self.pixel_size
            if self._drag_mode == "move":
                dx = (pos.x() - self._drag_anchor.x()) / ps
                dy = (pos.y() - self._drag_anchor.y()) / ps
                self.set_pending_pos(self._orig_pos[0] + dx, self._orig_pos[1] + dy)
                self.pendingChanged.emit()
            elif self._drag_mode == "resize":
                anchor_x = self.origin_x + self._pending["x"] * ps
                anchor_y = self.origin_y + self._pending["y"] * ps
                new_w = max(1, round((pos.x() - anchor_x) / ps))
                new_h = max(1, round((pos.y() - anchor_y) / ps))
                lock = bool(self._pending.get("aspect_locked"))
                if (new_w, new_h) != (self._pending["w"], self._pending["h"]):
                    self.set_pending_size(new_w, new_h, lock_aspect=lock)
            return

        if self.tool in PENDING_TOOLS and self._pending:
            if self._pending_handle_rect().contains(pos):
                self.setCursor(QCursor(Qt.SizeFDiagCursor))
            elif self._pending_body_rect().contains(pos):
                self.setCursor(QCursor(Qt.SizeAllCursor))
            else:
                self.setCursor(QCursor(Qt.ArrowCursor))

        if not (event.buttons() & Qt.LeftButton):
            return

        x = max(0, min(self.width_cells - 1, int(fx)))
        y = max(0, min(self.height_cells - 1, int(fy)))

        if self.tool in ("pencil", "eraser") and self.drawing:
            if (x, y) != self.last_cell:
                for px, py in bresenham_line(self.last_cell[0], self.last_cell[1], x, y):
                    if self.tool == "pencil":
                        self._draw_area(px, py, self.pencil_size)
                    else:
                        self._erase_area(px, py, self.eraser_size)
                self.last_cell = (x, y)
                self.pixelsChanged.emit()
                self.update()
        elif self.tool in SHAPE_TOOLS and self.shape_base is not None:
            self.pixels = [row[:] for row in self.shape_base]
            x0, y0 = self.start_cell
            for px, py in shape_points(self.tool, x0, y0, x, y):
                self._set_pixel(px, py, 1)
            self.pixelsChanged.emit()
            self.update()

    def mouseReleaseEvent(self, event):
        self.drawing = False
        self.shape_base = None
        self.start_cell = None
        self.last_cell = None
        self._drag_mode = None
        self._drag_anchor = None

    def keyPressEvent(self, event):
        if self._pending and event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self.commit_pending()
        elif self._pending and event.key() == Qt.Key_Escape:
            self.cancel_pending()
        else:
            super().keyPressEvent(event)

    def _enclosing_scroll_area(self):
        area = self.parentWidget()
        while area is not None and not isinstance(area, QScrollArea):
            area = area.parentWidget()
        return area

    def wheelEvent(self, event):
        # Plain wheel/trackpad = scroll vertically, Shift+wheel = scroll
        # horizontally, Ctrl+wheel = zoom. Handled explicitly here rather
        # than relying on default event propagation, which was not reliably
        # reaching the QScrollArea (the canvas has StrongFocus + mouse
        # tracking for drawing, which can swallow wheel events otherwise).
        area = self._enclosing_scroll_area()
        if area is None:
            event.ignore()
            return

        pos = event.position().toPoint() if hasattr(event, "position") else event.pos()

        if event.modifiers() & Qt.ControlModifier:
            # Never resize the canvas mid-stroke: changing pixel_size
            # recomputes the whole widget geometry, which desyncs an
            # in-progress pencil/shape/pending drag and made zoom feel like
            # it was "fighting" with drawing.
            if self.drawing or self.shape_base is not None or self._drag_mode:
                event.accept()
                return

            steps = event.angleDelta().y() / 120
            if not steps:
                event.accept()
                return

            old_ps = self.pixel_size
            # cell coordinate currently under the cursor, so we can put the
            # exact same spot back under the cursor after resizing --
            # zooms into the area you're pointing at instead of the
            # top-left corner.
            fx, fy = self._pos_to_cell(pos)
            hbar, vbar = area.horizontalScrollBar(), area.verticalScrollBar()
            old_hbar_val, old_vbar_val = hbar.value(), vbar.value()

            self.set_pixel_size(old_ps + int(steps))
            new_ps = self.pixel_size
            if new_ps != old_ps:
                mw = self.window()
                if hasattr(mw, "zoom_label"):
                    mw.zoom_label.setText(f"{new_ps}px")
                new_local_x = self.origin_x + fx * new_ps
                new_local_y = self.origin_y + fy * new_ps
                hbar.setValue(round(old_hbar_val + (new_local_x - pos.x())))
                vbar.setValue(round(old_vbar_val + (new_local_y - pos.y())))
            event.accept()
            return

        dy = event.angleDelta().y()
        dx = event.angleDelta().x()
        if event.modifiers() & Qt.ShiftModifier and dy and not dx:
            dx, dy = dy, dx

        if dy:
            vbar = area.verticalScrollBar()
            vbar.setValue(vbar.value() - dy)
        if dx:
            hbar = area.horizontalScrollBar()
            hbar.setValue(hbar.value() - dx)
        event.accept()



# --------------------------------------------------------- main window ----
class MainWindow(QMainWindow):
    def __init__(self, width, height):
        super().__init__()
        self.setWindowTitle("OLED Bitmap Editor")
        self.resize(1300, 860)
        self._icon_refs = []
        self._current_tool = "pencil"
        self._tool_before_pending = "pencil"
        self._table_refresh_timer = QTimer(self)
        self._table_refresh_timer.setSingleShot(True)
        self._table_refresh_timer.timeout.connect(self._refresh_byte_table)

        self.canvas = PixelCanvas(width, height)
        self.canvas.cursorMoved.connect(self._on_cursor_moved)
        self.canvas.pixelsChanged.connect(self._on_pixels_changed)
        self.canvas.pendingChanged.connect(self._sync_pending_panel)
        self.canvas.textToolClicked.connect(self._on_text_tool_clicked)

        self._build_toolbar()
        self._build_central()
        self.setStatusBar(QStatusBar())
        self._update_status()
        self._refresh_byte_table()

        undo_sc = QAction(self)
        undo_sc.setShortcut(QKeySequence("Ctrl+Z"))
        undo_sc.triggered.connect(self.canvas.undo)
        self.addAction(undo_sc)
        redo_sc = QAction(self)
        redo_sc.setShortcut(QKeySequence("Ctrl+Y"))
        redo_sc.triggered.connect(self.canvas.redo)
        self.addAction(redo_sc)
        save_sc = QAction(self)
        save_sc.setShortcut(QKeySequence("Ctrl+S"))
        save_sc.triggered.connect(self.quick_save_export)
        self.addAction(save_sc)

    # --------------------------------------------------------- toolbar ----
    def _tool_action(self, toolbar, kind, tool_name, tooltip, group):
        act = QAction(make_qicon(kind), tooltip, self)
        act.setCheckable(True)
        act.setData(tool_name)
        act.setToolTip(tooltip)
        act.setChecked(tool_name == "pencil")
        group.addAction(act)
        toolbar.addAction(act)
        return act

    def _plain_action(self, toolbar, kind, tooltip, slot):
        act = QAction(make_qicon(kind), tooltip, self)
        act.setToolTip(tooltip)
        act.triggered.connect(slot)
        toolbar.addAction(act)
        return act

    def _build_toolbar(self):
        bar = QToolBar("Tools")
        bar.setMovable(False)
        bar.setIconSize(QSize(19, 19))

        self.addToolBar(bar)

        self._plain_action(bar, "open", "Import from exported .h / .py file", self.import_from_header)
        self._plain_action(bar, "save", "Generate + save export to file (Ctrl+S)", self.quick_save_export)
        bar.addSeparator()

        group = QActionGroup(self)
        group.setExclusive(True)
        self._tool_action(bar, "pencil", "pencil", "Pencil", group)
        bar.addWidget(QLabel(" Pencil:"))
        self.pencil_size_spin = QSpinBox()
        self.pencil_size_spin.setRange(1, 20)
        self.pencil_size_spin.setValue(self.canvas.pencil_size)
        self.pencil_size_spin.setMaximumWidth(48)
        self.pencil_size_spin.setToolTip("Pencil size in pixels")
        self.pencil_size_spin.valueChanged.connect(self.canvas.set_pencil_size)
        bar.addWidget(self.pencil_size_spin)
        self._tool_action(bar, "eraser", "eraser", "Eraser", group)
        bar.addWidget(QLabel(" Eraser:"))
        self.eraser_size_spin = QSpinBox()
        self.eraser_size_spin.setRange(1, 20)
        self.eraser_size_spin.setValue(self.canvas.eraser_size)
        self.eraser_size_spin.setMaximumWidth(48)
        self.eraser_size_spin.setToolTip("Eraser size in pixels")
        self.eraser_size_spin.valueChanged.connect(self.canvas.set_eraser_size)
        bar.addWidget(self.eraser_size_spin)
        self._tool_action(bar, "fill", "fill", "Fill bucket (fill the shapes you draw)", group)
        bar.addSeparator()
        self._plain_action(bar, "invert", "Invert whole canvas (swap on/off pixels)", self.canvas.invert_all)
        self._plain_action(bar, "flip_h", "Flip whole canvas horizontally", self.canvas.flip_horizontal)
        self._plain_action(bar, "flip_v", "Flip whole canvas vertically", self.canvas.flip_vertical)
        bar.addSeparator()
        self._tool_action(bar, "line", "line", "Line", group)
        self._tool_action(bar, "rect", "rect", "Rectangle (outline -- fill with bucket)", group)
        self._tool_action(bar, "circle", "circle", "Circle (outline -- fill with bucket)", group)
        self._tool_action(bar, "ellipse", "ellipse", "Ellipse (outline -- fill with bucket)", group)
        self._tool_action(bar, "triangle", "triangle", "Triangle (outline -- fill with bucket)", group)
        self._tool_action(bar, "star", "star", "Star (outline -- fill with bucket)", group)
        self._tool_action(bar, "text", "text",
                           "Text (type/translate below, then click the canvas to place)", group)
        group.triggered.connect(self._on_tool_changed)
        self.tool_group = group
        bar.addSeparator()

        self._plain_action(bar, "image", "Import image (JPG/JPEG/PNG)...", self.import_image)
        bar.addSeparator()

        bar.addWidget(QLabel(" Res:"))
        self.res_w_spin = QSpinBox()
        self.res_w_spin.setRange(4, 512)
        self.res_w_spin.setSingleStep(4)
        self.res_w_spin.setValue(self.canvas.width_cells)
        self.res_w_spin.setMaximumWidth(58)
        self.res_w_spin.setToolTip("Canvas width (must be a multiple of 4)")
        self.res_w_spin.editingFinished.connect(lambda: self._snap_res_spin(self.res_w_spin))
        bar.addWidget(self.res_w_spin)
        bar.addWidget(QLabel("x"))
        self.res_h_spin = QSpinBox()
        self.res_h_spin.setRange(4, 512)
        self.res_h_spin.setSingleStep(4)
        self.res_h_spin.setValue(self.canvas.height_cells)
        self.res_h_spin.setMaximumWidth(58)
        self.res_h_spin.setToolTip("Canvas height (must be a multiple of 4)")
        self.res_h_spin.editingFinished.connect(lambda: self._snap_res_spin(self.res_h_spin))
        bar.addWidget(self.res_h_spin)
        apply_res_btn = QPushButton("Apply")
        apply_res_btn.setToolTip("Resize the canvas to the resolution above (clears the drawing)")
        bar.addWidget(apply_res_btn)
        apply_res_btn.clicked.connect(self.apply_resolution)
        bar.addSeparator()

        self._plain_action(bar, "undo", "Undo (Ctrl+Z)", self.canvas.undo)
        self._plain_action(bar, "redo", "Redo (Ctrl+Y)", self.canvas.redo)
        bar.addSeparator()
        bar.addWidget(QLabel(" Zoom:"))
        zoom_out_btn = QPushButton()
        zoom_out_btn.setIcon(make_qicon("zoom_out"))
        zoom_out_btn.setToolTip("Zoom out (min 2x2)")
        zoom_out_btn.setMaximumWidth(28)
        zoom_out_btn.clicked.connect(lambda: self._zoom(-1))
        bar.addWidget(zoom_out_btn)
        self.zoom_label = QLabel(f"{self.canvas.pixel_size}px")
        self.zoom_label.setAlignment(Qt.AlignCenter)
        self.zoom_label.setMinimumWidth(32)
        bar.addWidget(self.zoom_label)
        zoom_in_btn = QPushButton()
        zoom_in_btn.setIcon(make_qicon("zoom_in"))
        zoom_in_btn.setToolTip("Zoom in")
        zoom_in_btn.setMaximumWidth(28)
        zoom_in_btn.clicked.connect(lambda: self._zoom(1))
        bar.addWidget(zoom_in_btn)
        bar.addSeparator()
        self._plain_action(bar, "clear", "Clear all", self.clear_all)

    def _on_tool_changed(self, action):
        new_tool = action.data()
        if self._current_tool in PENDING_TOOLS and new_tool != self._current_tool and self.canvas._pending:
            self.canvas.commit_pending()
        self._current_tool = new_tool
        self.canvas.set_tool(new_tool)

    def _zoom(self, delta):
        area = getattr(self, "canvas_scroll", None)
        if area is None:
            self.canvas.set_pixel_size(self.canvas.pixel_size + delta)
            self.zoom_label.setText(f"{self.canvas.pixel_size}px")
            return
        vp = area.viewport()
        center = QPoint(vp.width() // 2, vp.height() // 2)
        hbar, vbar = area.horizontalScrollBar(), area.verticalScrollBar()
        old_hbar_val, old_vbar_val = hbar.value(), vbar.value()
        canvas_local = center + QPoint(old_hbar_val, old_vbar_val)
        fx, fy = self.canvas._pos_to_cell(canvas_local)
        old_ps = self.canvas.pixel_size
        self.canvas.set_pixel_size(old_ps + delta)
        new_ps = self.canvas.pixel_size
        self.zoom_label.setText(f"{new_ps}px")
        if new_ps != old_ps:
            new_local_x = self.canvas.origin_x + fx * new_ps
            new_local_y = self.canvas.origin_y + fy * new_ps
            hbar.setValue(round(new_local_x - center.x()))
            vbar.setValue(round(new_local_y - center.y()))

    def _snap_res_spin(self, spin):
        """Force the resolution spinboxes to stay on multiples of 4."""
        snapped = max(4, round(spin.value() / 4) * 4)
        if snapped != spin.value():
            spin.blockSignals(True)
            spin.setValue(snapped)
            spin.blockSignals(False)

    def apply_resolution(self):
        self._snap_res_spin(self.res_w_spin)
        self._snap_res_spin(self.res_h_spin)
        w = self.res_w_spin.value()
        h = self.res_h_spin.value()
        if w == self.canvas.width_cells and h == self.canvas.height_cells:
            return
        reply = QMessageBox.question(
            self, "Change resolution",
            f"Resize canvas to {w} x {h}? This clears the current drawing.",
            QMessageBox.Yes | QMessageBox.No)
        if reply != QMessageBox.Yes:
            return
        self.canvas.load_pixels(w, h, [[0] * w for _ in range(h)])
        self._update_status()
        self._refresh_byte_table()

    def clear_all(self):
        reply = QMessageBox.question(self, "Clear all", "Clear the whole canvas?",
                                      QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.canvas.clear_all()

    # -------------------------------------------------- text / translate --
    def _build_text_panel(self):
        box = QGroupBox("Text / Translate  (select the Text tool, then click the canvas to place)")
        v = QVBoxLayout(box)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Text:"))
        self.text_edit = QLineEdit()
        self.text_edit.setPlaceholderText("Type text here, translate it if you like, then click the canvas")
        self.text_edit.textChanged.connect(self._on_text_edit_changed)
        row1.addWidget(self.text_edit, 1)

        translate_toggle = QPushButton()
        translate_toggle.setIcon(make_qicon("translate", size=20))
        translate_toggle.setCheckable(True)
        translate_toggle.setToolTip("Show/hide translation controls")
        translate_toggle.setFixedWidth(34)
        translate_toggle.toggled.connect(self._toggle_translate_panel)
        row1.addWidget(translate_toggle)
        v.addLayout(row1)

        self.translate_panel = QWidget()
        tv = QVBoxLayout(self.translate_panel)
        tv.setContentsMargins(0, 0, 0, 0)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("From:"))
        self.lang_from = QComboBox()
        self.lang_from.addItem("Auto-detect", "auto")
        for name, code in LANGUAGE_CHOICES:
            self.lang_from.addItem(name, code)
        row2.addWidget(self.lang_from)

        row2.addWidget(QLabel("To:"))
        self.lang_to = QComboBox()
        for name, code in LANGUAGE_CHOICES:
            self.lang_to.addItem(name, code)
        row2.addWidget(self.lang_to)

        translate_btn = QPushButton("Translate")
        translate_btn.clicked.connect(self.do_translate)
        row2.addWidget(translate_btn)
        row2.addStretch(1)
        tv.addLayout(row2)

        hint = QLabel("Translation uses Google Translate online (via deep-translator) -- needs internet."
                       if TRANSLATOR_AVAILABLE else
                       "deep-translator is not installed -- run: pip install deep-translator --break-system-packages")
        hint.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 8pt;")
        tv.addWidget(hint)

        self.translate_panel.setVisible(False)  # hidden until the toggle icon is clicked
        v.addWidget(self.translate_panel)

        return box

    def _toggle_translate_panel(self, checked):
        self.translate_panel.setVisible(checked)

    def _on_text_edit_changed(self, text):
        if self.canvas._pending and self.canvas._pending.get("kind") == "text":
            self.canvas.set_pending_text(text)
            if self.canvas.last_font_warning:
                self.statusBar().showMessage(self.canvas.last_font_warning, 8000)

    def do_translate(self):
        text = self.text_edit.text().strip()
        if not text:
            QMessageBox.information(self, "Translate", "Type some text first.")
            return
        if not TRANSLATOR_AVAILABLE:
            QMessageBox.warning(self, "Translate",
                                 "deep-translator is not installed.\n\n"
                                 "Run:  pip install deep-translator --break-system-packages")
            return
        src = self.lang_from.currentData()
        dst = self.lang_to.currentData()
        try:
            result = GoogleTranslator(source=src, target=dst).translate(text)
        except Exception as e:
            QMessageBox.warning(self, "Translate failed",
                                 "Could not reach the translation service.\n\n"
                                 f"{e}\n\nCheck your internet connection and try again.")
            return
        if not result:
            QMessageBox.warning(self, "Translate failed", "No translation was returned. Try again.")
            return
        self.text_edit.setText(result)  # triggers _on_text_edit_changed -> updates pending too

    def _on_text_tool_clicked(self, x, y):
        text = self.text_edit.text().strip()
        if not text:
            QMessageBox.information(
                self, "Text tool",
                "Type (or translate) some text in the Text / Translate panel above, "
                "then click the canvas to place it.")
            return
        w, h = self.canvas.natural_text_size(text, min(self.canvas.height_cells, 16))
        self._tool_before_pending = self._current_tool
        self.canvas._new_pending("text", x, y, w, h, text=text)
        if self.canvas.last_font_warning:
            self.statusBar().showMessage(self.canvas.last_font_warning, 8000)
            QMessageBox.warning(self, "Font not available", self.canvas.last_font_warning)

    # -------------------------------------------------------- image import -
    @staticmethod
    def _load_image_via_opencv(path):
        """Fallback for files Qt's own plugins can't decode (odd JPEG color
        profiles, 16-bit PNGs, etc). Reads with OpenCV and converts straight
        to grayscale ourselves, since that's what we need anyway."""
        try:
            import cv2
            import numpy as np
        except ImportError:
            return None
        try:
            arr = cv2.imread(path, cv2.IMREAD_UNCHANGED)
            if arr is None:
                return None
            if arr.ndim == 2:
                gray = arr
            elif arr.shape[2] == 4:
                gray = cv2.cvtColor(arr, cv2.COLOR_BGRA2GRAY)
            else:
                gray = cv2.cvtColor(arr, cv2.COLOR_BGR2GRAY)
            if gray.dtype != np.uint8:
                gray = cv2.normalize(gray, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
            gray = np.ascontiguousarray(gray)
            h, w = gray.shape
            qimg = QImage(gray.data, w, h, w, QImage.Format_Grayscale8)
            return qimg.copy()  # detach from the numpy buffer above
        except Exception:
            return None

    @staticmethod
    def _load_image_via_pillow(path):
        try:
            from PIL import Image
        except ImportError:
            return None
        try:
            with Image.open(path) as im:
                im = im.convert("RGB")
                w, h = im.size
                data = im.tobytes("raw", "RGB")
                qimg = QImage(data, w, h, w * 3, QImage.Format_RGB888)
                return qimg.copy()  # detach from the bytes buffer above
        except Exception:
            return None

    def import_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Import image", "", "Images (*.png *.jpg *.jpeg *.bmp)")
        if not path:
            return

        # Don't silently clobber a text/image object the user hasn't
        # committed yet.
        if self.canvas._pending:
            self.canvas.commit_pending()

        img = QImage(path)
        if img.isNull():
            # Qt's built-in plugins sometimes choke on real-world photos
            # (progressive/CMYK JPEGs, unusual color profiles, 16-bit PNGs,
            # etc). Try OpenCV first (per user preference), then Pillow.
            img = self._load_image_via_opencv(path)
        if img is None or img.isNull():
            img = self._load_image_via_pillow(path)

        if img is None or img.isNull():
            QMessageBox.warning(
                self, "Import image",
                f"Could not load '{path}'.\n\n"
                "This usually means the file is corrupted, uses a color "
                "format none of Qt/OpenCV/Pillow can decode, or isn't "
                "actually a PNG/JPEG/BMP despite its extension.")
            return
        gray = img.convertToFormat(QImage.Format_Grayscale8)

        max_w, max_h = self.canvas.width_cells, self.canvas.height_cells
        scale = min(max_w / gray.width(), max_h / gray.height(), 1.0)
        if scale <= 0:
            scale = 1.0
        w = max(1, round(gray.width() * scale))
        h = max(1, round(gray.height() * scale))

        self._tool_before_pending = self._current_tool
        self._current_tool = "image"
        self.canvas.set_tool("image")
        self.canvas._new_pending(
            "image", 0, 0, w, h,
            source_image=gray, invert=False, brightness=0, contrast=0,
            aspect_locked=True, aspect_ratio=gray.width() / gray.height())

    # ------------------------------------------------- pending object panel
    def _build_pending_panel(self):
        box = QGroupBox("Placement -- drag to move, drag the corner handle to resize, "
                         "Enter/Commit to bake in, Esc/Cancel to discard")
        v = QVBoxLayout(box)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("X:"))
        self.obj_x = QSpinBox(); self.obj_x.setRange(-999, 999)
        row1.addWidget(self.obj_x)
        row1.addWidget(QLabel("Y:"))
        self.obj_y = QSpinBox(); self.obj_y.setRange(-999, 999)
        row1.addWidget(self.obj_y)
        row1.addWidget(QLabel("Width:"))
        self.obj_w = QSpinBox(); self.obj_w.setRange(1, 500)
        row1.addWidget(self.obj_w)
        row1.addWidget(QLabel("Height:"))
        self.obj_h = QSpinBox(); self.obj_h.setRange(1, 500)
        row1.addWidget(self.obj_h)

        self.obj_aspect = QCheckBox("Lock aspect ratio")
        self.obj_aspect.stateChanged.connect(self._on_aspect_toggled)
        row1.addWidget(self.obj_aspect)

        commit_btn = QPushButton("Commit (Enter)")
        commit_btn.clicked.connect(self.canvas.commit_pending)
        row1.addWidget(commit_btn)
        cancel_btn = QPushButton("Cancel (Esc)")
        cancel_btn.clicked.connect(self.canvas.cancel_pending)
        row1.addWidget(cancel_btn)
        row1.addStretch(1)
        v.addLayout(row1)

        row2 = QHBoxLayout()
        self.obj_invert = QCheckBox("Invert")
        self.obj_invert.stateChanged.connect(self._on_image_options_changed)
        row2.addWidget(self.obj_invert)
        row2.addWidget(QLabel("Brightness:"))
        self.obj_brightness = QSlider(Qt.Horizontal)
        self.obj_brightness.setRange(-100, 100)
        self.obj_brightness.setValue(0)
        self.obj_brightness.valueChanged.connect(self._on_image_options_changed)
        row2.addWidget(self.obj_brightness)
        row2.addWidget(QLabel("Contrast:"))
        self.obj_contrast = QSlider(Qt.Horizontal)
        self.obj_contrast.setRange(-100, 100)
        self.obj_contrast.setValue(0)
        self.obj_contrast.valueChanged.connect(self._on_image_options_changed)
        row2.addWidget(self.obj_contrast)
        self.image_options_row = row2
        v.addLayout(row2)

        for box_ in (self.obj_x, self.obj_y, self.obj_w, self.obj_h):
            box_.valueChanged.connect(self._panel_edited)

        box.setVisible(False)
        self.pending_panel = box
        return box

    def _set_image_controls_visible(self, visible):
        self.obj_invert.setVisible(visible)
        self.obj_brightness.setVisible(visible)
        self.obj_contrast.setVisible(visible)
        self.obj_aspect.setVisible(visible)

    def _sync_pending_panel(self):
        pending = self.canvas._pending
        if pending is None:
            # restore whichever exclusive tool was active before an image import
            if self._current_tool == "image":
                prev = self._tool_before_pending or "pencil"
                self._current_tool = prev
                self.canvas.set_tool(prev)
                for act in self.tool_group.actions():
                    if act.data() == prev:
                        act.setChecked(True)
            elif self._current_tool == "text":
                # once a text object is placed (or cancelled), jump back to
                # Pencil -- no need to stay parked on the Text tool.
                self._current_tool = "pencil"
                self.canvas.set_tool("pencil")
                for act in self.tool_group.actions():
                    if act.data() == "pencil":
                        act.setChecked(True)
            self.pending_panel.setVisible(False)
            return

        self.pending_panel.setVisible(True)
        is_image = pending["kind"] == "image"
        self._set_image_controls_visible(is_image)

        for box_, val in ((self.obj_x, round(pending["x"])),
                           (self.obj_y, round(pending["y"])),
                           (self.obj_w, pending["w"]),
                           (self.obj_h, pending["h"])):
            box_.blockSignals(True)
            box_.setValue(val)
            box_.blockSignals(False)

        if is_image:
            self.obj_aspect.blockSignals(True)
            self.obj_aspect.setChecked(bool(pending.get("aspect_locked")))
            self.obj_aspect.blockSignals(False)
            self.obj_invert.blockSignals(True)
            self.obj_invert.setChecked(bool(pending.get("invert")))
            self.obj_invert.blockSignals(False)
            self.obj_brightness.blockSignals(True)
            self.obj_brightness.setValue(pending.get("brightness", 0))
            self.obj_brightness.blockSignals(False)
            self.obj_contrast.blockSignals(True)
            self.obj_contrast.setValue(pending.get("contrast", 0))
            self.obj_contrast.blockSignals(False)

    def _panel_edited(self, _value):
        if not self.canvas._pending:
            return
        self.canvas.set_pending_pos(self.obj_x.value(), self.obj_y.value())
        lock = self.canvas._pending["kind"] == "image" and self.obj_aspect.isChecked()
        self.canvas.set_pending_size(self.obj_w.value(), self.obj_h.value(), lock_aspect=lock)

    def _on_aspect_toggled(self, _state):
        if not self.canvas._pending:
            return
        self.canvas._pending["aspect_locked"] = self.obj_aspect.isChecked()

    def _on_image_options_changed(self, _value):
        if not self.canvas._pending or self.canvas._pending["kind"] != "image":
            return
        self.canvas.set_pending_image_options(
            invert=self.obj_invert.isChecked(),
            brightness=self.obj_brightness.value(),
            contrast=self.obj_contrast.value())

    # --------------------------------------------------------- central ----
    def _build_central(self):
        central = QWidget()
        outer = QVBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self._build_text_panel())
        outer.addWidget(self._build_pending_panel())

        splitter = QSplitter(Qt.Vertical)

        scroll = QScrollArea()
        scroll.setWidget(self.canvas)
        scroll.setWidgetResizable(False)
        scroll.setAlignment(Qt.AlignCenter)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.canvas_scroll = scroll
        splitter.addWidget(scroll)

        tabs = QTabWidget()
        tabs.addTab(self._build_export_tab(), "Export")
        tabs.addTab(self._build_byte_table_tab(), "Byte Table (live, by page)")
        splitter.addWidget(tabs)
        splitter.setSizes([520, 300])

        outer.addWidget(splitter)
        self.setCentralWidget(central)

    def _build_export_tab(self):
        w = QWidget()
        v = QVBoxLayout(w)

        # Compact single-row layout: byte order / export area / output format
        # / variable name / action buttons all on one line, with the long
        # explanatory text moved into tooltips instead of inline QLabels
        # (was 3 separate rows -- this was eating too much vertical space).
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Order:"))
        self.byte_order_combo = QComboBox()
        self.byte_order_combo.addItems(["vertical", "horizontal"])
        self.byte_order_combo.setToolTip(
            "vertical = SSD1306 native/paged, matches your Excel;\n"
            "horizontal = row-major, standard drawBitmap")
        self.byte_order_combo.currentTextChanged.connect(self._on_byte_order_changed)
        row1.addWidget(self.byte_order_combo)

        row1.addWidget(QLabel("Area:"))
        self.export_area_combo = QComboBox()
        self.export_area_combo.addItems(["full", "crop"])
        self.export_area_combo.setToolTip(
            "full = whole screen, crop = only the area you drew (page/byte aligned)")
        row1.addWidget(self.export_area_combo)

        row1.addWidget(QLabel("Format:"))
        self.format_combo = QComboBox()
        self.format_combo.addItems(["c", "python", "raw"])
        self.format_combo.setToolTip(
            "'c' or 'python' embed a metadata comment that lets you re-import\n"
            "this exact drawing later via the folder toolbar button.\n"
            "'raw' cannot be re-imported.")
        row1.addWidget(self.format_combo)

        row1.addWidget(QLabel("Name:"))
        self.varname_edit = QLineEdit("bitmap")
        self.varname_edit.setMaximumWidth(120)
        row1.addWidget(self.varname_edit)

        gen_btn = QPushButton("Generate")
        gen_btn.setObjectName("GenerateBtn")
        gen_btn.clicked.connect(self.generate)
        row1.addWidget(gen_btn)
        copy_btn = QPushButton("Copy")
        copy_btn.clicked.connect(self.copy_output)
        row1.addWidget(copy_btn)
        save_btn = QPushButton("Save to file...")
        save_btn.clicked.connect(self.save_output_to_file)
        row1.addWidget(save_btn)
        row1.addStretch(1)
        v.addLayout(row1)

        self.meta_label = QLabel("")
        self.meta_label.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 8pt;")
        v.addWidget(self.meta_label)

        self.output_box = QPlainTextEdit()
        self.output_box.setReadOnly(False)
        v.addWidget(self.output_box, 1)
        return w

    def _build_byte_table_tab(self):
        w = QWidget()
        v = QVBoxLayout(w)
        info = QLabel("Live hex grid of the whole screen -- one row per page (or per row, "
                       "in horizontal byte-order), same layout as your spreadsheet.")
        info.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 8pt;")
        v.addWidget(info)
        self.byte_table = QTableWidget()
        v.addWidget(self.byte_table, 1)
        return w

    # ----------------------------------------------------------- events ---
    def _on_cursor_moved(self, x, y):
        self.statusBar().showMessage(
            f"{self.canvas.width_cells} x {self.canvas.height_cells}  |  cursor: ({x},{y})")

    def _on_pixels_changed(self):
        self._table_refresh_timer.start(120)

    def _update_status(self):
        self.statusBar().showMessage(
            f"{self.canvas.width_cells} x {self.canvas.height_cells}  |  "
            f"pages: {self.canvas.height_cells // 8}")

    def _on_byte_order_changed(self, order):
        self.canvas.set_byte_order(order)
        self._refresh_byte_table()

    # ------------------------------------------------------- byte export --
    def _bounding_box(self):
        pixels = self.canvas.pixels
        w, h = self.canvas.width_cells, self.canvas.height_cells
        min_x = min_y = max_x = max_y = None
        for y in range(h):
            row = pixels[y]
            for x in range(w):
                if row[x]:
                    if min_x is None or x < min_x:
                        min_x = x
                    if max_x is None or x > max_x:
                        max_x = x
                    if min_y is None or y < min_y:
                        min_y = y
                    if max_y is None or y > max_y:
                        max_y = y
        if min_x is None:
            return None
        return min_x, max_x, min_y, max_y

    def _to_bytes(self, order, crop):
        pixels = self.canvas.pixels
        w, h = self.canvas.width_cells, self.canvas.height_cells
        x0, x1, y0, y1 = 0, w - 1, 0, h - 1
        cropped = False

        if crop:
            bbox = self._bounding_box()
            if bbox is None:
                return [], [], None
            bx0, bx1, by0, by1 = bbox
            if order == "vertical":
                x0, x1 = bx0, bx1
                y0 = (by0 // 8) * 8
                y1 = min(h - 1, ((by1 // 8) + 1) * 8 - 1)
            else:
                y0, y1 = by0, by1
                x0 = (bx0 // 8) * 8
                x1 = min(w - 1, ((bx1 // 8) + 1) * 8 - 1)
            cropped = True

        width_used = x1 - x0 + 1
        height_used = y1 - y0 + 1
        out = []
        page_rows = []

        if order == "vertical":
            pages = height_used // 8
            for page in range(pages):
                row = []
                for x in range(x0, x1 + 1):
                    b = 0
                    for bit in range(8):
                        y = y0 + page * 8 + bit
                        if pixels[y][x]:
                            b |= (1 << bit)
                    row.append(b)
                page_rows.append(row)
                out.extend(row)
            meta = dict(order=order, x_offset=x0, y_offset=y0, page_offset=y0 // 8,
                        width=width_used, height=height_used, pages=pages,
                        cropped=cropped, count=len(out))
        else:
            for y in range(y0, y1 + 1):
                row = []
                for xbyte in range(x0, x1 + 1, 8):
                    b = 0
                    for bit in range(8):
                        x = xbyte + bit
                        if x <= x1 and pixels[y][x]:
                            b |= (1 << (7 - bit))
                    row.append(b)
                page_rows.append(row)
                out.extend(row)
            meta = dict(order=order, x_offset=x0, y_offset=y0, byte_offset=x0 // 8,
                        width=width_used, height=height_used,
                        bytes_per_row=width_used // 8, cropped=cropped, count=len(out))
        return out, page_rows, meta

    def _refresh_byte_table(self):
        order = self.canvas.byte_order
        _, page_rows, meta = self._to_bytes(order, crop=False)
        table = self.byte_table
        table.clear()
        if meta is None:
            table.setRowCount(0)
            table.setColumnCount(0)
            return
        rows = len(page_rows)
        cols = max((len(r) for r in page_rows), default=0)
        table.setRowCount(rows)
        table.setColumnCount(cols)
        label = "Page" if order == "vertical" else "Row"
        table.setVerticalHeaderLabels([f"{label} {i}" for i in range(rows)])
        col_label = "x" if order == "vertical" else "B"
        table.setHorizontalHeaderLabels([f"{col_label}{i}" for i in range(cols)])
        for r, row in enumerate(page_rows):
            for c, val in enumerate(row):
                item = QTableWidgetItem(f"0x{val:02X}")
                item.setTextAlignment(Qt.AlignCenter)
                if val == 0:
                    item.setForeground(QColor(TEXT_MUTED))
                table.setItem(r, c, item)
        table.resizeColumnsToContents()

    def generate(self):
        order = self.byte_order_combo.currentText()
        crop = self.export_area_combo.currentText() == "crop"
        data, page_rows, meta = self._to_bytes(order, crop)
        if meta is None:
            QMessageBox.warning(self, "Nothing drawn",
                                 "Draw something first, or switch Export area to 'full'.")
            return

        name = self.varname_edit.text().strip() or "bitmap"
        fmt = self.format_combo.currentText()

        if meta["order"] == "vertical":
            meta_txt = (f"{meta['width']}x{meta['height']}px  |  vertical/paged  |  "
                        f"x_offset={meta['x_offset']}  page_offset={meta['page_offset']}  "
                        f"pages={meta['pages']}  |  {meta['count']} bytes"
                        + ("  (cropped to drawing)" if meta["cropped"] else "  (full screen)"))
        else:
            meta_txt = (f"{meta['width']}x{meta['height']}px  |  horizontal/row-major  |  "
                        f"x_offset={meta['x_offset']}  y_offset={meta['y_offset']}  "
                        f"bytes/row={meta['bytes_per_row']}  |  {meta['count']} bytes"
                        + ("  (cropped to drawing)" if meta["cropped"] else "  (full screen)"))
        self.meta_label.setText(meta_txt)

        if fmt == "raw":
            label = "P" if meta["order"] == "vertical" else "Row"
            lines = []
            for idx, row in enumerate(page_rows):
                real_index = (meta["page_offset"] if meta["order"] == "vertical"
                              else meta["y_offset"]) + idx
                lines.append(f"{label}{real_index}:\t" + "\t".join(f"0x{b:X}" for b in row))
            text = "\n".join(lines)
        else:
            comment = "//" if fmt == "c" else "#"
            label = "Page" if meta["order"] == "vertical" else "Row"
            out_lines = []
            byte_cursor = 0
            for idx, row in enumerate(page_rows):
                real_index = (meta["page_offset"] if meta["order"] == "vertical"
                              else meta["y_offset"]) + idx
                start_i, end_i = byte_cursor, byte_cursor + len(row) - 1
                if meta["order"] == "vertical":
                    extra = f"columns {meta['x_offset']}-{meta['x_offset'] + meta['width'] - 1}"
                else:
                    extra = f"y={real_index}"
                out_lines.append(
                    f"  {comment} {label} {real_index}  ({extra}, {len(row)} bytes, "
                    f"array index {start_i}-{end_i})")
                hexvals = ", ".join(f"0x{b:02X}" for b in row)
                is_last = (idx == len(page_rows) - 1)
                out_lines.append(f"  {hexvals}" + ("" if is_last else ","))
                byte_cursor += len(row)
            body = "\n".join(out_lines)
            if fmt == "c":
                text = (f"// '{name}', {meta_txt}\n"
                        f"const unsigned char {name}[] PROGMEM = {{\n{body}\n}};\n")
            else:
                text = (f"# '{name}', {meta_txt}\n"
                        f"{name} = bytearray([\n{body}\n])\n")

        self.output_box.setPlainText(text)

    def copy_output(self):
        text = self.output_box.toPlainText().strip()
        if not text:
            self.generate()
            text = self.output_box.toPlainText().strip()
        QApplication.clipboard().setText(text)
        QMessageBox.information(self, "Copied", "Output copied to clipboard.")

    def save_output_to_file(self):
        text = self.output_box.toPlainText().strip()
        if not text:
            self.generate()
            text = self.output_box.toPlainText().strip()
        fmt = self.format_combo.currentText()
        ext = ".py" if fmt == "python" else (".h" if fmt == "c" else ".txt")
        path, _ = QFileDialog.getSaveFileName(
            self, "Save output", f"{self.varname_edit.text() or 'bitmap'}{ext}")
        if path:
            with open(path, "w") as f:
                f.write(text)
            QMessageBox.information(self, "Saved", f"Saved to {path}")

    def quick_save_export(self):
        self.generate()
        self.save_output_to_file()

    # ------------------------------------------------- import from .h/.py -
    _META_RE = re.compile(
        r'(\d+)x(\d+)px\s*\|\s*(vertical|horizontal)[^|]*\|\s*'
        r'x_offset=(-?\d+)\s+(?:page_offset=(-?\d+)|y_offset=(-?\d+))',
        re.IGNORECASE)
    _HEX_RE = re.compile(r'0x([0-9A-Fa-f]{1,2})')

    def _parse_exported_text(self, text):
        m = self._META_RE.search(text)
        if not m:
            raise ValueError(
                "Couldn't find the export metadata comment (the '// WxHpx | ...' line).\n"
                "Only files exported by this tool's 'c' or 'python' format can be re-imported "
                "-- 'raw' exports don't carry that metadata.")
        width, height = int(m.group(1)), int(m.group(2))
        order = m.group(3).lower()
        x_off = int(m.group(4))
        if order == "vertical":
            y_off = int(m.group(5)) * 8
        else:
            y_off = int(m.group(6))

        body = text[m.end():]
        hex_vals = [int(h, 16) for h in self._HEX_RE.findall(body)]
        if not hex_vals:
            raise ValueError("No hex byte values (0x..) found after the metadata line.")
        return width, height, order, x_off, y_off, hex_vals

    def _rebuild_pixels_from_bytes(self, width, height, order, x_off, y_off, hex_vals):
        cw, ch = self.canvas.width_cells, self.canvas.height_cells
        pixels = [[0] * cw for _ in range(ch)]
        idx = 0
        if order == "vertical":
            pages = height // 8
            for page in range(pages):
                for x in range(width):
                    if idx >= len(hex_vals):
                        break
                    b = hex_vals[idx]
                    idx += 1
                    xx = x_off + x
                    for bit in range(8):
                        yy = y_off + page * 8 + bit
                        if 0 <= xx < cw and 0 <= yy < ch and (b >> bit) & 1:
                            pixels[yy][xx] = 1
        else:
            bytes_per_row = width // 8
            for row in range(height):
                yy = y_off + row
                for bcol in range(bytes_per_row):
                    if idx >= len(hex_vals):
                        break
                    b = hex_vals[idx]
                    idx += 1
                    for bit in range(8):
                        xx = x_off + bcol * 8 + bit
                        if 0 <= xx < cw and 0 <= yy < ch and (b >> (7 - bit)) & 1:
                            pixels[yy][xx] = 1
        return pixels

    def import_from_header(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Import from exported file", "",
            "Header / Python (*.h *.py);;Text files (*.txt);;All files (*)")
        if not path:
            return
        try:
            with open(path, "r", errors="ignore") as f:
                text = f.read()
            width, height, order, x_off, y_off, hex_vals = self._parse_exported_text(text)
            pixels = self._rebuild_pixels_from_bytes(width, height, order, x_off, y_off, hex_vals)
        except (ValueError, OSError) as e:
            QMessageBox.warning(self, "Import failed", str(e))
            return

        self.canvas.load_pixels(self.canvas.width_cells, self.canvas.height_cells, pixels)
        self.byte_order_combo.blockSignals(True)
        self.byte_order_combo.setCurrentText(order)
        self.byte_order_combo.blockSignals(False)
        self.canvas.set_byte_order(order)
        self._update_status()
        self._refresh_byte_table()
        QMessageBox.information(
            self, "Imported",
            f"Reconstructed a {width}x{height} drawing at offset (x={x_off}, y={y_off}) "
            f"onto the current {self.canvas.width_cells}x{self.canvas.height_cells} canvas.")


def main():
    app = QApplication(sys.argv)
    app.setFont(QFont("Segoe UI", 9))
    app.setStyleSheet(STYLE_SHEET)

    w, h = (128, 64)
    win = MainWindow(w, h)
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()