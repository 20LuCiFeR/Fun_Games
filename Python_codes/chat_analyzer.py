#!/usr/bin/env python3
"""
LocalChat Analyzer
==================
A 100% offline chat analyzer for WhatsApp (1-to-1 and group) and Telegram exports.
Nothing is uploaded anywhere - everything is processed on your own computer.

Install:   pip install PyQt6 pandas numpy emoji
Run:       python chat_analyzer.py            (or drag a chat file onto the window)

Supported inputs
  * WhatsApp  -> Chat > More > Export chat > "Without media"  (.txt or the .zip)
  * Telegram  -> Desktop > Export chat history > JSON         (result.json)
"""
import sys
import re
import json
import math
import time
import random
import zipfile
import tempfile
import itertools
from collections import Counter
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from PyQt6.QtCore import Qt, QThread, pyqtSignal, QDate, QTimer, QRectF, QPointF
from PyQt6.QtGui import (QAction, QColor, QBrush, QFont, QFontMetrics, QLinearGradient, QPainter,
                         QPainterPath, QPen, QPixmap, QPolygonF, QRadialGradient, QTransform)
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QFrame, QLabel, QPushButton, QVBoxLayout,
    QHBoxLayout, QGridLayout, QTabWidget, QScrollArea, QFileDialog, QComboBox,
    QListWidget, QListWidgetItem, QDateEdit, QSpinBox, QTableWidget,
    QTableWidgetItem, QHeaderView, QLineEdit, QCheckBox, QTextBrowser, QStackedWidget,
    QProgressBar, QMessageBox, QSplitter, QAbstractItemView, QDialog,
)

# --------------------------------------------------------------------------- #
#  Theme
# --------------------------------------------------------------------------- #
BG, PANEL, PANEL2 = "#14151b", "#1d1f28", "#272a36"
TEXT, MUTED, ACCENT, BORDER = "#e8eaf0", "#8d93a6", "#7C9CFF", "#2d303e"
PALETTE = ["#7C9CFF", "#FF7A90", "#4ADE80", "#FBBF24", "#C084FC",
           "#22D3EE", "#FB923C", "#F472B6", "#A3E635", "#2DD4BF"]
OTHERS_COLOR = "#5b6075"
MAX_CHART_PEOPLE = 8

QSS = f"""
QWidget {{ background: {BG}; color: {TEXT}; font-size: 13px; }}
QLabel {{ background: transparent; }}
QFrame#sidebar {{ background: {PANEL}; border-right: 1px solid {BORDER}; }}
QFrame#card {{ background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #22242f, stop:1 {PANEL}); border: 1px solid {BORDER}; border-radius: 14px; }}
QFrame#card QLabel, QFrame#card QWidget {{ background: transparent; }}
QLabel#cardTitle {{ font-weight: 600; font-size: 13px; }}
QLabel#statValue {{ font-size: 24px; font-weight: 700; }}
QLabel#statCaption {{ color: {MUTED}; font-size: 11px; }}
QLabel#h1 {{ font-size: 18px; font-weight: 700; }}
QLabel#muted {{ color: {MUTED}; }}
QPushButton {{ background: {PANEL2}; border: 1px solid #373a4c; border-radius: 8px; padding: 7px 12px; }}
QPushButton:hover {{ border-color: {ACCENT}; }}
QPushButton#primary {{ background: {ACCENT}; color: #0d1124; font-weight: 700; border: none; }}
QPushButton#primary:hover {{ background: #9bb3ff; }}
QFrame#card QPushButton#primary {{ background: {ACCENT}; color: #0d1124; font-weight: 700; border: none; }}
QFrame#card QPushButton#primary:disabled {{ background: #3a3e50; color: #8d93a6; }}
QPushButton#ghost {{ background: transparent; border: 1px solid {BORDER}; padding: 3px 9px; color: {MUTED}; font-size: 11px; }}
QPushButton#ghost:hover {{ color: {TEXT}; border-color: {ACCENT}; }}
QTabWidget::pane {{ border: none; }}
QTabBar::tab {{ background: transparent; padding: 10px 18px; color: {MUTED}; border-bottom: 2px solid transparent; }}
QTabBar::tab:selected {{ color: {TEXT}; border-bottom: 2px solid {ACCENT}; }}
QTabBar::tab:hover {{ color: {TEXT}; }}
QTableWidget {{ background: {PANEL}; gridline-color: {BORDER}; border: 1px solid {BORDER};
               border-radius: 8px; alternate-background-color: #222531; }}
QHeaderView::section {{ background: {PANEL2}; color: {MUTED}; border: none; padding: 7px; font-weight: 600; }}
QLineEdit, QComboBox, QSpinBox, QDateEdit {{ background: {PANEL2}; border: 1px solid #373a4c;
               border-radius: 6px; padding: 5px 8px; }}
QComboBox QAbstractItemView {{ background: {PANEL2}; selection-background-color: {ACCENT}; selection-color: #0d1124; }}
QListWidget {{ background: {PANEL2}; border: 1px solid #373a4c; border-radius: 8px; }}
QListWidget::item {{ padding: 3px; }}
QScrollArea {{ border: none; background: transparent; }}
QCheckBox::indicator {{ width: 16px; height: 16px; border: 1px solid #4a4e63; border-radius: 4px; background: {PANEL2}; }}
QCheckBox::indicator:checked {{ background: {ACCENT}; }}
QTextBrowser {{ background: {PANEL}; border: 1px solid {BORDER}; border-radius: 10px; padding: 8px; }}
QScrollBar:vertical {{ background: transparent; width: 10px; }}
QScrollBar::handle:vertical {{ background: #3a3e50; border-radius: 5px; min-height: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; }}
QScrollBar::handle:horizontal {{ background: #3a3e50; border-radius: 5px; }}
QPushButton#typecard {{ background: {PANEL}; border: 1px solid #3a3e50; border-radius: 12px; text-align: left; }}
QPushButton#typecard:hover {{ border-color: {ACCENT}; background: {PANEL2}; }}
QPushButton#typecard[suggested="true"] {{ border: 1px solid {ACCENT}; }}
QDialog {{ background: {BG}; }}
QProgressBar {{ background: {PANEL2}; border: none; border-radius: 4px; max-height: 8px; }}
QProgressBar::chunk {{ background: {ACCENT}; border-radius: 4px; }}
QStatusBar {{ background: {PANEL}; color: {MUTED}; }}
QMenuBar {{ background: {PANEL}; }}
QMenu {{ background: {PANEL2}; border: 1px solid {BORDER}; }}
QMenu::item:selected {{ background: {ACCENT}; color: #0d1124; }}
"""

# --------------------------------------------------------------------------- #
#  Parsing
# --------------------------------------------------------------------------- #
WA_RE = re.compile(
    r"^\[?(\d{1,4}[/.\-]\d{1,2}[/.\-]\d{1,4}),?\s+"
    r"(\d{1,2}[:.]\d{2}(?:[:.]\d{2})?)\s*([AaPp]\.?\s?[Mm]\.?)?\]?\s*(?:-\s*)?(.*)$"
)
SENDER_RE = re.compile(r"^([^:]{1,60}?):(?:\s(.*))?$")
MEDIA_RE = re.compile(
    r"(<media omitted>|<attached:|\b(image|video|audio|sticker|gif|document|contact card)\s+omitted\b"
    r"|\(file attached\)|^\s*(img|vid|ptt|aud|stk)-\d{8}-wa\d+)", re.I)
DELETED = {"this message was deleted", "you deleted this message"}
EDITED_RE = re.compile(r"\s*<this message was edited>\s*$", re.I)

URL_RE = r"https?://\S+|www\.\S+"
TOKEN_RE = re.compile(r"[\w\u0900-\u097F]+(?:'[\w]+)?")

try:
    import emoji as _emoji

    def extract_emojis(t):
        return [d["emoji"] for d in _emoji.emoji_list(t)]
except Exception:  # fallback if the `emoji` package isn't installed
    _EMOJI_FALLBACK = re.compile("[\U0001F300-\U0001F3FA\U0001F400-\U0001FAFF\u2600-\u27BF\u2B50\u2B55]")

    def extract_emojis(t):
        return _EMOJI_FALLBACK.findall(t)

STOP = set("""
the and for are but not you your yours with this that have has had was were will would can could should
from they them their there then than what when where which who whom how why all any are been being both
did does doing done each few more most other some such only own same too very just also into over under
again further once here about above after before below between during out off its it's i'm i've i'll i'd
you're you've you'll you'd he's she's we're we've we'll they're they've they'll don't doesn't didn't won't
can't couldn't wouldn't shouldn't isn't aren't wasn't weren't haven't hasn't hadn't let's that's there's
what's who's yeah yes yep nope okay ok lol hmm umm like get got going gonna wanna one two now still even
really much many well way back see say said know think want need come going let make made
hai hain hoon hun hua hui hue tha thi the ho hona hota hoti hote kya ke ki ka ko se mein main mai tum tu
aap hum nahi nhi nahin na bhi toh to yeh ye woh wo kar kr karo karna kuch aur ya par pe liye mera meri
mere tera teri tere mujhe tujhe usse isse abhi bas ab jo ne koi ek kaise kyu kyun kab kaha kahan raha
rahi rha rhi gaya gaya gya haan han accha acha theek thik hi hee bhai yaar yar matlab fir phir kal aaj
media omitted image video audio sticker gif deleted message edited attached document
""".split())


def clean_text(s: str) -> str:
    return (s.replace("\u200e", "").replace("\u200f", "")
             .replace("\u202f", " ").replace("\u00a0", " "))


def classify(text: str) -> str:
    t = text.strip()
    if t.lower() in DELETED:
        return "deleted"
    if MEDIA_RE.search(t):
        return "media"
    return "text"


def tokenize(t: str):
    t = re.sub(URL_RE, " ", t.lower())
    return [w for w in TOKEN_RE.findall(t) if len(w) >= 3 and not w.isdigit() and w not in STOP]


def _detect_order(parts):
    first = [p[0] for p in parts]
    second = [p[1] for p in parts]
    if max(first) > 31:
        return "ymd"
    if max(first) > 12:
        return "dmy"
    if max(second) > 12:
        return "mdy"
    return "dmy"


def _build_rows(entries, order):
    rows, bad = [], 0
    for d, t, ap, sender, msg in entries:
        try:
            a, b, c = [int(x) for x in re.split(r"[/.\-]", d)]
            if order == "ymd":
                y, mo, da = a, b, c
            elif order == "dmy":
                da, mo, y = a, b, c
            else:
                mo, da, y = a, b, c
            if y < 100:
                y += 2000
            tp = [int(x) for x in re.split(r"[:.]", t)]
            h, mi = tp[0], tp[1]
            s = tp[2] if len(tp) > 2 else 0
            if ap:
                ap2 = ap.lower().replace(".", "").replace(" ", "")
                h = (h % 12) + (12 if ap2 == "pm" else 0)
            rows.append((datetime(y, mo, da, h, mi, s), sender, msg))
        except (ValueError, IndexError):
            bad += 1
    return rows, bad


def parse_whatsapp(text: str, order: str = "auto") -> pd.DataFrame:
    entries, cur = [], None
    for line in clean_text(text).split("\n"):
        line = line.rstrip("\r")
        m = WA_RE.match(line)
        if m:
            d, t, ap, rest = m.groups()
            sm = SENDER_RE.match(rest)
            if sm:
                cur = [d, t, ap, sm.group(1).strip(), sm.group(2) or ""]
                entries.append(cur)
            else:
                cur = None  # system message (joined, left, encryption notice ...)
        elif cur is not None:
            cur[4] += "\n" + line
    if not entries:
        raise ValueError("No WhatsApp-style messages found in this file.")

    parts = [[int(x) for x in re.split(r"[/.\-]", e[0])] for e in entries]
    if order == "auto":
        order = _detect_order(parts)
    rows, bad = _build_rows(entries, order)
    if order in ("dmy", "mdy") and bad > 0.02 * len(entries):
        alt = "mdy" if order == "dmy" else "dmy"
        rows2, bad2 = _build_rows(entries, alt)
        if bad2 < bad:
            rows = rows2
    if not rows:
        raise ValueError("Could not understand the dates in this file.")
    df = pd.DataFrame(rows, columns=["ts", "sender", "text"])
    df["text"] = df.text.str.replace(EDITED_RE, "", regex=True).str.strip()
    df["kind"] = df.text.map(classify)
    return df


def parse_telegram(text: str) -> pd.DataFrame:
    data = json.loads(text)
    if "chats" in data:  # full-account export: take the biggest chat
        chats = data["chats"]["list"]
        data = max(chats, key=lambda c: len(c.get("messages", [])))
    rows = []
    for m in data.get("messages", []):
        if m.get("type") != "message":
            continue
        t = m.get("text", "")
        if isinstance(t, list):
            t = "".join(x if isinstance(x, str) else x.get("text", "") for x in t)
        is_media = bool(m.get("media_type") or m.get("photo") or m.get("file"))
        if is_media and not t:
            t = "<media>"
        if not t.strip():
            continue
        try:
            ts = datetime.fromisoformat(m["date"])
        except Exception:
            continue
        rows.append((ts, m.get("from") or m.get("actor") or "Unknown", t,
                     "media" if is_media else "text"))
    if not rows:
        raise ValueError("No messages found in this Telegram export.")
    return pd.DataFrame(rows, columns=["ts", "sender", "text", "kind"])


def enrich(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values("ts", kind="stable").reset_index(drop=True)
    df["date"] = df.ts.dt.normalize()
    df["hour"] = df.ts.dt.hour
    df["weekday"] = df.ts.dt.dayofweek
    df["is_text"] = df.kind.eq("text")
    df["is_media"] = df.kind.eq("media")
    df["is_deleted"] = df.kind.eq("deleted")
    body = df.text.where(df.is_text, "")
    df["words"] = body.str.split().str.len().fillna(0).astype(int)
    df["chars"] = body.str.len()
    df["links"] = body.str.count(URL_RE)
    df["question"] = body.str.contains(r"\?", regex=True)
    df["night"] = df.hour.between(0, 4)
    df["emojis"] = [extract_emojis(t) if ok else [] for t, ok in zip(df.text, df.is_text)]
    df["n_emoji"] = df.emojis.map(len)
    df["tokens"] = [tokenize(t) if ok else [] for t, ok in zip(df.text, df.is_text)]
    return df


def read_chat_file(path: str):
    low = path.lower()
    if low.endswith(".zip"):
        with zipfile.ZipFile(path) as z:
            names = [n for n in z.namelist()
                     if n.lower().endswith((".txt", ".json")) and not n.startswith("__MACOSX")]
            if not names:
                raise ValueError("No .txt or .json chat file inside this zip.")
            name = max(names, key=lambda n: z.getinfo(n).file_size)
            raw, ext = z.read(name), name.lower().rsplit(".", 1)[-1]
    else:
        with open(path, "rb") as f:
            raw = f.read()
        ext = low.rsplit(".", 1)[-1]
    return raw.decode("utf-8-sig", errors="replace"), ext


def load_chat(path: str, order: str = "auto") -> pd.DataFrame:
    text, ext = read_chat_file(path)
    if ext == "json" or text.lstrip().startswith("{"):
        df = parse_telegram(text)
    else:
        df = parse_whatsapp(text, order)
    return enrich(df)


def make_demo_chat() -> str:
    rnd = random.Random(7)
    people = {"Aarav": 0.42, "Riya": 0.38, "Kabir": 0.20}
    names, weights = list(people), list(people.values())
    phrases = [
        "kal movie chalein? \U0001F37F", "haha that was so funny \U0001F602", "bro where are you??",
        "send me the notes please", "ok done", "good morning \u2600\uFE0F", "I'm hungry \U0001F355",
        "lets plan the trip this weekend", "did you see the match last night?", "<Media omitted>",
        "https://youtu.be/dQw4w9WgXcQ", "lol \U0001F602\U0001F602", "what time are we meeting?",
        "I'll call you in 5 minutes", "bhai pizza ya burger?", "exam ki taiyari kaisi hai?",
        "this is the best day ever \u2764\uFE0F", "can you check the assignment?", "good night \U0001F319",
        "no way \U0001F62D", "party tonight?", "traffic is crazy today", "love this song \U0001F3B6",
    ]
    angry = ["you never listen!!! I hate this", "STOP IT", "bakwas baat mat karo", "I'm really angry right now",
             "why do you always ignore me?!", "shut up yaar, enough", "this is so annoying \U0001F621"]
    sadp = ["I'm sad today \U0001F622", "feeling lonely tbh", "so worried about exams", "sorry yaar, my bad",
            "don't feel like talking", "I miss the old days \U0001F494"]
    hw = [3, 2, 1, 1, 0, 0, 1, 2, 3, 3, 3, 4, 5, 4, 3, 3, 4, 5, 6, 8, 9, 9, 8, 5]
    start, lines = datetime(2025, 1, 1), ["12/01/2025, 10:00 - Messages and calls are end-to-end encrypted."]
    for day in range(320):
        if rnd.random() < 0.1:
            continue
        for _ in range(rnd.randint(1, 4)):
            hour = rnd.choices(range(24), weights=hw)[0]
            ts = start + timedelta(days=day, hours=hour, minutes=rnd.randint(0, 59))
            for _ in range(rnd.randint(3, 25)):
                s = rnd.choices(names, weights)[0]
                ts += timedelta(seconds=rnd.randint(5, 500 if s != "Kabir" else 2500))
                pool = phrases
                if 100 <= day <= 115 and s == "Riya" and rnd.random() < 0.5:
                    pool = angry
                elif 200 <= day <= 212 and s == "Aarav" and rnd.random() < 0.4:
                    pool = sadp
                lines.append(f"{ts:%d/%m/%Y, %H:%M} - {s}: {rnd.choice(pool)}")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
#  Analytics
# --------------------------------------------------------------------------- #
def fmt_dur(minutes: float) -> str:
    if minutes is None or np.isnan(minutes):
        return "-"
    if minutes < 1:
        return f"{minutes * 60:.0f}s"
    if minutes < 60:
        return f"{minutes:.0f} min"
    if minutes < 1440:
        return f"{minutes / 60:.1f} h"
    return f"{minutes / 1440:.1f} d"


def hour_label(h: int) -> str:
    return f"{(h % 12) or 12} {'AM' if h < 12 else 'PM'}"


def compute_stats(df: pd.DataFrame, gap_hours: float):
    """Returns (overview dict, per-person DataFrame)."""
    df = df.reset_index(drop=True)
    gap = df.ts.diff()
    new_conv = gap.isna() | (gap > timedelta(hours=gap_hours))
    starters = df[new_conv].sender.value_counts()

    prev_sender = df.sender.shift()
    reply_mask = prev_sender.notna() & (prev_sender != df.sender) & (gap <= timedelta(hours=12))
    reply_min = (gap[reply_mask].dt.total_seconds() / 60).groupby(df.sender[reply_mask]).median()

    t = df.groupby("sender").agg(
        messages=("text", "size"), words=("words", "sum"), media=("is_media", "sum"),
        deleted=("is_deleted", "sum"), links=("links", "sum"), questions=("question", "sum"),
        emojis=("n_emoji", "sum"), night=("night", "sum"), text_msgs=("is_text", "sum"),
        longest=("words", "max"), active_days=("date", "nunique"),
    )
    t["share"] = t.messages / t.messages.sum() * 100
    t["avg_words"] = t.words / t.text_msgs.clip(lower=1)
    t["night_pct"] = t.night / t.messages * 100
    t["starts"] = starters.reindex(t.index).fillna(0).astype(int)
    gap_after = df.ts.shift(-1) - df.ts
    enders = df[gap_after.isna() | (gap_after > timedelta(hours=gap_hours))].sender.value_counts()
    t["ends"] = enders.reindex(t.index).fillna(0).astype(int)
    t["reply_min"] = reply_min.reindex(t.index)
    t = t.sort_values("messages", ascending=False)

    days = np.sort(df.date.unique())
    diffs = np.diff(days).astype("timedelta64[D]").astype(int) if len(days) > 1 else np.array([], dtype=int)
    streak = best = 1
    for d in diffs:
        streak = streak + 1 if d == 1 else 1
        best = max(best, streak)
    per_day = df.groupby("date").size()
    span = (df.date.max() - df.date.min()).days + 1
    ov = dict(
        total=len(df), words=int(df.words.sum()), media=int(df.is_media.sum()),
        people=df.sender.nunique(), span=span, active_days=len(days),
        per_day=len(df) / max(span, 1), busiest_date=per_day.idxmax(), busiest_count=int(per_day.max()),
        streak=best, silence=int(diffs.max() - 1) if len(diffs) and diffs.max() > 1 else 0,
        start=df.ts.min(), end=df.ts.max(), conversations=int(new_conv.sum()),
    )
    return ov, t


def build_insights(df, ov, t, ec) -> str:
    items = []
    top = t.index[0]
    items.append(f"<b>{top}</b> is the chatterbox with <b>{t.share.iloc[0]:.0f}%</b> of all messages.")
    if len(t) > 1:
        r = t.reply_min.dropna()
        if len(r):
            items.append(f"\u26A1 Fastest replier: <b>{r.idxmin()}</b> (median {fmt_dur(r.min())}). "
                         f"Slowest: <b>{r.idxmax()}</b> ({fmt_dur(r.max())}).")
        if t.starts.sum():
            s = t.starts.idxmax()
            items.append(f"\U0001F4AC <b>{s}</b> starts most conversations "
                         f"({t.starts.max() / t.starts.sum() * 100:.0f}%).")
        a = t.avg_words.idxmax()
        items.append(f"\U0001F4DD Longest messages on average: <b>{a}</b> ({t.avg_words.max():.1f} words/msg).")
    n = t.night_pct
    if n.max() >= 5:
        items.append(f"\U0001F989 Night owl: <b>{n.idxmax()}</b> sends {n.max():.0f}% of messages between 12-5 AM.")
    if t.emojis.sum():
        e = t.emojis.idxmax()
        fav = ec.get(e).most_common(1)[0][0] if ec.get(e) else ""
        items.append(f"\U0001F600 Emoji champion: <b>{e}</b> ({int(t.emojis.max()):,} emojis) {fav}")
    if t.questions.sum():
        items.append(f"\u2753 Curious one: <b>{t.questions.idxmax()}</b> asked {int(t.questions.max()):,} questions.")
    if t.links.sum():
        items.append(f"\U0001F517 Link sharer: <b>{t.links.idxmax()}</b> ({int(t.links.max()):,} links).")
    hc = df.groupby("hour").size()
    wd = df.groupby("weekday").size()
    names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    items.append(f"\u23F0 Peak chatting hour: <b>{hour_label(int(hc.idxmax()))}</b>; busiest weekday: "
                 f"<b>{names[int(wd.idxmax())]}</b>.")
    items.append(f"\U0001F4C5 Busiest day: <b>{ov['busiest_date']:%d %b %Y}</b> ({ov['busiest_count']:,} messages).")
    items.append(f"\U0001F525 Longest daily streak: <b>{ov['streak']} days</b>"
                 + (f"; longest silence: <b>{ov['silence']} days</b>." if ov['silence'] else "."))
    li = "".join(f"<li style='margin-bottom:7px'>{i}</li>" for i in items)
    return f"<ul style='margin-left:-18px;font-size:13px'>{li}</ul>"


def signature_words(wc: dict, min_total=40, top_n=8):
    """Words a person uses far more than everybody else."""
    total = Counter()
    for c in wc.values():
        total.update(c)
    out = {}
    for p, c in wc.items():
        n_p = sum(c.values())
        n_o = sum(total.values()) - n_p
        if n_p < min_total or n_o < min_total:
            continue
        scored = []
        for w, k in c.items():
            if k < 5:
                continue
            other = total[w] - k
            score = (k / n_p) / ((other + 1) / n_o)
            scored.append((score, k, w))
        out[p] = [w for _, _, w in sorted(scored, reverse=True)[:top_n]]
    return out


# --------------------------------------------------------------------------- #
#  Background loader
# --------------------------------------------------------------------------- #
class LoadWorker(QThread):
    done = pyqtSignal(object, str)
    failed = pyqtSignal(str)

    def __init__(self, path, order):
        super().__init__()
        self.path, self.order = path, order

    def run(self):
        try:
            self.done.emit(load_chat(self.path, self.order), self.path)
        except Exception as e:  # noqa
            self.failed.emit(str(e))


# --------------------------------------------------------------------------- #
#  Reusable widgets
# --------------------------------------------------------------------------- #
# --------------------------------------------------------------------------- #
#  3D toolkit  (pure QPainter - no extra dependencies)
#  Scene3D gives every chart an orbit camera: drag to rotate, Ctrl+scroll to zoom,
#  double-click to reset, hover to see the numbers.
# --------------------------------------------------------------------------- #
AF = Qt.AlignmentFlag


def aflags(*a):
    r = 0
    for x in a:
        r |= int(x)
    return r


def clamp(x, lo=0.0, hi=1.0):
    return lo if x < lo else hi if x > hi else x


def lerp(a, b, t):
    return a + (b - a) * t


def ease_out(t):
    t = clamp(t)
    return 1 - (1 - t) ** 3


def ease_io(t):
    t = clamp(t)
    return t * t * (3 - 2 * t)


def approach(cur, target, dt, rate=12.0):
    return target + (cur - target) * math.exp(-rate * dt)


_SHADE = {}
FACE_LIGHT = {"top": 1.14, "front": 0.92, "back": 0.62, "left": 0.76, "right": 0.68}


def shade(color, f):
    """Colour 'color' (hex string) multiplied by brightness f, cached."""
    key = (color, round(f, 2))
    c = _SHADE.get(key)
    if c is None:
        q = QColor(color)
        r, g, b = q.red(), q.green(), q.blue()
        if f > 1:
            t = f - 1
            c = QColor(int(r + (255 - r) * t), int(g + (255 - g) * t), int(b + (255 - b) * t))
        else:
            c = QColor(int(r * f), int(g * f), int(b * f))
        _SHADE[key] = c
    return c


def mix(c1, c2, t):
    a, b = QColor(c1), QColor(c2)
    return QColor(int(lerp(a.red(), b.red(), t)), int(lerp(a.green(), b.green(), t)),
                  int(lerp(a.blue(), b.blue(), t)))


def heat_color(t):
    t = clamp(t)
    if t < 0.55:
        return mix("#2b2f45", ACCENT, t / 0.55)
    return mix(ACCENT, "#ffffff", (t - 0.55) / 0.45)


class Scene3D(QWidget):
    """Base class: orbit camera + hover picking + tooltip. Subclasses implement paint_scene()."""
    HINT = "drag to rotate  \u00B7  Ctrl+scroll to zoom  \u00B7  double-click to reset"
    GROW_T = 1.6                      # seconds of intro animation

    def __init__(self, yaw=0.5, pitch=0.55, dist=30.0, min_h=260):
        super().__init__()
        self.setMinimumHeight(min_h)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.d_yaw, self.d_pitch = yaw, pitch
        self.yaw, self.pitch, self.zoom = yaw - 0.9, pitch + 0.3, 0.8      # intro: swing into place
        self.t_yaw, self.t_pitch, self.t_zoom = yaw, pitch, 1.0
        self.v_yaw = self.v_pitch = 0.0
        self.dist = dist
        self.fit_w, self.fit_h = 10.0, 6.0     # half-extent of the scene (world units) for auto-scaling
        self.focus_y = 0.0
        self.drag = None
        self.mouse = None
        self.hover = None
        self.picks = []
        self.born = time.perf_counter()
        self._last = self.born
        self.timer = QTimer(self)
        self.timer.setInterval(16)
        self.timer.timeout.connect(self._tick)
        self.touched = False

    # ----- animation -------------------------------------------------------- #
    def restart(self):
        self.born = time.perf_counter()
        self._last = self.born
        self.wake()

    def wake(self):
        if not self.timer.isActive():
            self._last = time.perf_counter()
            self.timer.start()

    def grow_t(self):
        return time.perf_counter() - self.born

    def busy(self):
        return False

    def _tick(self):
        now = time.perf_counter()
        dt = min(0.05, now - self._last)
        self._last = now
        if self.drag is None:
            self.t_yaw += self.v_yaw * dt
            self.t_pitch = clamp(self.t_pitch + self.v_pitch * dt, 0.12, 1.45)
            k = math.exp(-3.2 * dt)
            self.v_yaw *= k
            self.v_pitch *= k
            if abs(self.v_yaw) < 0.01:
                self.v_yaw = 0.0
            if abs(self.v_pitch) < 0.01:
                self.v_pitch = 0.0
        rate = 4.0 if self.grow_t() < 1.2 else 16.0
        self.yaw = approach(self.yaw, self.t_yaw, dt, rate)
        self.pitch = approach(self.pitch, self.t_pitch, dt, rate)
        self.zoom = approach(self.zoom, self.t_zoom, dt, rate)
        self.step(dt)
        self.update()
        settled = (abs(self.yaw - self.t_yaw) < 2e-3 and abs(self.pitch - self.t_pitch) < 2e-3
                   and abs(self.zoom - self.t_zoom) < 2e-3 and self.v_yaw == 0 and self.v_pitch == 0
                   and self.drag is None)
        if settled and self.grow_t() > self.GROW_T and not self.busy():
            self.timer.stop()

    def step(self, dt):
        pass

    def fit_points(self):
        return []

    # ----- camera ----------------------------------------------------------- #
    def view_rect(self):
        return QRectF(0, 0, self.width(), self.height())

    def cam_setup(self):
        y, p = self.yaw, self.pitch
        self._cy, self._sy, self._cp, self._sp = math.cos(y), math.sin(y), math.cos(p), math.sin(p)
        d = self.dist
        self.C = (d * self._cp * self._sy, d * self._sp + self.focus_y, -d * self._cp * self._cy)
        vr = self.view_rect()
        self._ox, self._oy = vr.center().x(), vr.center().y()
        fw = vr.width() * 0.47 / max(self.fit_w, 0.1)
        fh = vr.height() * 0.46 / max(self.fit_h, 0.1)
        self._f = d * min(fw, fh) * self.zoom
        pts = self.fit_points()
        if pts:                                        # shrink (never grow) so a rotated scene stays in frame
            xs, ys = [], []
            for q in pts:
                sx, sy, _ = self.P(*q)
                xs.append(sx)
                ys.append(sy)
            bw, bh = max(xs) - min(xs), max(ys) - min(ys)
            s = min(vr.width() * 0.95 / max(bw, 1.0), vr.height() * 0.9 / max(bh, 1.0), 1.0)
            if s < 1.0:
                self._f *= s

    def P(self, x, y, z):
        y -= self.focus_y
        x1 = x * self._cy + z * self._sy
        z1 = -x * self._sy + z * self._cy
        y2 = y * self._cp + z1 * self._sp
        z2 = -y * self._sp + z1 * self._cp
        k = self._f / (z2 + self.dist)
        return self._ox + x1 * k, self._oy - y2 * k, z2

    def poly(self, pts):
        out = []
        for q in pts:
            sx, sy, _ = self.P(*q)
            out.append(QPointF(sx, sy))
        return QPolygonF(out)

    def text3(self, p, s, x, y, z, px=10, color=MUTED, align=AF.AlignHCenter, bold=False, dy=0):
        sx, sy, _ = self.P(x, y, z)
        f = p.font()
        f.setPixelSize(px)
        f.setBold(bold)
        p.setFont(f)
        p.setPen(QColor(color))
        w = 200
        if align == AF.AlignRight:
            r = QRectF(sx - w, sy - 9 + dy, w, 18)
        elif align == AF.AlignLeft:
            r = QRectF(sx, sy - 9 + dy, w, 18)
        else:
            r = QRectF(sx - w / 2, sy - 9 + dy, w, 18)
        p.drawText(r, aflags(align, AF.AlignVCenter), s)

    def draw_face(self, p, pts, color, factor, pick=None, outline=None):
        pg = self.poly(pts)
        p.setBrush(shade(color, factor))
        p.setPen(QPen(outline or QColor(0, 0, 0, 55), 0.8))
        p.drawPolygon(pg)
        if pick is not None:
            self.picks.append((pg, pick))

    def draw_box(self, p, x0, x1, y0, y1, z0, z1, color, pick=None, hl=False, boost=1.0):
        """Draws the (up to 3) faces of an axis-aligned box that face the camera."""
        cx, cy, cz = self.C
        lit = 1.18 if hl else 1.0
        lit *= boost
        if cx < x0:
            self.draw_face(p, [(x0, y0, z0), (x0, y1, z0), (x0, y1, z1), (x0, y0, z1)], color,
                           FACE_LIGHT["left"] * lit, pick)
        elif cx > x1:
            self.draw_face(p, [(x1, y0, z0), (x1, y0, z1), (x1, y1, z1), (x1, y1, z0)], color,
                           FACE_LIGHT["right"] * lit, pick)
        if cz < z0:
            self.draw_face(p, [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0)], color,
                           FACE_LIGHT["front"] * lit, pick)
        elif cz > z1:
            self.draw_face(p, [(x0, y0, z1), (x0, y1, z1), (x1, y1, z1), (x1, y0, z1)], color,
                           FACE_LIGHT["back"] * lit, pick)
        if cy > y1:
            self.draw_face(p, [(x0, y1, z0), (x1, y1, z0), (x1, y1, z1), (x0, y1, z1)], color,
                           FACE_LIGHT["top"] * lit, pick,
                           QColor(255, 255, 255, 120) if hl else None)

    def floor(self, p, x0, x1, z0, z1, nx=0, nz=0):
        pg = self.poly([(x0, 0, z0), (x1, 0, z0), (x1, 0, z1), (x0, 0, z1)])
        g = QLinearGradient(pg.boundingRect().topLeft(), pg.boundingRect().bottomLeft())
        g.setColorAt(0, QColor(255, 255, 255, 8))
        g.setColorAt(1, QColor(255, 255, 255, 22))
        p.setBrush(QBrush(g))
        p.setPen(QPen(QColor(255, 255, 255, 40), 1))
        p.drawPolygon(pg)
        p.setPen(QPen(QColor(255, 255, 255, 14), 1))
        for i in range(1, nx):
            x = lerp(x0, x1, i / nx)
            a, b = self.P(x, 0, z0), self.P(x, 0, z1)
            p.drawLine(QPointF(a[0], a[1]), QPointF(b[0], b[1]))
        for j in range(1, nz):
            z = lerp(z0, z1, j / nz)
            a, b = self.P(x0, 0, z), self.P(x1, 0, z)
            p.drawLine(QPointF(a[0], a[1]), QPointF(b[0], b[1]))

    # ----- events ----------------------------------------------------------- #
    def pick_at(self, pos):
        for pg, pid in reversed(self.picks):
            if pg.containsPoint(pos, Qt.FillRule.OddEvenFill):
                return pid
        return None

    def on_hover(self, pos):
        return self.pick_at(pos)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.drag = e.position()
            self.touched = True
            self.v_yaw = self.v_pitch = 0.0
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            self.wake()

    def mouseMoveEvent(self, e):
        pos = e.position()
        self.mouse = pos
        if self.drag is not None:
            dx, dy = pos.x() - self.drag.x(), pos.y() - self.drag.y()
            self.drag = pos
            self.t_yaw += dx * 0.009
            self.t_pitch = clamp(self.t_pitch + dy * 0.007, 0.12, 1.45)
            self.v_yaw = dx * 0.009 * 60 * 0.5
            self.v_pitch = dy * 0.007 * 60 * 0.5
            self.wake()
        else:
            h = self.on_hover(pos)
            if h != self.hover:
                self.hover = h
                self.wake()
        self.update()

    def mouseReleaseEvent(self, e):
        self.drag = None
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.wake()

    def mouseDoubleClickEvent(self, e):
        self.t_yaw, self.t_pitch, self.t_zoom = self.d_yaw, self.d_pitch, 1.0
        self.v_yaw = self.v_pitch = 0.0
        self.wake()

    def leaveEvent(self, e):
        self.mouse = None
        if self.hover is not None:
            self.hover = None
            self.wake()
        self.update()

    def wheelEvent(self, e):
        if e.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.t_zoom = clamp(self.t_zoom * (1.0015 ** e.angleDelta().y()), 0.55, 2.4)
            self.wake()
            e.accept()
        else:
            e.ignore()                 # let the surrounding scroll area scroll

    # ----- painting --------------------------------------------------------- #
    def tip_info(self):
        return None

    def paint_scene(self, p):
        pass

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing)
        vr = self.view_rect()
        g = QRadialGradient(vr.center() + QPointF(0, vr.height() * 0.1), max(vr.width(), vr.height()) * 0.6)
        g.setColorAt(0, QColor(124, 156, 255, 26))
        g.setColorAt(1, QColor(124, 156, 255, 0))
        p.fillRect(self.rect(), QBrush(g))
        self.cam_setup()
        self.picks = []
        self.paint_scene(p)
        self.paint_tip(p)
        if not self.touched:
            f = p.font()
            f.setPixelSize(10)
            p.setFont(f)
            p.setPen(QColor(MUTED))
            p.drawText(QRectF(8, self.height() - 22, self.width() - 16, 18),
                       aflags(AF.AlignRight, AF.AlignVCenter), self.HINT)
        p.end()

    def paint_tip(self, p):
        tip = self.tip_info()
        if not tip or self.mouse is None:
            return
        title, lines = tip
        f = p.font()
        f.setPixelSize(12)
        f.setBold(False)
        p.setFont(f)
        fm = QFontMetrics(f)
        fb = QFont(f)
        fb.setBold(True)
        w = max([QFontMetrics(fb).horizontalAdvance(title)] + [fm.horizontalAdvance(t) + 16 for _, t in lines]) + 22
        h = 14 + 20 + 18 * len(lines)
        x = self.mouse.x() + 16
        y = self.mouse.y() + 14
        if x + w > self.width() - 4:
            x = self.mouse.x() - w - 12
        if y + h > self.height() - 4:
            y = self.mouse.y() - h - 10
        r = QRectF(max(4, x), max(4, y), w, h)
        p.setPen(QPen(QColor(255, 255, 255, 60), 1))
        p.setBrush(QColor(12, 14, 22, 235))
        p.drawRoundedRect(r, 9, 9)
        p.setFont(fb)
        p.setPen(QColor(TEXT))
        p.drawText(QRectF(r.left() + 11, r.top() + 7, w - 20, 18), aflags(AF.AlignLeft, AF.AlignVCenter), title)
        p.setFont(f)
        for i, (col, t) in enumerate(lines):
            yy = r.top() + 30 + i * 18
            if col:
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor(col))
                p.drawEllipse(QPointF(r.left() + 15, yy + 9), 4, 4)
            p.setPen(QColor("#d6d9e4"))
            p.drawText(QRectF(r.left() + 25, yy, w - 30, 18), aflags(AF.AlignLeft, AF.AlignVCenter), t)


class EmptyView(QWidget):
    def __init__(self, msg):
        super().__init__()
        self.msg = msg
        self.setMinimumHeight(200)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QColor(MUTED))
        p.drawText(self.rect(), int(AF.AlignCenter), self.msg)
        p.end()


# --------------------------------------------------------------------------- #
#  3D bar grid  (stacked columns, or a heat-map of towers)
# --------------------------------------------------------------------------- #
class Bars3D(Scene3D):
    def __init__(self):
        super().__init__(yaw=0.42, pitch=0.62, dist=54.0, min_h=300)
        self.vals = np.zeros((1, 1, 1))
        self.cols, self.rows, self.series = [], [], []
        self.heat = False
        self.unit = "messages"
        self.fmt = lambda v: f"{v:,.0f}"

    def set_data(self, cols, rows, series, vals, heat=False, unit="messages", fmt=None):
        """vals: array (rows, cols, series). series: list of (name, colour)."""
        self.cols, self.rows, self.series = list(cols), list(rows), list(series)
        self.vals = np.nan_to_num(np.asarray(vals, dtype=float))
        self.heat = heat
        self.unit = unit
        if fmt:
            self.fmt = fmt
        R, C, S = self.vals.shape
        tot = self.vals.sum(axis=2)
        self.vmax = float(tot.max()) or 1.0
        self.zp = 1.0 if R > 1 else 1.7
        self.hmax = clamp(0.30 * C, 3.2, 7.5)
        if heat and not self.touched:
            self.d_yaw, self.d_pitch = 0.28, 0.92
            self.t_yaw, self.t_pitch = self.d_yaw, self.d_pitch
        self.fit_w = C / 2 + 1.2
        self.fit_h = (R * self.zp / 2 + 1.6) * math.sin(self.d_pitch) + self.hmax * math.cos(self.d_pitch) * 0.8
        self.focus_y = self.hmax * 0.28
        self.hover = None
        self.restart()
        self.update()

    def fit_points(self):
        R, C, S = self.vals.shape
        x0, z0 = -C / 2.0 - 0.8, -R * self.zp / 2.0 - 1.4
        x1, z1 = C / 2.0 + 0.8, R * self.zp / 2.0 + 0.8
        return [(x, y, z) for x in (x0, x1) for z in (z0, z1) for y in (0, self.hmax)]

    def _cell_key(self, hid):
        return None if hid is None else (hid[0], hid[1])

    def paint_scene(self, p):
        R, C, S = self.vals.shape
        zp = self.zp
        x0, z0 = -C / 2.0, -R * zp / 2.0
        self.floor(p, x0 - 0.5, x0 + C + 0.5, z0 - 0.6, z0 + R * zp + 0.6, C, R)
        # axis labels
        every = max(1, int(round(C / 12.0)))
        for c in range(0, C, every):
            self.text3(p, self.cols[c], x0 + c + 0.5, 0, z0 - 1.0, 10, MUTED)
        if R > 1:
            last = None
            for r in range(R - 1, -1, -1):
                sy = self.P(x0 - 0.9, 0, z0 + (r + 0.5) * zp)[1]
                if last is None or abs(sy - last) > 12:
                    self.text3(p, self.rows[r], x0 - 0.9, 0, z0 + (r + 0.5) * zp, 10, MUTED, AF.AlignRight)
                    last = sy
        # sort cells far -> near
        cx, _, cz = self.C
        cells = []
        for r in range(R):
            for c in range(C):
                mx, mz = x0 + c + 0.5, z0 + (r + 0.5) * zp
                cells.append(((mx - cx) ** 2 + (mz - cz) ** 2, r, c))
        cells.sort(reverse=True)
        t = self.grow_t()
        hov = self._cell_key(self.hover)
        unit_h = self.hmax / self.vmax
        bw = 0.38
        bd = 0.38 * (zp if R == 1 else 1.0) + (0.1 if R == 1 else 0)
        for _, r, c in cells:
            delay = (c / max(C, 1)) * 0.45 + (r / max(R, 1)) * 0.25
            g = ease_out((t - delay) / 0.7)
            mx, mz = x0 + c + 0.5, z0 + (r + 0.5) * zp
            is_h = hov == (r, c)
            y = 0.0
            if self.heat:
                v = float(self.vals[r, c, 0])
                frac = v / self.vmax
                h = max(0.05, v * unit_h * g)
                col = heat_color(frac).name()
                self.draw_box(p, mx - bw, mx + bw, 0, h, mz - bd, mz + bd, col, (r, c, 0), is_h)
            else:
                for s in range(S):
                    v = float(self.vals[r, c, s])
                    if v <= 0:
                        continue
                    h = v * unit_h * g
                    self.draw_box(p, mx - bw, mx + bw, y, y + h, mz - bd, mz + bd, self.series[s][1],
                                  (r, c, s), is_h)
                    y += h

    def tip_info(self):
        h = self.hover
        if h is None:
            return None
        r, c, s = h
        title = (f"{self.rows[r]} \u00B7 {self.cols[c]}" if len(self.rows) > 1 and self.rows[r] else self.cols[c])
        if self.heat:
            return title, [(ACCENT, f"{self.fmt(self.vals[r, c, 0])} {self.unit}")]
        lines = [(self.series[k][1], f"{self.series[k][0]}  {self.fmt(self.vals[r, c, k])}")
                 for k in range(self.vals.shape[2]) if self.vals[r, c, k] > 0]
        if len(lines) > 1:
            lines.append((None, f"total  {self.fmt(self.vals[r, c].sum())}"))
        return title, lines or [(None, "no messages")]


# --------------------------------------------------------------------------- #
#  Horizontal 3D bars (leaderboards, words, emotion mix)
# --------------------------------------------------------------------------- #
class HBars3D(Scene3D):
    ROW_PX = 30

    def __init__(self):
        super().__init__(yaw=-0.30, pitch=0.78, dist=70.0, min_h=240)
        self.labels, self.rows = [], []
        self.fmt = lambda v: f"{v:,.0f}"
        self.pct = False

    def set_data(self, labels, rows, fmt=None, pct=False, min_h=240):
        """rows: list (one per label) of lists of (value, colour, name)."""
        self.labels, self.rows, self.pct = list(labels), [list(r) for r in rows], pct
        self.fmt = fmt or (lambda v: f"{v:,.0f}")
        n = len(self.labels)
        self.setMinimumHeight(max(min_h, 96 + n * self.ROW_PX))
        self.tot = [sum(v for v, _, _ in r) for r in self.rows]
        self.vmax = (100.0 if pct else (max(self.tot) if self.tot else 1.0)) or 1.0
        self.XM = 11.0
        self.pitch_z = 1.0
        self.fit_w = self.XM / 2 + 3.6
        self.fit_h = (n * self.pitch_z / 2 + 0.9) * math.sin(self.d_pitch) + 0.9
        self.focus_y = 0.0
        self.hover = None
        self.restart()
        self.update()

    def fit_points(self):
        n = len(self.labels)
        if not n:
            return []
        X0 = -self.XM / 2 + 1.3
        Z0 = -(n - 1) * self.pitch_z / 2
        return [(x, y, z) for x in (X0 - 4.5, X0 + self.XM + 1.8) for z in (Z0 - 0.8, Z0 + (n - 1) * self.pitch_z + 0.8)
                for y in (0, 0.9)]

    def paint_scene(self, p):
        n = len(self.labels)
        if not n:
            return
        zp, XM = self.pitch_z, self.XM
        X0 = -XM / 2 + 1.3                       # leave room for the row labels on the left
        Z0 = -(n - 1) * zp / 2
        z_of = lambda i: Z0 + (n - 1 - i) * zp
        self.floor(p, X0 - 0.4, X0 + XM + 0.4, Z0 - 0.7, Z0 + (n - 1) * zp + 0.7, 0, n)
        t = self.grow_t()
        cx, _, cz = self.C
        items = []
        for i, row in enumerate(self.rows):
            xx = 0.0
            for k, (v, col, name) in enumerate(row):
                L = v / self.vmax * XM
                items.append(((X0 + xx + L / 2 - cx) ** 2 + (z_of(i) - cz) ** 2, i, k, xx, L, col))
                xx += L
        items.sort(reverse=True)
        hov = self.hover[0] if self.hover else None
        for _, i, k, xx, L, col in items:
            g = ease_out((t - i * 0.04) / 0.7)
            z = z_of(i)
            hl = hov == i
            if L * g > 0.001:
                self.draw_box(p, X0 + xx * g, X0 + (xx + L) * g, 0, 0.62 + (0.12 if hl else 0), z - 0.34, z + 0.34,
                              col, (i, k), hl)
        for i in range(n):
            z = z_of(i)
            hl = hov == i
            self.text3(p, shorten(self.labels[i], 22), X0 - 0.7, 0, z, 12, TEXT if hl else "#c3c7d6",
                       AF.AlignRight, bold=hl)
            g = ease_out((t - i * 0.04) / 0.7)
            end = self.tot[i] / self.vmax * XM * g
            txt = f"{self.tot[i]:.0f}%" if self.pct else self.fmt(self.tot[i])
            self.text3(p, txt, X0 + end + 0.5, 0.75, z, 11, TEXT, AF.AlignLeft, dy=-3)

    def tip_info(self):
        h = self.hover
        if h is None:
            return None
        i, k = h
        row = self.rows[i]
        tot = self.tot[i] or 1
        lines = []
        for v, col, name in row:
            if len(row) == 1:
                lines.append((col, self.fmt(v) if not self.pct else f"{v:.1f}%"))
            else:
                lines.append((col, f"{name}  {v:.1f}%" if self.pct else f"{name}  {self.fmt(v)}  ({v / tot * 100:.0f}%)"))
        return self.labels[i], lines


# --------------------------------------------------------------------------- #
#  Extruded 3D donut with exploding slices and an interactive legend
# --------------------------------------------------------------------------- #
class Donut3D(Scene3D):
    RO, RI, H = 5.0, 2.85, 1.15

    def __init__(self):
        super().__init__(yaw=0.0, pitch=0.86, dist=46.0, min_h=300)
        self.names, self.values, self.colors = [], [], []
        self.center = ("", "")
        self.unit = "messages"
        self.exp = []
        self.legend_rects = []
        self.LIGHT = (-0.5, -0.85)
        n = math.hypot(*self.LIGHT)
        self.LIGHT = (self.LIGHT[0] / n, self.LIGHT[1] / n)

    def set_data(self, names, values, colors, center=("", ""), unit="messages"):
        self.names, self.values, self.colors = list(names), [float(v) for v in values], list(colors)
        self.center, self.unit = center, unit
        self.total = sum(self.values) or 1.0
        self.exp = [0.0] * len(self.names)
        self.fit_w = 5.5
        self.fit_h = 5.2 * math.sin(self.d_pitch) + 1.3
        self.focus_y = 0.0
        self.hover = None
        self.restart()
        self.update()

    def view_rect(self):
        lw = min(230.0, self.width() * 0.36)
        return QRectF(0, 0, self.width() - lw, self.height())

    def fit_points(self):
        r = self.RO + 1.0
        return [(r * math.cos(k * math.pi / 4), y, r * math.sin(k * math.pi / 4)) for k in range(8) for y in (0, self.H + 0.5)]

    def busy(self):
        want = [1.0 if self.hover == i else 0.0 for i in range(len(self.exp))]
        return any(abs(a - b) > 0.01 for a, b in zip(self.exp, want))

    def step(self, dt):
        for i in range(len(self.exp)):
            self.exp[i] = approach(self.exp[i], 1.0 if self.hover == i else 0.0, dt, 11)

    def on_hover(self, pos):
        for r, i in self.legend_rects:
            if r.contains(pos):
                return i
        return self.pick_at(pos)

    def _wall_light(self, nx, nz):
        d = nx * self.LIGHT[0] + nz * self.LIGHT[1]
        return 0.55 + 0.5 * clamp(d, 0, 1)

    def paint_scene(self, p):
        n = len(self.names)
        if not n:
            return
        RO, RI, H = self.RO, self.RI, self.H
        t = self.grow_t()
        sweep = ease_out(t / 1.25)
        hg = ease_out(t / 0.8)
        cx, cy, cz = self.C
        # soft shadow
        for rr, a in ((RO + 1.1, 24), (RO + 0.6, 40), (RO + 0.2, 60)):
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(0, 0, 0, a))
            p.drawPolygon(self.poly([(rr * math.cos(k * math.pi / 24), -0.02, rr * math.sin(k * math.pi / 24))
                                     for k in range(48)]))
        inner, mids, tops = [], [], []
        cum = 0.0
        hov = self.hover
        for i in range(n):
            f = self.values[i] / self.total
            a0 = math.pi / 2 - cum * 2 * math.pi * sweep
            cum += f
            a1 = math.pi / 2 - cum * 2 * math.pi * sweep
            if abs(a0 - a1) < 1e-4:
                continue
            am = (a0 + a1) / 2
            e = self.exp[i] * 0.55
            ox, oz = e * math.cos(am), e * math.sin(am)
            ns = max(2, int(abs(a0 - a1) / (2 * math.pi) * 72) + 1)
            ang = [lerp(a0, a1, k / ns) for k in range(ns + 1)]
            col = self.colors[i]
            hl = (hov == i)
            hh = H * hg * (1.0 + (0.18 * self.exp[i]))
            top_pts = [(ox + RO * math.cos(a), hh, oz + RO * math.sin(a)) for a in ang] + \
                      [(ox + RI * math.cos(a), hh, oz + RI * math.sin(a)) for a in reversed(ang)]
            tops.append((top_pts, col, 1.14 + 0.18 * self.exp[i], i))
            for k in range(ns):
                b0, b1 = ang[k], ang[k + 1]
                bm = (b0 + b1) / 2
                nxm, nzm = math.cos(bm), math.sin(bm)
                # outer wall
                mxo, mzo = ox + RO * nxm, oz + RO * nzm
                if (cx - mxo) * nxm + (cz - mzo) * nzm > 0:
                    pts = [(ox + RO * math.cos(b0), 0, oz + RO * math.sin(b0)),
                           (ox + RO * math.cos(b1), 0, oz + RO * math.sin(b1)),
                           (ox + RO * math.cos(b1), hh, oz + RO * math.sin(b1)),
                           (ox + RO * math.cos(b0), hh, oz + RO * math.sin(b0))]
                    mids.append(((mxo - cx) ** 2 + (mzo - cz) ** 2, pts, col,
                                 self._wall_light(nxm, nzm) * (1.12 if hl else 1.0), i))
                # inner wall (normal points to the hole)
                mxi, mzi = ox + RI * nxm, oz + RI * nzm
                if (cx - mxi) * (-nxm) + (cz - mzi) * (-nzm) > 0:
                    pts = [(ox + RI * math.cos(b0), 0, oz + RI * math.sin(b0)),
                           (ox + RI * math.cos(b0), hh, oz + RI * math.sin(b0)),
                           (ox + RI * math.cos(b1), hh, oz + RI * math.sin(b1)),
                           (ox + RI * math.cos(b1), 0, oz + RI * math.sin(b1))]
                    inner.append(((mxi - cx) ** 2 + (mzi - cz) ** 2, pts, col,
                                  self._wall_light(-nxm, -nzm) * 0.9 * (1.12 if hl else 1.0), i))
            # radial cut faces
            for a, (nx_, nz_) in ((a0, (-math.sin(a0), math.cos(a0))), (a1, (math.sin(a1), -math.cos(a1)))):
                midr = (RO + RI) / 2
                mx_, mz_ = ox + midr * math.cos(a), oz + midr * math.sin(a)
                if (cx - mx_) * nx_ + (cz - mz_) * nz_ > 0:
                    pts = [(ox + RI * math.cos(a), 0, oz + RI * math.sin(a)),
                           (ox + RO * math.cos(a), 0, oz + RO * math.sin(a)),
                           (ox + RO * math.cos(a), hh, oz + RO * math.sin(a)),
                           (ox + RI * math.cos(a), hh, oz + RI * math.sin(a))]
                    mids.append(((mx_ - cx) ** 2 + (mz_ - cz) ** 2 - 0.01, pts, col,
                                 self._wall_light(nx_, nz_) * 0.95, i))
        inner.sort(key=lambda q: -q[0])
        mids.sort(key=lambda q: -q[0])
        for _, pts, col, fac, i in inner + mids:
            self.draw_face(p, pts, col, fac, i, QColor(0, 0, 0, 40))
        for pts, col, fac, i in tops:
            self.draw_face(p, pts, col, fac, i, QColor(255, 255, 255, 150) if hov == i else QColor(0, 0, 0, 50))
        # centre text (shows the hovered slice)
        sx, sy, _ = self.P(0, H * hg, 0)
        if hov is not None and 0 <= hov < n:
            big, small = f"{self.values[hov] / self.total * 100:.0f}%", shorten(self.names[hov], 16)
            sub = f"{self.values[hov]:,.0f} {self.unit}"
            colr = self.colors[hov]
        else:
            big, small, sub, colr = self.center[0], self.center[1], "", TEXT
        f = p.font()
        f.setBold(True)
        f.setPixelSize(int(clamp(self._f / self.dist * 0.95, 14, 30)))
        p.setFont(f)
        p.setPen(QColor(colr))
        p.drawText(QRectF(sx - 90, sy - 24, 180, 30), int(AF.AlignCenter), big)
        f.setBold(False)
        f.setPixelSize(12)
        p.setFont(f)
        p.setPen(QColor(MUTED if hov is None else TEXT))
        p.drawText(QRectF(sx - 90, sy + 3, 180, 18), int(AF.AlignCenter), small)
        if sub:
            p.setPen(QColor(MUTED))
            p.drawText(QRectF(sx - 90, sy + 20, 180, 18), int(AF.AlignCenter), sub)
        self._paint_legend(p)

    def _paint_legend(self, p):
        n = len(self.names)
        lw = min(230.0, self.width() * 0.36)
        x0 = self.width() - lw + 6
        rh = 27.0
        y0 = max(10.0, (self.height() - n * rh) / 2)
        self.legend_rects = []
        f = p.font()
        f.setPixelSize(12)
        f.setBold(False)
        p.setFont(f)
        for i in range(n):
            r = QRectF(x0, y0 + i * rh, lw - 14, rh - 3)
            self.legend_rects.append((r, i))
            if self.hover == i:
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor(255, 255, 255, 22))
                p.drawRoundedRect(r, 7, 7)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(self.colors[i]))
            p.drawRoundedRect(QRectF(r.left() + 7, r.center().y() - 5, 10, 10), 3, 3)
            p.setPen(QColor(TEXT if self.hover == i else "#c3c7d6"))
            fm = QFontMetrics(f)
            p.drawText(QRectF(r.left() + 24, r.top(), r.width() - 70, r.height()), aflags(AF.AlignLeft, AF.AlignVCenter),
                       fm.elidedText(str(self.names[i]), Qt.TextElideMode.ElideRight, int(r.width() - 74)))
            p.setPen(QColor(MUTED if self.hover != i else TEXT))
            p.drawText(QRectF(r.right() - 48, r.top(), 44, r.height()), aflags(AF.AlignRight, AF.AlignVCenter),
                       f"{self.values[i] / self.total * 100:.0f}%")

    def tip_info(self):
        h = self.hover
        if h is None or self.mouse is None or any(r.contains(self.mouse) for r, _ in self.legend_rects):
            return None
        return None            # the donut shows hovered details in its centre instead


# --------------------------------------------------------------------------- #
#  Layered 3D area / ribbon chart (one extruded layer per person)
# --------------------------------------------------------------------------- #
def _bucket(xs, series, maxn=120):
    n = len(xs)
    if n <= maxn:
        return list(xs), series
    b = int(math.ceil(n / maxn))
    idx = list(range(0, n, b))
    out = []
    for name, col, ys in series:
        ys = np.asarray(ys, dtype=float)
        vals = []
        for i in idx:
            seg = ys[i:i + b]
            vals.append(np.nan if np.all(np.isnan(seg)) else float(np.nanmean(seg)))
        out.append((name, col, np.array(vals)))
    return [xs[i] for i in idx], out


class Area3D(Scene3D):
    W, DEPTH, PITCH_Z, HH = 18.0, 1.0, 1.6, 5.2

    def __init__(self):
        super().__init__(yaw=0.36, pitch=0.46, dist=56.0, min_h=320)
        self.xs, self.series = [], []
        self.xfmt = lambda x: str(x)
        self.fmt = lambda v: f"{v:,.1f}"
        self.ymin, self.ymax, self.zero_line = 0.0, 1.0, False
        self.hidx = None

    def set_data(self, xs, series, xfmt, ymin=0.0, ymax=None, zero_line=False, fmt=None, ylabels=None):
        series = [(n, c, np.asarray(y, dtype=float)) for n, c, y in series]
        series.sort(key=lambda s: -np.nansum(np.abs(s[2])))
        xs, series = _bucket(list(xs), series)
        self.xs, self.series, self.xfmt = xs, series, xfmt
        self.fmt = fmt or (lambda v: f"{v:,.1f}")
        allv = np.concatenate([s[2][np.isfinite(s[2])] for s in series]) if series else np.array([1.0])
        self.ymin = ymin
        self.ymax = ymax if ymax is not None else (float(allv.max()) if allv.size and allv.max() > 0 else 1.0)
        self.zero_line = zero_line
        self.ylabels = ylabels
        nl = len(series)
        self.fit_w = self.W / 2 + 2.6
        self.fit_h = (nl * self.PITCH_Z / 2 + 1.4) * math.sin(self.d_pitch) + self.HH * math.cos(self.d_pitch) * 0.8
        self.focus_y = self.HH * 0.25
        self.hidx = None
        self.hover = None
        self.restart()
        self.update()

    def _yv(self, v):
        return (v - self.ymin) / (self.ymax - self.ymin or 1.0) * self.HH

    def _xi(self, i):
        n = len(self.xs)
        return -self.W / 2 + self.W * (i / max(n - 1, 1))

    def _z0(self, k):                      # layer k (0 = biggest) -> back-most
        nl = len(self.series)
        return (nl - 1 - k) * self.PITCH_Z - (nl - 1) * self.PITCH_Z / 2

    def fit_points(self):
        nl = max(len(self.series), 1)
        zmin, zmax = self._z0(nl - 1) - 1.6, self._z0(0) + self.DEPTH + 0.8
        return [(x, y, z) for x in (-self.W / 2 - 2.6, self.W / 2 + 0.8) for z in (zmin, zmax) for y in (0, self.HH + 0.5)]

    def busy(self):
        return False

    def on_hover(self, pos):
        n = len(self.xs)
        if not n or not self.series:
            return None
        zmid = self._z0(len(self.series) // 2) + self.DEPTH / 2
        best, bd = None, 1e9
        for i in range(n):
            sx, sy, _ = self.P(self._xi(i), 0, zmid)
            d = abs(sx - pos.x())
            if d < bd:
                best, bd = i, d
        step = self.width() / max(n, 1)
        if bd > max(30, step * 1.5):
            best = None
        self.hidx = best
        return best

    def paint_scene(self, p):
        n = len(self.xs)
        if not n or not self.series:
            return
        W, D, HH = self.W, self.DEPTH, self.HH
        nl = len(self.series)
        zmin = self._z0(nl - 1)
        zmax = self._z0(0) + D
        self.floor(p, -W / 2 - 0.6, W / 2 + 0.6, zmin - 0.8, zmax + 0.8, 0, nl)
        ybase = self._yv(0.0 if self.ymin <= 0 <= self.ymax else self.ymin)
        t = self.grow_t()
        cx, _, cz = self.C
        # x labels along the front edge
        every = max(1, int(round(n / 8.0)))
        for i in range(0, n, every):
            self.text3(p, self.xfmt(self.xs[i]), self._xi(i), 0, zmin - 1.2, 10, MUTED)
        # y labels
        lab = self.ylabels or [(self.ymin, self.fmt(self.ymin)), (self.ymax, self.fmt(self.ymax))]
        for v, s in lab:
            self.text3(p, s, -W / 2 - 0.9, self._yv(v), zmin, 10, MUTED, AF.AlignRight)
            a, b = self.P(-W / 2, self._yv(v), zmin), self.P(W / 2, self._yv(v), zmin)
            p.setPen(QPen(QColor(255, 255, 255, 18), 1))
            p.drawLine(QPointF(a[0], a[1]), QPointF(b[0], b[1]))
        order = list(range(nl))
        order.sort(key=lambda k: -abs(self._z0(k) + D / 2 - cz))
        for k in order:
            name, col, ys = self.series[k]
            g = ease_out((t - (nl - 1 - k) * 0.1) / 0.95)
            z0, z1 = self._z0(k), self._z0(k) + D
            zf = z0 if cz < z0 + D / 2 else z1
            yy = [None if not np.isfinite(v) else ybase + (self._yv(v) - ybase) * g for v in ys]
            i = 0
            while i < n:
                if yy[i] is None:
                    i += 1
                    continue
                j = i
                while j + 1 < n and yy[j + 1] is not None:
                    j += 1
                if j > i:
                    xa, xb = self._xi(i), self._xi(j)
                    wall = [(xa, ybase, zf)] + [(self._xi(m), yy[m], zf) for m in range(i, j + 1)] + [(xb, ybase, zf)]
                    pg = self.poly(wall)
                    br = pg.boundingRect()
                    gr = QLinearGradient(br.topLeft(), br.bottomLeft())
                    c1, c2 = shade(col, 0.95 if zf == z0 else 0.62), shade(col, 0.5 if zf == z0 else 0.34)
                    c1.setAlpha(240)
                    c2.setAlpha(200)
                    gr.setColorAt(0, c1)
                    gr.setColorAt(1, c2)
                    p.setBrush(QBrush(gr))
                    p.setPen(Qt.PenStyle.NoPen)
                    p.drawPolygon(pg)
                    if cx < xa:
                        self.draw_face(p, [(xa, ybase, z0), (xa, yy[i], z0), (xa, yy[i], z1), (xa, ybase, z1)], col, 0.74)
                    if cx > xb:
                        self.draw_face(p, [(xb, ybase, z0), (xb, ybase, z1), (xb, yy[j], z1), (xb, yy[j], z0)], col, 0.66)
                    for m in range(i, j):
                        self.draw_face(p, [(self._xi(m), yy[m], z0), (self._xi(m + 1), yy[m + 1], z0),
                                           (self._xi(m + 1), yy[m + 1], z1), (self._xi(m), yy[m], z1)], col, 1.15,
                                       None, QColor(255, 255, 255, 40))
                elif True:                                   # an isolated point
                    xm = self._xi(i)
                    self.draw_box(p, xm - 0.08, xm + 0.08, min(ybase, yy[i]), max(ybase, yy[i]) + 0.03, z0, z1, col)
                i = j + 1
        if self.zero_line:
            a, b = self.P(-W / 2, ybase, zmin - 0.2), self.P(W / 2, ybase, zmin - 0.2)
            p.setPen(QPen(QColor(255, 255, 255, 90), 1.2, Qt.PenStyle.DashLine))
            p.drawLine(QPointF(a[0], a[1]), QPointF(b[0], b[1]))
        # hover crosshair
        h = self.hidx
        if h is not None and self.mouse is not None and 0 <= h < n:
            x = self._xi(h)
            pg = self.poly([(x, 0, zmin - 0.4), (x, HH + 0.4, zmin - 0.4), (x, HH + 0.4, zmax + 0.2), (x, 0, zmax + 0.2)])
            p.setBrush(QColor(255, 255, 255, 26))
            p.setPen(QPen(QColor(255, 255, 255, 110), 1))
            p.drawPolygon(pg)
            for k in range(nl):
                v = self.series[k][2][h]
                if np.isfinite(v):
                    sx, sy, _ = self.P(x, self._yv(v), self._z0(k) + D / 2)
                    p.setBrush(QColor(self.series[k][1]))
                    p.setPen(QPen(QColor("#ffffff"), 2))
                    p.drawEllipse(QPointF(sx, sy), 4.5, 4.5)
        self._legend(p)

    def _legend(self, p):
        f = p.font()
        f.setPixelSize(11)
        f.setBold(False)
        p.setFont(f)
        fm = QFontMetrics(f)
        x, y = 12.0, 10.0
        for name, col, _ in self.series[:10]:
            lab = shorten(name, 18)
            w = fm.horizontalAdvance(lab) + 26
            if x + w > self.width() - 8:
                x, y = 12.0, y + 18
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(col))
            p.drawRoundedRect(QRectF(x, y + 4, 10, 10), 3, 3)
            p.setPen(QColor("#c3c7d6"))
            p.drawText(QRectF(x + 15, y, w, 18), aflags(AF.AlignLeft, AF.AlignVCenter), lab)
            x += w + 6

    def tip_info(self):
        h = self.hidx
        if h is None or self.mouse is None or not (0 <= h < len(self.xs)):
            return None
        lines = []
        for name, col, ys in sorted(self.series, key=lambda s: -(s[2][h] if np.isfinite(s[2][h]) else -9e9)):
            v = ys[h]
            if np.isfinite(v):
                lines.append((col, f"{shorten(name, 20)}  {self.fmt(v)}"))
        return self.xfmt(self.xs[h]), lines or [(None, "no data")]


# --------------------------------------------------------------------------- #
#  Card that wraps a 3D chart  (same constructor / .empty() as the old matplotlib Chart)
# --------------------------------------------------------------------------- #
class Chart3D(QFrame):
    def __init__(self, title, min_h=280, extra=None):
        super().__init__()
        self.setObjectName("card")
        self.title, self.min_h, self.view = title, min_h, None
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        head = QHBoxLayout()
        lbl = QLabel(title)
        lbl.setObjectName("cardTitle")
        head.addWidget(lbl)
        tag = QLabel("3D")
        tag.setStyleSheet(f"background:{ACCENT};color:#0d1124;border-radius:6px;padding:0 6px;"
                          "font-size:10px;font-weight:800;")
        head.addWidget(tag)
        head.addStretch()
        if extra is not None:
            head.addWidget(extra)
        btn = QPushButton("Save PNG")
        btn.setObjectName("ghost")
        btn.clicked.connect(self.save)
        head.addWidget(btn)
        lay.addLayout(head)
        self.holder = QVBoxLayout()
        self.holder.setContentsMargins(0, 0, 0, 0)
        lay.addLayout(self.holder)
        self.empty("Waiting for data\u2026")

    def _install(self, w):
        if self.view is not None:
            self.holder.removeWidget(self.view)
            self.view.hide()
            self.view.deleteLater()
        self.view = w
        self.holder.addWidget(w)

    def _use(self, cls):
        if not isinstance(self.view, cls):
            v = cls()
            v.setMinimumHeight(self.min_h)
            self._install(v)
        return self.view

    def _safe(self, cls, **kw):
        try:
            v = self._use(cls)
            v.set_data(**kw)
            v.wake()
        except Exception as e:  # noqa
            self._install(EmptyView(f"Chart error: {e}"))

    def show_bars(self, **kw):
        self._safe(Bars3D, **kw)

    def show_hbars(self, **kw):
        kw.setdefault("min_h", self.min_h)
        self._safe(HBars3D, **kw)

    def show_donut(self, **kw):
        self._safe(Donut3D, **kw)

    def show_area(self, **kw):
        self._safe(Area3D, **kw)

    def empty(self, msg="No data"):
        self._install(EmptyView(msg))

    def save(self):
        name = re.sub(r"\W+", "_", self.title).strip("_").lower() + ".png"
        path, _ = QFileDialog.getSaveFileName(self, "Save chart", name, "PNG image (*.png)")
        if path and self.view is not None:
            self.view.grab().save(path)


def rows_of(values, colors, names=None):
    """One single-segment row per value (for simple leaderboards)."""
    return [[(float(v), c, (names[i] if names else ""))] for i, (v, c) in enumerate(zip(values, colors))]


# --------------------------------------------------------------------------- #
#  Stat card that tilts towards the mouse and counts up
# --------------------------------------------------------------------------- #
_NUM_RE = re.compile(r"^-?[\d,]*\.?\d+$")


class StatCard(QWidget):
    _next = 0

    def __init__(self, caption, accent=None):
        super().__init__()
        self.caption = caption
        self.accent = accent or PALETTE[StatCard._next % len(PALETTE)]
        StatCard._next += 1
        self.text = "-"
        self.num = None            # (target, decimals, commas)
        self.shown = 0.0
        self.count_t0 = 0.0
        self.tilt = [0.0, 0.0]
        self.tilt_t = [0.0, 0.0]
        self.mouse = None
        self.lift = 0.0
        self.setMinimumHeight(92)
        self.setMouseTracking(True)
        self.timer = QTimer(self)
        self.timer.setInterval(16)
        self.timer.timeout.connect(self._tick)
        self._last = time.perf_counter()

    def set(self, v, sub=None):
        s = str(v)
        self.setToolTip(sub or "")
        if _NUM_RE.match(s):
            val = float(s.replace(",", ""))
            dec = len(s.split(".")[1]) if "." in s else 0
            old = self.num[0] if self.num else 0.0
            self.num = (val, dec, "," in s)
            self.shown_from = old
            self.count_t0 = time.perf_counter()
        else:
            self.num = None
            self.text = s
        self.wake()

    def wake(self):
        self._last = time.perf_counter()
        if not self.timer.isActive():
            self.timer.start()

    def _value_text(self):
        if not self.num:
            return self.text
        val, dec, commas = self.num
        t = ease_out((time.perf_counter() - self.count_t0) / 0.9)
        x = lerp(getattr(self, "shown_from", 0.0), val, t)
        return f"{x:,.{dec}f}" if commas else f"{x:.{dec}f}"

    def _tick(self):
        now = time.perf_counter()
        dt = min(0.05, now - self._last)
        self._last = now
        for i in (0, 1):
            self.tilt[i] = approach(self.tilt[i], self.tilt_t[i], dt, 14)
        self.lift = approach(self.lift, 1.0 if self.mouse is not None else 0.0, dt, 12)
        counting = self.num is not None and (now - self.count_t0) < 0.95
        self.update()
        if (not counting and self.mouse is None and abs(self.tilt[0]) < 1e-3 and abs(self.tilt[1]) < 1e-3
                and self.lift < 0.01):
            self.timer.stop()

    def mouseMoveEvent(self, e):
        pos = e.position()
        self.mouse = pos
        nx = (pos.x() / max(self.width(), 1) - 0.5) * 2
        ny = (pos.y() / max(self.height(), 1) - 0.5) * 2
        self.tilt_t = [-ny * 0.30, nx * 0.34]
        self.wake()

    def leaveEvent(self, e):
        self.mouse = None
        self.tilt_t = [0.0, 0.0]
        self.wake()

    def _face(self, w, h):
        dpr = self.devicePixelRatioF()
        pix = QPixmap(int(w * dpr), int(h * dpr))
        pix.setDevicePixelRatio(dpr)
        pix.fill(Qt.GlobalColor.transparent)
        p = QPainter(pix)
        p.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing)
        r = QRectF(0.5, 0.5, w - 1, h - 1)
        g = QLinearGradient(0, 0, w, h)
        g.setColorAt(0, QColor("#2a2e44"))
        g.setColorAt(1, QColor("#181a25"))
        p.setPen(QPen(QColor(255, 255, 255, 34 + int(40 * self.lift)), 1))
        p.setBrush(QBrush(g))
        p.drawRoundedRect(r, 14, 14)
        glow = QRadialGradient(QPointF(w * 0.12, h * 1.05), w * 0.7)
        ac = QColor(self.accent)
        ac.setAlpha(70)
        glow.setColorAt(0, ac)
        ac.setAlpha(0)
        glow.setColorAt(1, ac)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(glow))
        p.drawRoundedRect(r, 14, 14)
        p.setBrush(QColor(self.accent))
        p.drawRoundedRect(QRectF(14, 16, 4, h - 32), 2, 2)
        f = QFont(self.font())
        f.setPixelSize(10)
        f.setBold(True)
        f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1.0)
        p.setFont(f)
        p.setPen(QColor(MUTED))
        p.drawText(QRectF(28, 12, w - 40, 18), aflags(AF.AlignLeft, AF.AlignVCenter), self.caption.upper())
        f = QFont(self.font())
        f.setPixelSize(max(20, min(30, int(h * 0.34))))
        f.setBold(True)
        p.setFont(f)
        p.setPen(QColor(TEXT))
        p.drawText(QRectF(28, 32, w - 40, h - 40), aflags(AF.AlignLeft, AF.AlignVCenter), self._value_text())
        p.end()
        return pix

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform)
        m = 8
        w, h = self.width() - 2 * m, self.height() - 2 * m
        if w < 20 or h < 20:
            return
        pix = self._face(w, h)
        ax, ay = self.tilt
        s = 1.0 + 0.035 * self.lift
        cx, cy = self.width() / 2, self.height() / 2
        quad = []
        for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
            x, y = sx * w / 2 * s, sy * h / 2 * s
            x1, z1 = x * math.cos(ay), -x * math.sin(ay)
            y2, z2 = y * math.cos(ax) - z1 * math.sin(ax), y * math.sin(ax) + z1 * math.cos(ax)
            k = 520.0 / (520.0 + z2)
            quad.append(QPointF(cx + x1 * k, cy + y2 * k))
        poly = QPolygonF(quad)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(0, 0, 0, int(60 + 30 * self.lift)))
        p.drawPolygon(poly.translated(ay * -10, 6 + 3 * self.lift))
        tr = QTransform()
        src = QPolygonF([QPointF(0, 0), QPointF(w, 0), QPointF(w, h), QPointF(0, h)])
        if QTransform.quadToQuad(src, poly, tr):
            p.save()
            p.setTransform(tr, True)
            p.drawPixmap(QRectF(0, 0, w, h), pix, QRectF(pix.rect()))
            p.restore()
        if self.mouse is not None:
            path = QPainterPath()
            path.addPolygon(poly)
            p.setClipPath(path)
            gl = QRadialGradient(self.mouse, w * 0.55)
            gl.setColorAt(0, QColor(255, 255, 255, 52))
            gl.setColorAt(1, QColor(255, 255, 255, 0))
            p.setBrush(QBrush(gl))
            p.drawRect(self.rect())
        p.end()


# --------------------------------------------------------------------------- #
#  Welcome screen: floating 3D chat bubbles (click one to spin it)
# --------------------------------------------------------------------------- #
BUBBLE_TEXT = ["Good morning!", "kal movie chalein?", "haha that was so funny", "send me the notes",
               "see you at 8", "ok done", "lets plan the trip", "bro where are you??", "I'm hungry",
               "did you see the match?", "call me later", "happy birthday!", "on my way", "love it",
               "wait what", "sounds good"]


class WelcomeScene(QWidget):
    def __init__(self, on_open, on_demo, on_help):
        super().__init__()
        self.setMouseTracking(True)
        rnd = random.Random(11)
        self.items = []
        n = len(BUBBLE_TEXT)
        for i, txt in enumerate(BUBBLE_TEXT):
            self.items.append(dict(
                text=txt, color=PALETTE[i % len(PALETTE)], a=i * 2 * math.pi / n + rnd.uniform(-0.2, 0.2),
                rx=rnd.uniform(5.2, 7.4), y=rnd.uniform(-3.0, 3.0), zs=rnd.uniform(0.45, 0.8),
                sp=rnd.choice([-1, 1]) * rnd.uniform(0.08, 0.16), ph=rnd.uniform(0, 6.28),
                mine=rnd.random() < 0.5, spin=-10.0, pix=None))
        self.mouse = None
        self.par = [0.0, 0.0]
        self.drag_on = False
        self.t0 = time.perf_counter()
        self.quads = []
        self.timer = QTimer(self)
        self.timer.setInterval(16)
        self.timer.timeout.connect(self.update)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addStretch(60)
        row = QHBoxLayout()
        row.addStretch()
        for text, cb, name in (("Open chat export\u2026", on_open, "primary"), ("Try demo chat", on_demo, ""),
                               ("How to export", on_help, "ghost")):
            b = QPushButton(text)
            if name:
                b.setObjectName(name)
            if name != "ghost":
                b.setMinimumHeight(40)
                b.setMinimumWidth(170)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(cb)
            row.addWidget(b)
        row.addStretch()
        lay.addLayout(row)
        lay.addStretch(34)

    def showEvent(self, e):
        self.timer.start()

    def hideEvent(self, e):
        self.timer.stop()

    def set_drag(self, on):
        self.drag_on = on

    def _bubble_pix(self, it):
        if it["pix"] is None:
            w, h = 250, 78
            s = 2
            pix = QPixmap(w * s, h * s)
            pix.fill(Qt.GlobalColor.transparent)
            p = QPainter(pix)
            p.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing)
            p.scale(s, s)
            col = QColor(it["color"])
            g = QLinearGradient(0, 0, 0, h)
            g.setColorAt(0, col.lighter(125))
            g.setColorAt(1, col.darker(130))
            p.setPen(QPen(QColor(255, 255, 255, 90), 1.4))
            p.setBrush(QBrush(g))
            body = QRectF(6, 4, w - 12, h - 18)
            p.drawRoundedRect(body, 20, 20)
            tail = QPainterPath()
            x0 = w - 52 if it["mine"] else 32
            d = -1 if it["mine"] else 1
            tail.moveTo(x0, h - 14)
            tail.lineTo(x0 + d * 4, h - 1)
            tail.lineTo(x0 + d * 22, h - 14)
            p.drawPath(tail)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(col.darker(115))
            p.drawRect(QRectF(min(x0, x0 + d * 22) + 1, h - 17, 20, 5))
            f = QFont(self.font())
            f.setPixelSize(17)
            f.setBold(True)
            p.setFont(f)
            p.setPen(QColor(255, 255, 255, 240))
            p.drawText(body.adjusted(10, 0, -10, 0), int(AF.AlignCenter), it["text"])
            p.end()
            it["pix"] = pix
        return it["pix"]

    def mouseMoveEvent(self, e):
        self.mouse = e.position()

    def leaveEvent(self, e):
        self.mouse = None

    def mousePressEvent(self, e):
        pt = e.position()
        for poly, i in reversed(self.quads):
            if poly.containsPoint(pt, Qt.FillRule.OddEvenFill):
                self.items[i]["spin"] = time.perf_counter() - self.t0
                break

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform |
                         QPainter.RenderHint.TextAntialiasing)
        W, H = self.width(), self.height()
        t = time.perf_counter() - self.t0
        g = QRadialGradient(QPointF(W / 2, H * 0.42), max(W, H) * 0.75)
        g.setColorAt(0, QColor("#232a52"))
        g.setColorAt(0.6, QColor("#14151b"))
        g.setColorAt(1, QColor("#0b0c11"))
        p.fillRect(self.rect(), QBrush(g))
        tx = ty = 0.0
        if self.mouse is not None:
            tx = (self.mouse.x() / W - 0.5) * 2
            ty = (self.mouse.y() / H - 0.5) * 2
        self.par[0] += (tx - self.par[0]) * 0.06
        self.par[1] += (ty - self.par[1]) * 0.06
        yaw, pitch = self.par[0] * 0.45, 0.10 + self.par[1] * 0.18
        cy_, sy_, cp, sp = math.cos(yaw), math.sin(yaw), math.cos(pitch), math.sin(pitch)
        dist, f = 15.0, min(W, H * 1.5) * 1.15
        hover_i = None
        proj = []
        for i, it in enumerate(self.items):
            a = it["a"] + t * it["sp"]
            x = it["rx"] * math.cos(a)
            z = it["rx"] * it["zs"] * math.sin(a) + 1.0
            y = it["y"] + 0.28 * math.sin(t * 0.8 + it["ph"])
            x1, z1 = x * cy_ + z * sy_, -x * sy_ + z * cy_
            y2, z2 = y * cp + z1 * sp, -y * sp + z1 * cp
            proj.append((z2, i, x1, y2))
        proj.sort(reverse=True)
        # drag-over ring behind the title
        self.quads = []
        out = []
        for z2, i, x1, y2 in proj:
            it = self.items[i]
            k = f / (z2 + dist)
            cx, cy = W / 2 + x1 * k, H * 0.42 - y2 * k
            sc = 0.0125
            bw, bh = 250 * sc, 78 * sc
            ry = 0.45 * math.sin(t * 0.6 + it["ph"]) - self.par[0] * 0.5
            sp_t = t - it["spin"]
            if 0 <= sp_t < 1.0:
                ry += 2 * math.pi * ease_io(sp_t)
            pts = []
            for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
                lx, ly = sx * bw / 2, sy * bh / 2
                wx = x1 + lx * math.cos(ry)
                wz = z2 - lx * math.sin(ry)
                kk = f / (wz + dist)
                pts.append(QPointF(W / 2 + wx * kk, H * 0.42 - (y2 - ly) * kk))
            poly = QPolygonF(pts)
            out.append((poly, i, z2))
        for poly, i, z2 in out:
            self.quads.append((poly, i))
        pos = self.mouse
        for poly, i, z2 in out:
            it = self.items[i]
            front = math.cos(0)  # always show the front side
            depth = clamp(1.0 - (z2 + 8) / 22.0, 0.15, 1.0)
            hv = pos is not None and poly.containsPoint(pos, Qt.FillRule.OddEvenFill)
            pix = self._bubble_pix(it)
            src = QPolygonF([QPointF(0, 0), QPointF(250, 0), QPointF(250, 78), QPointF(0, 78)])
            tr = QTransform()
            if not QTransform.quadToQuad(src, poly, tr):
                continue
            p.save()
            p.setOpacity(0.28 + 0.72 * depth)
            if hv:
                p.setPen(Qt.PenStyle.NoPen)
                gl = QColor(it["color"])
                gl.setAlpha(60)
                p.setBrush(gl)
                p.drawPolygon(poly.translated(0, 0))
            p.setTransform(tr, True)
            p.drawPixmap(QRectF(0, 0, 250, 78), pix, QRectF(pix.rect()))
            p.restore()
        # centre text (on a soft dark glow so it stays readable)
        gl = QRadialGradient(QPointF(W / 2, H * 0.30), W * 0.34)
        gl.setColorAt(0, QColor(11, 12, 17, 210))
        gl.setColorAt(1, QColor(11, 12, 17, 0))
        p.fillRect(self.rect(), QBrush(gl))
        p.setPen(QColor(TEXT))
        f1 = QFont(self.font())
        f1.setPixelSize(46)
        f1.setBold(True)
        p.setFont(f1)
        p.drawText(QRectF(0, H * 0.20, W, 60), int(AF.AlignCenter), "\U0001F4AC  LocalChat")
        f2 = QFont(self.font())
        f2.setPixelSize(16)
        p.setFont(f2)
        p.setPen(QColor("#c3c7d6"))
        p.drawText(QRectF(0, H * 0.20 + 62, W, 26), int(AF.AlignCenter),
                   "Drop a WhatsApp or Telegram export anywhere on this window")
        f2.setPixelSize(13)
        p.setFont(f2)
        p.setPen(QColor(MUTED))
        p.drawText(QRectF(0, H * 0.20 + 92, W, 22), int(AF.AlignCenter),
                   "\U0001F512 100% offline \u00B7 nothing ever leaves your computer \u00B7 click a bubble to spin it")
        if self.drag_on:
            p.setPen(QPen(QColor(ACCENT), 3, Qt.PenStyle.DashLine))
            p.setBrush(QColor(124, 156, 255, 28))
            p.drawRoundedRect(QRectF(24, 24, W - 48, H - 48), 24, 24)
            f1.setPixelSize(30)
            p.setFont(f1)
            p.setPen(QColor(TEXT))
            p.drawText(QRectF(0, H * 0.72, W, 50), int(AF.AlignCenter), "Drop to analyze")
        p.end()


# --------------------------------------------------------------------------- #
#  Stacked widget that turns like a 3D cube when you change page
# --------------------------------------------------------------------------- #
class _CubeOverlay(QWidget):
    def __init__(self, parent, old, new, direction, done):
        super().__init__(parent)
        self.old, self.new, self.dir, self.done = old, new, direction, done
        self.t0 = time.perf_counter()
        self.setGeometry(parent.rect())
        self.timer = QTimer(self)
        self.timer.setInterval(16)
        self.timer.timeout.connect(self._tick)
        self.timer.start()
        self.show()
        self.raise_()

    def _tick(self):
        if time.perf_counter() - self.t0 >= 0.55:
            self.timer.stop()
            self.hide()
            self.done()
            self.deleteLater()
        else:
            self.update()

    def _face(self, p, pix, phi, W, H):
        zc = W / 2.0
        D = W * 1.7
        pts = []
        for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
            x, y, z = sx * W / 2, sy * H / 2, -zc
            x1 = x * math.cos(phi) + z * math.sin(phi)
            z1 = -x * math.sin(phi) + z * math.cos(phi)
            z1 += zc
            k = D / (D + z1)
            pts.append(QPointF(W / 2 + x1 * k, H / 2 + y * k))
        poly = QPolygonF(pts)
        tr = QTransform()
        src = QPolygonF([QPointF(0, 0), QPointF(W, 0), QPointF(W, H), QPointF(0, H)])
        if QTransform.quadToQuad(src, poly, tr):
            p.save()
            p.setTransform(tr, True)
            p.drawPixmap(QRectF(0, 0, W, H), pix, QRectF(pix.rect()))
            p.restore()
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(0, 0, 0, int(150 * clamp(abs(math.sin(phi)) * 1.1))))
            p.drawPolygon(poly)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform)
        p.fillRect(self.rect(), QColor(BG))
        W, H = self.width(), self.height()
        t = ease_io((time.perf_counter() - self.t0) / 0.55)
        phi_old = self.dir * t * math.pi / 2
        phi_new = phi_old - self.dir * math.pi / 2
        # far face first
        faces = [(self.old, phi_old), (self.new, phi_new)]
        faces.sort(key=lambda fp: -abs(math.sin(fp[1])) * 0 + abs(fp[1]))
        for pix, phi in reversed(faces):
            self._face(p, pix, phi, W, H)
        p.end()


class FlipStack(QStackedWidget):
    def flip_to(self, i, direction=1):
        i = max(0, min(i, self.count() - 1))
        if i == self.currentIndex() or not self.isVisible() or self.width() < 60 or self.count() == 0:
            self.setCurrentIndex(i)
            return
        old = self.currentWidget().grab()
        self.setCurrentIndex(i)
        QApplication.processEvents()
        new = self.currentWidget().grab()
        _CubeOverlay(self, old, new, 1 if direction >= 0 else -1, lambda: None)


def scroll_page(widget: QWidget) -> QScrollArea:
    sa = QScrollArea()
    sa.setWidgetResizable(True)
    sa.setWidget(widget)
    return sa


def shorten(s, n=18):
    s = str(s)
    return s if len(s) <= n else s[: n - 1] + "\u2026"


# --------------------------------------------------------------------------- #
#  Mood / emotion detection  (all engines run locally - nothing leaves your PC)
# --------------------------------------------------------------------------- #
MOOD_COLORS = {"happy": "#FBBF24", "loving": "#FF7A90", "angry": "#EF4444", "sad": "#60A5FA",
               "anxious": "#A78BFA", "upset": "#FB923C", "neutral": "#5b6075"}
MOOD_EMOJI = {"happy": "\U0001F604", "loving": "\U0001F970", "angry": "\U0001F621", "sad": "\U0001F622",
              "anxious": "\U0001F630", "upset": "\U0001F61E", "neutral": "\U0001F610"}
MOOD_ORDER = ["happy", "loving", "neutral", "anxious", "sad", "upset", "angry"]

_LEX = {
    "happy": dict(
        strong=[r"(?:ha){2,}h?", r"hehe+", r"lo+l+", r"lm+a+o+", r"rofl", r"yay+", r"awesome", r"amazing", r"zabardast",
                r"jhakaas", r"badhiya", r"congrat\w*", r"mubarak", r"so happy", r"happy", r"excited", r"mast", r"maz[ae]+",
                r"khush\w*", r"enjoy\w*", r"bindaas"],
        weak=[r"great", r"nice", r"fun", r"cool", r"wow", r"party", r"thanks?", r"thank you", r"thx", r"shukriya", r"best",
              r"perfect", r"super", r"good", r"accha", r"acha", r"mst", r"win", r"won", r"proud"],
        emoji="\U0001F602\U0001F923\U0001F604\U0001F601\U0001F60A\U0001F600\U0001F973\U0001F389\U0001F606\U0001F64C\U0001F60E\U0001F603\U0001F639\U0001F44D"),
    "loving": dict(
        strong=[r"love (?:you|u)", r"luv u", r"i love", r"miss (?:you|u)", r"miss kar\w*", r"pyaa?r", r"jaan", r"jaanu", r"janu",
                r"babu", r"shona", r"ily", r"sweetheart"],
        weak=[r"love", r"miss", r"dear", r"baby", r"babe", r"cutie", r"darling", r"hug", r"kiss", r"bae", r"honey"],
        emoji="\u2764\U0001F495\U0001F496\U0001F497\U0001F60D\U0001F618\U0001F970\U0001F63B\U0001FAF6\U0001F49E\U0001F493\U0001F61A"),
    "angry": dict(
        strong=[r"shut ?up", r"stfu", r"wtf+", r"fuck\w*", r"bullshit", r"idiot", r"stupid", r"bewakoof", r"bakwas", r"harami",
                r"kamin[ae]\w*", r"gussa", r"angry", r"hate", r"pissed", r"nonsense", r"irritat\w+", r"annoy\w+",
                r"leave me alone", r"get lost", r"chup ?kar", r"mad at"],
        weak=[r"damn", r"shit", r"bekar", r"boring", r"useless", r"rude", r"ignor\w+", r"whatever", r"seriously", r"enough",
              r"tang", r"pagal", r"saala", r"saali", r"bc", r"mc", r"never listen", r"stop it", r"fed up"],
        emoji="\U0001F621\U0001F92C\U0001F620\U0001F47F\U0001F4A2\U0001F595"),
    "sad": dict(
        strong=[r"sad", r"cry\w*", r"crying", r"depress\w+", r"lonely", r"heartbroken", r"udaas", r"dukh", r"rona", r"ro raha",
                r"ro rahi", r"hurt\w*"],
        weak=[r"alone", r"upset", r"tired", r"bad", r"kharab", r"sigh", r"hopeless", r"down", r"disappoint\w*",
              r"give up"],
        emoji="\U0001F622\U0001F61E\U0001F614\U0001F494\U0001F97A\U0001F63F\U0001F641\u2639",
        weak_emoji="\U0001F62D"),
    "anxious": dict(
        strong=[r"worried", r"anxious", r"panic\w*", r"scared", r"afraid", r"nervous", r"stress\w*", r"chinta", r"darr?",
                r"tension"],
        weak=[r"worry", r"fear", r"careful", r"nahi pata", r"what if", r"urgent", r"asap", r"hurry", r"jaldi"],
        emoji="\U0001F630\U0001F628\U0001F61F\U0001F62C\U0001F631\U0001F613"),
}


def _compile_words(ws):
    return re.compile(r"(?<!\w)(?:" + "|".join(ws) + r")(?!\w)", re.I)


_LEX_RE = {k: (_compile_words(v["strong"]), _compile_words(v["weak"])) for k, v in _LEX.items()}
_EMOJI_W = {}
for _k, _v in _LEX.items():
    for _c in _v["emoji"]:
        _EMOJI_W[_c] = (_k, 2.0)
    for _c in _v.get("weak_emoji", ""):
        _EMOJI_W[_c] = (_k, 1.0)
_NEG_RE = re.compile(r"(?<!\w)(?:not|no|never|nahi|nhi|nahin|mat|don'?t|dont|isn'?t|aren'?t|can'?t|cant|won'?t|wont)\s+(?:\w+\s+){0,2}$", re.I)
_REPEAT_RE = re.compile(r"(\w)\1{2,}")


def _score_text(t):
    t0 = _REPEAT_RE.sub(r"\1\1", t)
    sc = dict.fromkeys(("happy", "loving", "angry", "sad", "anxious"), 0.0)
    for cat, (sre, wre) in _LEX_RE.items():
        for rx, w in ((sre, 2.0), (wre, 1.0)):
            for m in rx.finditer(t0):
                if _NEG_RE.search(t0[max(0, m.start() - 24):m.start()]):
                    if cat in ("happy", "loving"):
                        sc["sad"] += w * 0.5  # "not happy", "don't love"
                    continue
                sc[cat] += w
    if not t0.isascii():
        for ch in t0:
            hit = _EMOJI_W.get(ch)
            if hit:
                sc[hit[0]] += hit[1]
    letters = [c for c in t if c.isalpha()]
    shout = len(letters) >= 4 and sum(c.isupper() for c in letters) / len(letters) > 0.7
    lead = max(sc, key=sc.get)
    if sc[lead] > 0:
        if shout and lead in ("angry", "sad", "anxious"):
            sc[lead] *= 1.5
        if t.count("!") >= 2:
            sc[lead] *= 1.3
    elif shout:
        sc["angry"] += 1.0
    top = max(sc, key=sc.get)
    mood = top if sc[top] >= 2 else "neutral"
    pos, neg = sc["happy"] + sc["loving"], sc["angry"] + sc["sad"] + 0.5 * sc["anxious"]
    return mood, (pos - neg) / (pos + neg + 2), sc[top]


def mood_lexicon(texts, progress=None):
    out = []
    n = len(texts)
    for i, t in enumerate(texts):
        out.append(_score_text(t))
        if progress and i % 2000 == 0:
            progress(i, n)
    return out


TRANSFORMER_MODEL = "cardiffnlp/twitter-xlm-roberta-base-sentiment"   # multilingual (incl. Hindi)


def mood_transformers(texts, progress, model_name=TRANSFORMER_MODEL):
    try:
        from transformers import pipeline
    except ImportError:
        raise RuntimeError("The local AI engine needs:\n    pip install transformers torch sentencepiece\n"
                           "The model is downloaded once (the model only - your chat is never sent), then runs offline.")
    clf = pipeline("text-classification", model=model_name, top_k=None, truncation=True, max_length=128)
    base = mood_lexicon(texts)
    out, B = [], 32
    for i in range(0, len(texts), B):
        for j, probs in enumerate(clf([t[:400] for t in texts[i:i + B]])):
            d = {p["label"].lower(): p["score"] for p in probs}
            v = d.get("positive", d.get("label_2", 0.0)) - d.get("negative", d.get("label_0", 0.0))
            lm = base[i + j][0]
            if v > 0.35:
                mood = lm if lm in ("happy", "loving") else "happy"
            elif v < -0.35:
                mood = lm if lm in ("angry", "sad", "anxious") else "upset"
            else:
                mood = "neutral"
            out.append((mood, float(v), abs(float(v)) * 3))
        progress(min(i + B, len(texts)), len(texts))
    return out


def mood_ollama(texts, progress, model="qwen2.5:7b", host="http://localhost:11434"):
    import urllib.request
    import urllib.error
    base = mood_lexicon(texts)
    out, B = list(base), 25
    allowed = ("happy", "loving", "angry", "sad", "anxious", "neutral")
    for start in range(0, len(texts), B):
        chunk = texts[start:start + B]
        lines = "\n".join(f"{i}: {t[:300]!r}" for i, t in enumerate(chunk))
        prompt = (
            "You analyse emotions in casual chat messages (English, Hindi, Hinglish, emojis; beware sarcasm and jokes between "
            "friends). For EACH numbered message give the emotion of the sender: one of happy, loving, angry, sad, anxious, "
            "neutral, and a valence from -1 (very negative) to 1 (very positive).\n"
            'Reply ONLY with JSON: {"results":[{"i":0,"emotion":"neutral","valence":0.0}, ...]}\n\nMessages:\n' + lines)
        body = json.dumps({"model": model, "prompt": prompt, "stream": False, "format": "json",
                           "options": {"temperature": 0}}).encode()
        req = urllib.request.Request(host + "/api/generate", data=body, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                resp = json.loads(json.loads(r.read())["response"])
        except urllib.error.URLError:
            raise RuntimeError("Could not reach Ollama on this computer.\nInstall it from ollama.com, then run:\n"
                               f"    ollama pull {model}\nand keep it running.")
        except Exception:
            continue  # bad JSON from the model -> keep the built-in guess for this chunk
        items = resp.get("results", resp) if isinstance(resp, dict) else resp
        for it in items if isinstance(items, list) else []:
            try:
                i, emo = int(it["i"]), str(it["emotion"]).lower()
                v = max(-1.0, min(1.0, float(it.get("valence", 0))))
            except Exception:
                continue
            if 0 <= i < len(chunk) and emo in allowed:
                out[start + i] = (emo, v, abs(v) * 3)
        progress(min(start + B, len(texts)), len(texts))
    return out


class MoodWorker(QThread):
    progress = pyqtSignal(int, int)
    done = pyqtSignal(object, str)
    failed = pyqtSignal(str)

    def __init__(self, df, engine, model, max_n):
        super().__init__()
        self.df, self.engine, self.model, self.max_n = df, engine, model, max_n

    def run(self):
        try:
            cand = self.df[self.df.is_text & (self.df.words >= 1)]
            if self.engine != 0 and len(cand) > self.max_n:
                rich = cand[cand.words >= 2]
                pool = rich if len(rich) >= self.max_n else cand
                cand = pool.iloc[np.linspace(0, len(pool) - 1, self.max_n).astype(int)]
            texts = cand.text.tolist()
            cb = lambda a, b: self.progress.emit(a, b)  # noqa
            if self.engine == 0:
                res, name = mood_lexicon(texts, cb), "built-in"
            elif self.engine == 1:
                res, name = mood_transformers(texts, cb, self.model or TRANSFORMER_MODEL), "local AI model"
            else:
                res, name = mood_ollama(texts, cb, self.model or "qwen2.5:7b"), "Ollama"
            self.done.emit(pd.DataFrame(res, index=cand.index, columns=["mood", "valence", "intensity"]), name)
        except Exception as e:  # noqa
            self.failed.emit(str(e))


def mood_summary(df, gap_h):
    """Per-person mood mix, best/worst days, and the most tense / happiest conversations."""
    a = df[df.valence.notna()]
    mix = (a.groupby("sender").mood.value_counts(normalize=True).unstack(fill_value=0) * 100)
    for m in MOOD_ORDER:
        if m not in mix:
            mix[m] = 0.0
    mix = mix.reindex(df.sender.value_counts().index).dropna(how="all").fillna(0)
    counts = a.groupby("sender").size()

    days = {}
    d = a.groupby(["sender", "date"]).valence.agg(["mean", "size"]).reset_index()
    for s, g in d.groupby("sender"):
        g = g[g["size"] >= 5] if (g["size"] >= 5).any() else g[g["size"] >= 2]
        if len(g):
            lo, hi = g.loc[g["mean"].idxmin()], g.loc[g["mean"].idxmax()]
            days[s] = dict(worst=(lo["date"], lo["mean"], int(lo["size"])), best=(hi["date"], hi["mean"], int(hi["size"])))

    conv_id = (df.ts.diff() > timedelta(hours=gap_h)).cumsum()
    a = a.assign(conv=conv_id.loc[a.index])
    convs = []
    for _, g in a.groupby("conv"):
        if len(g) < 3:
            continue
        angry = g[g.mood.isin(["angry", "upset"])].sender.value_counts()
        worst, best = g.loc[g.valence.idxmin()], g.loc[g.valence.idxmax()]
        convs.append(dict(when=g.ts.min(), n=len(g), mean=g.valence.mean(),
                          angriest=(angry.index[0] if len(angry) else worst.sender),
                          happiest=g.groupby("sender").valence.mean().idxmax(),
                          worst=worst, best=best))
    tense = sorted([c for c in convs if c["mean"] < -0.05], key=lambda c: c["mean"])[:8]
    happy = sorted([c for c in convs if c["mean"] > 0.05], key=lambda c: -c["mean"])[:8]
    return dict(mix=mix, counts=counts, days=days, tense=tense, happy=happy, analyzed=len(a))


# --------------------------------------------------------------------------- #
#  Story-style report ("Wrapped" cards, one step at a time)
# --------------------------------------------------------------------------- #
RC = {  # card themes: (background, text colour)
    "indigo": ("#1f2a5a", "#aebcff"), "purple": ("#2a1550", "#cdb8ff"), "brown": ("#5a3017", "#f2bb92"),
    "green": ("#146a50", "#a2e8cf"), "maroon": ("#5a1829", "#f5a9bf"), "olive": ("#5c470d", "#f0d27a"),
    "sand": ("#473320", "#dcc6a4"), "teal": ("#124a45", "#9fe5d8"), "blue": ("#1b2c5c", "#a9c0ff"),
    "amber": ("#6b4a0a", "#f6d78a"),
}
MONO = "'JetBrains Mono','DejaVu Sans Mono','Consolas','Courier New',monospace"


def _lbl(text, css="", wrap=False):
    l = QLabel(str(text))
    l.setStyleSheet(css)
    l.setWordWrap(wrap)
    return l


def rcard(title, key):
    bg, fg = RC[key]
    f = QFrame()
    f.setObjectName("rc")
    f.setStyleSheet(f"QWidget{{background:transparent;}} QFrame#rc{{background:{bg};border-radius:16px;border:none;}} "
                    f"QLabel{{background:transparent;color:{fg};}}")
    v = QVBoxLayout(f)
    v.setContentsMargins(16, 14, 16, 16)
    v.setSpacing(8)
    if title:
        v.addWidget(_lbl(title, "font-size:14px;font-weight:600;"))
    return f, v


def bignum(value, unit="", size=34):
    w = QWidget()
    h = QHBoxLayout(w)
    h.setContentsMargins(0, 0, 0, 0)
    h.setSpacing(6)
    h.addWidget(_lbl(value, f"font-family:{MONO};font-size:{size}px;font-weight:700;"), 0, Qt.AlignmentFlag.AlignBottom)
    if unit:
        h.addWidget(_lbl(unit, "font-size:11px;"), 0, Qt.AlignmentFlag.AlignBottom)
    h.addStretch()
    return w


class Bar(QWidget):
    def __init__(self, frac, color, h=10):
        super().__init__()
        self.frac, self.color, self.h = max(0.0, min(1.0, frac)), color, h
        self.setFixedHeight(h)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(255, 255, 255, 30))
        p.drawRoundedRect(QRectF(0, 0, self.width(), self.h), self.h / 2, self.h / 2)
        p.setBrush(QColor(self.color))
        w = max(self.width() * self.frac, self.h) if self.frac > 0 else 0
        p.drawRoundedRect(QRectF(0, 0, w, self.h), self.h / 2, self.h / 2)


class HourBars(QWidget):
    def __init__(self, counts):
        super().__init__()
        self.c = np.asarray(counts, dtype=float)
        self.setMinimumHeight(110)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H, lab = self.width(), self.height(), 18
        ch = H - lab
        mx = self.c.max() or 1
        slot = W / 24
        bw = slot * 0.62
        p.setPen(Qt.PenStyle.NoPen)
        for i, c in enumerate(self.c):
            x = i * slot + (slot - bw) / 2
            if c <= 0:
                p.setBrush(QColor("#efe3b0"))
                p.drawRect(QRectF(x, ch - 2, bw, 2))
            else:
                h = max(4.0, ch * c / mx)
                p.setBrush(QColor("#a89048"))
                p.drawRoundedRect(QRectF(x, ch - h, bw, h), 2, 2)
        p.setPen(QColor("#e1d199"))
        for hr in (0, 6, 12, 18):
            p.drawText(QRectF(hr * slot, ch + 3, slot * 3, lab), Qt.AlignmentFlag.AlignLeft, f"{hr:02d}")


def bar_rows(items, colors, icon="\U0001F4AC", show_count=True, show_pct=True):
    tot = sum(v for _, v in items) or 1
    mx = max(v for _, v in items) or 1
    w = QWidget()
    v = QVBoxLayout(w)
    v.setContentsMargins(0, 4, 0, 0)
    v.setSpacing(5)
    for name, val in items:
        col = colors.get(name, OTHERS_COLOR)
        row = QHBoxLayout()
        row.setSpacing(6)
        row.addWidget(_lbl("\u25CF", f"color:{col};font-size:10px;"))
        row.addWidget(_lbl(shorten(name, 26), "font-size:12px;color:#ececec;"))
        row.addStretch()
        if show_count:
            row.addWidget(_lbl(f"{val:,.0f} {icon}", "font-size:12px;color:#ececec;"))
        if show_pct:
            pct = _lbl(f"{val / tot * 100:.0f}%", "font-size:12px;font-weight:700;color:#ffffff;")
            pct.setMinimumWidth(38)
            pct.setAlignment(Qt.AlignmentFlag.AlignRight)
            row.addWidget(pct)
        v.addLayout(row)
        v.addWidget(Bar(val / mx, col))
        v.addSpacing(6)
    return w


def top_with_others(series, n=6):
    s = series[series > 0].sort_values(ascending=False)
    items = list(s.head(n).items())
    if len(s) > n:
        items.append(("Others", s.iloc[n:].sum()))
    return items


class _Slide:
    def __init__(self, title, sub=None):
        self.page = QWidget()
        outer = QHBoxLayout(self.page)
        outer.setContentsMargins(20, 22, 20, 20)
        self.col = QWidget()
        self.col.setMaximumWidth(600)
        self.v = QVBoxLayout(self.col)
        self.v.setContentsMargins(0, 0, 0, 0)
        self.v.setSpacing(12)
        self.title = title
        self.v.addWidget(_lbl(title, "font-size:26px;font-weight:700;color:#ececec;"))
        if sub:
            self.v.addWidget(_lbl(sub, "font-size:13px;color:#9a9eae;", True))
        outer.addStretch(1)
        outer.addWidget(self.col, 4)
        outer.addStretch(1)


class ReportView(QWidget):
    finished = pyqtSignal()

    def __init__(self):
        super().__init__()
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        self.stack = FlipStack()
        v.addWidget(self.stack, 1)
        nav = QHBoxLayout()
        nav.setContentsMargins(20, 6, 20, 14)
        self.btn_save = QPushButton("Save slide PNG")
        self.btn_all = QPushButton("Export all slides")
        for b in (self.btn_save, self.btn_all):
            b.setObjectName("ghost")
        self.btn_back = QPushButton("\u2190  Back")
        self.btn_next = QPushButton("Continue  \u2192")
        self.btn_next.setObjectName("primary")
        self.btn_next.setMinimumWidth(150)
        self.lbl_pos = QLabel("")
        self.lbl_pos.setObjectName("muted")
        nav.addWidget(self.btn_save)
        nav.addStretch()
        nav.addWidget(self.btn_back)
        nav.addWidget(self.lbl_pos)
        nav.addWidget(self.btn_next)
        nav.addStretch()
        nav.addWidget(self.btn_all)
        v.addLayout(nav)
        self.btn_back.clicked.connect(lambda: self.go(-1))
        self.btn_next.clicked.connect(lambda: self.go(1))
        self.btn_save.clicked.connect(self.save_current)
        self.btn_all.clicked.connect(self.save_all)
        self.titles = []

    # ----- navigation ----- #
    def go(self, d):
        i = self.stack.currentIndex() + d
        if i >= self.stack.count():
            self.finished.emit()
            return
        self.stack.flip_to(max(0, i), d)
        self._sync()

    def _sync(self):
        i, n = self.stack.currentIndex(), self.stack.count()
        self.lbl_pos.setText(f"{i + 1} / {n}")
        self.btn_back.setEnabled(i > 0)
        self.btn_next.setText("Open dashboard  \u2192" if i == n - 1 else "Continue  \u2192")

    def _grab(self):
        return self.stack.currentWidget()._col.grab()

    def save_current(self):
        i = self.stack.currentIndex()
        name = re.sub(r"\W+", "_", self.titles[i]).strip("_").lower() + ".png"
        p, _ = QFileDialog.getSaveFileName(self, "Save slide", name, "PNG image (*.png)")
        if p:
            self._grab().save(p)

    def save_all(self):
        d = QFileDialog.getExistingDirectory(self, "Choose a folder for the report images")
        if not d:
            return
        cur = self.stack.currentIndex()
        for i in range(self.stack.count()):
            self.stack.setCurrentIndex(i)
            QApplication.processEvents()
            name = f"{i + 1:02d}_" + re.sub(r"\W+", "_", self.titles[i]).strip("_").lower() + ".png"
            self._grab().save(f"{d}/{name}")
        self.stack.setCurrentIndex(cur)
        self._sync()

    def _commit(self, sl):
        sl.v.addStretch(1)
        sa = scroll_page(sl.page)
        sa._col = sl.col
        self.stack.addWidget(sa)
        self.titles.append(sl.title)

    # ----- content ----- #
    def build(self, df, ov, t, wc, ec, colors, gap_h, ctype="other"):
        cfg = CHAT_TYPES.get(ctype, CHAT_TYPES["other"])
        T = {**DEFAULT_TITLES, **cfg["titles"]}
        prev = self.stack.currentIndex()
        while self.stack.count():
            w = self.stack.widget(0)
            self.stack.removeWidget(w)
            w.deleteLater()
        self.titles = []
        multi = len(t) > 1
        top_name = t.index[0]
        topics = []
        for label, pat, key in cfg["topics"]:
            c = kw_counts(df, pat, t.index)
            if c.sum() > 0:
                topics.append((label, c, key))

        # 1. intro
        kind = "Group chat" if ov["people"] > 2 else "1-to-1 chat"
        s = _Slide(T["intro"], f"{cfg['emoji']} {cfg['label']} \u00B7 {kind} \u00B7 "
                               f"{ov['start']:%d %b %Y} \u2192 {ov['end']:%d %b %Y}")
        f, v = rcard("Total messages", "indigo")
        v.addWidget(bignum(f"{ov['total']:,}", "messages", 44))
        v.addWidget(_lbl(f"about {ov['per_day']:.0f} a day, across {ov['active_days']:,} active days", "font-size:12px;"))
        s.v.addWidget(f)
        g = QGridLayout()
        g.setSpacing(12)
        for i, (cap, val, key) in enumerate([("People", f"{ov['people']}", "purple"),
                                             ("Words", f"{ov['words']:,}", "teal"),
                                             ("Media shared", f"{ov['media']:,}", "brown"),
                                             ("Conversations", f"{ov['conversations']:,}", "olive")]):
            f, v = rcard(cap, key)
            v.addWidget(bignum(val, "", 26))
            g.addWidget(f, i // 2, i % 2)
        s.v.addLayout(g)
        self._commit(s)

        # 2. who talks more
        pct = t.share.iloc[0]
        s = _Slide(T["talk"], f"{top_name} sends {pct:.0f}% of all messages." if multi else None)
        f, v = rcard("Messages", "teal")
        v.addWidget(bar_rows(top_with_others(t.messages), colors))
        s.v.addWidget(f)
        f, v = rcard("Words", "blue")
        v.addWidget(bar_rows(top_with_others(t.words), colors, icon="\U0001F4DD"))
        s.v.addWidget(f)
        if len(t) == 2:
            sh = sorted(t.share)
            bal = sh[0] / sh[1] * 100 if sh[1] else 0
            f, v = rcard("Balance", "purple")
            v.addWidget(bignum(f"{bal:.0f}%", "balanced", 30))
            v.addWidget(_lbl("Almost perfectly balanced." if bal >= 90 else
                             f"{top_name} talks a bit more." if bal >= 60 else
                             f"{top_name} does most of the talking.", "font-size:12px;"))
            s.v.addWidget(f)
        f, v = rcard("Average message length", "sand")
        v.addWidget(bar_rows([(n, round(x, 1)) for n, x in t.avg_words.sort_values(ascending=False).head(6).items()],
                             colors, icon="words / msg", show_pct=False))
        s.v.addWidget(f)
        self._commit(s)

        # 3. who messages first
        if multi and t.starts.sum():
            st = t.starts.sort_values(ascending=False)
            s = _Slide(T["first"],
                       f"{st.index[0]} starts {st.iloc[0] / st.sum() * 100:.0f}% of conversations. "
                       f"A new conversation = {gap_h:g}+ hours of silence.")
            f, v = rcard("Conversation starters", "amber")
            v.addWidget(bar_rows(top_with_others(st), colors, icon="\U0001F44B"))
            v.addWidget(_lbl(f"{ov['conversations']:,} conversations in total", "font-size:11px;"))
            s.v.addWidget(f)
            en = t.ends.sort_values(ascending=False)
            f, v = rcard("Who gets the last word", "purple")
            v.addWidget(bar_rows(top_with_others(en), colors, icon="\U0001F3C1"))
            s.v.addWidget(f)
            self._commit(s)

        # 4. rhythm
        s = _Slide(T["rhythm"])
        r = t.reply_min.dropna().sort_values()
        if len(r):
            f, v = rcard("Median reply time", "purple")
            row = QHBoxLayout()
            row.setSpacing(10)
            items = list(r.head(3).items())
            order = {1: [0], 2: [1, 0]}.get(len(items), [1, 0, 2])
            medals, bgs, hts = ["\U0001F947", "\U0001F948", "\U0001F949"], ["#34417f", "#2d3973", "#3b2a7c"], [130, 108, 92]
            for i in order:
                name, m = items[i]
                box = QFrame()
                box.setStyleSheet(f"QFrame{{background:{bgs[i]};border-radius:14px;}} QLabel{{background:transparent;color:#c9d2ff;}}")
                box.setMinimumHeight(hts[i])
                bv = QVBoxLayout(box)
                bv.setAlignment(Qt.AlignmentFlag.AlignCenter)
                bv.addWidget(_lbl(medals[i], "font-size:24px;"), 0, Qt.AlignmentFlag.AlignCenter)
                bv.addWidget(_lbl(shorten(name, 14), "font-size:11px;font-weight:600;"), 0, Qt.AlignmentFlag.AlignCenter)
                val, unit = (("< 1", "min") if m < 1 else (f"{m:.0f}", "min") if m < 60 else
                             (f"{m / 60:.1f}", "h") if m < 1440 else (f"{m / 1440:.1f}", "days"))
                bv.addWidget(bignum(val, unit, 18), 0, Qt.AlignmentFlag.AlignCenter)
                row.addWidget(box, 1, Qt.AlignmentFlag.AlignBottom)
            v.addSpacing(6)
            v.addLayout(row)
            s.v.addWidget(f)
        f, v = rcard("Record day", "brown")
        rw = QWidget()
        rh = QHBoxLayout(rw)
        rh.setContentsMargins(0, 0, 0, 0)
        rh.addWidget(bignum(f"{ov['busiest_count']}", "", 34))
        rh.addWidget(_lbl(f"messages on {ov['busiest_date']:%d %B %Y}", "font-size:11px;"), 1, Qt.AlignmentFlag.AlignBottom)
        v.addWidget(rw)
        s.v.addWidget(f)
        h = QHBoxLayout()
        h.setSpacing(12)
        f, v = rcard("Streak", "green")
        v.addWidget(bignum(ov["streak"], "days", 34))
        h.addWidget(f)
        f, v = rcard("Longest silence", "maroon")
        v.addWidget(bignum(ov["silence"], "days", 34))
        h.addWidget(f)
        s.v.addLayout(h)
        hours = df.groupby("hour").size().reindex(range(24), fill_value=0)
        late = hours.loc[22:].sum() / max(hours.sum(), 1) * 100
        f, v = rcard("By hour", "olive")
        v.addWidget(HourBars(hours.values))
        v.addWidget(_lbl(f"{late:.0f}% after 10pm \u00B7 peak at {hour_label(int(hours.idxmax()))}", "font-size:11px;"))
        s.v.addWidget(f)
        if ctype == "work":
            office = (df.weekday < 5) & df.hour.between(9, 17)
            f, v = rcard("Office hours", "blue")
            v.addWidget(bignum(f"{office.mean() * 100:.0f}%", "of messages Mon\u2013Fri, 9am\u20136pm", 28))
            after = (~office).groupby(df.sender).sum().reindex(t.index).fillna(0)
            if after.sum() > 0:
                v.addWidget(_lbl("After-hours & weekend messages", "font-size:11px;"))
                v.addWidget(bar_rows(top_with_others(after), colors, icon="\U0001F319", show_pct=False))
            s.v.addWidget(f)
        self._commit(s)

        # 4b. moods (only if the mood analysis has been run)
        if "valence" in df.columns and df.valence.notna().any():
            ms = mood_summary(df, gap_h)
            mix = ms["mix"]
            s = _Slide(T["mood"], f"Based on {ms['analyzed']:,} analysed messages. Approximate \u2013 jokes and sarcasm can fool it.")

            def mood_card(title, key, cols, unit):
                ser = mix[cols].sum(axis=1).round(1).sort_values(ascending=False)
                ser = ser[ser > 0].head(6)
                if len(ser):
                    f, v = rcard(title, key)
                    v.addWidget(bar_rows(list(ser.items()), colors, icon=unit, show_pct=False))
                    s.v.addWidget(f)
            mood_card("\U0001F604 Happiest vibes", "amber", ["happy", "loving"], "% happy / loving")
            mood_card("\U0001F621 Short fuse", "maroon", ["angry", "upset"], "% angry / upset")
            mood_card("\U0001F622 Low moments", "blue", ["sad", "anxious"], "% sad / anxious")
            for title, key, lst, who, side in (("Most tense conversation", "brown", ms["tense"], "angriest", "worst"),
                                               ("Happiest conversation", "green", ms["happy"], "happiest", "best")):
                if not lst:
                    continue
                c = lst[0]
                f, v = rcard(title, key)
                v.addWidget(_lbl(f"{c['when']:%d %B %Y}", f"font-family:{MONO};font-size:20px;font-weight:700;"))
                v.addWidget(_lbl(f"{c['n']} messages \u00B7 {who}: {c[who]}", "font-size:12px;"))
                m = c[side]
                bub = QFrame()
                bub.setStyleSheet("QFrame{background:#17171c;border-radius:12px;} QLabel{background:transparent;}")
                bl = QVBoxLayout(bub)
                bl.setContentsMargins(10, 7, 10, 8)
                bl.setSpacing(2)
                bl.addWidget(_lbl(shorten(m.sender, 30), f"font-size:10px;font-weight:700;color:{colors.get(m.sender, ACCENT)};"))
                bl.addWidget(_lbl(shorten(m.text, 200), "font-size:12px;color:#e6e6e6;", True))
                v.addWidget(bub)
                s.v.addWidget(f)
            self._commit(s)

        # 5. themed slide for this chat type
        if topics:
            s = _Slide(T["themed"])
            for label, c, key in topics:
                f, v = rcard(label, key)
                v.addWidget(bar_rows(top_with_others(c), colors, icon="\u00D7"))
                s.v.addWidget(f)
            self._commit(s)

        # 6. longest message
        txt = df[df.is_text]
        if len(txt):
            idx = txt.groupby("sender").words.idxmax()
            s = _Slide(T["long"])
            for name in t.index[:6]:
                if name not in idx.index:
                    continue
                r = df.loc[idx[name]]
                f, v = rcard(shorten(name, 30), "sand")
                v.addWidget(bignum(int(r.words), "words", 30))
                v.addWidget(_lbl(f"{r.ts:%d %B %Y}", "font-size:10px;"))
                bub = QFrame()
                bub.setStyleSheet("QFrame{background:#17171c;border-radius:12px;} QLabel{background:transparent;}")
                bl = QVBoxLayout(bub)
                bl.setContentsMargins(10, 7, 10, 8)
                bl.setSpacing(2)
                bl.addWidget(_lbl(shorten(name, 30), f"font-size:10px;font-weight:700;color:{colors.get(name, ACCENT)};"))
                msg = r.text if len(r.text) <= 260 else r.text[:259] + "\u2026"
                bl.addWidget(_lbl(msg, "font-size:12px;color:#e6e6e6;", True))
                v.addWidget(bub)
                s.v.addWidget(f)
            self._commit(s)

        # 7. words & emojis
        allw, alle = Counter(), Counter()
        for k in wc:
            allw.update(wc[k])
            alle.update(ec[k])
        s = _Slide(T["words"])
        f, v = rcard("Most used words", "green")
        for i, (w_, c) in enumerate(allw.most_common(5), 1):
            row = QHBoxLayout()
            row.addWidget(_lbl(f"#{i}", f"font-family:{MONO};font-size:10px;"))
            row.addWidget(_lbl(w_, "font-size:15px;font-weight:700;"))
            row.addStretch()
            row.addWidget(_lbl(f"{c:,}\u00D7", "font-size:11px;"))
            v.addLayout(row)
        if not allw:
            v.addWidget(_lbl("Not enough text yet.", ""))
        s.v.addWidget(f)
        f, v = rcard("Most used emojis", "amber")
        row = QHBoxLayout()
        for e, c in alle.most_common(6):
            col = QVBoxLayout()
            col.setSpacing(0)
            col.addWidget(_lbl(e, "font-size:28px;"), 0, Qt.AlignmentFlag.AlignCenter)
            col.addWidget(_lbl(f"{c:,}", "font-size:10px;"), 0, Qt.AlignmentFlag.AlignCenter)
            row.addLayout(col)
        row.addStretch()
        if not alle:
            row.addWidget(_lbl("No emojis found.", ""))
        v.addLayout(row)
        s.v.addWidget(f)
        sig = signature_words(wc, min_total=30)
        if sig and multi:
            f, v = rcard("Words only they say", "blue")
            for p_, ws in list(sig.items())[:6]:
                v.addWidget(_lbl(f"<b style='color:#ffffff'>{shorten(p_, 22)}</b> &nbsp; {', '.join(ws[:4])}", "font-size:12px;", True))
            s.v.addWidget(f)
        self._commit(s)

        # 8. awards
        if multi:
            aw = []
            for label, c, key in topics[:4]:
                if c.max() >= 3:
                    aw.append((f"\U0001F3C6 {label}", c.idxmax(), f"{c.max():,.0f} times"))

            def add(title, ser, fmt, minv=1):
                if len(ser) and ser.max() >= minv:
                    aw.append((title, ser.idxmax(), fmt(ser.max())))
            add("\U0001F989 Night owl", t.night_pct, lambda x: f"{x:.0f}% of messages sent 12\u20135 AM", 3)
            add("\U0001F602 Emoji champion", t.emojis, lambda x: f"{x:,.0f} emojis")
            add("\u2753 Curious mind", t.questions, lambda x: f"{x:,.0f} questions asked")
            add("\U0001F517 Link dropper", t.links, lambda x: f"{x:,.0f} links shared")
            add("\U0001F4F8 Media machine", t.media, lambda x: f"{x:,.0f} photos, videos & stickers")
            add("\U0001F4DD Essay writer", t.avg_words, lambda x: f"{x:.1f} words per message")
            add("\U0001F5D1 Unsender", t.deleted, lambda x: f"{x:,.0f} deleted messages")
            aw = aw[:8]
            if aw:
                s = _Slide(T["awards"])
                g = QGridLayout()
                g.setSpacing(12)
                keys = list(RC)
                for i, (title, who, val) in enumerate(aw):
                    f, v = rcard(title, keys[(i + 2) % len(keys)])
                    v.addWidget(_lbl(shorten(who, 22), "font-size:19px;font-weight:700;color:#ffffff;"))
                    v.addWidget(_lbl(val, "font-size:11px;", True))
                    g.addWidget(f, i // 2, i % 2)
                s.v.addLayout(g)
                self._commit(s)

        self.stack.setCurrentIndex(min(prev, self.stack.count() - 1) if prev > 0 else 0)
        self._sync()


# --------------------------------------------------------------------------- #
#  Chat types (the report adapts to what kind of chat this is)
# --------------------------------------------------------------------------- #
DEFAULT_TITLES = dict(intro="Your chat.", talk="Who talks more.", first="Who messages first.",
                      rhythm="Your rhythm.", long="The longest message.", words="Your words.",
                      themed="The details.", awards="The awards.", mood="The moods.")

CHAT_TYPES = {
    "romantic": dict(
        emoji="\U0001F48C", label="Romantic", desc="Partner, crush, situationship, first date, ex\u2026",
        titles=dict(talk="Who texts more.", first="Who reaches out first.", rhythm="Your rhythm together.",
                    themed="The love language.", awards="The little things."),
        topics=[
            ("\U0001F495 Love & hearts", r"love (you|u)\b|\bluv u\b|\bily\b|[\u2764\U0001F495\U0001F496\U0001F497\U0001F498\U0001F60D\U0001F618\U0001F970]", "maroon"),
            ("\U0001F97A \u201CMiss you\u201D", r"miss(ing)? (you|u)\b|\bmiss kar|yaad aa", "purple"),
            ("\u2600\uFE0F Good morning", r"good ?morning|\bgm\b|suprabhat", "amber"),
            ("\U0001F319 Good night", r"good ?night|\bgn\b|shubh ?ratri|sweet dreams", "indigo"),
            ("\U0001F43B Pet names", r"\b(jaan|janu|jaanu|babu|baby|babe|bae|shona|sona|honey|cutie|darling)\b", "brown"),
            ("\U0001F64F Sorry", r"\b(sorry|sry|maaf\w*|my bad)\b", "teal"),
        ]),
    "friends_group": dict(
        emoji="\U0001F602", label="Friends group", desc="Friends, classmates, sports clubs, gaming crews\u2026",
        titles=dict(talk="Who runs the group.", first="Who starts the chat.", rhythm="When the group is awake.",
                    long="The longest rant.", words="The group's vocabulary.", themed="The vibe.", awards="The awards."),
        topics=[
            ("\U0001F602 Laughs", r"\b(ha){2,}\b|\bhaha\w*|\blol\w*|\blmao\b|\brofl\b|[\U0001F602\U0001F923\U0001F606\U0001F639]", "amber"),
            ("\U0001F389 Plans & hangouts", r"\b(plan|party|trip|movie|chalein|chalo|milte|let'?s go|outing|hangout)\b", "green"),
            ("\U0001F525 Hype (!!!)", r"!{2,}", "maroon"),
            ("\U0001F62D Drama", r"\U0001F62D|\bno way\b|\bomg\b|\bwtf\b|\bbruh\b", "purple"),
            ("\U0001F355 Food talk", r"\b(pizza|burger|biryani|chai|coffee|food|hungry|lunch|dinner|maggi|momos?)\b|[\U0001F355\U0001F354\U0001F35F]", "brown"),
        ]),
    "any_friend": dict(
        emoji="\U0001F917", label="Any friend", desc="Best friend, childhood friend, new friend\u2026",
        titles=dict(talk="Who talks more.", first="Who reaches out first.", rhythm="Your rhythm.",
                    themed="Your friendship, in numbers.", awards="The awards."),
        topics=[
            ("\U0001F602 Laughs", r"\b(ha){2,}\b|\bhaha\w*|\blol\w*|\blmao\b|[\U0001F602\U0001F923\U0001F606]", "amber"),
            ("\U0001FAF6 Support", r"thank(s| you)|\bthx\b|take care|proud of you|you got this|\bi'?m here\b|\bmiss (you|u)\b", "green"),
            ("\U0001F64F Sorry", r"\b(sorry|sry|maaf\w*|my bad)\b", "purple"),
            ("\U0001F389 Plans", r"\b(plan|party|trip|movie|chalein|chalo|milte|let'?s go|hangout|dinner)\b", "teal"),
            ("\U0001F198 Asking for advice", r"what should i|kya karu|\bhelp\b|any (idea|suggestion)|\badvice\b", "brown"),
        ]),
    "family": dict(
        emoji="\U0001F3E0", label="Family", desc="Family group, your mum, your dad, siblings\u2026",
        titles=dict(talk="Who keeps in touch.", first="Who starts the conversation.", rhythm="Family time.",
                    themed="Family things.", awards="The family awards."),
        topics=[
            ("\U0001F35B Food & chai", r"khana|khaana|khaya|nashta|\b(dinner|lunch|breakfast|chai|roti|tiffin)\b", "brown"),
            ("\U0001F917 Care & check-ins", r"take care|dhyan|dhyaan|careful|reach(ed)?\b|pahunch|\bsafe\b", "green"),
            ("\U0001F64F Blessings & greetings", r"good ?morning|suprabhat|namaste|ram ram|blessing|shubh|\U0001F64F", "amber"),
            ("\U0001F4DE Calls", r"\bcall\b|\bphone\b|\bring\b", "blue"),
            ("\U0001F3E0 Where are you?", r"kahan|kaha ho|where are you|kab aa|\bghar\b|\bhome\b", "purple"),
            ("\u2764\uFE0F Love", r"love (you|u)\b|miss (you|u)\b|\u2764", "maroon"),
        ]),
    "work": dict(
        emoji="\U0001F4CB", label="Work / team", desc="Project chat, startup team, colleagues, work friends\u2026",
        titles=dict(talk="Who drives the chat.", first="Who kicks things off.", rhythm="The work rhythm.",
                    themed="Work talk.", awards="The standouts."),
        topics=[
            ("\U0001F4C5 Meetings & calls", r"\b(meeting|standup|sync|zoom|teams|call|meet)\b", "blue"),
            ("\u23F0 Deadlines & urgency", r"\b(deadline|urgent|asap|eod|due|priority|blocker)\b", "maroon"),
            ("\U0001F64F Thank-yous", r"\b(thanks|thank you|thx|tysm|shukriya|dhanyawad)\b|\U0001F64F", "green"),
            ("\u2705 Acknowledgements", r"\b(done|noted|okay|ok|sure|will do|on it|got it)\b", "teal"),
            ("\U0001F4CE Docs & files", r"\b(doc|docs|sheet|pdf|ppt|report|file|attached|figma|jira)\b", "olive"),
        ]),
    "other": dict(
        emoji="\U0001F937", label="Other", desc="Roommates, neighbors, or anything else\u2026",
        titles={}, topics=[]),
}


def kw_counts(df, pattern, senders):
    body = df.text.where(df.is_text, "")
    c = body.str.count("(?i)" + pattern)
    return c.groupby(df.sender).sum().reindex(senders).fillna(0)


class ChatTypeDialog(QDialog):
    def __init__(self, parent, suggested):
        super().__init__(parent)
        self.setWindowTitle("Choose chat type")
        self.setModal(True)
        self.setMinimumWidth(540)
        self.choice = suggested
        v = QVBoxLayout(self)
        v.setContentsMargins(22, 20, 22, 20)
        v.setSpacing(10)
        v.addWidget(_lbl("What type of chat would you like LocalChat to analyze?",
                         "font-size:19px;font-weight:700;color:#ececec;", True))
        v.addWidget(_lbl("The report adapts to this \u2013 romantic chats get different insights than work chats.",
                         "font-size:12px;color:#8d93a6;", True))
        v.addSpacing(6)
        for key, cfg in CHAT_TYPES.items():
            b = QPushButton()
            b.setObjectName("typecard")
            b.setProperty("suggested", key == suggested)
            b.setMinimumHeight(66)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            h = QHBoxLayout(b)
            h.setContentsMargins(12, 8, 12, 8)
            icon = _lbl(cfg["emoji"], "font-size:26px;background:#2a2d3a;border-radius:10px;padding:6px;")
            icon.setFixedSize(52, 52)
            icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
            col = QVBoxLayout()
            col.setSpacing(2)
            col.addWidget(_lbl(cfg["label"] + ("   \u2022 suggested" if key == suggested else ""),
                               "font-size:12px;color:#9a9eae;background:transparent;"))
            col.addWidget(_lbl(cfg["desc"], "font-size:13px;font-weight:600;color:#ececec;background:transparent;"))
            h.addWidget(icon)
            h.addLayout(col, 1)
            for ch in b.findChildren(QLabel):
                ch.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            b.clicked.connect(lambda _, k=key: self._pick(k))
            v.addWidget(b)

    def _pick(self, key):
        self.choice = key
        self.accept()


# --------------------------------------------------------------------------- #
#  Main window
# --------------------------------------------------------------------------- #
class MainWindow(QMainWindow):
    TABLE_COLS = [
        ("Person", None), ("Messages", "messages"), ("Share %", "share"), ("Words", "words"),
        ("Avg words/msg", "avg_words"), ("Media", "media"), ("Links", "links"),
        ("Questions", "questions"), ("Emojis", "emojis"), ("Starts convo", "starts"),
        ("Median reply (min)", "reply_min"), ("Night % (12-5AM)", "night_pct"), ("Longest msg (words)", "longest"),
    ]
    METRICS = {
        "Messages": "messages", "Words": "words", "Avg words per message": "avg_words", "Media shared": "media",
        "Links": "links", "Questions asked": "questions", "Emojis used": "emojis",
        "Night-time % (12-5 AM)": "night_pct", "Longest message": "longest", "Active days": "active_days",
    }

    def __init__(self):
        super().__init__()
        self.setWindowTitle("LocalChat Analyzer \u2013 your chats never leave this computer")
        self.resize(1360, 860)
        self.setAcceptDrops(True)
        self.df_all = self.df = None
        self.colors = {}
        self.stats = None
        self.wc, self.ec = {}, {}
        self.worker = None
        self.mood_worker = None
        self.mood_engine_name = ""
        self.path = None
        self._timer = QTimer(singleShot=True, interval=250)
        self._timer.timeout.connect(self.refresh)
        self._build_menu()
        self._build_ui()
        self.statusBar().showMessage("Open a chat export, drop a file here, or try the demo chat.")

    # ----- UI construction ------------------------------------------------- #
    def _build_menu(self):
        m = self.menuBar().addMenu("&File")
        for text, fn, key in [("Open chat\u2026", self.open_dialog, "Ctrl+O"),
                              ("Load demo chat", self.load_demo, None),
                              ("Export people stats (CSV)\u2026", self.export_stats, None),
                              ("Export cleaned messages (CSV)\u2026", self.export_messages, None),
                              ("Quit", self.close, "Ctrl+Q")]:
            a = QAction(text, self)
            if key:
                a.setShortcut(key)
            a.triggered.connect(fn)
            m.addAction(a)
        h = self.menuBar().addMenu("&Help")
        a = QAction("Privacy & how to export", self)
        a.triggered.connect(self.show_help)
        h.addAction(a)

    def _build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        lay = QHBoxLayout(root)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(self._build_sidebar())
        self.stack = FlipStack()
        lay.addWidget(self.stack, 1)
        self.stack.addWidget(self._build_welcome())
        self.stack.addWidget(self._build_tabs())
        pb = QProgressBar()
        pb.setRange(0, 0)
        pb.setFixedWidth(160)
        pb.hide()
        self.progress = pb
        self.statusBar().addPermanentWidget(pb)

    def _build_sidebar(self):
        sb = QFrame()
        sb.setObjectName("sidebar")
        sb.setFixedWidth(290)
        v = QVBoxLayout(sb)
        v.setContentsMargins(16, 16, 16, 16)
        v.setSpacing(8)
        t = QLabel("\U0001F4AC LocalChat")
        t.setObjectName("h1")
        v.addWidget(t)
        s = QLabel("\U0001F512 100% offline \u2013 no uploads")
        s.setObjectName("muted")
        v.addWidget(s)
        b = QPushButton("Open chat export\u2026")
        b.setObjectName("primary")
        b.clicked.connect(self.open_dialog)
        v.addWidget(b)
        b2 = QPushButton("Try demo chat")
        b2.clicked.connect(self.load_demo)
        v.addWidget(b2)
        self.lbl_file = QLabel("No file loaded")
        self.lbl_file.setObjectName("muted")
        self.lbl_file.setWordWrap(True)
        v.addWidget(self.lbl_file)

        v.addWidget(self._sec("Chat type"))
        self.cb_type = QComboBox()
        for key, c in CHAT_TYPES.items():
            self.cb_type.addItem(f"{c['emoji']}  {c['label']}", key)
        self.cb_type.currentIndexChanged.connect(self._schedule)
        v.addWidget(self.cb_type)

        v.addWidget(self._sec("Date format (WhatsApp)"))
        self.cb_order = QComboBox()
        self.cb_order.addItems(["Auto-detect", "DD/MM/YYYY", "MM/DD/YYYY"])
        self.cb_order.currentIndexChanged.connect(self._reload)
        v.addWidget(self.cb_order)

        v.addWidget(self._sec("Date range"))
        row = QHBoxLayout()
        self.de_from, self.de_to = QDateEdit(), QDateEdit()
        for d in (self.de_from, self.de_to):
            d.setCalendarPopup(True)
            d.setDisplayFormat("dd MMM yyyy")
            d.dateChanged.connect(self._schedule)
            row.addWidget(d)
        v.addLayout(row)

        v.addWidget(self._sec("New chat after (hrs of silence)"))
        self.sp_gap = QSpinBox()
        self.sp_gap.setRange(1, 72)
        self.sp_gap.setValue(6)
        self.sp_gap.valueChanged.connect(self._schedule)
        v.addWidget(self.sp_gap)

        v.addWidget(self._sec("Participants"))
        self.lst = QListWidget()
        self.lst.itemChanged.connect(self._schedule)
        v.addWidget(self.lst, 1)
        row = QHBoxLayout()
        for txt, st in (("All", Qt.CheckState.Checked), ("None", Qt.CheckState.Unchecked)):
            bb = QPushButton(txt)
            bb.setObjectName("ghost")
            bb.clicked.connect(lambda _, s=st: self._set_all(s))
            row.addWidget(bb)
        v.addLayout(row)
        return sb

    def _sec(self, text):
        l = QLabel(text.upper())
        l.setObjectName("statCaption")
        l.setStyleSheet("margin-top:6px;")
        return l

    def _build_welcome(self):
        self.welcome = WelcomeScene(self.open_dialog, self.load_demo, self.show_help)
        return self.welcome

    def _build_tabs(self):
        self.tabs = QTabWidget()
        self.report = ReportView()
        self.report.finished.connect(lambda: self.tabs.setCurrentIndex(1))
        self.tabs.addTab(self.report, "Report")
        self.tabs.addTab(self._tab_overview(), "Overview")
        self.tabs.addTab(self._tab_activity(), "Activity")
        self.tabs.addTab(self._tab_people(), "People")
        self.tabs.addTab(self._tab_words(), "Words && Emojis")
        self.tabs.addTab(self._tab_mood(), "Mood (AI)")
        self.tabs.addTab(self._tab_search(), "Search")
        return self.tabs

    def _tab_overview(self):
        w = QWidget()
        v = QVBoxLayout(w)
        grid = QGridLayout()
        grid.setSpacing(10)
        caps = ["Messages", "Words", "Days covered", "Active days", "Messages / day",
                "Media shared", "Conversations", "Participants"]
        self.cards = {}
        for i, c in enumerate(caps):
            card = StatCard(c)
            self.cards[c] = card
            grid.addWidget(card, i // 4, i % 4)
        v.addLayout(grid)
        row = QHBoxLayout()
        self.ch_share = Chart3D("Who talks the most", 300)
        self.insights = QTextBrowser()
        self.insights.setMinimumHeight(300)
        row.addWidget(self.ch_share, 1)
        row.addWidget(self.insights, 1)
        v.addLayout(row)
        self.table = QTableWidget()
        self.table.setColumnCount(len(self.TABLE_COLS))
        self.table.setHorizontalHeaderLabels([c[0] for c in self.TABLE_COLS])
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().hide()
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.setMinimumHeight(260)
        v.addWidget(self.table)
        return scroll_page(w)

    def _tab_activity(self):
        w = QWidget()
        v = QVBoxLayout(w)
        self.cb_freq = QComboBox()
        self.cb_freq.addItems(["Daily (7-day avg)", "Weekly", "Monthly"])
        self.cb_freq.setCurrentIndex(2)
        self.cb_freq.currentIndexChanged.connect(self._update_timeline)
        self.ch_time = Chart3D("Messages over time", 300, extra=self.cb_freq)
        self.ch_hour = Chart3D("Time of day", 300)
        self.ch_heat = Chart3D("When do you chat? (weekday \u00D7 hour)", 300)
        self.ch_month = Chart3D("Messages by weekday", 260)
        v.addWidget(self.ch_time)
        r = QHBoxLayout()
        r.addWidget(self.ch_hour, 1)
        r.addWidget(self.ch_heat, 1)
        v.addLayout(r)
        v.addWidget(self.ch_month)
        return scroll_page(w)

    def _tab_people(self):
        w = QWidget()
        v = QVBoxLayout(w)
        self.cb_metric = QComboBox()
        self.cb_metric.addItems(list(self.METRICS))
        self.cb_metric.currentIndexChanged.connect(self._update_metric)
        self.ch_metric = Chart3D("Compare people", 300, extra=self.cb_metric)
        self.ch_reply = Chart3D("Median reply time (minutes)", 280)
        self.ch_start = Chart3D("Who starts the conversation?", 280)
        v.addWidget(self.ch_metric)
        r = QHBoxLayout()
        r.addWidget(self.ch_reply, 1)
        r.addWidget(self.ch_start, 1)
        v.addLayout(r)
        return scroll_page(w)

    def _tab_words(self):
        w = QWidget()
        v = QVBoxLayout(w)
        top = QHBoxLayout()
        top.addWidget(QLabel("Show for:"))
        self.cb_person = QComboBox()
        self.cb_person.currentIndexChanged.connect(self._update_words)
        top.addWidget(self.cb_person)
        top.addWidget(QLabel("Top"))
        self.sp_top = QSpinBox()
        self.sp_top.setRange(5, 50)
        self.sp_top.setValue(20)
        self.sp_top.valueChanged.connect(self._update_words)
        top.addWidget(self.sp_top)
        top.addStretch()
        v.addLayout(top)
        r = QHBoxLayout()
        self.ch_words = Chart3D("Most used words", 520)
        r.addWidget(self.ch_words, 3)
        col = QVBoxLayout()
        self.emoji_table = QTableWidget(0, 2)
        self.emoji_table.setHorizontalHeaderLabels(["Emoji", "Count"])
        self.emoji_table.verticalHeader().hide()
        self.emoji_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.emoji_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.emoji_table.setStyleSheet("QTableWidget{font-size:18px;}")
        col.addWidget(QLabel("Top emojis"))
        col.addWidget(self.emoji_table)
        r.addLayout(col, 1)
        v.addLayout(r)
        v.addWidget(QLabel("Signature words (used much more by this person than by others)"))
        self.sig = QTextBrowser()
        self.sig.setMinimumHeight(140)
        v.addWidget(self.sig)
        return scroll_page(w)

    def _tab_mood(self):
        w = QWidget()
        v = QVBoxLayout(w)
        box = QFrame()
        box.setObjectName("card")
        g = QGridLayout(box)
        g.setContentsMargins(14, 12, 14, 12)
        g.setSpacing(8)
        g.addWidget(QLabel("Engine"), 0, 0)
        self.cb_engine = QComboBox()
        self.cb_engine.addItems(["Built-in \u2013 instant, English + Hinglish + emoji",
                                 "Local AI model \u2013 multilingual (pip install transformers torch)",
                                 "Local LLM via Ollama \u2013 best for Hinglish & context (slow)"])
        self.cb_engine.currentIndexChanged.connect(self._engine_changed)
        g.addWidget(self.cb_engine, 0, 1, 1, 3)
        self.lbl_model = QLabel("Model")
        self.ed_model = QLineEdit()
        self.lbl_max = QLabel("Max messages")
        self.sp_maxmsg = QSpinBox()
        self.sp_maxmsg.setRange(200, 100000)
        self.sp_maxmsg.setSingleStep(500)
        self.sp_maxmsg.setValue(3000)
        g.addWidget(self.lbl_model, 1, 0)
        g.addWidget(self.ed_model, 1, 1)
        g.addWidget(self.lbl_max, 1, 2)
        g.addWidget(self.sp_maxmsg, 1, 3)
        self.btn_mood = QPushButton("Analyze mood")
        self.btn_mood.setObjectName("primary")
        self.btn_mood.clicked.connect(self.run_mood)
        g.addWidget(self.btn_mood, 0, 4, 2, 1)
        note = QLabel("\U0001F512 Every engine runs on this computer \u2013 your messages are never sent to any server. "
                      "AI engines look at a sample of up to \u201CMax messages\u201D spread across the whole chat.")
        note.setObjectName("muted")
        note.setWordWrap(True)
        g.addWidget(note, 2, 0, 1, 5)
        g.setColumnStretch(1, 1)
        v.addWidget(box)
        self.lbl_mood_status = QLabel("")
        self.lbl_mood_status.setObjectName("muted")
        v.addWidget(self.lbl_mood_status)

        self.mood_stack = QStackedWidget()
        ph = QLabel("Pick an engine and press  \u201CAnalyze mood\u201D  to see who was happy, angry or sad \u2013 and when.")
        ph.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ph.setObjectName("muted")
        self.mood_stack.addWidget(ph)
        body = QWidget()
        bv = QVBoxLayout(body)
        self.mood_insights = QTextBrowser()
        self.mood_insights.setMinimumHeight(190)
        bv.addWidget(self.mood_insights)
        self.cb_mfreq = QComboBox()
        self.cb_mfreq.addItems(["Daily", "Weekly", "Monthly"])
        self.cb_mfreq.setCurrentIndex(1)
        self.cb_mfreq.currentIndexChanged.connect(self._update_mood)
        self.ch_mood_time = Chart3D("Mood over time (above 0 = happier, below 0 = angrier / sadder)", 300, extra=self.cb_mfreq)
        self.ch_mood_mix = Chart3D("Emotion mix per person", 280)
        bv.addWidget(self.ch_mood_time)
        bv.addWidget(self.ch_mood_mix)
        self.tbl_tense = self._mood_table()
        self.tbl_happy = self._mood_table()
        bv.addWidget(QLabel("\U0001F621  Most tense conversations"))
        bv.addWidget(self.tbl_tense)
        bv.addWidget(QLabel("\U0001F604  Happiest conversations"))
        bv.addWidget(self.tbl_happy)
        self.mood_stack.addWidget(scroll_page(body))
        v.addWidget(self.mood_stack, 1)
        self._engine_changed()
        return w

    def _mood_table(self):
        t = QTableWidget(0, 5)
        t.setHorizontalHeaderLabels(["When", "Messages", "Person", "Avg mood", "Key message"])
        t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        t.verticalHeader().hide()
        t.setAlternatingRowColors(True)
        t.setWordWrap(True)
        t.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        t.setColumnWidth(0, 150)
        t.setColumnWidth(1, 80)
        t.setColumnWidth(2, 130)
        t.setColumnWidth(3, 80)
        t.setMinimumHeight(230)
        return t

    def _engine_changed(self, *_):
        i = self.cb_engine.currentIndex()
        for w in (self.lbl_model, self.ed_model, self.lbl_max, self.sp_maxmsg):
            w.setVisible(i != 0)
        self.ed_model.setText(["", TRANSFORMER_MODEL, "qwen2.5:7b"][i])
        self.sp_maxmsg.setValue(3000 if i == 1 else 1000)

    def run_mood(self):
        if self.df_all is None or (getattr(self, "mood_worker", None) and self.mood_worker.isRunning()):
            return
        self.btn_mood.setEnabled(False)
        self.lbl_mood_status.setText("Analysing\u2026")
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.show()
        self.mood_worker = MoodWorker(self.df_all[["text", "is_text", "words"]].copy(), self.cb_engine.currentIndex(),
                                      self.ed_model.text().strip(), self.sp_maxmsg.value())
        self.mood_worker.progress.connect(lambda a, b: (self.progress.setRange(0, max(b, 1)), self.progress.setValue(a)))
        self.mood_worker.done.connect(self._mood_done)
        self.mood_worker.failed.connect(self._mood_failed)
        self.mood_worker.start()

    def _mood_failed(self, msg):
        self.btn_mood.setEnabled(True)
        self.progress.hide()
        self.progress.setRange(0, 0)
        self.lbl_mood_status.setText("Mood analysis failed.")
        QMessageBox.warning(self, "Mood analysis", msg)

    def _mood_done(self, res, name):
        self.btn_mood.setEnabled(True)
        self.progress.hide()
        self.progress.setRange(0, 0)
        d = self.df_all
        d["mood"] = res["mood"].reindex(d.index)
        d["valence"] = res["valence"].reindex(d.index).astype(float)
        d["intensity"] = res["intensity"].reindex(d.index).astype(float)
        self.mood_engine_name = name
        self.lbl_mood_status.setText(f"Done \u2013 {len(res):,} messages analysed with the {name} engine.")
        self.refresh()

    def _update_mood(self, *_):
        df = self.df
        has = df is not None and "valence" in df.columns and df["valence"].notna().any()
        self.mood_stack.setCurrentIndex(1 if has else 0)
        if not has:
            return
        ms = mood_summary(df, self.sp_gap.value())
        mix = ms["mix"]
        # ---- insights ----
        rows = []
        for p_, r in mix.iterrows():
            nn = r.drop("neutral")
            dom = nn.idxmax() if nn.max() > 0 else "neutral"
            line = (f"<b style='color:{self._col(p_)}'>{p_}</b> \u2013 mostly {MOOD_EMOJI[dom]} <b>{dom}</b> when not neutral "
                    f"({r['happy'] + r['loving']:.0f}% happy/loving, {r['angry'] + r['upset']:.0f}% angry/upset, "
                    f"{r['sad'] + r['anxious']:.0f}% sad/anxious)")
            d = ms["days"].get(p_)
            if d:
                line += (f"<br>&nbsp;&nbsp;\U0001F621 toughest day <b>{d['worst'][0]:%d %b %Y}</b> (mood {d['worst'][1]:+.2f}) \u00B7 "
                         f"\U0001F604 best day <b>{d['best'][0]:%d %b %Y}</b> ({d['best'][1]:+.2f})")
            rows.append(f"<li style='margin-bottom:8px'>{line}</li>")
        extra = ""
        if ms["tense"]:
            c = ms["tense"][0]
            extra += (f"<p>\U0001F525 <b>Most tense conversation:</b> {c['when']:%d %b %Y} \u2013 {c['angriest']} seemed the most upset "
                      f"({c['n']} messages).</p>")
        if ms["happy"]:
            c = ms["happy"][0]
            extra += f"<p>\u2728 <b>Happiest conversation:</b> {c['when']:%d %b %Y} ({c['n']} messages).</p>"
        self.mood_insights.setHtml(f"<ul style='margin-left:-18px'>{''.join(rows)}</ul>{extra}")

        # ---- timeline ----
        freq = ["D", "W", "MS"][self.cb_mfreq.currentIndex()]
        minn = 2 if freq == "D" else 3
        a = df[df.valence.notna()]

        grp = a.groupby([pd.Grouper(key="ts", freq=freq), "sender_c"]).valence
        m, n = grp.mean().unstack(), grp.size().unstack()
        m = m.where(n >= minn)
        names = list(n.sum().sort_values(ascending=False).index[:MAX_CHART_PEOPLE])
        idx = pd.date_range(m.index.min(), m.index.max(), freq=freq)
        m = m.reindex(idx)
        peak = float(np.nanmax(np.abs(m[names].values))) if m[names].notna().any().any() else 1.0
        lim = max(0.3, min(1.0, math.ceil(peak * 10) / 10))
        mfmt = "%b %y" if freq == "MS" else "%d %b %y"
        self.ch_mood_time.show_area(
            xs=list(idx), series=[(c, self._col(c), m[c].values) for c in names],
            xfmt=lambda x: x.strftime(mfmt), ymin=-lim, ymax=lim, zero_line=True,
            fmt=lambda v: f"{v:+.2f}", ylabels=[(-lim, f"sadder {-lim:.1f}"), (0.0, "0"), (lim, f"happier +{lim:.1f}")])
        mm = mix.head(MAX_CHART_PEOPLE)
        rows = [[(float(mm.loc[p_, k]), MOOD_COLORS[k], k) for k in MOOD_ORDER if k in mm and mm.loc[p_, k] > 0]
                for p_ in mm.index]
        self.ch_mood_mix.show_hbars(labels=list(mm.index), rows=rows, pct=True)

        # ---- tables ----
        def fill(tbl, lst, who, side):
            tbl.setRowCount(len(lst))
            for i, c in enumerate(lst):
                m = c[side]
                vals = [f"{c['when']:%d %b %Y, %I:%M %p}", str(c["n"]), c[who], f"{c['mean']:+.2f}", m.text]
                for j, val in enumerate(vals):
                    it = QTableWidgetItem(val)
                    if j == 2:
                        it.setForeground(QBrush(QColor(self._col(val))))
                    tbl.setItem(i, j, it)
            tbl.resizeRowsToContents()
        fill(self.tbl_tense, ms["tense"], "angriest", "worst")
        fill(self.tbl_happy, ms["happy"], "happiest", "best")

    def _tab_search(self):
        w = QWidget()
        v = QVBoxLayout(w)
        row = QHBoxLayout()
        self.ed_search = QLineEdit()
        self.ed_search.setPlaceholderText("Search a word or phrase (e.g. 'love', 'sorry', 'haha')\u2026")
        self.ed_search.returnPressed.connect(self.do_search)
        self.chk_word = QCheckBox("Whole word")
        b = QPushButton("Search")
        b.setObjectName("primary")
        b.clicked.connect(self.do_search)
        row.addWidget(self.ed_search, 1)
        row.addWidget(self.chk_word)
        row.addWidget(b)
        v.addLayout(row)
        self.lbl_search = QLabel("")
        self.lbl_search.setObjectName("muted")
        v.addWidget(self.lbl_search)
        r = QHBoxLayout()
        self.ch_s_person = Chart3D("Who says it", 240)
        self.ch_s_time = Chart3D("When it was said (per month)", 240)
        r.addWidget(self.ch_s_person, 1)
        r.addWidget(self.ch_s_time, 2)
        v.addLayout(r)
        self.res = QTableWidget(0, 3)
        self.res.setHorizontalHeaderLabels(["When", "Who", "Message"])
        self.res.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.res.verticalHeader().hide()
        self.res.setAlternatingRowColors(True)
        self.res.setWordWrap(True)
        self.res.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.res.setColumnWidth(0, 200)
        self.res.setColumnWidth(1, 130)
        self.res.setMinimumHeight(300)
        v.addWidget(self.res, 1)
        return w

    # ----- loading --------------------------------------------------------- #
    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            self.welcome.set_drag(True)
            e.acceptProposedAction()

    def dragLeaveEvent(self, e):
        self.welcome.set_drag(False)

    def dropEvent(self, e):
        self.welcome.set_drag(False)
        urls = e.mimeData().urls()
        if urls:
            self.load(urls[0].toLocalFile())

    def open_dialog(self):
        p, _ = QFileDialog.getOpenFileName(self, "Open chat export", "",
                                           "Chat exports (*.txt *.zip *.json);;All files (*)")
        if p:
            self.load(p)

    def load_demo(self):
        f = tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8")
        f.write(make_demo_chat())
        f.close()
        self.load(f.name, label="Demo chat (synthetic data)")

    def _reload(self):
        if self.path:
            self.load(self.path, label=self.lbl_file.text())

    def load(self, path, label=None):
        if self.worker and self.worker.isRunning():
            return
        self.path = path
        self._label = label or path.replace("\\", "/").rsplit("/", 1)[-1]
        order = ["auto", "dmy", "mdy"][self.cb_order.currentIndex()]
        self.progress.show()
        self.statusBar().showMessage("Reading and analysing\u2026")
        self.worker = LoadWorker(path, order)
        self.worker.done.connect(self._loaded)
        self.worker.failed.connect(self._failed)
        self.worker.start()

    def _failed(self, msg):
        self.progress.hide()
        self.statusBar().showMessage("Failed to load file.")
        QMessageBox.warning(self, "Couldn't read that file", msg)

    def _loaded(self, df, path):
        self.progress.hide()
        self.df_all = df
        order = df.sender.value_counts().index.tolist()
        self.colors = {s: PALETTE[i % len(PALETTE)] for i, s in enumerate(order)}
        self.colors["Others"] = OTHERS_COLOR
        self.lbl_file.setText(self._label)
        for w in (self.lst, self.de_from, self.de_to, self.cb_person):
            w.blockSignals(True)
        self.lst.clear()
        for s in order:
            it = QListWidgetItem(f"{s}  ({(df.sender == s).sum():,})")
            it.setData(Qt.ItemDataRole.UserRole, s)
            it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            it.setCheckState(Qt.CheckState.Checked)
            it.setForeground(QBrush(QColor(self.colors[s])))
            self.lst.addItem(it)
        lo, hi = df.ts.min().date(), df.ts.max().date()
        for d in (self.de_from, self.de_to):
            d.setDateRange(QDate(lo.year, lo.month, lo.day), QDate(hi.year, hi.month, hi.day))
        self.de_from.setDate(QDate(lo.year, lo.month, lo.day))
        self.de_to.setDate(QDate(hi.year, hi.month, hi.day))
        self.cb_person.clear()
        self.cb_person.addItem("Everyone")
        self.cb_person.addItems(order)
        for w in (self.lst, self.de_from, self.de_to, self.cb_person):
            w.blockSignals(False)
        key = self.ask_chat_type(len(order))
        self.cb_type.blockSignals(True)
        self.cb_type.setCurrentIndex(max(0, self.cb_type.findData(key)))
        self.cb_type.blockSignals(False)
        self.tabs.setCurrentIndex(0)
        self.report.stack.setCurrentIndex(0)
        self.lbl_mood_status.setText("")
        self.refresh()
        self.stack.flip_to(1, 1)
        kind = "group chat" if len(order) > 2 else "1-to-1 chat"
        self.statusBar().showMessage(
            f"Loaded {len(df):,} messages from {len(order)} people ({kind}). All processing happened locally.")

    def ask_chat_type(self, n_people):
        suggested = "friends_group" if n_people > 2 else "any_friend"
        dlg = ChatTypeDialog(self, suggested)
        dlg.exec()
        return dlg.choice

    # ----- filtering / refresh --------------------------------------------- #
    def _set_all(self, state):
        self.lst.blockSignals(True)
        for i in range(self.lst.count()):
            self.lst.item(i).setCheckState(state)
        self.lst.blockSignals(False)
        self._schedule()

    def _schedule(self, *_):
        if self.df_all is not None:
            self._timer.start()

    def selected_senders(self):
        return [self.lst.item(i).data(Qt.ItemDataRole.UserRole)
                for i in range(self.lst.count()) if self.lst.item(i).checkState() == Qt.CheckState.Checked]

    def refresh(self):
        if self.df_all is None:
            return
        d0, d1 = self.de_from.date().toPyDate(), self.de_to.date().toPyDate()
        df = self.df_all
        mask = (df.date >= pd.Timestamp(d0)) & (df.date <= pd.Timestamp(d1)) & df.sender.isin(self.selected_senders())
        df = df[mask].copy()
        if df.empty:
            self.df = None
            self.statusBar().showMessage("No messages match the current filters.")
            for c in (self.ch_share, self.ch_time, self.ch_hour, self.ch_heat, self.ch_month, self.ch_metric,
                      self.ch_reply, self.ch_start, self.ch_words, self.ch_s_person, self.ch_s_time):
                c.empty("No messages match the filters")
            self.table.setRowCount(0)
            return
        top = df.sender.value_counts().index[:MAX_CHART_PEOPLE]
        df["sender_c"] = df.sender.where(df.sender.isin(top), "Others")
        self.df = df
        self.ov, self.stats = compute_stats(df, self.sp_gap.value())
        self.wc, self.ec = {}, {}
        for s, g in df.groupby("sender"):
            self.wc[s] = Counter(itertools.chain.from_iterable(g.tokens))
            self.ec[s] = Counter(itertools.chain.from_iterable(g.emojis))
        self.report.build(df, self.ov, self.stats, self.wc, self.ec, self.colors, self.sp_gap.value(),
                          self.cb_type.currentData())
        self._update_overview()
        self._update_timeline()
        self._update_activity()
        self._update_metric()
        self._update_people()
        self._update_words()
        self._update_mood()
        if self.ed_search.text().strip():
            self.do_search()

    # ----- tab updates ----------------------------------------------------- #
    def _col(self, name):
        return self.colors.get(name, OTHERS_COLOR)

    def _update_overview(self):
        o, t = self.ov, self.stats
        c = self.cards
        c["Messages"].set(f"{o['total']:,}")
        c["Words"].set(f"{o['words']:,}")
        c["Days covered"].set(f"{o['span']:,}")
        c["Active days"].set(f"{o['active_days']:,}")
        c["Messages / day"].set(f"{o['per_day']:.1f}")
        c["Media shared"].set(f"{o['media']:,}")
        c["Conversations"].set(f"{o['conversations']:,}")
        c["Participants"].set(o["people"])

        s = self.df.sender_c.value_counts()
        self.ch_share.show_donut(names=[str(n) for n in s.index], values=list(s.values),
                                 colors=[self._col(n) for n in s.index],
                                 center=(f"{o['total']:,}", "messages"))
        self.insights.setHtml(build_insights(self.df, o, t, self.ec))
        self._fill_table(t)

    def _fill_table(self, t):
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(t))
        for r, (name, row) in enumerate(t.iterrows()):
            it = QTableWidgetItem(name)
            it.setForeground(QBrush(QColor(self._col(name))))
            self.table.setItem(r, 0, it)
            for c, (_, key) in enumerate(self.TABLE_COLS[1:], start=1):
                v = row[key]
                it = QTableWidgetItem()
                if pd.isna(v):
                    it.setData(Qt.ItemDataRole.DisplayRole, "-")
                elif key in ("share", "avg_words", "night_pct", "reply_min"):
                    it.setData(Qt.ItemDataRole.DisplayRole, round(float(v), 1))
                else:
                    it.setData(Qt.ItemDataRole.DisplayRole, int(v))
                it.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.table.setItem(r, c, it)
        self.table.setSortingEnabled(True)
        self.table.resizeColumnsToContents()
        for c in range(self.table.columnCount()):
            self.table.setColumnWidth(c, self.table.columnWidth(c) + 18)

    def _update_timeline(self, *_):
        if self.df is None:
            return
        freq, label = [("D", "daily"), ("W", "weekly"), ("MS", "monthly")][self.cb_freq.currentIndex()]
        daily = freq == "D"

        g = self.df.groupby([pd.Grouper(key="ts", freq=freq), "sender_c"]).size().unstack(fill_value=0)
        g = g.reindex(pd.date_range(g.index.min(), g.index.max(), freq=freq), fill_value=0)
        if daily:
            g = g.rolling(7, min_periods=1).mean()
        cols = list(g.sum().sort_values(ascending=False).index)
        dfmt = "%b %y" if freq == "MS" else "%d %b %y"
        self.ch_time.show_area(xs=list(g.index), series=[(c, self._col(c), g[c].values) for c in cols],
                               xfmt=lambda x: x.strftime(dfmt),
                               fmt=(lambda v: f"{v:,.1f} / day") if daily else (lambda v: f"{v:,.0f}"))

    def _update_activity(self):
        df = self.df

        wk = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        g = df.groupby(["hour", "sender_c"]).size().unstack(fill_value=0).reindex(range(24), fill_value=0)
        cols = list(g.sum().sort_values(ascending=False).index)
        self.ch_hour.show_bars(cols=[hour_label(h) for h in range(24)], rows=[""],
                               series=[(c, self._col(c)) for c in cols],
                               vals=np.stack([g[c].values for c in cols], axis=1)[None])
        m = df.groupby(["weekday", "hour"]).size().unstack(fill_value=0).reindex(
            index=range(7), columns=range(24), fill_value=0)
        self.ch_heat.show_bars(cols=[hour_label(h) for h in range(24)], rows=wk,
                               series=[("messages", ACCENT)], vals=m.values[:, :, None], heat=True)
        g = df.groupby(["weekday", "sender_c"]).size().unstack(fill_value=0).reindex(range(7), fill_value=0)
        cols = list(g.sum().sort_values(ascending=False).index)
        self.ch_month.show_bars(cols=wk, rows=[""], series=[(c, self._col(c)) for c in cols],
                                vals=np.stack([g[c].values for c in cols], axis=1)[None])

    def _update_metric(self, *_):
        if self.df is None:
            return
        label = self.cb_metric.currentText()
        key = self.METRICS[label]
        t = self.stats[key].sort_values(ascending=False).head(15)
        is_f = key in ("avg_words", "night_pct")
        self.ch_metric.show_hbars(
            labels=list(t.index), rows=rows_of(t.values, [self._col(n) for n in t.index]),
            fmt=(lambda v: f"{v:.1f}") if is_f else (lambda v: f"{v:,.0f}"))

    def _update_people(self):
        t = self.stats
        r = t.reply_min.dropna().sort_values().head(15)
        if len(r):
            self.ch_reply.show_hbars(labels=list(r.index), rows=rows_of(r.values, [self._col(n) for n in r.index]),
                                     fmt=fmt_dur)
        else:
            self.ch_reply.empty("Need at least two people to measure replies")
        s = t.starts.sort_values(ascending=False).head(15)
        self.ch_start.show_hbars(labels=list(s.index), rows=rows_of(s.values, [self._col(n) for n in s.index]))

    def _update_words(self, *_):
        if self.df is None or self.cb_person.currentText() == "":
            return
        who = self.cb_person.currentText()
        if who == "Everyone":
            wc, ec = Counter(), Counter()
            for s in self.wc:
                wc.update(self.wc[s])
                ec.update(self.ec[s])
            color = ACCENT
        else:
            wc, ec, color = self.wc.get(who, Counter()), self.ec.get(who, Counter()), self._col(who)
        words = wc.most_common(self.sp_top.value())
        if words:
            self.ch_words.show_hbars(labels=[w for w, _ in words],
                                     rows=rows_of([c for _, c in words], [color] * len(words)))
        else:
            self.ch_words.empty("No words")
        em = ec.most_common(30)
        self.emoji_table.setRowCount(len(em))
        for i, (e, c) in enumerate(em):
            a = QTableWidgetItem(e)
            a.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            b = QTableWidgetItem(f"{c:,}")
            b.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.emoji_table.setItem(i, 0, a)
            self.emoji_table.setItem(i, 1, b)
        sig = signature_words(self.wc)
        if sig:
            html = "".join(f"<p><b style='color:{self._col(p)}'>{p}</b>: {', '.join(ws)}</p>" for p, ws in sig.items())
        else:
            html = "<p style='color:#8d93a6'>Not enough text to find signature words.</p>"
        self.sig.setHtml(html)

    # ----- search ---------------------------------------------------------- #
    def do_search(self):
        if self.df is None:
            return
        q = self.ed_search.text().strip()
        if not q:
            return
        pat = re.escape(q)
        if self.chk_word.isChecked():
            pat = rf"(?<!\w){pat}(?!\w)"
        d = self.df[self.df.is_text & self.df.text.str.contains(pat, case=False, regex=True)]
        total_occ = int(self.df.text.where(self.df.is_text, "").str.count(f"(?i){pat}").sum())
        self.lbl_search.setText(f"{len(d):,} messages contain \u201c{q}\u201d  \u2022  {total_occ:,} total mentions")
        if d.empty:
            self.ch_s_person.empty("No matches")
            self.ch_s_time.empty("No matches")
            self.res.setRowCount(0)
            return
        c = d.sender_c.value_counts()
        self.ch_s_person.show_hbars(labels=list(c.index), rows=rows_of(c.values, [self._col(n) for n in c.index]))

        g = d.groupby([pd.Grouper(key="ts", freq="MS"), "sender_c"]).size().unstack(fill_value=0)
        g = g.reindex(pd.date_range(g.index.min(), g.index.max(), freq="MS"), fill_value=0)
        cols = list(g.sum().sort_values(ascending=False).index)
        self.ch_s_time.show_bars(cols=[f"{i:%b %y}" for i in g.index], rows=[""],
                                 series=[(c, self._col(c)) for c in cols],
                                 vals=np.stack([g[c].values for c in cols], axis=1)[None])

        shown = d.head(1000)
        self.res.setRowCount(len(shown))
        for i, (_, r) in enumerate(shown.iterrows()):
            self.res.setItem(i, 0, QTableWidgetItem(f"{r.ts:%d %b %Y, %I:%M %p}"))
            who = QTableWidgetItem(r.sender)
            who.setForeground(QBrush(QColor(self._col(r.sender))))
            self.res.setItem(i, 1, who)
            self.res.setItem(i, 2, QTableWidgetItem(r.text))
        self.res.resizeRowsToContents()

    # ----- export / help --------------------------------------------------- #
    def export_stats(self):
        if self.stats is None:
            return
        p, _ = QFileDialog.getSaveFileName(self, "Export people stats", "people_stats.csv", "CSV (*.csv)")
        if p:
            self.stats.to_csv(p)

    def export_messages(self):
        if self.df is None:
            return
        p, _ = QFileDialog.getSaveFileName(self, "Export cleaned messages", "messages.csv", "CSV (*.csv)")
        if p:
            self.df[["ts", "sender", "kind", "text"]].to_csv(p, index=False)

    def show_help(self):
        box = QMessageBox(self)
        box.setWindowTitle("Privacy & how to export")
        box.setText(HELP_HTML)
        box.exec()


HELP_HTML = """
<h3>\U0001F512 Privacy</h3>
<p>This app has no network code. Your chat is read from disk, analysed in memory on this computer,
and never sent anywhere.</p>
<h3>Chat type</h3>
<p>After loading, pick what kind of chat it is (romantic, friends, family, work…). The report then shows insights that fit it. You can change it any time from the sidebar.</p>
<h3>How to export</h3>
<p><b>WhatsApp:</b> open the chat \u2192 \u22EE / chat name \u2192 <i>Export chat</i> \u2192 <i>Without media</i>.
Works for both 1-to-1 and group chats. Load the .txt (or the .zip) here.</p>
<p><b>Telegram:</b> Desktop app \u2192 chat menu \u2192 <i>Export chat history</i> \u2192 format <i>JSON</i>.
Load <code>result.json</code>.</p>
<p><b>Tip:</b> if days/months look swapped, change <i>Date format</i> in the sidebar.</p>
"""


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(QSS)
    w = MainWindow()
    w.show()
    if len(sys.argv) > 1:
        w.load(sys.argv[1])
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
