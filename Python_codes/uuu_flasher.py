#!/usr/bin/env python3
"""
UUU Flasher v3 - 3D Qt GUI for NXP uuu (Universal Update Utility)

Run:
    pip install PySide6
    python3 uuu_flasher.py

Equivalent terminal command:
    sudo uuu -b emmc_all <imx-boot>.bin-flash_all <image>.wic.zst
"""
import glob
import html
import math
import os
import re
import shlex
import shutil
import sys

from PySide6.QtCore import QElapsedTimer, QPointF, QProcess, QRectF, QSettings, QSize, Qt, QTimer, QVariantAnimation
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPalette,
    QPen,
    QPixmap,
    QPolygonF,
    QRadialGradient,
    QTextCursor,
    QTransform,
)
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

# target -> (label, needs_image)
TARGETS = {
    "emmc_all": ("eMMC  -  bootloader + full image", True),
    "sd_all": ("SD card  -  bootloader + full image", True),
    "emmc": ("eMMC  -  bootloader only", False),
    "sd": ("SD card  -  bootloader only", False),
}

ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
# "Success 0    Failure 0"
SC_RE = re.compile(r"Success\s+(\d+)\s+Failure\s+(\d+)")
# a row of "uuu -lsusb":  1:8   MX95   SDP   0x1FC9 ...
DEV_RE = re.compile(r"^\d+:\d+(?:\.\d+)*$")
# split before every "1:8-85FCC09F 4/ 8" device/step prefix
SEG_SPLIT_RE = re.compile(r"(?=\b\d+:\d+-[0-9A-Fa-f]+\s+\d+\s*/)")
# "1:8-85FCC09F 4/ 8 [=========74%=====>     ] FB: flash -raw2sparse all ..."
PROG_RE = re.compile(r"(\S+)\s+(\d+)\s*/\s*(\d+)\s*\[[^\]]*?(\d+)%[^\]]*\]\s*(.*)")
# "1:8-85FCC09F 8/ 8 [Done        ] FB: DONE"
STEP_RE = re.compile(r"(\S+)\s+(\d+)\s*/\s*(\d+)\s*\[\s*([A-Za-z][^\]]*?)\s*\]\s*(.*)")

STYLE = """
QLabel { background: transparent; color:#e6e6ee; }
QLabel#title    { font-size:26px; font-weight:bold; color:#ffffff; }
QLabel#subtitle { color:#e3e8ff; }
QLabel#field    { color:#b4bad6; font-weight:bold; }
QLabel#hint     { color:#8a90ab; }
QLabel#cap      { color:#7f86a6; font-size:10px; font-weight:bold; }
QLabel#stepline { color:#c9ceea; font-weight:bold; }
QLabel#badge {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #0a0b10, stop:1 #1a1c27);
    border:1px solid #07080c; border-bottom:1px solid #4a4f68; border-radius:10px;
    padding:4px 12px; font-weight:bold; color:#d0d4ea;
}

/* inset inputs (the well itself is painted by InsetEdit) */
QLineEdit { background:transparent; border:none; padding:7px 11px; color:#f0f0f8;
            selection-background-color:#4f8cff; }
QLineEdit:disabled { color:#666b80; }
QLineEdit[readOnly="true"] { color:#8fd0ff; font-family:monospace; }

QComboBox {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #07080c, stop:0.15 #10111a, stop:1 #1d1f2b);
    border:1px solid #05060a; border-top:2px solid #05060a; border-bottom:1px solid #565c7a;
    border-radius:9px; padding:7px 11px; color:#f0f0f8; selection-background-color:#4f8cff;
}
QComboBox:focus { border:1px solid #4f8cff; border-top:2px solid #2f5fc4; }
QComboBox:disabled { color:#666b80; }
QComboBox QAbstractItemView {
    background:#1d1f29; color:#f0f0f8; border:1px solid #4a4f68; selection-background-color:#3d6cf0;
}

/* terminal */
QPlainTextEdit {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #05060a, stop:0.06 #0a0c12, stop:1 #12141c);
    border:1px solid #05060a; border-bottom:1px solid #565c7a; border-radius:11px; padding:8px;
    color:#d0d0d8;
}
QScrollBar:vertical { background:transparent; width:12px; margin:4px 2px; }
QScrollBar::handle:vertical {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #5a607d, stop:1 #3a3f58);
    border:1px solid #1a1c27; border-radius:5px; min-height:28px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height:0; }
QToolTip { background:#1d1f29; color:#f0f0f8; border:1px solid #4a4f68; padding:4px; }
"""


# ===================================================================== helpers
def mix(a, b, t):
    a, b = QColor(a), QColor(b)
    return QColor(
        int(a.red() + (b.red() - a.red()) * t),
        int(a.green() + (b.green() - a.green()) * t),
        int(a.blue() + (b.blue() - a.blue()) * t),
        int(a.alpha() + (b.alpha() - a.alpha()) * t),
    )


def alpha(c, a):
    c = QColor(c)
    c.setAlpha(int(max(0, min(255, a))))
    return c


def scale(c, f):
    c = QColor(c)
    return QColor(min(255, int(c.red() * f)), min(255, int(c.green() * f)), min(255, int(c.blue() * f)))


def lgrad(p0, p1, *stops):
    g = QLinearGradient(p0, p1)
    for pos, col in stops:
        g.setColorAt(pos, QColor(col))
    return g


def vgrad(y0, y1, *stops):
    return lgrad(QPointF(0, y0), QPointF(0, y1), *stops)


def add_shadow(widget, blur=34, dy=10, alpha_=150, color=(0, 0, 0)):
    fx = QGraphicsDropShadowEffect(widget)
    fx.setBlurRadius(blur)
    fx.setOffset(0, dy)
    fx.setColor(QColor(color[0], color[1], color[2], alpha_))
    widget.setGraphicsEffect(fx)


def paint_well(p, r, rad=9, focus=False, dim=False):
    """Recessed input well: dark gradient, inner top shadow, lit bottom lip."""
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(255, 255, 255, 28))
    p.drawRoundedRect(r.translated(0, 1), rad, rad)
    p.setBrush(vgrad(r.top(), r.bottom(), (0, "#06070b"), (0.15, "#10111a"), (1, "#1d1f2b")))
    p.drawRoundedRect(r, rad, rad)
    clip = QPainterPath()
    clip.addRoundedRect(r, rad, rad)
    p.save()
    p.setClipPath(clip)
    p.fillRect(QRectF(r.left(), r.top(), r.width(), 8),
               QBrush(vgrad(r.top(), r.top() + 8, (0, QColor(0, 0, 0, 170)), (1, QColor(0, 0, 0, 0)))))
    p.restore()
    if focus:
        p.setPen(QPen(QColor(79, 140, 255, 230), 1.6))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(r.adjusted(0.8, 0.8, -0.8, -0.8), rad, rad)


def draw_led(p, c, r, color, k=1.0):
    """Real-looking LED: halo, chrome bezel, dark socket, glass orb, specular dot."""
    color = QColor(color)
    p.setPen(Qt.NoPen)
    if k > 0.05:
        halo = QRadialGradient(c, r * 3.4)
        halo.setColorAt(0, alpha(color, 120 * k))
        halo.setColorAt(1, alpha(color, 0))
        p.setBrush(halo)
        p.drawEllipse(c, r * 3.4, r * 3.4)
    p.setBrush(vgrad(c.y() - r - 3, c.y() + r + 3, (0, "#e4e7f5"), (1, "#2c2f42")))
    p.drawEllipse(c, r + 3, r + 3)
    p.setBrush(QColor("#08090d"))
    p.drawEllipse(c, r + 1, r + 1)
    orb = QRadialGradient(c, r, QPointF(c.x() - r * 0.35, c.y() - r * 0.4))
    orb.setColorAt(0, mix("#3a3d50", "#ffffff", 0.2 + 0.5 * k) if k < 0.1 else mix(color, "#ffffff", 0.7 * k))
    orb.setColorAt(0.5, mix("#1e2030", color, k))
    orb.setColorAt(1, mix("#0a0b10", color, 0.5 * k))
    p.setBrush(orb)
    p.drawEllipse(c, r, r)
    p.setBrush(QColor(255, 255, 255, int(150 * (0.4 + 0.6 * k))))
    p.drawEllipse(QPointF(c.x() - r * 0.3, c.y() - r * 0.42), r * 0.36, r * 0.22)


# ================================================================== backdrop
class Backdrop(QWidget):
    """Window background: brushed-metal sheet with soft coloured light and vignette."""

    def __init__(self):
        super().__init__()
        self.setObjectName("root")
        self._pm = None

    def _build(self):
        w, h = max(1, self.width()), max(1, self.height())
        pm = QPixmap(w, h)
        p = QPainter(pm)
        full = QRectF(0, 0, w, h)
        p.fillRect(full, QBrush(vgrad(0, h, (0, "#272b3d"), (1, "#0f1017"))))
        g = QRadialGradient(w * 0.15, -h * 0.05, w * 0.8)
        g.setColorAt(0, QColor(80, 110, 255, 80))
        g.setColorAt(1, QColor(80, 110, 255, 0))
        p.fillRect(full, QBrush(g))
        g = QRadialGradient(w * 0.9, h * 1.05, w * 0.7)
        g.setColorAt(0, QColor(150, 70, 240, 60))
        g.setColorAt(1, QColor(150, 70, 240, 0))
        p.fillRect(full, QBrush(g))
        p.setPen(QPen(QColor(255, 255, 255, 5), 1))
        for y in range(0, h, 3):
            p.drawLine(0, y, w, y)
        g = QRadialGradient(w / 2, h / 2, max(w, h) * 0.75)
        g.setColorAt(0.55, QColor(0, 0, 0, 0))
        g.setColorAt(1, QColor(0, 0, 0, 130))
        p.fillRect(full, QBrush(g))
        p.end()
        self._pm = pm

    def paintEvent(self, _):
        if self._pm is None or self._pm.size() != self.size():
            self._build()
        QPainter(self).drawPixmap(0, 0, self._pm)


# =================================================================== panels
class Panel3D(QFrame):
    """Raised slab: contact shadow, side wall, bevelled face, glossy sheen."""

    DEPTH = 7
    EXTRA = 12  # bottom padding a child layout must leave for depth + shadow
    KINDS = {
        "card": ("#383d55", "#252837", "#0b0c13", "#5a6180"),
        "header": ("#5a86ff", "#7b3fe4", "#1a1d62", "#c2d0ff"),
    }

    def __init__(self, kind="card"):
        super().__init__()
        self.kind = kind

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        top, bot, side, edge = (QColor(c) for c in self.KINDS[self.kind])
        d, rad = self.DEPTH, 16
        r = QRectF(self.rect()).adjusted(4, 2, -4, -(d + 5))
        p.setPen(Qt.NoPen)
        for i in range(7):  # soft contact shadow
            p.setBrush(QColor(0, 0, 0, 30 - i * 4))
            p.drawRoundedRect(r.adjusted(-i, d + i * 0.4, i, d + i + 1), rad + i, rad + i)
        p.setBrush(side)
        p.drawRoundedRect(r.translated(0, d), rad, rad)
        p.setBrush(vgrad(r.top(), r.bottom(), (0, top), (1, bot)))
        p.drawRoundedRect(r, rad, rad)
        bevel = QPen(QBrush(vgrad(r.top(), r.bottom(), (0, edge), (0.35, alpha(edge, 50)), (1, QColor(0, 0, 0, 150)))), 1.4)
        p.setPen(bevel)
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(r.adjusted(0.7, 0.7, -0.7, -0.7), rad, rad)
        gl = QRectF(r.left() + 2, r.top() + 2, r.width() - 4, r.height() * 0.42)
        p.setPen(Qt.NoPen)
        p.setBrush(vgrad(gl.top(), gl.bottom(), (0, QColor(255, 255, 255, 62 if self.kind == "header" else 30)),
                         (1, QColor(255, 255, 255, 0))))
        p.drawRoundedRect(gl, rad - 2, rad - 2)


def pad_layout(layout, l=20, t=16, r=20, b=16):
    layout.setContentsMargins(l, t, r, b + Panel3D.EXTRA)


# ================================================================== controls
class Button3D(QPushButton):
    """Physical keycap: side wall + glossy face that sinks when pressed."""

    PAL = {  # face-top, face-bottom, side wall, lit edge
        "normal": ("#6a7196", "#3d4264", "#12142a", "#9aa1c8"),
        "flash": ("#62f5a0", "#1f9a52", "#0a4a26", "#b4ffd8"),
        "stop": ("#ff7474", "#b02c2c", "#501010", "#ffbcbc"),
        "check": ("#6fb0ff", "#2a62c8", "#0f2a66", "#c4dcff"),
        "off": ("#2e3040", "#252736", "#14151e", "#3a3d50"),
    }

    def __init__(self, text="", kind="normal", small=False):
        super().__init__(text)
        self.kind, self.small, self._hover = kind, small, False
        self.depth = 4 if small else (7 if kind == "flash" else 5)
        self.margin = 9 if kind == "flash" else 3  # room for glow / shadow
        f = self.font()
        if kind == "flash":
            f.setPointSize(f.pointSize() + 3)
        if kind in ("flash", "stop", "check"):
            f.setBold(True)
        self.setFont(f)
        self.setAttribute(Qt.WA_Hover)
        self.setCursor(Qt.PointingHandCursor)

    def sizeHint(self):
        fm = self.fontMetrics()
        ph, pv = (30, 9) if self.small else (40 if self.kind == "flash" else 28, 22 if self.kind == "flash" else 14)
        return QSize(fm.horizontalAdvance(self.text()) + ph + 2 * self.margin,
                     fm.height() + pv + self.depth + 2 * self.margin)

    minimumSizeHint = sizeHint

    def enterEvent(self, e):
        self._hover = True
        self.update()

    def leaveEvent(self, e):
        self._hover = False
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        en, down = self.isEnabled(), self.isDown()
        top, bot, side, edge = (QColor(c) for c in self.PAL[self.kind if en else "off"])
        if en and self._hover and not down:
            top, bot = mix(top, "#ffffff", 0.16), mix(bot, "#ffffff", 0.12)
        m, D = self.margin, self.depth
        sink = 1 if down else D
        area = QRectF(self.rect()).adjusted(m, m, -m, -m)
        face = QRectF(area.left(), area.top() + (D - sink), area.width(), area.height() - D)
        rad = 9 if self.small else 12
        p.setPen(Qt.NoPen)
        if en and self.kind in ("flash", "stop"):  # coloured under-glow
            for i in range(1, 7):
                p.setBrush(alpha(edge if self.kind == "flash" else top, (34 if self._hover else 22) - i * 3))
                p.drawRoundedRect(face.adjusted(-i, -i + D, i, i + D), rad + i, rad + i)
        for i in range(3):  # contact shadow on the panel
            p.setBrush(QColor(0, 0, 0, 55 - i * 15))
            p.drawRoundedRect(face.adjusted(-i, sink + 1, i, sink + 2 + i), rad, rad)
        p.setBrush(side)
        p.drawRoundedRect(face.translated(0, sink), rad, rad)
        p.setBrush(vgrad(face.top(), face.bottom(), (0, top), (1, bot)))
        p.drawRoundedRect(face, rad, rad)
        p.setPen(QPen(QBrush(vgrad(face.top(), face.bottom(), (0, edge), (0.5, alpha(edge, 40)), (1, alpha("#000000", 90)))), 1.2))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(face.adjusted(0.6, 0.6, -0.6, -0.6), rad, rad)
        if en:  # specular sheen
            hl = QRectF(face.left() + 3, face.top() + 2, face.width() - 6, face.height() * 0.46)
            p.setPen(Qt.NoPen)
            p.setBrush(vgrad(hl.top(), hl.bottom(), (0, QColor(255, 255, 255, 105)), (1, QColor(255, 255, 255, 6))))
            p.drawRoundedRect(hl, rad - 3, rad - 3)
        p.setFont(self.font())
        p.setPen(QColor(0, 0, 0, 150) if en else QColor(0, 0, 0, 0))
        p.drawText(face.translated(0, 1.2), Qt.AlignCenter, self.text())
        p.setPen(QColor("#ffffff") if en else QColor("#6a6f86"))
        p.drawText(face, Qt.AlignCenter, self.text())


class SwitchBox(QCheckBox):
    """Slide switch: recessed track that lights green, metal knob."""

    def __init__(self, text=""):
        super().__init__(text)
        self._pos = 1.0 if self.isChecked() else 0.0
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(140)
        self._anim.valueChanged.connect(self._set_pos)
        self.toggled.connect(self._on_toggled)
        self.setCursor(Qt.PointingHandCursor)

    def _set_pos(self, v):
        self._pos = float(v)
        self.update()

    def _on_toggled(self, on):
        self._anim.stop()
        self._anim.setStartValue(self._pos)
        self._anim.setEndValue(1.0 if on else 0.0)
        self._anim.start()

    def sizeHint(self):
        return QSize(62 + self.fontMetrics().horizontalAdvance(self.text()), 30)

    def hitButton(self, pos):
        return self.rect().contains(pos)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setOpacity(1.0 if self.isEnabled() else 0.45)
        on = self._pos
        tr = QRectF(2, (self.height() - 24) / 2, 48, 24)
        p.setPen(Qt.NoPen)
        if on > 0.02:
            p.setBrush(QColor(60, 240, 140, int(46 * on)))
            p.drawRoundedRect(tr.adjusted(-3, -3, 3, 3), 15, 15)
        p.setBrush(QColor(255, 255, 255, 30))
        p.drawRoundedRect(tr.translated(0, 1), 12, 12)
        p.setBrush(vgrad(tr.top(), tr.bottom(), (0, mix("#05060a", "#0b5a30", on)), (1, mix("#1c1e2a", "#33dc82", on))))
        p.drawRoundedRect(tr, 12, 12)
        k = QRectF(tr.left() + 3 + on * 24, tr.top() + 3, 18, 18)
        p.setBrush(QColor(0, 0, 0, 100))
        p.drawEllipse(k.translated(0, 2).adjusted(-1, 0, 1, 1))
        p.setBrush(vgrad(k.top(), k.bottom(), (0, "#f6f7fc"), (1, "#8d93ad")))
        p.drawEllipse(k)
        p.setBrush(vgrad(k.top(), k.bottom(), (0, "#a9afc6"), (1, "#eceef6")))
        p.drawEllipse(k.adjusted(4.5, 4.5, -4.5, -4.5))
        p.setFont(self.font())
        p.setPen(QColor("#d6d8e6"))
        p.drawText(QRectF(60, 0, self.width() - 60, self.height()), Qt.AlignVCenter | Qt.AlignLeft, self.text())


class InsetEdit(QLineEdit):
    """Line edit drawn as a recessed well."""

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        paint_well(p, QRectF(self.rect()).adjusted(1, 1, -1, -2), 9, focus=self.hasFocus())
        p.end()
        super().paintEvent(e)


class FileEdit(InsetEdit):
    """Inset edit that accepts drag & drop of a file."""

    def __init__(self, placeholder=""):
        super().__init__()
        self.setAcceptDrops(True)
        self.setPlaceholderText(placeholder)

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        urls = e.mimeData().urls()
        if urls:
            self.setText(urls[0].toLocalFile())


class StatusPlate(QWidget):
    """Recessed status window with a lamp that pulses while flashing."""

    COL = {"idle": ("#9aa0bd", "IDLE"), "scan": ("#5ac8ff", "SCANNING"),
           "nodev": ("#ff9f5a", "NO DEVICE FOUND"), "found": ("#5ac8ff", "DEVICE FOUND"),
           "run": ("#ffc857", "FLASHING"), "ok": ("#5af08f", "DONE"),
           "fail": ("#ff6b6b", "FAILED"), "stop": ("#ffb347", "STOPPED")}

    def __init__(self):
        super().__init__()
        self.setFixedSize(236, 48)
        self._state, self._t = "idle", 0.0
        self._timer = QTimer(self)
        self._timer.setInterval(40)
        self._timer.timeout.connect(self._tick)

    def set_state(self, s):
        self._state = s
        self._timer.start() if s in ("run", "scan") else self._timer.stop()
        self.update()

    def _tick(self):
        self._t += 0.04
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.TextAntialiasing)
        col, txt = self.COL[self._state]
        r = QRectF(self.rect()).adjusted(2, 2, -2, -4)
        paint_well(p, r, 12)
        k = {"idle": 0.0}.get(self._state, 1.0)
        if self._state in ("run", "scan"):
            k = 0.7 + 0.3 * math.sin(self._t * 6)
        draw_led(p, QPointF(r.left() + 25, r.center().y()), 7.5, col, k)
        f = QFont(self.font())
        f.setBold(True)
        f.setPointSize(11)
        p.setFont(f)
        p.setPen(alpha("#000000", 180))
        p.drawText(QRectF(r.left() + 46, r.top() + 1, r.width() - 46, r.height()), Qt.AlignVCenter | Qt.AlignLeft, txt)
        p.setPen(QColor(col) if self._state != "idle" else QColor("#aab0cc"))
        p.drawText(QRectF(r.left() + 46, r.top(), r.width() - 46, r.height()), Qt.AlignVCenter | Qt.AlignLeft, txt)


class ProgressTube(QProgressBar):
    """Glass tube filled with glossy liquid; animated stripes while running."""

    FILL = {"idle": ("#8fd6ff", "#3d8bff", "#2766d6", "#5cbcff"),
            "run": ("#8fd6ff", "#3d8bff", "#2766d6", "#5cbcff"),
            "ok": ("#a4ffc8", "#37d67a", "#1d9a52", "#5cf0a0"),
            "fail": ("#ffb0b0", "#f05a5a", "#b02c2c", "#ff7a7a")}

    def __init__(self):
        super().__init__()
        self.setFixedHeight(48)
        self._state, self._phase = "idle", 0.0
        self._timer = QTimer(self)
        self._timer.setInterval(33)
        self._timer.timeout.connect(self._tick)

    def set_state(self, s):
        self._state = s
        self._timer.start() if s == "run" else self._timer.stop()
        self.update()

    def _tick(self):
        self._phase += 1.0
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.TextAntialiasing)
        W = self.width()
        tube = QRectF(2, 3, W - 4, 30)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(255, 255, 255, 34))
        p.drawRoundedRect(tube.translated(0, 1.5), 15, 15)
        p.setBrush(vgrad(tube.top(), tube.bottom(), (0, "#05060a"), (1, "#2b2e40")))
        p.drawRoundedRect(tube, 15, 15)
        inner = tube.adjusted(3, 3, -3, -3)
        ir = inner.height() / 2
        p.setBrush(vgrad(inner.top(), inner.bottom(), (0, "#090a0f"), (1, "#1b1d29")))
        p.drawRoundedRect(inner, ir, ir)

        mn, mx = self.minimum(), self.maximum()
        indet = mx == mn
        frac = 0.0 if indet else max(0.0, min(1.0, (self.value() - mn) / (mx - mn)))
        if indet:
            seg = inner.width() * 0.33
            x = inner.left() + ((self._phase * 0.012) % 1.0) * (inner.width() + seg) - seg
            fill = QRectF(x, inner.top(), seg, inner.height())
        else:
            fill = QRectF(inner.left(), inner.top(), max(inner.height(), inner.width() * frac) if frac > 0 else 0, inner.height())

        clip = QPainterPath()
        clip.addRoundedRect(inner, ir, ir)
        p.save()
        p.setClipPath(clip)
        if fill.width() > 0:
            l, m, d, b = self.FILL.get(self._state, self.FILL["idle"])
            p.setBrush(vgrad(fill.top(), fill.bottom(), (0, l), (0.48, m), (0.52, d), (1, b)))
            p.drawRoundedRect(fill, ir, ir)
            if self._state == "run":
                fp = QPainterPath()
                fp.addRoundedRect(fill, ir, ir)
                p.setClipPath(clip.intersected(fp))
                off, h = (self._phase * 0.8) % 22, inner.height()
                p.setBrush(QColor(255, 255, 255, 26))
                x = fill.left() - h - 22
                while x < fill.right() + h:
                    p.drawPolygon(QPolygonF([QPointF(x + off, inner.bottom()), QPointF(x + off + 11, inner.bottom()),
                                             QPointF(x + off + 11 + h, inner.top()), QPointF(x + off + h, inner.top())]))
                    x += 22
                p.setClipPath(clip)
            if not indet and 0 < frac < 1:
                p.setBrush(QColor(255, 255, 255, 110))
                p.drawRect(QRectF(fill.right() - 2, inner.top(), 2, inner.height()))
        gl = QRectF(inner.left() + 4, inner.top() + 2, inner.width() - 8, inner.height() * 0.42)
        p.setBrush(vgrad(gl.top(), gl.bottom(), (0, QColor(255, 255, 255, 84)), (1, QColor(255, 255, 255, 6))))
        p.drawRoundedRect(gl, ir - 2, ir - 2)
        p.restore()

        f = QFont(self.font())
        f.setBold(True)
        f.setPointSize(11)
        p.setFont(f)
        txt = "WORKING..." if indet else f"{int(round(frac * 100))}%"
        p.setPen(QColor(0, 0, 0, 170))
        p.drawText(inner.translated(0, 1.2), Qt.AlignCenter, txt)
        p.setPen(QColor("#ffffff"))
        p.drawText(inner, Qt.AlignCenter, txt)
        p.setPen(QPen(QColor("#4a4f68"), 1))
        for i in range(11):  # scale ticks under the tube
            x = inner.left() + ir * 0 + i * inner.width() / 10
            p.drawLine(QPointF(x, tube.bottom() + 5), QPointF(x, tube.bottom() + (11 if i % 5 == 0 else 8)))


# ================================================================= 3D board
class BoardView(QWidget):
    """Pseudo-3D (orthographic) i.MX board. Drag to rotate. Lights up while flashing."""

    BASE = 0.28  # board floats on rubber feet
    ACCENT = {"idle": "#6f7fb8", "scan": "#46d7ff", "nodev": "#ff9f5a", "found": "#5ac8ff",
              "run": "#46d7ff", "ok": "#5af08f", "fail": "#ff6b6b", "stop": "#ffb347"}
    LIGHT = (-0.45, 0.35, 0.82)

    def __init__(self):
        super().__init__()
        self.setMinimumSize(300, 250)
        self._state, self._progress, self._target = "idle", 0.0, "emmc"
        self._t, self._yaw, self._drag = 0.0, 0.62, None
        self._el = math.radians(36)
        self._c = self._s = self._S = self._cx = self._cy = 0.0
        n = math.sqrt(sum(v * v for v in self.LIGHT))
        self._L = tuple(v / n for v in self.LIGHT)
        self._timer = QTimer(self)
        self._timer.setInterval(33)
        self._timer.timeout.connect(self._tick)
        self.setCursor(Qt.OpenHandCursor)
        self.setToolTip("Drag to rotate  -  double-click to reset")

    # ---- state
    def set_state(self, s):
        self._state = s
        self.update()

    def set_progress(self, v):
        self._progress = max(0.0, min(1.0, v))

    def set_target(self, t):
        self._target = t
        self.update()

    def showEvent(self, e):
        self._timer.start()

    def hideEvent(self, e):
        self._timer.stop()

    def _tick(self):
        self._t += 0.033
        self.update()

    def mousePressEvent(self, e):
        self._drag = (e.position().x(), self._yaw)
        self.setCursor(Qt.ClosedHandCursor)

    def mouseMoveEvent(self, e):
        if self._drag:
            self._yaw = self._drag[1] + (e.position().x() - self._drag[0]) * 0.012

    def mouseReleaseEvent(self, e):
        self._drag = None
        self.setCursor(Qt.OpenHandCursor)

    def mouseDoubleClickEvent(self, e):
        self._yaw = 0.62

    # ---- projection helpers
    def _proj(self, x, y, z):
        X = x * self._c - y * self._s
        Y = x * self._s + y * self._c
        return QPointF(self._cx + X * self._S, self._cy + Y * self._S * math.sin(self._el) - z * self._S * math.cos(self._el)), Y

    def _pt(self, x, y, z):
        return self._proj(x, y, z)[0]

    def _surf(self, x, y, w, d, z):
        return QPolygonF([self._pt(x, y, z), self._pt(x + w, y, z), self._pt(x + w, y + d, z), self._pt(x, y + d, z)])

    def _surf_tr(self, x, y, z):
        o = self._pt(x, y, z)
        ux, uy = self._pt(x + 1, y, z) - o, self._pt(x, y + 1, z) - o
        return QTransform(ux.x(), ux.y(), uy.x(), uy.y(), o.x(), o.y())

    def _surf_text(self, p, x, y, z, w, d, text, size, color):
        p.save()
        p.setTransform(self._surf_tr(x, y, z), False)
        p.scale(0.01, 0.01)
        f = QFont("Sans")
        f.setBold(True)
        f.setPixelSize(max(1, int(size * 100)))
        p.setFont(f)
        p.setPen(QColor(color))
        p.drawText(QRectF(0, 0, w * 100, d * 100), Qt.AlignCenter | Qt.TextSingleLine | Qt.TextDontClip, text)
        p.restore()

    def _glow(self, p, pt, r, color, a):
        g = QRadialGradient(pt, r)
        g.setColorAt(0, alpha(color, a))
        g.setColorAt(1, alpha(color, 0))
        p.setPen(Qt.NoPen)
        p.setBrush(g)
        p.drawEllipse(pt, r, r)

    def _box(self, p, x, y, z, w, d, h, color, metal=False):
        xs, ys, zs = (x, x + w), (y, y + d), (z, z + h)
        P = [self._pt(xs[a], ys[b], zs[c]) for c in (0, 1) for a, b in ((0, 0), (1, 0), (1, 1), (0, 1))]
        faces = [((0, 0, 1), (4, 5, 6, 7)), ((1, 0, 0), (1, 2, 6, 5)), ((-1, 0, 0), (0, 3, 7, 4)),
                 ((0, 1, 0), (3, 2, 6, 7)), ((0, -1, 0), (0, 1, 5, 4))]
        L = self._L
        for n, idx in faces:
            nx, ny, nz = n[0] * self._c - n[1] * self._s, n[0] * self._s + n[1] * self._c, n[2]
            if ny * math.cos(self._el) + nz * math.sin(self._el) <= 0:
                continue
            lam = max(0.0, nx * L[0] + ny * L[1] + nz * L[2])
            col = scale(color, 0.45 + 0.75 * lam)
            if metal and n == (0, 0, 1):
                brush = lgrad(P[4], P[6], (0, mix(color, "#ffffff", 0.5)), (0.5, color), (1, mix(color, "#000000", 0.3)))
            else:
                brush = col
            p.setBrush(brush)
            p.setPen(QPen(QColor(0, 0, 0, 80), 0.8))
            p.drawPolygon(QPolygonF([P[i] for i in idx]))

    def _trace(self, p, pts, T, color, width):
        path = QPainterPath()
        q = [self._pt(x, y, T) for x, y in pts]
        path.moveTo(q[0])
        for pt in q[1:]:
            path.lineTo(pt)
        pen = QPen(color, width)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        p.drawPath(path)

    @staticmethod
    def _along(pts, dist):
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            seg = math.hypot(x1 - x0, y1 - y0)
            if dist <= seg:
                f = dist / seg if seg else 0
                return x0 + (x1 - x0) * f, y0 + (y1 - y0) * f
            dist -= seg
        return pts[-1]

    # ---- paint
    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.TextAntialiasing)
        W, H = self.width(), self.height()
        yaw = self._yaw + (0 if self._drag else 0.10 * math.sin(self._t * 0.7))
        self._c, self._s = math.cos(yaw), math.sin(yaw)
        self._S = min(W / 12.2, H / 9.0)
        self._cx, self._cy = W / 2, H * 0.57
        acc = QColor(self.ACCENT[self._state])
        running, st = self._state in ("run", "scan"), self._state
        lit = st not in ("idle", "nodev")
        pulse = 0.6 + 0.4 * math.sin(self._t * 5)
        B = self.BASE
        T = B + 0.3

        # stage: recessed viewport with floor grid
        stage = QRectF(self.rect()).adjusted(1, 1, -1, -2)
        sp = QPainterPath()
        sp.addRoundedRect(stage, 14, 14)
        bg = QRadialGradient(W / 2, H * 0.5, max(W, H) * 0.7)
        bg.setColorAt(0, QColor("#2d3454"))
        bg.setColorAt(1, QColor("#0a0b11"))
        p.fillPath(sp, QBrush(bg))
        p.save()
        p.setClipPath(sp)
        for i in range(-9, 10):
            p.setPen(QPen(QColor(150, 170, 255, int(46 * (1 - abs(i) / 9.5))), 1))
            p.drawLine(self._pt(i, -9, 0), self._pt(i, 9, 0))
            p.drawLine(self._pt(-9, i, 0), self._pt(9, i, 0))
        # board shadow on the floor
        p.setPen(Qt.NoPen)
        for i in range(7):
            e = 0.12 * i
            p.setBrush(QColor(0, 0, 0, 26))
            p.drawPolygon(self._surf(-5 - e + 0.4, -3 - e + 0.2, 10 + 2 * e, 6 + 2 * e, 0))
        if lit:  # under-glow on the floor
            g = QRadialGradient(self._pt(0, 0, 0), self._S * 6.5)
            g.setColorAt(0, alpha(acc, 70 * (pulse if running else 0.8)))
            g.setColorAt(1, alpha(acc, 0))
            p.setBrush(g)
            p.drawEllipse(self._pt(0, 0, 0), self._S * 6.5, self._S * 4)

        pcb = "#0e4f63"
        for fx, fy in ((-4.4, -2.4), (3.9, -2.4), (-4.4, 1.9), (3.9, 1.9)):
            self._box(p, fx, fy, 0, 0.5, 0.5, B, "#15161c")
        self._box(p, -5, -3, B, 10, 6, 0.3, pcb)
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QColor(255, 255, 255, 55), 1))
        p.drawPolygon(self._surf(-4.8, -2.8, 9.6, 5.6, T))
        for hx, hy in ((-4.6, -2.6), (4.6, -2.6), (-4.6, 2.6), (4.6, 2.6)):
            p.save()
            p.setTransform(self._surf_tr(hx, hy, T), False)
            p.setPen(QPen(QColor("#d8b45a"), 0.07))
            p.setBrush(QColor("#07080c"))
            p.drawEllipse(QPointF(0, 0), 0.22, 0.22)
            p.restore()

        # traces
        copper = alpha("#c79b45", 150)
        w1 = max(1.2, 0.06 * self._S)
        for yy in (-0.6, -0.3, 0, 0.3, 0.6):
            self._trace(p, [(-2.5, yy), (-1.5, yy)], T, copper, w1)
        for yy in (-0.8, -0.6, -0.4, -0.2, 0):
            self._trace(p, [(1.1, yy), (1.9, yy)], T, copper, w1)
        route = [(-2.3, 2.0), (-2.3, 1.6), (-0.2, 1.6), (-0.2, 0)]
        route += [(1.5, 0), (1.5, -0.4), (2.6, -0.4)] if self._target == "emmc" else [(0.9, 0), (0.9, 2.05), (3.5, 2.05)]
        self._trace(p, route, T, copper, w1 * 1.4)
        if lit:
            self._trace(p, route, T, alpha(acc, 55 * (pulse if running else 1)), w1 * 4.5)
            self._trace(p, route, T, alpha(acc, 230), w1 * 1.5)
        if running:  # data packets USB -> SoC -> storage
            total = sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(route, route[1:]))
            for i in range(7):
                x, y = self._along(route, (self._t * 4.2 + i * total / 7) % total)
                self._glow(p, self._pt(x, y, T), self._S * 0.34, "#bff3ff", 230)

        # components, back to front
        ledc = {"idle": "#3a3d50", "nodev": "#ff9f5a", "found": "#5ac8ff", "scan": "#5ac8ff", "run": "#ffc857",
                "ok": "#5af08f", "fail": "#ff6b6b", "stop": "#ffb347"}[st]
        comps = [
            ("ddr", -3.8, -1.0, T, 1.4, 2.0, 0.14, "#16171d", False, "LPDDR5", 0.26),
            ("soc", -1.6, -1.4, T, 2.8, 2.8, 0.26, "#23252e", False, None, 0),
            ("ihs", -1.3, -1.1, T + 0.26, 2.2, 2.2, 0.10, "#9199ad", True, "i.MX", 0.36),
            ("emmc", 1.8, -1.2, T, 1.6, 1.6, 0.14, "#14151b", False, "eMMC", 0.30),
            ("sd", 2.2, 1.4, T, 2.6, 1.3, 0.22, "#a2a9bb", True, "SD", 0.34),
            ("usb", -3.0, 2.0, T, 1.4, 1.3, 0.5, "#b3b9c8", True, "USB-C", 0.27),
            ("hdr", -4.6, -2.8, T, 4.0, 0.5, 0.32, "#0e0f14", False, None, 0),
            ("btn", 4.1, -1.5, T, 0.55, 0.55, 0.2, "#3b3f50", False, None, 0),
            ("c1", -4.5, 0.2, T, 0.5, 0.5, 0.3, "#c9a24a", False, None, 0),
            ("c2", -4.5, 1.0, T, 0.5, 0.5, 0.3, "#c9a24a", False, None, 0),
            ("r1", 0.6, 2.2, T, 0.5, 0.25, 0.1, "#2a2a2e", False, None, 0),
            ("r2", 0.6, 2.6, T, 0.5, 0.25, 0.1, "#2a2a2e", False, None, 0),
            ("led", 4.1, -2.6, T, 0.35, 0.35, 0.1, ledc, False, None, 0),
        ]

        def depth(c):
            # round the centre first so stacked parts (SoC package + heat spreader) tie exactly,
            # then height decides: the lower part is always drawn first
            cx, cy = round(c[1] + c[4] / 2, 4), round(c[2] + c[5] / 2, 4)
            return round(cx * self._s + cy * self._c, 6), c[3]

        for key, x, y, z, w, d, h, col, metal, label, lsz in sorted(comps, key=depth):
            self._box(p, x, y, z, w, d, h, col, metal)
            top = z + h
            if key == self._target and self._progress > 0:
                p.setPen(Qt.NoPen)
                p.setBrush(alpha(acc, 120))
                p.drawPolygon(self._surf(x, y, w * self._progress, d, top + 0.005))
            if key == "ihs" and lit:
                p.setPen(Qt.NoPen)
                p.setBrush(alpha(acc, (90 * pulse) if running else 60))
                p.drawPolygon(self._surf(x, y, w, d, top + 0.01))
            if label:
                self._surf_text(p, x, y, top + 0.012, w, d, label, lsz, "#2a2d3a" if metal else "#9aa2b8")
            if key == "hdr":
                p.setPen(Qt.NoPen)
                p.setBrush(QColor("#d8b45a"))
                for i in range(16):
                    pt = self._pt(x + 0.15 + i * 0.245, y + 0.25, top + 0.01)
                    p.drawEllipse(pt, self._S * 0.055, self._S * 0.055)
            if key == "ihs" and lit:
                self._glow(p, self._pt(x + w / 2, y + d / 2, top), self._S * 2.2, acc, 70 * (pulse if running else 0.8))
            if key == "led":
                self._glow(p, self._pt(x + w / 2, y + d / 2, top), self._S * 1.0, ledc, 190 if st not in ("idle",) else 0)

        # HUD
        f = QFont(self.font())
        f.setPixelSize(10)
        f.setBold(True)
        p.setFont(f)
        p.setPen(QColor("#8a90ab"))
        p.drawText(QRectF(14, H - 26, W - 28, 16), Qt.AlignLeft | Qt.AlignVCenter, "IMX-FRDM")
        p.drawText(QRectF(14, H - 26, W - 28, 16), Qt.AlignRight | Qt.AlignVCenter, "DRAG TO ROTATE")
        p.setPen(acc)
        p.drawText(QRectF(14, 10, W - 28, 16), Qt.AlignLeft | Qt.AlignVCenter,
                   "TARGET: " + ("eMMC" if self._target == "emmc" else "SD CARD"))
        if st == "run":
            p.drawText(QRectF(14, 10, W - 28, 16), Qt.AlignRight | Qt.AlignVCenter, f"{int(self._progress * 100)}%")
        p.restore()
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QBrush(vgrad(stage.top(), stage.bottom(), (0, "#04050a"), (1, "#565c7a"))), 1.4))
        p.drawRoundedRect(stage, 14, 14)


class Flasher(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("UUU Flasher  -  i.MX95 FRDM")
        self.setMinimumSize(1000, 800)
        self.resize(1120, 900)
        self.settings = QSettings("uuu-flasher", "gui")
        self._password = None
        self._sudo_used = False
        self._last_step_key = None
        self._counts = (0, 0)
        self._devices = []          # devices found by the last scan
        self._pending_flash = False  # flash requested; waiting for the device scan
        self._mode = "flash"        # "scan" (uuu -lsusb) or "flash"
        self._buf = ""              # raw output of the current run
        self._stopping = False

        self.clock = QElapsedTimer()
        self.tick = QTimer(self)
        self.tick.setInterval(500)
        self.tick.timeout.connect(self._update_clock)

        self.proc = QProcess(self)
        self.proc.setProcessChannelMode(QProcess.MergedChannels)
        self.proc.readyReadStandardOutput.connect(self._on_output)
        self.proc.started.connect(self._on_started)
        self.proc.finished.connect(self._on_finished)
        self.proc.errorOccurred.connect(self._on_error)

        self._build_ui()
        self._load_settings()
        self._update_preview()
        self._set_led("idle")
        QTimer.singleShot(300, self._prime_sudo)

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        root = Backdrop()
        self.setCentralWidget(root)
        v = QVBoxLayout(root)
        v.setContentsMargins(22, 18, 22, 10)
        v.setSpacing(2)

        # ----- header plate -----
        header = Panel3D("header")
        hl = QHBoxLayout(header)
        pad_layout(hl, 26, 16, 22, 16)
        tcol = QVBoxLayout()
        tcol.setSpacing(2)
        title = QLabel("⚡ UUU Flasher")
        title.setObjectName("title")
        add_shadow(title, blur=14, dy=2, alpha_=150, color=(10, 10, 60))
        sub = QLabel("NXP i.MX Universal Update Utility  •  select files and program the board")
        sub.setObjectName("subtitle")
        tcol.addWidget(title)
        tcol.addWidget(sub)
        hl.addLayout(tcol, 1)
        self.led = StatusPlate()
        hl.addWidget(self.led)
        v.addWidget(header)

        # ----- middle row: settings + 3D board -----
        mid = QHBoxLayout()
        mid.setSpacing(4)

        sc = Panel3D()
        grid = QGridLayout(sc)
        pad_layout(grid, 22, 18, 22, 18)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(11)

        def field(text):
            l = QLabel(text)
            l.setObjectName("field")
            return l

        grid.addWidget(field("Bootloader"), 0, 0)
        self.boot_edit = FileEdit("imx-boot-...-sd.bin-flash_all   (drag & drop or Browse)")
        self.boot_edit.textChanged.connect(self._update_preview)
        b1 = Button3D("Browse", small=True)
        b1.clicked.connect(lambda: self._browse(self.boot_edit, "Select bootloader", "Boot images (*.bin* *flash_all*);;All files (*)"))
        grid.addWidget(self.boot_edit, 0, 1)
        grid.addWidget(b1, 0, 2)

        grid.addWidget(field("Image"), 1, 0)
        self.img_edit = FileEdit("*.wic.zst / *.wic / *.sdcard   (drag & drop or Browse)")
        self.img_edit.textChanged.connect(self._update_preview)
        b2 = Button3D("Browse", small=True)
        b2.clicked.connect(lambda: self._browse(self.img_edit, "Select image", "Images (*.wic *.wic.zst *.wic.gz *.wic.bz2 *.sdcard *.img *.zst);;All files (*)"))
        grid.addWidget(self.img_edit, 1, 1)
        grid.addWidget(b2, 1, 2)

        grid.addWidget(field("Target"), 2, 0)
        self.target = QComboBox()
        for key, (label, _) in TARGETS.items():
            self.target.addItem(f"{key}   -   {label}", key)
        self.target.currentIndexChanged.connect(self._on_target_changed)
        auto = Button3D("Auto-detect folder", small=True)
        auto.setToolTip("Pick the deploy/images folder; the boot and image files are found automatically")
        auto.clicked.connect(self._autodetect)
        grid.addWidget(self.target, 2, 1)
        grid.addWidget(auto, 2, 2)

        grid.addWidget(field("uuu binary"), 3, 0)
        self.uuu_edit = InsetEdit(shutil.which("uuu") or "uuu")
        self.uuu_edit.textChanged.connect(self._update_preview)
        b3 = Button3D("Browse", small=True)
        b3.clicked.connect(lambda: self._browse(self.uuu_edit, "Select uuu binary", "All files (*)"))
        grid.addWidget(self.uuu_edit, 3, 1)
        grid.addWidget(b3, 3, 2)

        opts = QHBoxLayout()
        self.sudo_chk = SwitchBox("Run with sudo")
        self.sudo_chk.setChecked(os.geteuid() != 0)
        self.sudo_chk.setEnabled(os.geteuid() != 0)
        self.sudo_chk.toggled.connect(self._update_preview)
        self.verbose_chk = SwitchBox("Verbose (-v)")
        self.verbose_chk.toggled.connect(self._update_preview)
        opts.addWidget(self.sudo_chk)
        opts.addSpacing(22)
        opts.addWidget(self.verbose_chk)
        opts.addStretch(1)
        grid.addLayout(opts, 4, 1, 1, 2)

        grid.addWidget(field("Command"), 5, 0)
        self.preview = InsetEdit()
        self.preview.setReadOnly(True)
        grid.addWidget(self.preview, 5, 1, 1, 2)
        grid.setColumnStretch(1, 1)
        mid.addWidget(sc, 1)

        bp = Panel3D()
        bp.setFixedWidth(350)
        bl = QVBoxLayout(bp)
        pad_layout(bl, 14, 12, 14, 12)
        bl.setSpacing(6)
        cap = QLabel("TARGET DEVICE  •  3D VIEW")
        cap.setObjectName("cap")
        self.board = BoardView()
        bl.addWidget(cap)
        bl.addWidget(self.board, 1)
        self.dev_combo = QComboBox()
        self.dev_combo.addItem("No device found", None)
        self.dev_combo.setEnabled(False)
        self.dev_combo.setToolTip("Connected i.MX devices - choose which one to flash")
        self.dev_combo.currentIndexChanged.connect(self._update_preview)
        bl.addWidget(self.dev_combo)
        self.check_btn = Button3D("🔌  Check Device", "check")
        self.check_btn.setToolTip("List connected i.MX devices (uuu -lsusb)")
        self.check_btn.clicked.connect(self._check_device)
        bl.addWidget(self.check_btn)
        mid.addWidget(bp)
        v.addLayout(mid)

        # ----- action buttons -----
        btns = QHBoxLayout()
        btns.setContentsMargins(6, 4, 6, 0)
        btns.setSpacing(8)
        clear_btn = Button3D("Clear log")
        clear_btn.clicked.connect(lambda: self.log.clear())
        self.stop_btn = Button3D("■  Stop", "stop")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self._stop)
        self.flash_btn = Button3D("⚡  FLASH", "flash")
        self.flash_btn.clicked.connect(self._flash)
        btns.addWidget(clear_btn)
        btns.addStretch(1)
        btns.addWidget(self.stop_btn)
        btns.addWidget(self.flash_btn)
        v.addLayout(btns)

        # ----- progress panel -----
        pc = Panel3D()
        pl = QVBoxLayout(pc)
        pad_layout(pl, 22, 14, 22, 12)
        pl.setSpacing(8)

        top = QHBoxLayout()
        self.step_lbl = QLabel("Step  -  / -")
        self.step_lbl.setObjectName("stepline")
        self.ok_badge = QLabel("✔ Success 0")
        self.ok_badge.setObjectName("badge")
        self.fail_badge = QLabel("✘ Failure 0")
        self.fail_badge.setObjectName("badge")
        self.time_badge = QLabel("⏱ 00:00")
        self.time_badge.setObjectName("badge")
        top.addWidget(self.step_lbl, 1)
        top.addWidget(self.ok_badge)
        top.addWidget(self.fail_badge)
        top.addWidget(self.time_badge)
        pl.addLayout(top)

        self.progress = ProgressTube()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.valueChanged.connect(lambda val: self.board.set_progress(max(0, val) / 100))
        pl.addWidget(self.progress)

        self.status = QLabel("Ready.  Put the board in USB download (SDP) mode, connect it and press Check Device.")
        self.status.setObjectName("hint")
        pl.addWidget(self.status)
        v.addWidget(pc)

        # ----- terminal -----
        lp = Panel3D()
        ll = QVBoxLayout(lp)
        pad_layout(ll, 16, 12, 16, 14)
        ll.setSpacing(6)
        cap2 = QLabel("TERMINAL OUTPUT")
        cap2.setObjectName("cap")
        ll.addWidget(cap2)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(2000)
        mono = QFont("Monospace")
        mono.setStyleHint(QFont.Monospace)
        mono.setPointSize(10)
        self.log.setFont(mono)
        ll.addWidget(self.log, 1)
        v.addWidget(lp, 1)

    # ------------------------------------------------------------ helpers
    def _set_led(self, state):
        self.led.set_state(state)
        self.board.set_state(state)
        self.progress.set_state(state)

    def _update_clock(self):
        s = self.clock.elapsed() // 1000
        self.time_badge.setText(f"⏱ {s // 60:02d}:{s % 60:02d}")

    def _browse(self, edit, title, flt):
        start = os.path.dirname(edit.text()) if edit.text() else self.settings.value("last_dir", os.path.expanduser("~"))
        path, _ = QFileDialog.getOpenFileName(self, title, start, flt)
        if path:
            edit.setText(path)
            self.settings.setValue("last_dir", os.path.dirname(path))

    def _autodetect(self):
        start = self.settings.value("last_dir", os.path.expanduser("~"))
        d = QFileDialog.getExistingDirectory(self, "Select deploy/images folder", start)
        if not d:
            return
        self.settings.setValue("last_dir", d)

        def pick(patterns):
            for pat in patterns:
                found = [p for p in glob.glob(os.path.join(d, pat)) if os.path.isfile(p)]
                if found:
                    return min(found, key=len)  # shortest = un-timestamped symlink name
            return ""

        boot = pick(["imx-boot*flash_all*", "imx-boot*.bin*"])
        img = pick(["imx-image-full*.wic.zst", "*.wic.zst", "*.wic", "*.sdcard*"])
        if boot:
            self.boot_edit.setText(boot)
        if img:
            self.img_edit.setText(img)
        self._log(f"Auto-detect: boot  = {boot or 'NOT FOUND'}", "#9fb4d8")
        self._log(f"Auto-detect: image = {img or 'NOT FOUND'}", "#9fb4d8")

    def _on_target_changed(self):
        needs_image = TARGETS[self.target.currentData()][1]
        self.img_edit.setEnabled(needs_image)
        self.board.set_target("emmc" if "emmc" in self.target.currentData() else "sd")
        self._update_preview()

    def _uuu_cmd(self, args):
        uuu = self.uuu_edit.text().strip() or "uuu"
        return [uuu] + args

    def _flash_args(self):
        args = []
        if self.verbose_chk.isChecked():
            args.append("-v")
        if len(self._devices) > 1 and self.dev_combo.currentData():
            args += ["-m", self.dev_combo.currentData()]  # only talk to the chosen device
        t = self.target.currentData()
        args += ["-b", t, self.boot_edit.text().strip() or "<bootloader>"]
        if TARGETS[t][1]:
            args.append(self.img_edit.text().strip() or "<image>")
        return args

    def _update_preview(self, *_):
        if not hasattr(self, "preview"):
            return
        cmd = self._uuu_cmd(self._flash_args())
        if self.sudo_chk.isChecked():
            cmd = ["sudo"] + cmd
        self.preview.setText(shlex.join(cmd))

    def _log(self, text, color=None):
        esc = html.escape(text)
        if color is None:
            low = text.lower()
            if "fail" in low or "error" in low or "denied" in low:
                color = "#ff6b6b"
            elif "okay" in low or "success" in low or "done" in low:
                color = "#6bdc8b"
            elif "wait" in low:
                color = "#f0c36b"
            else:
                color = "#d0d0d8"
        self.log.appendHtml(f'<span style="color:{color}; white-space:pre;">{esc}</span>')
        self.log.moveCursor(QTextCursor.End)

    def _set_running(self, running):
        self.flash_btn.setEnabled(not running)
        self.check_btn.setEnabled(not running)
        self.stop_btn.setEnabled(running)
        for w in (self.boot_edit, self.img_edit, self.target, self.uuu_edit, self.sudo_chk, self.verbose_chk):
            w.setEnabled(not running)
        self.dev_combo.setEnabled(not running and bool(self._devices))
        if not running:
            self.img_edit.setEnabled(TARGETS[self.target.currentData()][1])
            self.sudo_chk.setEnabled(os.geteuid() != 0)

    def _reset_progress(self, indeterminate):
        self._last_step_key = None
        self._counts = (0, 0)
        self._update_counts()
        self.step_lbl.setText("Step  -  / -")
        self.progress.setRange(0, 0 if indeterminate else 100)
        self.progress.setValue(0)

    def _update_counts(self):
        self.ok_badge.setText(f"✔ Success {self._counts[0]}")
        self.fail_badge.setText(f"✘ Failure {self._counts[1]}")

    # -------------------------------------------------------------- run
    @staticmethod
    def _sudo_ok(pw):
        """True if sudo works: pw=None -> no password needed (NOPASSWD / live ticket); else verify pw."""
        p = QProcess()
        if pw is None:
            p.start("sudo", ["-n", "true"])
        else:
            p.start("sudo", ["-S", "-k", "-p", "", "true"])
            if p.waitForStarted(3000):
                p.write((pw + "\n").encode())
                p.closeWriteChannel()
        if not p.waitForFinished(6000):
            p.kill()
            return False
        return p.exitStatus() == QProcess.NormalExit and p.exitCode() == 0

    def _ask_password(self):
        """Ask for the sudo password (once per session); a wrong one is rejected right here."""
        if self._password is not None or shutil.which("sudo") is None or self._sudo_ok(None):
            return True
        while True:
            pw, ok = QInputDialog.getText(self, "sudo password", "Enter sudo password (asked only once per session):", QLineEdit.Password)
            if not ok:
                return False
            if self._sudo_ok(pw):
                self._password = pw
                self._log("sudo authenticated.", "#6bdc8b")
                return True
            QMessageBox.warning(self, "sudo", "Incorrect password, please try again.")

    def _prime_sudo(self):
        """At launch: ask for the sudo password once, then look for a device."""
        if os.geteuid() != 0 and self.sudo_chk.isChecked() and not self._ask_password():
            return
        self._check_device()

    def _run(self, args, mode="flash"):
        cmd = self._uuu_cmd(args)
        use_sudo = self.sudo_chk.isChecked() and os.geteuid() != 0
        self._sudo_used = use_sudo
        if use_sudo:
            if not self._ask_password():
                self._pending_flash = False
                return
            program, pargs = "sudo", ["-S", "-p", ""] + cmd
        else:
            program, pargs = cmd[0], cmd[1:]

        self._mode, self._buf, self._stopping = mode, "", False
        self._log("$ " + shlex.join((["sudo"] if use_sudo else []) + cmd), "#6fa8ff")
        self._reset_progress(indeterminate=(mode == "flash"))
        if mode == "flash":
            self.clock.start()
            self._update_clock()
            self.tick.start()
        self._set_running(True)
        self._set_led("run" if mode == "flash" else "scan")
        self.proc.start(program, pargs)

    # ---- device scan
    def _check_device(self):
        self.status.setText("Scanning USB devices (uuu -lsusb)...")
        self._run(["-lsusb"], "scan")

    @staticmethod
    def _parse_devices(text):
        """Rows of 'uuu -lsusb':  Path  Chip  Pro  Vid  Pid  BcdVersion  Serial_no"""
        devs = []
        for line in text.splitlines():
            f = line.split()
            if len(f) >= 3 and DEV_RE.match(f[0]):
                devs.append({"path": f[0], "chip": f[1], "pro": f[2].rstrip(":"),
                             "serial": f[6][-8:] if len(f) >= 7 else ""})
        return devs

    @staticmethod
    def _dev_label(d):
        return f"{d['path']}  •  {d['chip']}  •  {d['pro']}" + (f"  •  {d['serial']}" if d["serial"] else "")

    def _fill_devices(self, select=None):
        self.dev_combo.blockSignals(True)
        self.dev_combo.clear()
        if self._devices:
            for d in self._devices:
                self.dev_combo.addItem(self._dev_label(d), d["path"])
            self.dev_combo.setCurrentIndex(max(self.dev_combo.findData(select), 0))
        else:
            self.dev_combo.addItem("No device found", None)
        self.dev_combo.setEnabled(bool(self._devices))
        self.dev_combo.blockSignals(False)
        self._update_preview()

    def _finish_scan(self, code):
        pending, self._pending_flash = self._pending_flash, False
        if self._stopping:
            self.status.setText("■ Scan stopped.")
            self._log("=== STOPPED ===", "#f0c36b")
            self._set_led("stop")
            return
        if code != 0:
            self._devices = []
            self._fill_devices()
            self._log(f"Device scan failed (exit code {code}).", "#ff6b6b")
            self.status.setText(f"✘ Device scan failed (exit code {code}). Check the log.")
            self._set_led("fail")
            return
        prev = self.dev_combo.currentData()
        self._devices = self._parse_devices(self._buf)
        self._fill_devices(prev)
        n = len(self._devices)
        if n == 0:
            self._log("No device found.", "#ffb347")
            self.status.setText("✘ No device found.  Put the board in USB download (SDP) mode, connect the cable and press Check Device.")
            self._set_led("nodev")
            if pending:
                QMessageBox.warning(self, "No device found",
                                    "No i.MX device was detected.\n\nPut the board in USB download (SDP) mode, "
                                    "connect the USB cable, then try again.")
            return
        for d in self._devices:
            self._log(f"Device found: {self._dev_label(d)}", "#6bdc8b")
        self._set_led("found")
        self.status.setText(f"✔ Device found: {self._dev_label(self._devices[0])}" if n == 1
                            else f"✔ {n} devices found.  Select the device to flash.")
        if pending:
            self._begin_flash()

    # ---- flash
    def _flash(self):
        t = self.target.currentData()
        boot = self.boot_edit.text().strip()
        img = self.img_edit.text().strip()
        if not boot or not os.path.isfile(boot):
            QMessageBox.warning(self, "Bootloader missing", "Please select a valid bootloader file.")
            return
        if TARGETS[t][1] and (not img or not os.path.isfile(img)):
            QMessageBox.warning(self, "Image missing", "Please select a valid image file.")
            return
        self._pending_flash = True  # scan first; flashing only starts if a device is found
        self._check_device()
        self.status.setText("Looking for a connected device...")

    def _begin_flash(self):
        t = self.target.currentData()
        if len(self._devices) > 1:
            labels = [self._dev_label(d) for d in self._devices]
            label, ok = QInputDialog.getItem(self, "Select device", "Multiple devices found.\nSelect the device to flash:",
                                             labels, max(0, self.dev_combo.currentIndex()), False)
            if not ok:
                self.status.setText("Flash cancelled.")
                return
            self.dev_combo.setCurrentIndex(labels.index(label))
        dev = self._dev_label(self._devices[max(0, self.dev_combo.currentIndex())])
        if QMessageBox.question(
            self, "Confirm flash",
            f"Target: {t}\nDevice: {dev}\n\nThe board's {'eMMC' if 'emmc' in t else 'SD card'} will be overwritten.\nContinue?",
        ) != QMessageBox.Yes:
            self.status.setText("Flash cancelled.")
            return
        self.settings.setValue("boot", self.boot_edit.text().strip())
        self.settings.setValue("img", self.img_edit.text().strip())
        self.settings.setValue("target", t)
        self.status.setText("Flashing...  Do not unplug the cable; keep the board in boot mode.")
        self._run(self._flash_args())

    # ---- stop
    def _root_cmd(self, args):
        """Run a command as root (a process started through sudo cannot be signalled by a normal user)."""
        p = QProcess(self)
        p.finished.connect(p.deleteLater)
        if self._password is not None:
            p.started.connect(lambda: (p.write((self._password + "\n").encode()), p.closeWriteChannel()))
            p.start("sudo", ["-S", "-p", ""] + args)
        else:
            p.start("sudo", ["-n"] + args)

    def _signal_proc(self, sig):
        pid = int(self.proc.processId())
        if pid <= 0:
            return
        if self._sudo_used:
            self._root_cmd(["pkill", f"-{sig}", "-P", str(pid)])  # uuu itself (child of sudo)
            self._root_cmd(["kill", f"-{sig}", str(pid)])         # the sudo wrapper
        elif sig == "KILL":
            self.proc.kill()
        else:
            self.proc.terminate()

    def _stop(self):
        if self.proc.state() == QProcess.NotRunning:
            return
        self._stopping = True
        self._pending_flash = False
        self._log("Stopping...", "#f0c36b")
        self.status.setText("Stopping...")
        self.stop_btn.setEnabled(False)
        self._signal_proc("TERM")
        QTimer.singleShot(2500, self._force_stop)

    def _force_stop(self):
        if self._stopping and self.proc.state() != QProcess.NotRunning:
            self._log("Process did not exit - killing it.", "#f0c36b")
            self._signal_proc("KILL")

    # ----------------------------------------------------- process events
    def _on_started(self):
        if self._sudo_used and self._password is not None:
            self.proc.write((self._password + "\n").encode())

    def _on_output(self):
        data = bytes(self.proc.readAllStandardOutput()).decode(errors="replace")
        data = ANSI_RE.sub("", data)
        self._buf += data

        latest = None  # only the newest progress info in this chunk matters
        for piece in re.split(r"[\r\n]+", data):
            piece = piece.strip()
            if not piece:
                continue

            low = piece.lower()
            if "incorrect password" in low or "sorry, try again" in low:
                self._password = None
                self._log("Wrong sudo password.", "#ff6b6b")
                continue

            m = SC_RE.search(piece)
            if m:
                self._counts = (int(m.group(1)), int(m.group(2)))
                piece = SC_RE.sub("", piece).strip()
                if not piece:
                    continue

            handled = False
            for seg in SEG_SPLIT_RE.split(piece):
                seg = seg.strip()
                if not seg:
                    continue
                mp = PROG_RE.search(seg)
                if mp:
                    latest = ("pct", mp.groups())
                    handled = True
                    continue
                ms = STEP_RE.search(seg)
                if ms:
                    latest = ("state", ms.groups())
                    handled = True
                    continue
            if not handled:
                self._log(piece)

        self._update_counts()
        if latest:
            self._apply_progress(*latest)

    def _apply_progress(self, kind, g):
        dev, step, total = g[0], int(g[1]), int(g[2])
        if kind == "pct":
            pct, desc = int(g[3]), g[4].strip()
            if self.progress.maximum() == 0:
                self.progress.setRange(0, 100)
            self.progress.setValue(min(pct, 100))
        else:
            state, desc = g[3], g[4].strip()
            if self.progress.maximum() == 0:
                self.progress.setRange(0, 100)
            if state.lower().startswith("done") and step == total:
                self.progress.setValue(100)

        short = desc if len(desc) <= 70 else desc[:67] + "..."
        self.step_lbl.setText(f"Step {step} / {total}   •   {short}" if short else f"Step {step} / {total}")

        # one log line per step change, never per percent tick
        key = (dev, step, desc)
        if key != self._last_step_key and desc:
            self._last_step_key = key
            self._log(f"▶ [{step}/{total}] {desc}", "#8fd0ff")

    def _on_finished(self, code, _status):
        self.tick.stop()
        self._set_running(False)
        if self._mode == "scan":
            self._finish_scan(code)
            return
        self._update_clock()
        self.progress.setRange(0, 100)
        if self._stopping:
            self.status.setText("■ Stopped by user.")
            self._log("=== STOPPED ===", "#f0c36b")
            self._set_led("stop")
        elif code == 0:
            self.progress.setValue(100)
            self.status.setText(f"✔ Complete in {self.time_badge.text()[2:]}  -  flashing finished successfully.")
            self._log("=== SUCCESS ===", "#6bdc8b")
            self._set_led("ok")
        else:
            self.status.setText(f"✘ Failed (exit code {code}). Check the log.")
            self._log(f"=== FINISHED with exit code {code} ===", "#ff6b6b")
            self._set_led("fail")

    def _on_error(self, err):
        if err == QProcess.FailedToStart:
            self._pending_flash = False
            self.tick.stop()
            self._set_running(False)
            self.progress.setRange(0, 100)
            self._log("Could not start the command. Check the 'uuu' path (and that sudo is installed).", "#ff6b6b")
            self.status.setText("✘ Failed to start process.")
            self._set_led("fail")

    # ---------------------------------------------------------- settings
    def _load_settings(self):
        self.boot_edit.setText(self.settings.value("boot", ""))
        self.img_edit.setText(self.settings.value("img", ""))
        idx = self.target.findData(self.settings.value("target", "emmc_all"))
        self.target.setCurrentIndex(max(idx, 0))
        self._on_target_changed()

    def closeEvent(self, e):
        if self.proc.state() != QProcess.NotRunning:
            if QMessageBox.question(self, "Quit", "Flashing is in progress. Quit anyway?") != QMessageBox.Yes:
                e.ignore()
                return
            self._stop()
            if not self.proc.waitForFinished(2500):
                self._force_stop()
                self.proc.waitForFinished(1500)
        e.accept()


def dark_palette():
    p = QPalette()
    p.setColor(QPalette.Window, QColor("#1b1d27"))
    p.setColor(QPalette.WindowText, QColor("#e6e6ee"))
    p.setColor(QPalette.Base, QColor("#14151c"))
    p.setColor(QPalette.AlternateBase, QColor("#1d1f29"))
    p.setColor(QPalette.Text, QColor("#f0f0f8"))
    p.setColor(QPalette.Button, QColor("#383c58"))
    p.setColor(QPalette.ButtonText, QColor("#ffffff"))
    p.setColor(QPalette.ToolTipBase, QColor("#1d1f29"))
    p.setColor(QPalette.ToolTipText, QColor("#f0f0f8"))
    p.setColor(QPalette.Highlight, QColor("#3d6cf0"))
    p.setColor(QPalette.HighlightedText, QColor("#ffffff"))
    return p


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setPalette(dark_palette())
    app.setStyleSheet(STYLE)
    w = Flasher()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()