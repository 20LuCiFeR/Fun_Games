"""
Bluff (also known as Cheat / BS) - vs CPU bots or with friends over the network - PyQt5

How to play:
 * One or more standard 52-card decks (1-4) are shuffled and dealt to everyone.
   1 deck = 4 cards of every rank, 2 decks = 8, and so on.
 * On your turn, select cards from your hand, choose which rank you CLAIM they are, and
   press Play.  The cards go face-down onto the pile.  You may lie: put down two Kings and
   two 2s and claim "4 Kings".
 * Only the player whose turn is NEXT may call "Bluff!" on the previous play:
     - if the cards were NOT all the claimed rank (it was a lie), the liar picks up the whole pile;
     - if the claim was true, the player who called Bluff picks up the whole pile.
   Whoever picks up the pile starts the next round.  If the next player doesn't call Bluff,
   they simply play their own cards.
 * The first player to get rid of all their cards wins.  (If someone plays their last cards and
   the next player doesn't call Bluff, they win.)
 * There is no time limit for people.  Bots move on their own after a 2-second pause.

Rank rule (chosen by whoever starts the game):
 * Free choice  : you can claim any rank on each turn.
 * Classic order: the claimed rank is forced and goes A, 2, 3 ... K, A, 2 ... each turn.

Game modes:
 * Play vs CPU : you + CPU bots.
 * Host Game   : you decide how many people play (and decks / rank rule).  Friends on the same
                 WiFi / network choose "Join Game" and type your IP (shown in your window).
                 Cards are dealt only when every seat is filled.  Each player only ever
                 sees their own cards.
 * Join Game   : enter the host's IP.

If a player gets disconnected during a network game, the game pauses for up to 1 minute while
their program keeps trying to reconnect (they get their own seat and cards back).  If they do not
return in time they are out: their cards are dealt to the remaining players.  When only 2 players
are left, the game ends after 30 more plays and whoever holds the FEWEST cards wins (equal = draw).
If only 1 player is left, that player wins.

Controls (3D table):
 * Click a card to select it (click again for more copies of a stacked card).
   Right-click / Shift+click selects every card of that rank.
 * Pick the rank you CLAIM with the gold chips, then press Play (or Enter).
   B = Bluff, Esc = clear selection.   Mouse wheel over the right panel scrolls the play log.

Install:  fully automatic.  Needs only Python 3.8+ (and internet the first time).  If PyQt5 is
          missing the script installs it itself: normal pip -> repairs pip if it is missing -> falls
          back to a private environment in your home folder (~/.bluff_3d_env) when the system Python
          is locked down.  On Linux it also checks for missing system libraries and offers to install
          them.  Problems are shown in a pop-up window, so nothing just flashes closed.
Run:      python bluff_3d.py      (Windows: double-click it, or "py bluff_3d.py")
"""

import json
import math
import os
import random
import secrets
import shutil
import subprocess
import sys
import time
from collections import Counter


# ====================================================================== bootstrap
# Everything below runs BEFORE PyQt5 is imported.  It makes the script work on a fresh computer.
MIN_PYTHON = (3, 8)
_LINUX_APT_PACKAGES = [
    "libgl1", "libegl1", "libglib2.0-0", "libfontconfig1", "libdbus-1-3", "libxkbcommon0",
    "libxkbcommon-x11-0", "libxcb-icccm4", "libxcb-image0", "libxcb-keysyms1", "libxcb-randr0",
    "libxcb-render-util0", "libxcb-shape0", "libxcb-xinerama0", "libxcb-xkb1",
]


def _fatal(message):
    """Show a problem where the person will actually see it (console AND a pop-up), then quit."""
    print("\n" + message, file=sys.stderr)
    try:                                         # pop-up for people who double-clicked the file
        import tkinter
        from tkinter import messagebox
        root = tkinter.Tk()
        root.withdraw()
        messagebox.showerror("Bluff", message)
        root.destroy()
    except Exception:
        pass
    if os.name == "nt":                          # keep a double-clicked console window open
        try:
            input("\nPress Enter to close...")
        except Exception:
            pass
    sys.exit(1)


def _run(cmd, **kw):
    try:
        return subprocess.call(cmd, **kw) == 0
    except (OSError, ValueError):
        return False


def _venv_dir():
    return os.path.join(os.path.expanduser("~"), ".bluff_3d_env")


def _venv_python():
    sub = ("Scripts", "python.exe") if os.name == "nt" else ("bin", "python")
    return os.path.join(_venv_dir(), *sub)


def _venv_has_qt():
    py = _venv_python()
    return os.path.exists(py) and _run([py, "-c", "from PyQt5 import QtWidgets, QtNetwork"],
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _pip_install_here():
    """Install PyQt5 into the Python that is running us.  Returns True on success."""
    base = [sys.executable, "-m", "pip", "install", "--disable-pip-version-check", "PyQt5"]
    variants = ([], ["--user"], ["--break-system-packages"], ["--user", "--break-system-packages"])
    for round_ in range(2):
        for extra in variants:
            if _run(base[:-1] + extra + base[-1:]):
                return True
        if round_ == 0:                          # maybe pip itself is missing: repair it, try again
            print("pip did not work - trying to repair pip...")
            if not (_run([sys.executable, "-m", "ensurepip", "--upgrade"]) or
                    _run([sys.executable, "-m", "ensurepip", "--user", "--upgrade"])):
                break
    return False


def _install_in_private_venv():
    """Last resort (locked-down system Python): own little environment in the home folder."""
    print("Installing PyQt5 into a private environment: " + _venv_dir())
    if not os.path.exists(_venv_python()):
        if not _run([sys.executable, "-m", "venv", _venv_dir()]):
            return False
    if not _venv_has_qt():
        _run([_venv_python(), "-m", "pip", "install", "--disable-pip-version-check", "PyQt5"])
    return _venv_has_qt()


def _relaunch_in_private_venv():
    env = dict(os.environ, BLUFF_3D_CHILD="1")
    sys.exit(subprocess.call([_venv_python()] + sys.argv, env=env))


def _linux_fix_libs(why):
    """Linux only: a system library Qt needs is missing.  Offer to install it with apt."""
    if not sys.platform.startswith("linux"):
        return False
    is_root = hasattr(os, "geteuid") and os.geteuid() == 0
    apt = shutil.which("apt-get")
    cmd = ([] if is_root else ["sudo"]) + ["apt-get", "install", "-y"] + _LINUX_APT_PACKAGES
    print("\n" + why)
    print("Qt needs some system libraries that are not installed on this computer.")
    if apt and sys.stdin and sys.stdin.isatty():
        try:
            answer = input("Install them now with apt (it may ask for your password)? [Y/n] ").strip().lower()
        except EOFError:
            answer = "n"
        if answer in ("", "y", "yes"):
            _run((["sudo"] if not is_root else []) + ["apt-get", "update"])    # refresh the package list
            return _run(cmd)
    print("To fix it yourself run:\n   " + " ".join(cmd) +
          "\n(other distributions: install the xcb / OpenGL / fontconfig packages for Qt5)")
    return False


def _import_qt():
    try:
        from PyQt5 import QtCore, QtGui, QtNetwork, QtWidgets  # noqa: F401
        return None
    except ImportError as e:
        return e


def _ensure_pyqt5():
    """Make sure PyQt5 can be imported, installing whatever is needed.  Never leaves a silent failure."""
    if sys.version_info < MIN_PYTHON:
        _fatal("Bluff needs Python %d.%d or newer (this is %d.%d).\nPlease install a newer Python "
               "from https://www.python.org/downloads/" % (MIN_PYTHON + sys.version_info[:2]))
    try:
        import PyQt5  # noqa: F401
        have_pkg = True
    except ImportError:
        have_pkg = False

    if have_pkg:
        err = _import_qt()
        if err is None:
            return
        # PyQt5 is installed but cannot load: almost always a missing system library on Linux
        if _linux_fix_libs("PyQt5 could not start: %s" % err) and _import_qt() is None:
            return
        _fatal("PyQt5 is installed but could not be loaded:\n%s" % err)

    if os.environ.get("BLUFF_3D_CHILD"):
        _fatal("PyQt5 could not be installed, even in a private environment.\nCheck your internet "
               "connection and run the game again.")
    if _venv_has_qt():                           # installed earlier by this script
        _relaunch_in_private_venv()

    print("PyQt5 not found, installing it (one-time only)...")
    if _pip_install_here():
        import importlib
        import site
        importlib.invalidate_caches()
        for extra in (site.getusersitepackages(),):
            if extra not in sys.path:
                sys.path.append(extra)
        err = _import_qt()
        if err is None:
            return
        if _linux_fix_libs("PyQt5 was installed but could not start: %s" % err) and _import_qt() is None:
            return
        _fatal("PyQt5 was installed but could not be loaded:\n%s" % err)

    if _install_in_private_venv():
        _relaunch_in_private_venv()
    _fatal("Could not install PyQt5 automatically.\nCheck your internet connection, then run:\n"
           "    %s -m pip install PyQt5" % os.path.basename(sys.executable or "python"))


def _preflight_display():
    """Before opening a window: make sure there is a desktop to draw on (Linux), and Qt's X11 libraries."""
    if not sys.platform.startswith("linux") or os.environ.get("QT_QPA_PLATFORM"):
        return
    if not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
        _fatal("No desktop display found.\nRun the game from a graphical desktop session "
               "(not a plain SSH / text-only terminal).")
    try:
        import glob
        import PyQt5
        plugin = glob.glob(os.path.join(os.path.dirname(PyQt5.__file__), "Qt*", "plugins", "platforms",
                                        "libqxcb.so"))
        if plugin and shutil.which("ldd"):
            out = subprocess.run(["ldd", plugin[0]], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                 universal_newlines=True, timeout=30).stdout
            missing = sorted({ln.split()[0] for ln in out.splitlines() if "not found" in ln})
            if missing:
                if not _linux_fix_libs("Missing system libraries: " + ", ".join(missing)):
                    _fatal("Missing system libraries: " + ", ".join(missing) +
                           "\nInstall them (see the console for the command) and run the game again.")
    except SystemExit:
        raise
    except Exception:
        pass                                     # the check is only a convenience


_ensure_pyqt5()


from PyQt5.QtCore import QPointF, QRectF, Qt, QTimer
from PyQt5.QtGui import (
    QBrush, QColor, QFont, QFontMetrics, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap,
    QPolygonF, QRadialGradient, QTransform,
)
from PyQt5.QtNetwork import (
    QAbstractSocket, QHostAddress, QNetworkInterface, QTcpServer, QTcpSocket,
)
from PyQt5.QtWidgets import (
    QApplication, QCheckBox, QDialog, QGridLayout, QLabel, QLineEdit, QMessageBox, QPushButton,
    QSpinBox, QVBoxLayout, QWidget,
)


PORT = 5566
BOT_DELAY_MS = 2000          # pause before every bot move
HISTORY_VISIBLE = 4          # plays visible without scrolling
HISTORY_MAX = 60             # how many past plays can be scrolled through
WAITING = "Waiting…"
RECONNECT_S = 60             # how long a disconnected player has to come back
LIMIT_PLAYS = 30             # plays left once only 2 players remain; then fewest cards wins

SUITS = ["♠", "♥", "♦", "♣"]
RED_SUITS = {1, 2}
RANK_NAMES = {
    1: ("Ace", "Aces"), 2: ("Two", "Twos"), 3: ("Three", "Threes"), 4: ("Four", "Fours"),
    5: ("Five", "Fives"), 6: ("Six", "Sixes"), 7: ("Seven", "Sevens"), 8: ("Eight", "Eights"),
    9: ("Nine", "Nines"), 10: ("Ten", "Tens"), 11: ("Jack", "Jacks"), 12: ("Queen", "Queens"),
    13: ("King", "Kings"),
}
RANK_SHORT = {1: "A", 11: "J", 12: "Q", 13: "K"}
AVATAR_COLORS = ["#f9a825", "#1e88e5", "#8e24aa", "#00897b", "#e53935", "#6d4c41"]


def rank_short(r):
    return RANK_SHORT.get(r, str(r))


def card_str(card):
    return rank_short(card[0]) + SUITS[card[1]]


def claim_text(count, rank):
    return f"{count} {RANK_NAMES[rank][0 if count == 1 else 1]}"


def initials(name, idx):
    if name == "You":
        return "Y"
    if name.startswith("Bot "):
        return "B" + name[4:]
    if name == WAITING:
        return "?"
    return name[:1].upper() or str(idx + 1)


def avatar_style(idx, size):
    return (f"background-color: {AVATAR_COLORS[idx % len(AVATAR_COLORS)]}; color: white;"
            f"border-radius: {size // 2}px; font-weight: bold; font-size: {int(size * 0.42)}px;")


def local_ips():
    ips = []
    for a in QNetworkInterface.allAddresses():
        s = a.toString()
        if a.protocol() == QAbstractSocket.IPv4Protocol and not s.startswith("127."):
            ips.append(s)
    return ips or ["127.0.0.1"]


# ====================================================================== game rules (no UI)
class Engine:
    """All the rules of Bluff. Knows every hand; hands out a private 'view' to each player."""

    def __init__(self, names, decks, classic):
        self.names = list(names)           # seat names (None = empty seat)
        self.n = len(names)
        self.decks = decks
        self.classic = classic
        self.reset()

    def reset(self):
        self.hands = [Counter() for _ in range(self.n)]    # (rank, suit) -> copies
        self.pile = []
        self.last = None                    # {"player", "cards", "claim"}: the play that can be challenged
        self.history = []
        self.req = 1                        # rank that must be claimed (classic mode)
        self.turn = 0
        self.phase = "lobby"                # lobby | play | over
        self.winner = None
        self.abort_msg = ""
        self.win_note = ""                  # "" | forfeit | count | tie  (why the game ended)
        self.active = [True] * self.n       # False = player left for good
        self.away = {}                      # seat -> monotonic deadline to reconnect (game is paused)
        self.plays_left = None              # counts down once only 2 players remain

    def deal(self):
        deck = [(r, s) for _ in range(self.decks) for r in range(1, 14) for s in range(4)]
        random.shuffle(deck)
        self.reset()
        for i, card in enumerate(deck):
            self.hands[i % self.n][card] += 1
        self.turn = random.randrange(self.n)
        self.phase = "play"

    # ---------- helpers ----------
    def hand_size(self, p):
        return sum(self.hands[p].values())

    def rank_counts(self, p):
        c = Counter()
        for (r, _s), n in self.hands[p].items():
            c[r] += n
        return c

    def take_rank(self, p, rank, n):
        out = []
        for s in range(4):
            have = self.hands[p].get((rank, s), 0)
            out.extend([(rank, s)] * min(have, n - len(out)))
        return out

    def pending_win(self):
        return self.last is not None and self.hand_size(self.last["player"]) == 0

    def active_seats(self):
        return [i for i in range(self.n) if self.active[i]]

    def next_active(self, p):
        for step in range(1, self.n + 1):
            q = (p + step) % self.n
            if self.active[q]:
                return q
        return p

    def limit_reached(self):
        return self.plays_left is not None and self.plays_left <= 0

    def pending_end(self):
        """The last play can end the game: the player emptied their hand, or the play limit is used up."""
        return self.last is not None and (self.hand_size(self.last["player"]) == 0 or self.limit_reached())

    def _finish_by_count(self):
        act = self.active_seats()
        low = min(self.hand_size(i) for i in act)
        best = [i for i in act if self.hand_size(i) == low]
        self.phase = "over"
        self.winner = best[0] if len(best) == 1 else None
        self.win_note = "count" if len(best) == 1 else "tie"

    # ---------- actions (each returns None on success, or an error text) ----------
    def play(self, p, cards, claim):
        if self.phase != "play":
            return "The game is not running."
        if self.away:
            return "Waiting for a player to reconnect."
        if p != self.turn:
            return "It is not your turn."
        if self.pending_end():
            return "You must call Bluff or accept."
        try:
            cards = [(int(c[0]), int(c[1])) for c in cards]
            claim = int(claim)
        except (TypeError, ValueError, IndexError):
            return "Bad move."
        if not cards or not 1 <= claim <= 13:
            return "Bad move."
        if any(not (1 <= r <= 13 and 0 <= s <= 3) for r, s in cards):
            return "Bad move."
        if self.classic and claim != self.req:
            return "You must claim the required rank."
        for c, k in Counter(cards).items():
            if self.hands[p].get(c, 0) < k:
                return "You do not have those cards."
        for c in cards:
            self.hands[p][c] -= 1
            if self.hands[p][c] <= 0:
                del self.hands[p][c]
        self.pile.extend(cards)
        self.last = {"player": p, "cards": list(cards), "claim": claim}
        self.history.append({"player": p, "count": len(cards), "claim": claim, "verdict": None})
        self.turn = self.next_active(p)
        if self.plays_left is not None:
            self.plays_left -= 1
        if self.classic:
            self.req = self.req % 13 + 1
        return None

    def challenge(self, p):
        """Only the player whose turn is next may call Bluff."""
        if self.phase != "play" or self.away or p != self.turn or self.last is None:
            return "You cannot call Bluff now."
        last = self.last
        claimer = last["player"]
        truthful = all(c[0] == last["claim"] for c in last["cards"])
        loser = p if truthful else claimer
        self.history[-1].update(verdict="true" if truthful else "lie", challenger=p, taker=loser,
                                revealed=list(last["cards"]))
        for c in self.pile:
            self.hands[loser][c] += 1
        self.pile = []
        self.last = None
        if truthful and self.hand_size(claimer) == 0:
            self.winner = claimer
            self.phase = "over"
        elif self.limit_reached():
            self._finish_by_count()                 # play limit used up: fewest cards wins
        else:
            self.turn = loser                       # whoever picked up the pile starts the next round
        return None

    def accept(self, p):
        if self.phase != "play" or self.away or p != self.turn or not self.pending_end():
            return "Nothing to accept."
        if self.hand_size(self.last["player"]) == 0:
            self.winner = self.last["player"]
            self.phase = "over"
        else:
            self._finish_by_count()
        return None

    def abort(self, msg):
        self.phase = "over"
        self.winner = None
        self.abort_msg = msg

    def remove_player(self, seat):
        """A player is gone for good: deal their cards to the others and carry on without them."""
        self.away.pop(seat, None)
        if self.phase != "play" or not self.active[seat]:
            return
        self.active[seat] = False
        left = self.active_seats()
        cards = [c for c, k in self.hands[seat].items() for _ in range(k)]
        self.hands[seat] = Counter()
        random.shuffle(cards)
        if self.last is not None and self.last["player"] == seat:
            self.last = None                        # their play stands, but nobody can challenge it now
        recv = left
        if self.last is not None and self.hand_size(self.last["player"]) == 0:
            recv = [i for i in left if i != self.last["player"]] or left   # keep a pending win intact
        for k, c in enumerate(cards):
            self.hands[recv[k % len(recv)]][c] += 1
        if len(left) <= 1:                          # everybody else left: last one standing wins
            self.phase = "over"
            self.winner = left[0] if left else None
            self.win_note = "forfeit"
            return
        if self.turn == seat:
            self.turn = self.next_active(seat)
        if len(left) == 2 and self.plays_left is None:
            self.plays_left = LIMIT_PLAYS

    # ---------- what one player is allowed to see ----------
    def view_for(self, p):
        names = [("You" if i == p else (nm or WAITING)) for i, nm in enumerate(self.names)]
        end_sub = ""
        if self.phase != "over":
            end_msg = ""
        elif self.abort_msg:
            end_msg = self.abort_msg
        elif self.winner is None:
            end_msg = "It's a draw! 🤝"
            end_sub = "Equal number of cards when the play limit ran out"
        else:
            end_msg = "You win! 🎉" if self.winner == p else f"{names[self.winner]} wins 😅"
            if self.win_note == "forfeit":
                end_sub = "Everyone else left the game"
            elif self.win_note == "count":
                end_sub = "Fewest cards when the play limit ran out"
        history = []
        for e in self.history[-HISTORY_MAX:]:
            d = {"player": e["player"], "count": e["count"], "claim": e["claim"],
                 "verdict": e.get("verdict")}
            if e.get("verdict") in ("lie", "true"):
                d.update(challenger=e["challenger"], taker=e["taker"],
                         revealed=[list(c) for c in e["revealed"]])
            history.append(d)
        last = None
        if self.last is not None:
            last = {"player": self.last["player"], "count": len(self.last["cards"]),
                    "claim": self.last["claim"]}
        return {
            "phase": self.phase, "names": names, "me": p,
            "hand": {f"{r},{s}": k for (r, s), k in self.hands[p].items()},
            "counts": [self.hand_size(i) for i in range(self.n)],
            "pile": len(self.pile), "last": last, "history": history,
            "req": self.req, "turn": self.turn, "decks": self.decks, "classic": self.classic,
            "end_msg": end_msg, "end_sub": end_sub, "pending_win": self.pending_end(),
            "final": self.limit_reached() and self.last is not None,
            "active": list(self.active), "plays_left": self.plays_left,
            "away": [[s, max(0, int(round(d - time.monotonic())))] for s, d in self.away.items()],
        }

    # ---------- bots ----------
    def bot_step(self):
        """The bot whose turn it is either calls Bluff, accepts, or plays."""
        b = self.turn
        if self.last is not None:
            if self.bot_should_challenge(b):
                self.challenge(b)
                return
            if self.pending_win():
                self.accept(b)
                return
        cards, claim = self.bot_choose_play(b)
        self.play(b, cards, claim)

    def bot_should_challenge(self, b):
        last = self.last
        k = len(last["cards"])
        top = 4 * self.decks
        own = self.rank_counts(b).get(last["claim"], 0)
        if own + k > top:                                   # impossible claim: certain lie
            return True
        if self.pending_win():                              # not challenging means losing the game
            return random.random() < 0.9
        p = 0.08 + 0.45 * (k - 1) / top
        if self.hand_size(last["player"]) <= 2:
            p += 0.15
        if len(self.pile) > 12:
            p *= 0.7
        return random.random() < min(max(p, 0.05), 0.75)

    def _dump_cards(self, b, k):
        """Pick k cards to get rid of, preferring ranks the bot holds the fewest of."""
        counts = self.rank_counts(b)
        ranks = sorted(counts, key=lambda r: (counts[r], random.random()))
        out = []
        for r in ranks:
            out.extend(self.take_rank(b, r, k - len(out)))
            if len(out) >= k:
                break
        return out

    def bot_choose_play(self, b):
        by_rank = self.rank_counts(b)
        total = sum(by_rank.values())
        top = 4 * self.decks
        if self.classic:
            claim = self.req
            mine = by_rank.get(claim, 0)
            if mine:
                cards = self.take_rank(b, claim, mine)
                if total > mine and random.random() < 0.2:    # sneak in an extra card
                    others = [c for c, n in self.hands[b].items() if c[0] != claim for _ in range(n)]
                    cards.append(random.choice(others))
            else:
                cards = self._dump_cards(b, min(total, random.choice([1, 1, 2])))
            return cards, claim
        best = max(by_rank.values())
        r = random.choice([x for x, n in by_rank.items() if n == best])
        if best == total or total == 1 or random.random() >= 0.3:
            return self.take_rank(b, r, best), r               # honest play
        k = min(total, random.choice([1, 1, 2, 3]))             # bluff
        cards = self._dump_cards(b, k)
        used = {c[0] for c in cards}
        options = [x for x in range(1, 14) if x not in used and by_rank.get(x, 0) + k <= top]
        options = options or [x for x in range(1, 14) if x not in used] or [r]
        return cards, random.choice(options)


# ====================================================================== 3D toolkit
# Everything below draws with plain QPainter.  A card is a textured quad that is pushed through a
# tiny perspective camera, so cards can really flip, tilt, fly and lie on a tilted 3D table.
UI_FONT = "Segoe UI"
CARD_W, CARD_H = 100.0, 140.0          # card size in "table units"
TEX = 2                                # card texture super-sampling
TABLE_W, TABLE_H = 1500, 1000          # table size in table units
RIM = 58                               # wooden rim width
RED_INK = QColor("#c62828")
BLACK_INK = QColor("#1c2230")


def lerp(a, b, t):
    return a + (b - a) * t


def clamp(x, lo=0.0, hi=1.0):
    return lo if x < lo else hi if x > hi else x


def ease_out(t):
    t = clamp(t)
    return 1 - (1 - t) ** 3


def ease_in(t):
    t = clamp(t)
    return t * t * t


def ease_io(t):
    t = clamp(t)
    return t * t * (3 - 2 * t)


def ease_back(t):
    """Ease-out with a little overshoot (used for pop-in animations)."""
    t = clamp(t) - 1
    return 1 + t * t * (2.7 * t + 1.7)


def approach(cur, target, dt, rate=12.0):
    return target + (cur - target) * math.exp(-rate * dt)


def lerp_angle(a, b, t):
    d = (b - a + math.pi) % (2 * math.pi) - math.pi
    return a + d * t


def font(px, bold=True, family=None):
    f = QFont(family or UI_FONT)
    f.setPixelSize(int(px))
    f.setBold(bold)
    return f


def text_in(p, rect, text, px, color, bold=True, align=Qt.AlignCenter, family=None):
    p.setFont(font(px, bold, family))
    p.setPen(QColor(color))
    p.drawText(QRectF(rect), int(align), text)


# ---------------------------------------------------------------- vector suits
def _build_suits():
    heart = QPainterPath()
    heart.moveTo(0, 0.5)
    heart.cubicTo(-0.58, 0.12, -0.62, -0.30, -0.30, -0.42)
    heart.cubicTo(-0.14, -0.48, 0, -0.38, 0, -0.20)
    heart.cubicTo(0, -0.38, 0.14, -0.48, 0.30, -0.42)
    heart.cubicTo(0.62, -0.30, 0.58, 0.12, 0, 0.5)
    heart.closeSubpath()

    body = QTransform().scale(0.95, -0.95).map(heart)
    stem = QPainterPath()
    stem.moveTo(0, 0.0)
    stem.lineTo(-0.17, 0.5)
    stem.lineTo(0.17, 0.5)
    stem.closeSubpath()
    spade = body.united(stem)

    diamond = QPainterPath()
    diamond.moveTo(0, -0.5)
    diamond.lineTo(0.36, 0)
    diamond.lineTo(0, 0.5)
    diamond.lineTo(-0.36, 0)
    diamond.closeSubpath()

    club = QPainterPath()
    for cx, cy in ((0, -0.25), (-0.26, 0.08), (0.26, 0.08)):
        c = QPainterPath()
        c.addEllipse(QPointF(cx, cy), 0.23, 0.23)
        club = club.united(c)
    mid = QPainterPath()
    mid.addEllipse(QPointF(0, -0.02), 0.17, 0.17)
    club = club.united(mid)
    cstem = QPainterPath()
    cstem.moveTo(0, 0.02)
    cstem.lineTo(-0.17, 0.5)
    cstem.lineTo(0.17, 0.5)
    cstem.closeSubpath()
    club = club.united(cstem)
    return [spade, heart, diamond, club]          # same order as SUITS


_SUIT_PATHS = _build_suits()


def draw_suit(p, suit, cx, cy, size, color):
    p.save()
    p.translate(cx, cy)
    p.scale(size, size)
    p.setPen(Qt.NoPen)
    p.fillPath(_SUIT_PATHS[suit], QBrush(QColor(color)))
    p.restore()


# ---------------------------------------------------------------- card artwork (cached textures)
_PIPS = {
    2: [(1, 0), (1, 1)],
    3: [(1, 0), (1, .5), (1, 1)],
    4: [(0, 0), (2, 0), (0, 1), (2, 1)],
    5: [(0, 0), (2, 0), (1, .5), (0, 1), (2, 1)],
    6: [(0, 0), (2, 0), (0, .5), (2, .5), (0, 1), (2, 1)],
    7: [(0, 0), (2, 0), (1, .25), (0, .5), (2, .5), (0, 1), (2, 1)],
    8: [(0, 0), (2, 0), (1, .25), (0, .5), (2, .5), (1, .75), (0, 1), (2, 1)],
    9: [(0, 0), (2, 0), (0, 1 / 3), (2, 1 / 3), (1, .5), (0, 2 / 3), (2, 2 / 3), (0, 1), (2, 1)],
    10: [(0, 0), (2, 0), (1, 1 / 6), (0, 1 / 3), (2, 1 / 3), (0, 2 / 3), (2, 2 / 3), (1, 5 / 6),
         (0, 1), (2, 1)],
}


def _render_face(rank, suit):
    pix = QPixmap(int(CARD_W * TEX), int(CARD_H * TEX))
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing | QPainter.SmoothPixmapTransform)
    p.scale(TEX, TEX)
    col = RED_INK if suit in RED_SUITS else BLACK_INK
    g = QLinearGradient(0, 0, 0, CARD_H)
    g.setColorAt(0, QColor("#ffffff"))
    g.setColorAt(1, QColor("#e6eaf1"))
    p.setPen(QPen(QColor("#8d96a8"), 1.0))
    p.setBrush(QBrush(g))
    p.drawRoundedRect(QRectF(1, 1, CARD_W - 2, CARD_H - 2), 8, 8)

    label = rank_short(rank)

    def corner():
        text_in(p, QRectF(1, 3, 24, 24), label, 21 if len(label) == 1 else 17, col, True, Qt.AlignCenter, "Georgia")
        draw_suit(p, suit, 13, 34, 14, col)

    corner()
    p.save()
    p.translate(CARD_W, CARD_H)
    p.rotate(180)
    corner()
    p.restore()

    if rank == 1:
        ring = QRadialGradient(QPointF(50, 70), 34)
        tint = QColor(col)
        tint.setAlpha(34)
        ring.setColorAt(0, tint)
        tint.setAlpha(0)
        ring.setColorAt(1, tint)
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(ring))
        p.drawEllipse(QPointF(50, 70), 34, 34)
        draw_suit(p, suit, 50, 70, 50, col)
    elif rank >= 11:
        panel = QRectF(27, 25, 46, 90)
        tint = QColor(col)
        tint.setAlpha(26)
        p.setPen(QPen(col, 1.3))
        p.setBrush(tint)
        p.drawRoundedRect(panel, 6, 6)
        inner = panel.adjusted(4, 4, -4, -4)
        tint.setAlpha(60)
        p.setPen(QPen(tint, 0.8))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(inner, 4, 4)
        text_in(p, panel, label, 50, col, True, Qt.AlignCenter, "Georgia")
        draw_suit(p, suit, 50, 38, 11, col)
        p.save()
        p.translate(50, 102)
        p.rotate(180)
        draw_suit(p, suit, 0, 0, 11, col)
        p.restore()
    else:
        size = 19 if rank <= 6 else 17
        xs = (31, 50, 69)
        y0, y1 = 29, 111
        for cx, fy in _PIPS[rank]:
            x, y = xs[cx], y0 + (y1 - y0) * fy
            if fy > 0.5001:
                p.save()
                p.translate(x, y)
                p.rotate(180)
                draw_suit(p, suit, 0, 0, size, col)
                p.restore()
            else:
                draw_suit(p, suit, x, y, size, col)
    p.end()
    return pix


def _render_back():
    pix = QPixmap(int(CARD_W * TEX), int(CARD_H * TEX))
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
    p.scale(TEX, TEX)
    p.setPen(QPen(QColor("#8d96a8"), 1.0))
    p.setBrush(QColor("#f4f6fa"))
    p.drawRoundedRect(QRectF(1, 1, CARD_W - 2, CARD_H - 2), 8, 8)
    inner = QRectF(6, 6, CARD_W - 12, CARD_H - 12)
    g = QLinearGradient(0, 0, CARD_W, CARD_H)
    g.setColorAt(0, QColor("#3f55c9"))
    g.setColorAt(1, QColor("#17216b"))
    p.setPen(Qt.NoPen)
    p.setBrush(QBrush(g))
    p.drawRoundedRect(inner, 5, 5)
    clip = QPainterPath()
    clip.addRoundedRect(inner, 5, 5)
    p.setClipPath(clip)
    p.setPen(QPen(QColor(255, 255, 255, 46), 0.9))
    for i in range(-16, 26):
        x = i * 9.0
        p.drawLine(QPointF(x, 0), QPointF(x + CARD_H, CARD_H))
        p.drawLine(QPointF(x + CARD_H, 0), QPointF(x, CARD_H))
    p.setClipping(False)
    p.setPen(QPen(QColor(255, 255, 255, 120), 0.9))
    p.setBrush(Qt.NoBrush)
    p.drawRoundedRect(inner.adjusted(5, 5, -5, -5), 3, 3)
    # medallion
    p.save()
    p.translate(CARD_W / 2, CARD_H / 2)
    p.rotate(45)
    gold = QLinearGradient(-22, -22, 22, 22)
    gold.setColorAt(0, QColor("#ffe082"))
    gold.setColorAt(1, QColor("#c9971c"))
    p.setPen(QPen(QBrush(gold), 2.2))
    p.setBrush(QColor("#0f1747"))
    p.drawRoundedRect(QRectF(-20, -20, 40, 40), 4, 4)
    p.restore()
    draw_suit(p, 0, CARD_W / 2, CARD_H / 2 - 1, 23, QColor("#ffe082"))
    p.end()
    return pix


class Art:
    _faces = {}
    _back = None

    @classmethod
    def face(cls, rank, suit):
        pix = cls._faces.get((rank, suit))
        if pix is None:
            pix = cls._faces[(rank, suit)] = _render_face(rank, suit)
        return pix

    @classmethod
    def back(cls):
        if cls._back is None:
            cls._back = _render_back()
        return cls._back

    @classmethod
    def table(cls):
        if getattr(cls, "_table", None) is None:
            cls._table = _render_table()
        return cls._table


def _render_table():
    """Wooden rim + green felt, drawn once at half resolution."""
    half = 0.5
    W, H = int(TABLE_W * half), int(TABLE_H * half)
    pix = QPixmap(W, H)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
    p.scale(half, half)
    R = TABLE_H / 2.0
    outer = QRectF(2, 2, TABLE_W - 4, TABLE_H - 4)
    wood = QLinearGradient(0, 0, 0, TABLE_H)
    wood.setColorAt(0.0, QColor("#8a5d38"))
    wood.setColorAt(0.5, QColor("#5b371d"))
    wood.setColorAt(1.0, QColor("#7a5130"))
    p.setPen(QPen(QColor("#2a160a"), 3))
    p.setBrush(QBrush(wood))
    p.drawRoundedRect(outer, R, R)
    # wood grain
    rnd = random.Random(7)
    clip = QPainterPath()
    clip.addRoundedRect(outer, R, R)
    p.setClipPath(clip)
    for _ in range(90):
        y = rnd.uniform(0, TABLE_H)
        p.setPen(QPen(QColor(0, 0, 0, rnd.randint(8, 22)), rnd.uniform(1, 3)))
        p.drawLine(QPointF(0, y), QPointF(TABLE_W, y + rnd.uniform(-12, 12)))
    p.setClipping(False)
    p.setPen(QPen(QColor(255, 255, 255, 46), 3))
    p.setBrush(Qt.NoBrush)
    p.drawRoundedRect(outer.adjusted(6, 6, -6, -6), R - 6, R - 6)
    # padded inner lip
    lip = QRectF(RIM - 12, RIM - 12, TABLE_W - 2 * (RIM - 12), TABLE_H - 2 * (RIM - 12))
    p.setPen(Qt.NoPen)
    p.setBrush(QColor("#140b05"))
    p.drawRoundedRect(lip, R - RIM + 12, R - RIM + 12)
    felt = QRectF(RIM, RIM, TABLE_W - 2 * RIM, TABLE_H - 2 * RIM)
    fr = R - RIM
    rg = QRadialGradient(QPointF(TABLE_W / 2, TABLE_H / 2 - 40), TABLE_W * 0.62)
    rg.setColorAt(0.0, QColor("#33996a"))
    rg.setColorAt(0.5, QColor("#217049"))
    rg.setColorAt(1.0, QColor("#0e3a27"))
    p.setBrush(QBrush(rg))
    p.drawRoundedRect(felt, fr, fr)
    fclip = QPainterPath()
    fclip.addRoundedRect(felt, fr, fr)
    p.setClipPath(fclip)
    # felt fibres
    for _ in range(9000):
        x, y = rnd.uniform(0, TABLE_W), rnd.uniform(0, TABLE_H)
        p.setPen(QColor(0, 0, 0, rnd.randint(6, 16)) if rnd.random() < 0.5 else QColor(255, 255, 255, rnd.randint(4, 10)))
        p.drawPoint(QPointF(x, y))
    # inner shadow along the rail
    sh = QPainterPath()
    sh.addRect(QRectF(0, 0, TABLE_W, TABLE_H))
    sh = sh.subtracted(fclip)
    p.setClipping(False)
    p.setClipPath(fclip)
    for i in range(14):
        p.setPen(QPen(QColor(0, 0, 0, 5 + i * 3), 2))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(felt.adjusted(i * 2.2, i * 2.2, -i * 2.2, -i * 2.2), max(fr - i * 2.2, 4), max(fr - i * 2.2, 4))
    p.setClipping(False)
    # gold line + centre ring
    p.setPen(QPen(QColor(255, 214, 120, 120), 2.5))
    p.setBrush(Qt.NoBrush)
    p.drawRoundedRect(felt.adjusted(30, 30, -30, -30), fr - 30, fr - 30)
    p.setPen(QPen(QColor(255, 255, 255, 52), 3, Qt.DashLine))
    p.drawEllipse(QPointF(TABLE_W / 2, TABLE_H / 2), 175, 175)
    for i, s in enumerate((0, 1, 2, 3)):
        ang = math.pi / 4 + i * math.pi / 2
        draw_suit(p, s, TABLE_W / 2 + 175 * math.cos(ang), TABLE_H / 2 + 175 * math.sin(ang), 34,
                  QColor(255, 255, 255, 40))
    p.end()
    return pix


# ---------------------------------------------------------------- camera + textured quads
class Cam:
    """A table whose top is tilted back by 'theta' radians, seen through a pinhole camera.
    Table space: x right, y toward the player, h = height above the felt."""

    def __init__(self, theta, dist, scale, cx, cy):
        self.set(theta, dist, scale, cx, cy)

    def set(self, theta, dist, scale, cx, cy):
        self.theta, self.dist, self.scale, self.cx, self.cy = theta, dist, scale, cx, cy
        self.ct, self.st = math.cos(theta), math.sin(theta)

    def project(self, x, y, h=0.0):
        yy = y * self.ct - h * self.st
        zz = -y * self.st - h * self.ct
        k = self.dist / (self.dist + zz * self.scale)
        return (self.cx + x * self.scale * k, self.cy + yy * self.scale * k, k)

    def sy(self, y, h=0.0):
        return self.project(0, y, h)[1]


def card_pts(cam, pose):
    """Four projected corners (TL, TR, BR, BL) of a card.
    pose = (u, v, h, rz, al, ry, k): position, spin on the table, tilt (standing up), flip, size."""
    u, v, h, rz, al, ry, k = pose
    hw, hh = CARD_W * k / 2, CARD_H * k / 2
    cry, sry = math.cos(ry), math.sin(ry)
    crz, srz = math.cos(rz), math.sin(rz)
    cal, sal = math.cos(al), math.sin(al)
    out = []
    for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
        x, y = sx * hw, sy * hh
        x1, z1 = x * cry, x * sry                      # flip around the card's vertical axis
        x2, y2 = x1 * crz - y * srz, x1 * srz + y * crz   # spin in the card's plane
        y3 = y2 * cal + z1 * sal                       # stand the card up
        z3 = -y2 * sal + z1 * cal
        out.append(cam.project(u + x2, v + y3, h + z3))
    return out


_SRC_QUAD = QPolygonF([QPointF(0, 0), QPointF(CARD_W, 0), QPointF(CARD_W, CARD_H), QPointF(0, CARD_H)])


def draw_card_3d(p, cam, face, pose, shadow=0, alpha=1.0):
    """Draw one card. face=(rank, suit) or None (unknown -> always shows the back).
    shadow: 0 none, 1 footprint on the table, 2 small offset (cards in a hand).
    Returns the screen polygon (used for mouse hit-testing)."""
    pts = card_pts(cam, pose)
    poly = QPolygonF([QPointF(x, y) for x, y, _ in pts])
    ry = pose[5]
    cr = math.cos(ry)
    if alpha <= 0.01:
        return poly
    if shadow == 1:
        h = max(pose[2], 0.0)
        fp = card_pts(cam, (pose[0] + h * 0.10, pose[1] + 3 + h * 0.30, 0.0, pose[3], 0.0, 0.0, pose[6]))
        a = int(95 * alpha / (1.0 + h / 110.0))
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(0, 0, 0, a))
        p.drawPolygon(QPolygonF([QPointF(x, y) for x, y, _ in fp]))
    elif shadow == 2:
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(0, 0, 0, int(85 * alpha)))
        p.drawPolygon(poly.translated(-6, 3))
    front = cr > 0 and face is not None
    pix = Art.face(*face) if front else Art.back()
    order = (0, 1, 2, 3) if cr >= 0 else (1, 0, 3, 2)
    dst = QPolygonF([poly[i] for i in order])
    tr = QTransform()
    if not QTransform.quadToQuad(_SRC_QUAD, dst, tr):
        return poly
    p.save()
    if alpha < 0.999:
        p.setOpacity(alpha)
    p.setTransform(tr, True)
    p.drawPixmap(QRectF(0, 0, CARD_W, CARD_H), pix, QRectF(pix.rect()))
    p.restore()
    edge = 1.0 - abs(cr)
    if edge > 0.02:
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(0, 0, 0, int(120 * edge * alpha)))
        p.drawPolygon(poly)
    return poly



# ====================================================================== start dialog
class LogoWidget(QWidget):
    """Four cards that keep flipping in 3D above the title."""

    def __init__(self):
        super().__init__()
        self.setFixedHeight(214)
        self.setMinimumWidth(420)
        self.t0 = time.perf_counter()
        self.faces = [(1, 0), (13, 1), (12, 2), (11, 3)]
        self.cam = Cam(0.22, 650.0, 1.0, 200.0, 80.0)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update)
        self.timer.start(25)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing | QPainter.SmoothPixmapTransform)
        t = time.perf_counter() - self.t0
        W = self.width()
        self.cam.set(0.22, 650.0, 1.0, W / 2.0, 80.0)
        for i, face in enumerate(self.faces):
            ph = t * 1.25 + i * 0.85
            ry = (math.pi / 2) * (1 + math.sin(ph))
            u = (i - 1.5) * 84
            h = 14 * math.sin(t * 2 + i * 1.3)
            draw_card_3d(p, self.cam, face, (u, 6 + 8 * abs(i - 1.5), 20 + h, (i - 1.5) * 0.17, 0.22, ry, 0.72),
                         shadow=1)
        p.setFont(font(40, True))
        path = QPainterPath()
        path.addText(0, 0, font(42, True), "BLUFF")
        br = path.boundingRect()
        p.save()
        p.translate(W / 2 - br.center().x(), 202)
        g = QLinearGradient(0, -34, 0, 4)
        g.setColorAt(0, QColor("#fff3c4"))
        g.setColorAt(1, QColor("#f2a900"))
        p.setPen(QPen(QColor(0, 0, 0, 120), 5, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.setBrush(QBrush(g))
        p.drawPath(path)
        p.restore()


class StartDialog(QDialog):
    STYLE = """
    QDialog { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #1d3560, stop:1 #090f20); }
    QLabel { color: #dbe6fb; font-size: 13px; }
    QLabel#info { color: #8ea5cc; font-size: 12px; }
    QLabel#sep { color: #8ea5cc; font-size: 12px; margin-top: 6px; }
    QLineEdit, QSpinBox { background: rgba(255,255,255,18); color: white; border: 1px solid rgba(255,255,255,60);
        border-radius: 9px; padding: 6px 10px; font-size: 14px; selection-background-color: #4f8cff; }
    QLineEdit:focus, QSpinBox:focus { border: 1px solid #ffd54f; }
    QSpinBox::up-button, QSpinBox::down-button { width: 18px; border: none; background: transparent; }
    QCheckBox { color: #dbe6fb; font-size: 13px; spacing: 8px; }
    QCheckBox::indicator { width: 18px; height: 18px; border-radius: 5px; border: 1px solid rgba(255,255,255,90);
        background: rgba(255,255,255,18); }
    QCheckBox::indicator:checked { background: #ffd54f; border: 1px solid #ffffff; }
    QPushButton { color: white; font-size: 15px; font-weight: bold; border: 1px solid rgba(255,255,255,70);
        border-radius: 12px; padding: 0 12px; }
    QPushButton#cpu  { background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #34d27b, stop:1 #13803f); }
    QPushButton#cpu:hover  { background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #5ae596, stop:1 #1a9a4e); }
    QPushButton#host { background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #5b97ff, stop:1 #2447b8); }
    QPushButton#host:hover { background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #82b0ff, stop:1 #2f58d6); }
    QPushButton#join { background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #ffb02e, stop:1 #c26a00); }
    QPushButton#join:hover { background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #ffc660, stop:1 #db7a05); }
    QPushButton:pressed { margin-top: 2px; }
    """

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Bluff")
        self.setStyleSheet(self.STYLE)
        self.mode = None
        self.players = 4
        self.decks = 1
        self.classic = False
        self.name = ""
        self.ip = ""
        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 18, 28, 24)
        lay.setSpacing(10)
        lay.addWidget(LogoWidget())

        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(8)
        grid.addWidget(QLabel("Your name"), 0, 0)
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("(optional)")
        self.name_edit.setMaxLength(14)
        grid.addWidget(self.name_edit, 0, 1)
        grid.addWidget(QLabel("Total players (max 10)"), 1, 0)
        self.spin_players = QSpinBox()
        self.spin_players.setRange(2, 10)
        self.spin_players.setValue(4)
        grid.addWidget(self.spin_players, 1, 1)
        grid.addWidget(QLabel("Number of decks"), 2, 0)
        self.spin_decks = QSpinBox()
        self.spin_decks.setRange(1, 4)
        self.spin_decks.setValue(1)
        grid.addWidget(self.spin_decks, 2, 1)
        lay.addLayout(grid)

        self.info = QLabel()
        self.info.setObjectName("info")
        self.info.setWordWrap(True)
        lay.addWidget(self.info)
        self.spin_players.valueChanged.connect(self._update_info)
        self.spin_decks.valueChanged.connect(self._update_info)

        self.chk = QCheckBox("Classic rank order (A, 2, 3 ... K) instead of free choice")
        lay.addWidget(self.chk)

        def button(text, mode):
            b = QPushButton(text)
            b.setObjectName(mode)
            b.setMinimumHeight(44)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda: self._choose(mode))
            lay.addWidget(b)

        button("Play vs CPU  (you + bots)", "cpu")
        button("Host Game  (friends join you)", "host")
        sep = QLabel("To join a friend's game, type their IP:")
        sep.setObjectName("sep")
        lay.addWidget(sep)
        self.ip_edit = QLineEdit()
        self.ip_edit.setPlaceholderText("Host IP, e.g. 192.168.1.5  (same PC: 127.0.0.1)")
        lay.addWidget(self.ip_edit)
        button("Join Game", "join")
        self._update_info()

    def _update_info(self):
        n, d = self.spin_players.value(), self.spin_decks.value()
        self.info.setText(f"{52 * d} cards in total, about {52 * d // n} cards each. "
                          f"Each rank appears {4 * d} times.\n"
                          f"(vs CPU needs 3+ players. When joining, the host's settings are used.)")

    def _choose(self, mode):
        ip = self.ip_edit.text().strip()
        if mode == "join" and not ip:
            self.ip_edit.setFocus()
            return
        self.mode = mode
        self.players = self.spin_players.value()
        self.decks = self.spin_decks.value()
        self.classic = self.chk.isChecked()
        self.name = self.name_edit.text().strip()
        self.ip = ip
        self.accept()



# ====================================================================== game window
def blank_view(n, me, decks, classic):
    names = [WAITING] * n
    names[me] = "You"
    return {"phase": "lobby", "names": names, "me": me, "hand": {}, "counts": [0] * n, "pile": 0,
            "last": None, "history": [], "req": 1, "turn": 0, "decks": decks, "classic": classic,
            "end_msg": "", "end_sub": "", "pending_win": False, "final": False,
            "active": [True] * n, "plays_left": None, "away": []}


class Btn:
    def __init__(self, key, text, c1, c2):
        self.key, self.text = key, text
        self.c1, self.c2 = QColor(c1), QColor(c2)
        self.rect = QRectF()
        self.enabled = True
        self.visible = True
        self.hov = 0.0
        self.press = 0.0
        self.px = 16


class PileVis:
    """One face-down card lying in the middle of the table."""
    __slots__ = ("u", "v", "h", "rz", "face", "grp", "row")

    def __init__(self):
        self.u = random.uniform(-42, 42)
        self.v = random.uniform(-30, 30)
        self.h = 0.0
        self.rz = random.uniform(-0.9, 0.9)
        self.face = None
        self.grp = 0
        self.row = None


class HandVis:
    """One card (or a stack of identical cards) in your hand, with its animated pose."""

    def __init__(self, card, delay, start=None):
        self.card, self.delay = card, delay
        self.u, self.v, self.h = 0.0, 0.0, 170.0
        self.rz, self.al, self.ry, self.k = 0.0, 0.6, math.pi, 0.9
        if start:
            self.u, self.v, self.h, self.rz, self.al, self.ry, self.k = start
        self.hov = 0.0
        self.sel = 0.0

    def pose(self):
        return (self.u, self.v, self.h, self.rz, self.al, self.ry, self.k)


class Flyer:
    """A card travelling through the air from A to B."""

    def __init__(self, face, a, b, t0, dur, arc, on_land):
        self.face, self.a, self.b = face, a, b
        self.t0, self.dur, self.arc, self.on_land = t0, dur, arc, on_land


class BluffWindow(QWidget):
    """Draws a 3D table for whatever 'view' it is given and sends the player's clicks to its controller."""
    PANEL_W = 300
    THETA = 0.70               # table tilt (radians)
    HAND_H = 64.0
    BADGE_W, BADGE_H = 176, 54
    FAN_MAX = 14               # max face-down cards drawn in an opponent's fan

    def __init__(self, ctrl, n, me, decks, classic, new_policy="always", role=""):
        super().__init__()
        self.ctrl = ctrl
        self.n = n
        self.decks = decks
        self.classic = classic
        self.new_policy = new_policy         # always | over_only | never
        self.lobby_hint = ""
        self.sel = Counter()                 # your selected cards: (rank, suit) -> copies selected
        self.hand = Counter()
        self.v = blank_view(n, me, decks, classic)
        self.claim = 1
        self.hcards = {}                     # card -> HandVis
        self.vis_pile = []
        self.flyers = []
        self.reveal = None
        self.reveal_id = 0
        self.banner = None
        self.confetti = []
        self.opp_shown = [0] * n
        self.opp_acc = [0.0] * n
        self.hover = None
        self.pressed = None
        self.hit_cards = []
        self.chip_rects = {}
        self.chip_hov = {r: 0.0 for r in range(1, 14)}
        self.hist_scroll = 0.0
        self.hist_len = -1
        self.end_t0 = None
        self.end_fx = False
        self.shake = 0.0
        self._snap = None
        self._bg = None
        self.hand_v = 560.0
        self.hand_scale = 1.4
        self.hand_k = 1.2
        self.conn_until = None               # set while THIS player is trying to reconnect
        self.away_info = []                  # [(seat, seconds left when the view arrived)]
        self.away_t0 = 0.0
        self.setWindowTitle("Bluff" + (f" ({role})" if role else ""))
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMinimumSize(1080, 720)
        self.resize(1260, 820)

        self.cam = Cam(self.THETA, 1500.0, 0.5, 400.0, 300.0)
        self.seats = self._make_seats(me)
        self.btns = {
            "new": Btn("new", "New game", "#4f8cff", "#2447b8"),
            "menu": Btn("menu", "Menu", "#7b8ba5", "#4b5a73"),
            "clear": Btn("clear", "Clear", "#7b8ba5", "#4b5a73"),
            "play": Btn("play", "Play", "#34d27b", "#13803f"),
            "accept": Btn("accept", "Accept", "#ffb02e", "#c26a00"),
            "bluff": Btn("bluff", "Bluff!", "#ff5a5a", "#b01c2e"),
            "again": Btn("again", "Play again", "#34d27b", "#13803f"),
            "menu2": Btn("menu2", "Menu", "#7b8ba5", "#4b5a73"),
        }
        for k in ("new", "menu", "clear"):
            self.btns[k].px = 14
        for k in ("play", "accept", "bluff", "again", "menu2"):
            self.btns[k].px = 18
        self.t0 = time.perf_counter()
        self.last_t = self.t0
        self.now = 0.0
        self._relayout()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(20)

    # ================= geometry =================
    def _make_seats(self, me):
        seats = []
        for i in range(self.n):
            rel = (i - me) % self.n
            ang = math.pi / 2 + 2 * math.pi * rel / self.n
            c, s = math.cos(ang), math.sin(ang)
            if rel == 0:
                seats.append(dict(u=0.0, v=520.0, rot=0.0, tx=1.0, ty=0.0, bu=0.0, bv=520.0))
                continue
            u, v = 560 * c, 300 * s
            d = math.hypot(u, v)
            dx, dy = -u / d, -v / d
            if abs(c) > 0.55:                                    # side seat: badge above / below the fan
                bu, bv = u * 1.02, v + (200 if s > 0.2 else -200)
                if self.n >= 7 and s > 0.2:                      # seats beside me: keep clear of my hand
                    bu += 135 if c > 0 else -135
            else:
                bu, bv = u + 150 * c, v + 150 * s
            seats.append(dict(u=u, v=v, rot=math.atan2(dx, -dy), tx=dy, ty=-dx, bu=bu, bv=bv))
        return seats

    def _relayout(self):
        W, H = self.width(), self.height()
        self.panel_x = W - self.PANEL_W
        self.rw = self.panel_x
        S = min(self.rw * 0.56 / 1000.0, (H - 330) / 640.0)
        cam = self.cam
        cam.set(self.THETA, 1500.0, S, self.rw / 2.0, 0.0)
        cam.cy = 168 - cam.project(0, -TABLE_H / 2.0, 0)[1]
        # where does my hand sit?  solve for the table-y that lands the cards at the right screen height
        target = H - 122 - 112
        lo, hi = 200.0, 1100.0
        for _ in range(40):
            mid = (lo + hi) / 2
            if cam.project(0, mid, self.HAND_H)[1] < target:
                lo = mid
            else:
                hi = mid
        self.hand_v = (lo + hi) / 2
        self.hand_k = cam.project(0, self.hand_v, self.HAND_H)[2]
        want_h = clamp(H * 0.2, 118, 170)
        self.hand_scale = want_h / (CARD_H * S * self.hand_k)
        self.seats[self.v["me"]].update(u=0.0, v=self.hand_v, bu=-9999.0, bv=0.0)
        # tables transform
        c = [cam.project(x, y, 0) for x, y in ((-TABLE_W / 2, -TABLE_H / 2), (TABLE_W / 2, -TABLE_H / 2),
                                               (TABLE_W / 2, TABLE_H / 2), (-TABLE_W / 2, TABLE_H / 2))]
        dst = QPolygonF([QPointF(a, b) for a, b, _ in c])
        src = QPolygonF([QPointF(0, 0), QPointF(TABLE_W, 0), QPointF(TABLE_W, TABLE_H), QPointF(0, TABLE_H)])
        self.tr_tab = QTransform()
        QTransform.quadToQuad(src, dst, self.tr_tab)
        self.tr_cen = QTransform.fromTranslate(TABLE_W / 2.0, TABLE_H / 2.0) * self.tr_tab
        outline = QPainterPath()
        outline.addRoundedRect(QRectF(0, 0, TABLE_W, TABLE_H), TABLE_H / 2.0, TABLE_H / 2.0)
        self.table_outline = self.tr_tab.map(outline)
        # UI rects
        cx = self.rw / 2.0
        yc, yb = H - 122, H - 80
        cw, gap = 38.0, 5.0
        x0 = cx - (13 * cw + 12 * gap) / 2
        self.chip_rects = {r: QRectF(x0 + (r - 1) * (cw + gap), yc, cw, 32) for r in range(1, 14)}
        b = self.btns
        b["clear"].rect = QRectF(cx - 330, yb, 100, 44)
        b["play"].rect = QRectF(cx - 218, yb, 250, 44)
        b["accept"].rect = QRectF(cx - 218, yb, 250, 44)
        b["bluff"].rect = QRectF(cx + 44, yb, 170, 44)
        b["menu"].rect = QRectF(self.rw - 104, 14, 90, 34)
        b["new"].rect = QRectF(self.rw - 104 - 108, 14, 100, 34)
        b["again"].rect = QRectF(self.rw / 2 - 190, H / 2 + 56, 180, 54)
        b["menu2"].rect = QRectF(self.rw / 2 + 10, H / 2 + 56, 180, 54)
        self._bg = None

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._relayout()

    def closeEvent(self, e):
        self.timer.stop()
        super().closeEvent(e)

    # ================= receiving a new view =================
    def set_view(self, v):
        old = self.v
        self.v = v
        self.away_info = [(int(s), float(t)) for s, t in v.get("away", [])]
        self.away_t0 = self.now
        self.hand = Counter({tuple(int(x) for x in k.split(",")): n for k, n in v["hand"].items()})
        fresh = v["phase"] == "play" and (old["phase"] != "play" or
                                          (not v["history"] and (old["history"] or old["pile"])))
        if fresh or v["phase"] == "lobby":
            self._reset_scene()
        self._detect(old, v)
        self._sync_hand()
        if self.classic:
            self.claim = v["req"]
        self._clamp_sel()
        self.update()

    def show_notice(self, text):
        """Connection problems: freeze the game and show a message."""
        v = dict(self.v)
        v.update(phase="over", end_msg=text, end_sub="", pending_win=False, final=False, away=[])
        self.conn_until = None
        self.set_view(v)

    def _reset_scene(self):
        self.hcards.clear()
        self.vis_pile = []
        self.flyers = []
        self.reveal = None
        self.banner = None
        self.confetti = []
        self.end_t0 = None
        self.end_fx = False
        self.opp_shown = [0] * self.n
        self.hist_scroll = 0.0
        self.sel = Counter()
        self._snap = None

    def _sync_hand(self):
        for card in list(self.hcards):
            if card not in self.hand:
                del self.hcards[card]
        fresh = [c for c in sorted(self.hand) if c not in self.hcards]
        r = self.reveal
        for i, card in enumerate(fresh):
            if r and r["taker"] == self.me():          # picking up the pile: join the hand as the sweep arrives
                start = (0.0, self.hand_v + 30, 110.0, 0.0, self.THETA - 0.24, math.pi, self.hand_scale * 0.55)
                self.hcards[card] = HandVis(card, r["t0"] + 3.25 + min(i * 0.03, 0.4), start)
            else:
                self.hcards[card] = HandVis(card, self.now + min(i * 0.045, 1.6))

    def _detect(self, old, v):
        added = v["pile"] - old["pile"]
        if v["phase"] in ("play", "over") and added > 0 and v["last"] is not None:
            self._spawn_play(v["last"]["player"], added)
        delay = 0.9
        e = v["history"][-1] if v["history"] else None
        if (old["last"] is not None and v["last"] is None and old["pile"] > 0 and e is not None
                and e.get("verdict") in ("lie", "true")):
            self._start_reveal(e, old["pile"])
            delay = 4.2
        if v["phase"] == "over" and old["phase"] != "over":
            self.end_t0 = self.now + (delay if old["phase"] == "play" else 0.2)
            self.end_fx = False
        if len(v["history"]) != self.hist_len:
            self.hist_scroll = 0.0
            self.hist_len = len(v["history"])

    # ================= scene bookkeeping =================
    def _fan_pose(self, i, j, m):
        s = self.seats[i]
        t = (j - (m - 1) / 2.0)
        return (s["u"] + s["tx"] * t * 20.0, s["v"] + s["ty"] * t * 20.0, 3.0, s["rot"] + t * 0.045,
                0.0, math.pi, 0.80)

    def _spawn_play(self, player, count):
        snap = self._snap
        self._snap = None
        use_snap = (player == self.v["me"] and snap is not None and self.now - snap[0] < 4.0
                    and len(snap[1]) == count)
        m = max(self.opp_shown[player], 1)
        for j in range(count):
            if use_snap:
                face, a = snap[1][j]
            else:
                face = None
                a = self._fan_pose(player, random.randrange(m), m) if player != self.v["me"] else \
                    (0.0, self.hand_v, 60.0, 0.0, self.THETA - 0.24, math.pi, self.hand_scale)
            pv = PileVis()
            end = (pv.u, pv.v, 0.0, pv.rz, 0.0, math.pi, 0.95)

            def land(pv=pv):
                self.vis_pile.append(pv)
                pv.h = 0.5 * min(len(self.vis_pile), 40)
            self.flyers.append(Flyer(face, a, end, self.now + j * 0.075, 0.62, 150.0, land))

    def _land_all_flyers(self):
        for f in sorted(self.flyers, key=lambda f: f.t0):
            f.on_land()
        self.flyers = []

    def _start_reveal(self, e, pile_before):
        self._land_all_flyers()
        if self.reveal:
            # A previous reveal is still animating (a quick second Bluff call).  Finish it right
            # away: its cards were already taken by someone, and leaving them in the pile with
            # their old reveal data made _pile_pose crash.
            old_id = self.reveal["id"]
            self.vis_pile = [pv for pv in self.vis_pile if pv.grp != old_id]
            self.reveal = None
            self.banner = None
        while len(self.vis_pile) < pile_before:
            self.vis_pile.insert(0, PileVis())
        k = len(e["revealed"])
        self.reveal_id += 1
        rid = self.reveal_id
        for pv in self.vis_pile:
            pv.grp = rid
        top = self.vis_pile[-k:] if k else []
        sp = min(122.0, 760.0 / max(k, 1))
        for j, pv in enumerate(top):
            pv.face = tuple(e["revealed"][j])
            pv.row = ((j - (k - 1) / 2.0) * sp, -6.0)
        names = self.v["names"]
        lie = e["verdict"] == "lie"

        def is_(n):
            return "are" if n == "You" else "is"

        def verb(n, v):
            return v if n == "You" else v + "s"
        claimer, chal, taker = names[e["player"]], names[e["challenger"]], names[e["taker"]]
        self.reveal = dict(id=rid, t0=self.now, k=k, top=top, taker=e["taker"], lie=lie,
                           shown=False, n=pile_before,
                           text="LIE!" if lie else "TRUE!",
                           sub=(f"{claimer} {'were' if claimer == 'You' else 'was'} caught bluffing" if lie
                                else f"{chal} {'were' if chal == 'You' else 'was'} wrong") +
                               f"  —  {taker} {verb(taker, 'take')} {pile_before} card{'s' if pile_before != 1 else ''}")

    def _pile_pose(self, pv):
        base = (pv.u, pv.v, pv.h, pv.rz, 0.0, math.pi, 0.95)
        r = self.reveal
        if not r or pv.grp != r["id"]:
            return base
        t = self.now - r["t0"]
        hold = base
        if pv.row is not None and any(pv is x for x in r["top"]):
            j = next(i for i, x in enumerate(r["top"]) if x is pv)
            s = ease_io((t - 0.05 * j) / 0.6)
            f = ease_io((t - 0.65 - 0.1 * j) / 0.5)
            ru, rv = pv.row
            u, v = lerp(pv.u, ru, s), lerp(pv.v, rv, s)
            h = lerp(pv.h, 46.0, s) + 80 * math.sin(math.pi * clamp((t - 0.05 * j) / 0.6))
            rz = lerp(pv.rz, 0.0, s)
            al = lerp(0.0, 0.5, s)
            ry = lerp(math.pi, 0.0, f)
            k = lerp(0.95, 1.5, s)
            hold = (ru, rv, 46.0, 0.0, 0.5, 0.0, 1.5)
            base = (u, v, h + 40 * math.sin(math.pi * f), rz, al, ry, k)
        sw = (t - 3.0) / 0.7
        if sw > 0:
            tgt = self.seats[r["taker"]]
            e = ease_in(sw)
            return (lerp(hold[0], tgt["u"], e), lerp(hold[1], tgt["v"], e), lerp(hold[2], 30, e) + 90 * math.sin(math.pi * clamp(sw)),
                    lerp(hold[3], hold[3] + 0.8, e), lerp(hold[4], 0.0, e), hold[5], lerp(hold[6], 0.55, e))
        return base

    # ================= helpers =================
    def me(self):
        return self.v["me"]

    def paused(self):
        return bool(self.away_info)

    def my_turn(self):
        return (self.v["phase"] == "play" and self.v["turn"] == self.me()
                and not self.paused() and self.conn_until is None)

    def _away_text(self):
        names = self.v["names"]
        secs = max(0, int(min(t - (self.now - self.away_t0) for _s, t in self.away_info) + 0.99))
        who = ", ".join(names[s] if s < len(names) else "?" for s, _t in self.away_info)
        return f"Game paused: {who} lost connection. Waiting {secs}s for them to come back…"

    def selected_total(self):
        return sum(min(n, self.hand.get(c, 0)) for c, n in self.sel.items())

    def claim_rank(self):
        return self.v["req"] if self.classic else max(1, self.claim)

    def rank_totals(self):
        c = Counter()
        for (r, _s), n in self.hand.items():
            c[r] += n
        return c

    def _clamp_sel(self):
        for card in list(self.sel):
            have = self.hand.get(card, 0)
            if have <= 0:
                del self.sel[card]
            else:
                self.sel[card] = min(self.sel[card], have)

    # ================= selecting your cards =================
    def cycle_slot(self, card):
        have = self.hand.get(card, 0)
        if have <= 0 or self.v["phase"] != "play":
            return
        self.sel[card] = (self.sel.get(card, 0) + 1) % (have + 1)

    def select_rank(self, rank):
        if self.v["phase"] != "play":
            return
        cards = [(rank, s) for s in range(4) if self.hand.get((rank, s), 0) > 0]
        if not cards:
            return
        all_sel = all(self.sel.get(c, 0) >= self.hand[c] for c in cards)
        for c in cards:
            self.sel[c] = 0 if all_sel else self.hand[c]

    def clear_selection(self):
        self.sel = Counter()

    def play_clicked(self):
        if not self.my_turn() or self.v["pending_win"]:
            return
        cards, snap = [], []
        for c, k in sorted(self.sel.items()):
            hv = self.hcards.get(c)
            for _ in range(min(k, self.hand.get(c, 0))):
                cards.append(c)
                if hv:
                    snap.append((c, hv.pose()))
                else:
                    snap.append((c, (0.0, self.hand_v, 60.0, 0.0, 0.5, 0.0, self.hand_scale)))
        if not cards:
            return
        self._snap = (self.now, snap)
        claim = self.claim_rank()
        self.sel = Counter()
        self.ctrl.play(cards, claim)

    def menu_clicked(self):
        self.ctrl.go_menu = True
        self.close()

    # ================= per-frame animation =================
    def _tick(self):
        t = time.perf_counter()
        dt = min(0.05, t - self.last_t)
        self.last_t = t
        self.now = t - self.t0
        now = self.now
        for b in self.btns.values():
            b.hov = approach(b.hov, 1.0 if (self.hover == ("btn", b.key) and b.enabled) else 0.0, dt, 18)
            b.press = approach(b.press, 1.0 if self.pressed == ("btn", b.key) else 0.0, dt, 30)
        for r in self.chip_hov:
            self.chip_hov[r] = approach(self.chip_hov[r], 1.0 if self.hover == ("chip", r) else 0.0, dt, 18)
        self._update_btns()
        self._layout_hand(dt)
        for f in list(self.flyers):
            if now - f.t0 >= f.dur:
                f.on_land()
                self.flyers.remove(f)
        r = self.reveal
        if r:
            tt = now - r["t0"]
            if tt >= 1.3 and not r["shown"]:
                r["shown"] = True
                self.banner = dict(t0=now, text=r["text"], sub=r["sub"], lie=r["lie"])
                if r["lie"]:
                    self.shake = 1.0
            if tt >= 3.75:
                self.vis_pile = [pv for pv in self.vis_pile if pv.grp != r["id"]]
                self.reveal = None
        if self.banner and now - self.banner["t0"] > 2.2:
            self.banner = None
        v = self.v
        for i in range(self.n):
            tgt = min(v["counts"][i], self.FAN_MAX) if v["phase"] != "lobby" else 0
            if self.opp_shown[i] < tgt:
                self.opp_acc[i] += dt * 30
                step = int(self.opp_acc[i])
                if step:
                    self.opp_shown[i] = min(tgt, self.opp_shown[i] + step)
                    self.opp_acc[i] -= step
            else:
                self.opp_shown[i] = tgt
        if self.end_t0 is not None and now >= self.end_t0 and not self.end_fx:
            self.end_fx = True
            if v["end_msg"].startswith("You win"):
                self._burst()
        self.shake = max(0.0, self.shake - dt * 2.4)
        for c in self.confetti:
            c[0] += c[2] * dt
            c[1] += c[3] * dt
            c[3] += 260 * dt
            c[2] *= 0.995
            c[4] += c[5] * dt
        self.confetti = [c for c in self.confetti if c[1] < self.height() + 30]
        self.update()

    def _burst(self):
        cols = ["#ffd54f", "#ef5350", "#42a5f5", "#66bb6a", "#ab47bc", "#ffffff", "#ff7043"]
        for _ in range(170):
            x = random.uniform(0, self.rw)
            self.confetti.append([x, random.uniform(-60, 20), random.uniform(-120, 120), random.uniform(60, 380),
                                  random.uniform(0, 6.28), random.uniform(-9, 9), random.choice(cols),
                                  random.uniform(6, 12), random.uniform(4, 8)])

    def _layout_hand(self, dt):
        keys = [k for k in sorted(self.hcards) if self.now >= self.hcards[k].delay]
        n = len(keys)
        if not n:
            return
        S = self.cam.scale
        avail = (self.rw - 90) / (S * self.hand_k)
        cw = CARD_W * self.hand_scale
        spacing = cw * 0.80
        if n > 1:
            spacing = min(spacing, (avail - cw) / (n - 1))
        mid = (n - 1) / 2.0
        fan = min(0.42, 0.028 * n)
        for i, key in enumerate(keys):
            hv = self.hcards[key]
            nrm = (i - mid) / max(mid, 1.0)
            tu = (i - mid) * spacing
            tv = self.hand_v + 26 * nrm * nrm
            hv.hov = approach(hv.hov, 1.0 if self.hover == ("card", key) else 0.0, dt, 18)
            hv.sel = approach(hv.sel, 1.0 if self.sel.get(key, 0) > 0 else 0.0, dt, 14)
            th = self.HAND_H + 26 * hv.hov + 58 * hv.sel
            trz = nrm * fan / 2
            tal = self.THETA - 0.24 + 0.10 * hv.sel
            tk = self.hand_scale * (1 + 0.05 * hv.hov)
            hv.u = approach(hv.u, tu, dt, 8)
            hv.v = approach(hv.v, tv, dt, 8)
            hv.h = approach(hv.h, th, dt, 8 if hv.h > 120 else 16)
            hv.rz = approach(hv.rz, trz, dt, 9)
            hv.al = approach(hv.al, tal, dt, 8)
            hv.ry = approach(hv.ry, 0.0, dt, 7)
            hv.k = approach(hv.k, tk, dt, 9)

    # ================= enabled/visible state of the buttons =================
    def _end_visible(self):
        return self.v["phase"] == "over" and self.end_t0 is not None and self.now >= self.end_t0

    def _update_btns(self):
        v = self.v
        my_turn, pending, phase = self.my_turn(), v["pending_win"], v["phase"]
        n_sel = self.selected_total()
        b = self.btns
        b["play"].text = f"Play {n_sel} as {RANK_NAMES[self.claim_rank()][1]}" if n_sel else "Play"
        b["play"].enabled = my_turn and n_sel > 0 and not pending
        b["play"].visible = not (my_turn and pending)
        b["accept"].visible = my_turn and pending
        b["accept"].enabled = my_turn and pending
        b["bluff"].enabled = my_turn and v["last"] is not None
        b["clear"].enabled = n_sel > 0
        policy_ok = {"always": True, "over_only": phase == "over"}.get(self.new_policy, False)
        b["new"].enabled = policy_ok
        ov = self._end_visible()
        b["again"].visible = ov
        b["menu2"].visible = ov
        b["again"].enabled = policy_ok
        b["again"].text = "Play again" if self.new_policy != "never" else "Waiting for host"

    # ================= mouse / keyboard =================
    def _pick(self, pos):
        pt = QPointF(pos)
        if self._end_visible():
            for k in ("again", "menu2"):
                if self.btns[k].rect.contains(pt):
                    return ("btn", k)
            return None
        for k, b in self.btns.items():
            if k in ("again", "menu2") or not b.visible:
                continue
            if b.rect.contains(pt):
                return ("btn", k)
        if self.v["phase"] == "play":
            for r, rect in self.chip_rects.items():
                if rect.contains(pt):
                    return ("chip", r)
        for poly, key in reversed(self.hit_cards):
            if poly.containsPoint(pt, Qt.OddEvenFill):
                return ("card", key)
        return None

    def _clickable(self, tgt):
        if tgt is None:
            return False
        if tgt[0] == "btn":
            return self.btns[tgt[1]].enabled
        if tgt[0] == "chip":
            return (not self.classic) and self.my_turn()
        return self.v["phase"] == "play"

    def mouseMoveEvent(self, e):
        self.hover = self._pick(e.pos())
        self.setCursor(Qt.PointingHandCursor if self._clickable(self.hover) else Qt.ArrowCursor)

    def leaveEvent(self, e):
        self.hover = None

    def mousePressEvent(self, e):
        tgt = self._pick(e.pos())
        self.hover = tgt
        if tgt is None:
            return
        if tgt[0] == "card":
            if e.button() == Qt.RightButton or (e.modifiers() & Qt.ShiftModifier):
                self.select_rank(tgt[1][0])
            elif e.button() == Qt.LeftButton:
                self.cycle_slot(tgt[1])
        elif tgt[0] == "chip":
            if e.button() == Qt.LeftButton and not self.classic and self.my_turn():
                self.claim = tgt[1]
        elif tgt[0] == "btn" and e.button() == Qt.LeftButton:
            self.pressed = tgt

    def mouseReleaseEvent(self, e):
        tgt, self.pressed = self.pressed, None
        if tgt is None or self._pick(e.pos()) != tgt:
            return
        key = tgt[1]
        if not self.btns[key].enabled:
            return
        if key == "play":
            self.play_clicked()
        elif key == "bluff":
            self.ctrl.bluff()
        elif key == "accept":
            self.ctrl.accept()
        elif key == "clear":
            self.clear_selection()
        elif key in ("new", "again"):
            self.ctrl.new_game()
        elif key in ("menu", "menu2"):
            self.menu_clicked()

    def wheelEvent(self, e):
        if e.pos().x() >= self.panel_x:
            self.hist_scroll -= e.angleDelta().y() * 0.6

    def keyPressEvent(self, e):
        k = e.key()
        if k in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space) and self.btns["play"].enabled and self.btns["play"].visible:
            self.play_clicked()
        elif k in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space) and self.btns["accept"].visible and self.btns["accept"].enabled:
            self.ctrl.accept()
        elif k == Qt.Key_B and self.btns["bluff"].enabled:
            self.ctrl.bluff()
        elif k in (Qt.Key_Escape, Qt.Key_Backspace):
            self.clear_selection()
        else:
            super().keyPressEvent(e)

    # ================= drawing =================
    def paintEvent(self, _):
        p = QPainter(self)
        try:
            p.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing | QPainter.SmoothPixmapTransform)
            p.drawPixmap(0, 0, self._background())
            if self.shake > 0.01:
                a = self.shake * self.shake * 7
                p.translate(random.uniform(-a, a), random.uniform(-a, a))
            self.hit_cards = []
            self._draw_table(p)
            self._draw_glows(p)
            self._draw_opponents(p)
            self._draw_pile(p)
            self._draw_hand(p)
            self._draw_flyers(p)
            self._draw_hud(p)
            self._draw_banner(p)
            self._draw_confetti(p)
            self._draw_panel(p)
            if self._end_visible():
                self._draw_end(p)
        finally:
            p.end()                 # an exception above must never leave the painter active (hard crash)

    def _background(self):
        size = (self.width(), self.height())
        if self._bg is not None and self._bg.size().width() == size[0] and self._bg.size().height() == size[1]:
            return self._bg
        pix = QPixmap(*size)
        p = QPainter(pix)
        p.setRenderHint(QPainter.Antialiasing)
        g = QRadialGradient(QPointF(self.rw / 2, size[1] * 0.42), max(size) * 0.8)
        g.setColorAt(0, QColor("#24406b"))
        g.setColorAt(0.55, QColor("#101c36"))
        g.setColorAt(1, QColor("#060a16"))
        p.fillRect(0, 0, size[0], size[1], QBrush(g))
        rnd = random.Random(3)
        p.setPen(Qt.NoPen)
        for _ in range(26):
            x, y, r = rnd.uniform(0, self.rw), rnd.uniform(0, size[1]), rnd.uniform(14, 70)
            bk = QRadialGradient(QPointF(x, y), r)
            bk.setColorAt(0, QColor(120, 170, 255, 22))
            bk.setColorAt(1, QColor(120, 170, 255, 0))
            p.setBrush(QBrush(bk))
            p.drawEllipse(QPointF(x, y), r, r)
        p.end()
        self._bg = pix
        return pix

    def _draw_table(self, p):
        scr = self.table_outline
        p.save()
        p.setPen(Qt.NoPen)
        for dy, a in ((54, 26), (38, 40), (24, 56), (12, 74)):
            p.setBrush(QColor(0, 0, 0, a))
            p.drawPath(scr.translated(0, dy))
        p.setBrush(QColor("#2b180c"))
        for dy in range(2, 21, 2):
            p.drawPath(scr.translated(0, dy))
        p.restore()
        p.save()
        p.setTransform(self.tr_tab, True)
        p.drawPixmap(QRectF(0, 0, TABLE_W, TABLE_H), Art.table(), QRectF(Art.table().rect()))
        p.restore()

    def _draw_glows(self, p):
        v = self.v
        if v["phase"] != "play":
            return
        i = v["turn"]
        s = self.seats[i]
        pulse = 0.55 + 0.45 * math.sin(self.now * 4.0)
        p.save()
        p.setTransform(self.tr_cen, True)
        cx, cy = (s["u"], s["v"]) if i != self.me() else (0.0, 395.0)
        rad = 230 if i != self.me() else 330
        g = QRadialGradient(QPointF(cx, cy), rad)
        g.setColorAt(0, QColor(255, 214, 79, int(120 * pulse)))
        g.setColorAt(1, QColor(255, 214, 79, 0))
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(g))
        p.drawEllipse(QPointF(cx, cy), rad, rad)
        p.restore()

    def _draw_opponents(self, p):
        order = sorted((i for i in range(self.n) if i != self.me()), key=lambda i: self.seats[i]["v"])
        for i in order:
            m = self.opp_shown[i]
            for j in range(m):
                draw_card_3d(p, self.cam, None, self._fan_pose(i, j, m), shadow=1)

    def _draw_pile(self, p):
        vis = self.vis_pile
        start = max(0, len(vis) - 46)
        for idx, pv in enumerate(vis):
            if idx < start and not (self.reveal and pv.grp == self.reveal["id"]):
                continue
            draw_card_3d(p, self.cam, pv.face, self._pile_pose(pv), shadow=1)
        if self.v["phase"] == "lobby" or (self.v["phase"] == "over" and not vis):
            self._draw_lobby_card(p)

    def _draw_lobby_card(self, p):
        if self.v["phase"] != "lobby":
            return
        ry = self.now * 1.6
        h = 60 + 14 * math.sin(self.now * 2.0)
        draw_card_3d(p, self.cam, (1, 0), (0.0, 0.0, h, 0.0, 0.5, ry, 1.35), shadow=1)

    def _draw_hand(self, p):
        for key in sorted(self.hcards):
            hv = self.hcards[key]
            if self.now < hv.delay:
                continue
            poly = draw_card_3d(p, self.cam, key, hv.pose(), shadow=2)
            self.hit_cards.append((poly, key))
            if hv.sel > 0.03:
                p.setBrush(Qt.NoBrush)
                p.setPen(QPen(QColor(255, 214, 79, int(70 * hv.sel)), 9))
                p.drawPolygon(poly)
                p.setPen(QPen(QColor(255, 214, 79, int(240 * hv.sel)), 3))
                p.drawPolygon(poly)
            elif hv.hov > 0.03:
                p.setBrush(Qt.NoBrush)
                p.setPen(QPen(QColor(255, 255, 255, int(170 * hv.hov)), 2.5))
                p.drawPolygon(poly)
            have = self.hand.get(key, 0)
            k = self.sel.get(key, 0)
            label = None
            if have > 1:
                label = f"{k}/{have}" if k else f"×{have}"
            if label or k:
                pt = poly[1]
                w = 34 if label else 22
                r = QRectF(pt.x() - w - 2, pt.y() + 3, w, 20)
                p.setPen(QPen(QColor(255, 255, 255, 200), 1.2))
                p.setBrush(QColor("#f5b400") if k else QColor(20, 30, 55, 225))
                p.drawRoundedRect(r, 10, 10)
                if label:
                    text_in(p, r, label, 12, "#1b1b1b" if k else "#ffffff")
                else:
                    p.setPen(QPen(QColor("#1b1b1b"), 2.2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
                    c = r.center()
                    p.drawPolyline(QPolygonF([QPointF(c.x() - 5, c.y()), QPointF(c.x() - 1, c.y() + 4),
                                              QPointF(c.x() + 5, c.y() - 4)]))

    def _draw_flyers(self, p):
        for f in self.flyers:
            t = (self.now - f.t0) / f.dur
            if t <= 0:
                continue
            e = ease_io(t)
            a, b = f.a, f.b
            fl = ease_io((t - 0.12) / 0.7)
            pose = (lerp(a[0], b[0], e), lerp(a[1], b[1], e),
                    lerp(a[2], b[2], e) + f.arc * math.sin(math.pi * clamp(t)),
                    lerp_angle(a[3], b[3], e), lerp(a[4], b[4], e), lerp(a[5], b[5], fl), lerp(a[6], b[6], e))
            draw_card_3d(p, self.cam, f.face, pose, shadow=1 if t > 0.5 else 0)

    # ---------------- HUD ----------------
    def _glass(self, p, rect, radius=14, alpha=170, border=None):
        p.setPen(QPen(border or QColor(255, 255, 255, 46), 1.2))
        g = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        g.setColorAt(0, QColor(30, 44, 78, alpha))
        g.setColorAt(1, QColor(8, 14, 30, alpha))
        p.setBrush(QBrush(g))
        p.drawRoundedRect(rect, radius, radius)

    def _draw_hud(self, p):
        v = self.v
        W, H = self.width(), self.height()
        # title
        for i, s in enumerate((0, 1, 2, 3)):
            draw_suit(p, s, 34 + i * 0, 0, 0, "#000") if False else None
        fm = QFontMetrics(font(30, True))
        tw = fm.horizontalAdvance("BLUFF")
        draw_suit(p, 0, 30, 32, 20, "#e8edf7")
        draw_suit(p, 1, 54, 32, 20, "#ff6b6b")
        text_in(p, QRectF(72, 10, tw + 4, 44), "BLUFF", 30, "#ffffff", True, Qt.AlignLeft | Qt.AlignVCenter)
        draw_suit(p, 2, 72 + tw + 22, 32, 20, "#ff6b6b")
        draw_suit(p, 3, 72 + tw + 46, 32, 20, "#e8edf7")
        info = (f"{self.decks} deck{'s' if self.decks > 1 else ''} · "
                f"{'classic order' if self.classic else 'free choice'}")
        text_in(p, QRectF(72 + tw + 70, 10, 300, 44), info, 14, "#9db4d8", False, Qt.AlignLeft | Qt.AlignVCenter)
        # prompt
        my_turn, pending = self.my_turn(), v["pending_win"]
        msg = self._prompt_text(my_turn, pending)
        pw = min(self.rw - 60, 760)
        pr = QRectF((self.rw - pw) / 2, 58, pw, 44)
        pulse = 0.5 + 0.5 * math.sin(self.now * 4)
        border = QColor(255, 214, 79, int(140 + 100 * pulse)) if my_turn else QColor(255, 255, 255, 40)
        self._glass(p, pr, 22, 190, border)
        p.setFont(font(15, True))
        p.setPen(QColor("#fff3c4") if my_turn else QColor("#dfe8f7"))
        p.drawText(pr.adjusted(18, 0, -18, 0), int(Qt.AlignCenter | Qt.TextWordWrap), msg)

        if self.conn_until is not None:
            secs = max(0, int(self.conn_until - time.monotonic()))
            cr = QRectF((self.rw - pw) / 2, 108, pw, 38)
            self._glass(p, cr, 19, 225, QColor(255, 90, 90, 220))
            text_in(p, cr, f"Connection lost: reconnecting…  {secs}s left", 14, "#ffffff")
        # badges
        hand_box = None                      # where my cards are on screen right now
        for poly, _key in self.hit_cards:
            br = poly.boundingRect()
            hand_box = br if hand_box is None else hand_box.united(br)
        for i in sorted(range(self.n), key=lambda i: self.seats[i]["bv"]):
            if i == self.me():
                self._draw_badge(p, (self.rw / 2 + 232 + self.rw - 8) / 2, H - 55, i)
            else:
                s = self.seats[i]
                x, y, _ = self.cam.project(s["bu"], s["bv"], 0)
                k = self._badge_scale(i)
                half = self.BADGE_W * k / 2 + 10
                x = clamp(x, half, self.rw - half)
                if hand_box is not None and (y + self.BADGE_H * k / 2 > hand_box.top()
                                             and y - self.BADGE_H * k / 2 < hand_box.bottom()):
                    # the badge is level with my hand: slide it sideways so it never covers a card
                    if x < hand_box.center().x():
                        x = min(x, hand_box.left() - half - 4)
                    else:
                        x = max(x, hand_box.right() + half + 4)
                    x = clamp(x, half, self.rw - half)
                self._draw_badge(p, x, y, i)

        # claim + pile labels
        if v["phase"] == "play" and not self.reveal:
            self._draw_claim(p)
        # chips
        self._draw_chips(p)
        # buttons
        for b in self.btns.values():
            if b.key not in ("again", "menu2"):
                self._draw_btn(p, b)
        # hint
        text_in(p, QRectF(0, H - 26, self.rw, 20),
                "Click a card to select it   ·   Right-click / Shift+click: every card of that rank   ·   Enter = Play   ·   B = Bluff",
                11, "#7f93b5", False, Qt.AlignCenter)

    def _draw_claim(self, p):
        v = self.v
        x, y, _ = self.cam.project(0, -185, 0)
        last = v["last"]
        if last:
            big = claim_text(last["count"], last["claim"])
            small = f"claimed by {v['names'][last['player']]}"
        else:
            big, small = "New round", "no claim yet"
        r = QRectF(x - 138, y - 30, 276, 60)
        self._glass(p, r, 16, 200, QColor(255, 214, 79, 160) if last else None)
        if last:
            circ = QRectF(r.left() + 10, r.top() + 10, 40, 40)
            g = QLinearGradient(circ.topLeft(), circ.bottomRight())
            g.setColorAt(0, QColor("#ffe082"))
            g.setColorAt(1, QColor("#e0a100"))
            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(g))
            p.drawEllipse(circ)
            text_in(p, circ, rank_short(last["claim"]), 22, "#2a1c00", True, Qt.AlignCenter, "Georgia")
            tx = r.adjusted(58, 0, -8, 0)
        else:
            tx = r
        text_in(p, QRectF(tx.left(), tx.top() + 7, tx.width(), 28), big, 21, "#ffffff",
                True, Qt.AlignLeft | Qt.AlignVCenter if last else Qt.AlignCenter)
        text_in(p, QRectF(tx.left(), tx.top() + 33, tx.width(), 20), small, 12, "#b7c6e3", False,
                Qt.AlignLeft | Qt.AlignVCenter if last else Qt.AlignCenter)
        if v["pile"]:
            x2, y2, _ = self.cam.project(0, 150, 0)
            pr = QRectF(x2 - 46, y2 - 14, 92, 28)
            self._glass(p, pr, 14, 190)
            text_in(p, pr, f"Pile  {v['pile']}", 14, "#ffffff")

    def _badge_scale(self, i):
        """Opponent badges shrink on crowded tables (7+ players); your own badge keeps full size."""
        if i == self.me() or self.n <= 6:
            return 1.0
        return max(0.7, 1.0 - 0.075 * (self.n - 6))

    def _draw_badge(self, p, cx, cy, i):
        k = self._badge_scale(i)
        if k != 1.0:
            p.save()
            p.translate(cx, cy)
            p.scale(k, k)
            self._draw_badge_full(p, 0.0, 0.0, i)
            p.restore()
        else:
            self._draw_badge_full(p, cx, cy, i)

    def _draw_badge_full(self, p, cx, cy, i):
        v = self.v
        name = v["names"][i]
        present = name != WAITING
        active = v["phase"] == "play" and v["turn"] == i
        w, h = self.BADGE_W, self.BADGE_H
        r = QRectF(cx - w / 2, cy - h / 2, w, h)
        pulse = 0.5 + 0.5 * math.sin(self.now * 4)
        if active:
            glow = QRadialGradient(r.center(), w * 0.8)
            glow.setColorAt(0, QColor(255, 214, 79, int(70 + 60 * pulse)))
            glow.setColorAt(1, QColor(255, 214, 79, 0))
            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(glow))
            p.drawEllipse(r.center(), w * 0.8, h * 1.2)
            border = QColor(255, 214, 79, 255)
        else:
            border = QColor(255, 255, 255, 60)
        p.setPen(QPen(border, 2.4 if active else 1.2, Qt.SolidLine if present else Qt.DashLine))
        g = QLinearGradient(r.topLeft(), r.bottomLeft())
        g.setColorAt(0, QColor(40, 56, 94, 215) if active else QColor(26, 38, 68, 200))
        g.setColorAt(1, QColor(10, 16, 34, 225))
        p.setBrush(QBrush(g))
        p.drawRoundedRect(r, h / 2, h / 2)
        av = QRectF(r.left() + 6, r.top() + 6, h - 12, h - 12)
        col = QColor(AVATAR_COLORS[i % len(AVATAR_COLORS)] if present else "#546e7a")
        ag = QLinearGradient(av.topLeft(), av.bottomRight())
        ag.setColorAt(0, col.lighter(130))
        ag.setColorAt(1, col.darker(130))
        p.setPen(QPen(QColor(255, 255, 255, 190), 1.6))
        p.setBrush(QBrush(ag))
        p.drawEllipse(av)
        text_in(p, av, initials(name, i), 17, "#ffffff")
        cnt = v["counts"][i]
        away = {s: t for s, t in self.away_info}
        if v["phase"] == "lobby":
            sub = "joined" if present else "waiting…"
        elif not v.get("active", [True] * self.n)[i]:
            sub = "left the game"
        elif i in away:
            sub = f"reconnecting {max(0, int(away[i] - (self.now - self.away_t0) + 0.99))}s"
        elif active:
            sub = "thinking" + "." * (int(self.now * 2.5) % 4) if i != self.me() else "your turn"
        else:
            sub = f"{cnt} card{'s' if cnt != 1 else ''}"
        tx = r.adjusted(h - 2, 0, -12, 0)
        fm = QFontMetrics(font(14, True))
        text_in(p, QRectF(tx.left(), tx.top() + 7, tx.width(), 22), fm.elidedText(name, Qt.ElideRight, int(tx.width())),
                14, "#ffffff", True, Qt.AlignLeft | Qt.AlignVCenter)
        text_in(p, QRectF(tx.left(), tx.top() + 28, tx.width(), 18), sub, 12,
                "#ffe082" if active else "#9db4d8", False, Qt.AlignLeft | Qt.AlignVCenter)

    def _draw_chips(self, p):
        v = self.v
        W, H = self.width(), self.height()
        enabled = (not self.classic) and self.my_turn()
        tot = self.rank_totals()
        r0 = self.chip_rects[1]
        text_in(p, QRectF(r0.left() - 108, r0.top(), 100, r0.height()), "I CLAIM:", 12, "#9db4d8", True,
                Qt.AlignRight | Qt.AlignVCenter)
        cur = self.claim_rank()
        for r, rect in self.chip_rects.items():
            hov = self.chip_hov[r] if enabled else 0.0
            on = r == cur
            rr = rect.adjusted(0, -3 * hov - (3 if on else 0), 0, -3 * hov - (3 if on else 0))
            p.setPen(QPen(QColor(255, 255, 255, 220 if on else 60), 1.5 if on else 1.0))
            if on:
                g = QLinearGradient(rr.topLeft(), rr.bottomLeft())
                g.setColorAt(0, QColor("#ffe082"))
                g.setColorAt(1, QColor("#f2a900"))
                p.setBrush(QBrush(g))
            else:
                p.setBrush(QColor(255, 255, 255, int(24 + 40 * hov)) if enabled else QColor(0, 0, 0, 70))
            p.drawRoundedRect(rr, 9, 9)
            col = "#2a1c00" if on else ("#ffffff" if enabled else "#6f7f9c")
            text_in(p, rr, rank_short(r), 15, col)
            if tot.get(r):
                dot = QRectF(rr.right() - 11, rr.top() - 6, 16, 16)
                p.setPen(QPen(QColor(255, 255, 255, 200), 1))
                p.setBrush(QColor("#2563eb"))
                p.drawEllipse(dot)
                text_in(p, dot, str(tot[r]), 10, "#ffffff")

    def _draw_btn(self, p, b):
        if not b.visible:
            return
        s = 1.0 - 0.05 * b.press + 0.03 * b.hov
        rr = QRectF(0, 0, b.rect.width() * s, b.rect.height() * s)
        rr.moveCenter(b.rect.center() - QPointF(0, 2.5 * b.hov))
        rad = rr.height() / 2.0
        if b.enabled:
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(0, 0, 0, 90))
            p.drawRoundedRect(rr.translated(0, 4 - 2 * b.press), rad, rad)
            if b.key == "bluff" and self.my_turn():
                pu = 0.5 + 0.5 * math.sin(self.now * 5)
                p.setPen(QPen(QColor(255, 90, 90, int(40 + 110 * pu)), 6))
                p.setBrush(Qt.NoBrush)
                p.drawRoundedRect(rr.adjusted(-4, -4, 4, 4), rad + 4, rad + 4)
        c1, c2 = (b.c1, b.c2) if b.enabled else (QColor("#566075"), QColor("#394254"))
        if b.enabled:
            c1 = c1.lighter(100 + int(22 * b.hov))
        g = QLinearGradient(rr.topLeft(), rr.bottomLeft())
        g.setColorAt(0, c1)
        g.setColorAt(1, c2)
        p.setPen(QPen(QColor(255, 255, 255, 80 if b.enabled else 30), 1.2))
        p.setBrush(QBrush(g))
        p.drawRoundedRect(rr, rad, rad)
        if b.enabled:
            gl = QLinearGradient(rr.topLeft(), QPointF(rr.left(), rr.center().y()))
            gl.setColorAt(0, QColor(255, 255, 255, 80))
            gl.setColorAt(1, QColor(255, 255, 255, 0))
            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(gl))
            p.drawRoundedRect(rr.adjusted(3, 2, -3, -rr.height() / 2), rad - 2, rad - 2)
        text_in(p, rr, b.text, b.px, "#ffffff" if b.enabled else "#8793ab")

    # ---------------- side panel ----------------
    def _hist_rows(self):
        v = self.v
        names = v["names"]
        rows = []
        shown = v["history"][::-1]
        for ix, e in enumerate(shown):
            who = names[e["player"]]
            line1 = f"{who} played {claim_text(e['count'], e['claim'])}"
            verdict = e.get("verdict")
            tag, tagc = None, "#9db4d8"
            bg, border, c2 = QColor(255, 255, 255, 14), QColor(255, 255, 255, 26), "#8fa6c8"
            if verdict in ("lie", "true"):
                cards = sorted(tuple(c) for c in e["revealed"])
                sh = " ".join(card_str(c) for c in cards[:5]) + (f" +{len(cards) - 5}" if len(cards) > 5 else "")
                line2 = f"{sh}  ·  pile → {names[e['taker']]}"
                if verdict == "lie":
                    tag, tagc, c2 = "LIE", "#ff6b6b", "#ffc9c9"
                    bg, border = QColor(183, 28, 28, 80), QColor("#ef5350")
                else:
                    tag, tagc, c2 = "TRUE", "#5fe08a", "#c3f0d0"
                    bg, border = QColor(27, 110, 52, 90), QColor("#66bb6a")
            elif ix == 0 and v["phase"] == "play" and v["last"] is not None:
                turn = v["turn"]
                line2 = f"waiting for {'your' if turn == v['me'] else names[turn] + chr(39) + 's'} decision…"
                tag, tagc, c2 = "…", "#ffd54f", "#fff3c4"
                bg, border = QColor(255, 213, 79, 28), QColor("#ffd54f")
            elif ix == 0 and v["phase"] == "over":
                line2, c2 = "nobody called Bluff", "#fff3c4"
                bg, border = QColor(255, 213, 79, 28), QColor("#ffd54f")
            else:
                line2 = "accepted — no challenge"
            rows.append((e["player"], initials(who, e["player"]), line1, line2, c2, tag, tagc, bg, border))
        return rows

    def _draw_panel(self, p):
        v = self.v
        W, H = self.width(), self.height()
        x = self.panel_x
        panel = QRectF(x + 2, 14, W - x - 16, H - 28)
        self._glass(p, panel, 20, 175)
        text_in(p, QRectF(panel.left() + 18, panel.top() + 14, panel.width() - 36, 20), "GAME", 12, "#7f93b5",
                True, Qt.AlignLeft | Qt.AlignVCenter)
        lines = [(f"{52 * self.decks} cards · each rank ×{4 * self.decks}", False),
                 ("Rank rule: classic order" if self.classic else "Rank rule: free choice", False)]
        if self.classic and v["phase"] == "play":
            lines.append((f"You must claim: {RANK_NAMES[v['req']][1]}", True))
        if v["phase"] == "play" and v.get("plays_left") is not None:
            lines.append((f"Plays left: {max(0, v['plays_left'])}  (fewest cards wins)", True))
        for i, (t, hi) in enumerate(lines):
            text_in(p, QRectF(panel.left() + 18, panel.top() + 38 + i * 21, panel.width() - 36, 20), t, 13,
                    "#ffe082" if hi else "#d5e0f5", hi, Qt.AlignLeft | Qt.AlignVCenter)
        y0 = panel.top() + 38 + len(lines) * 21 + 14
        p.setPen(QPen(QColor(255, 255, 255, 30), 1))
        p.drawLine(QPointF(panel.left() + 16, y0), QPointF(panel.right() - 16, y0))
        text_in(p, QRectF(panel.left() + 18, y0 + 8, panel.width() - 36, 20), "RECENT PLAYS", 12, "#7f93b5", True,
                Qt.AlignLeft | Qt.AlignVCenter)
        area = QRectF(panel.left() + 10, y0 + 34, panel.width() - 20, panel.bottom() - y0 - 46)
        rows = self._hist_rows()
        rh, gap = 58.0, 6.0
        total = len(rows) * (rh + gap)
        self.hist_scroll = clamp(self.hist_scroll, 0, max(0.0, total - area.height()))
        p.save()
        p.setClipRect(area)
        if not rows:
            text_in(p, area.adjusted(0, 10, 0, 0), "No plays yet.\nThe first player starts the round.", 13,
                    "#6f83a6", False, Qt.AlignHCenter | Qt.AlignTop)
        for k, (idx, letter, l1, l2, c2, tag, tagc, bg, border) in enumerate(rows):
            top = area.top() + k * (rh + gap) - self.hist_scroll
            if top > area.bottom() or top + rh < area.top():
                continue
            rr = QRectF(area.left(), top, area.width() - 12, rh)
            p.setPen(QPen(border, 1.4))
            p.setBrush(bg)
            p.drawRoundedRect(rr, 12, 12)
            av = QRectF(rr.left() + 8, rr.top() + 14, 30, 30)
            col = QColor(AVATAR_COLORS[idx % len(AVATAR_COLORS)])
            p.setPen(QPen(QColor(255, 255, 255, 170), 1.2))
            p.setBrush(col)
            p.drawEllipse(av)
            text_in(p, av, letter, 13, "#ffffff")
            tw = 0
            if tag:
                tw = 42
                tr = QRectF(rr.right() - tw - 6, rr.top() + 8, tw, 20)
                tc = QColor(tagc)
                p.setPen(QPen(tc, 1.2))
                fill = QColor(tc)
                fill.setAlpha(46)
                p.setBrush(fill)
                p.drawRoundedRect(tr, 10, 10)
                text_in(p, tr, tag, 11, tagc)
            fm1 = QFontMetrics(font(12, True))
            fm2 = QFontMetrics(font(11, False))
            wtxt = int(rr.width() - 50 - tw - 8)
            text_in(p, QRectF(rr.left() + 46, rr.top() + 7, wtxt, 22), fm1.elidedText(l1, Qt.ElideRight, wtxt), 12,
                    "#ffffff", True, Qt.AlignLeft | Qt.AlignVCenter)
            wl2 = int(rr.width() - 56)
            text_in(p, QRectF(rr.left() + 46, rr.top() + 30, wl2, 22), fm2.elidedText(l2, Qt.ElideRight, wl2), 11,
                    c2, False, Qt.AlignLeft | Qt.AlignVCenter)
        p.restore()
        if total > area.height():
            frac = area.height() / total
            th = max(30.0, area.height() * frac)
            ty = area.top() + (area.height() - th) * (self.hist_scroll / max(1.0, total - area.height()))
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(255, 255, 255, 70))
            p.drawRoundedRect(QRectF(area.right() - 5, ty, 5, th), 2.5, 2.5)

    # ---------------- overlays ----------------
    def _draw_banner(self, p):
        b = self.banner
        if not b:
            return
        t = self.now - b["t0"]
        pop = ease_back(t / 0.35)
        fade = clamp((2.2 - t) / 0.4)
        x, _, _ = self.cam.project(0, 0, 0)
        y = self.cam.project(0, -6, 60)[1] - 118
        col = QColor("#ff5a5a" if b["lie"] else "#4ade80")
        path = QPainterPath()
        f = font(92, True)
        path.addText(0, 0, f, b["text"])
        br = path.boundingRect()
        p.save()
        p.setOpacity(fade)
        p.translate(x, y)
        p.scale(pop, pop)
        p.translate(-br.center().x(), -br.center().y())
        p.setPen(Qt.NoPen)
        for w, a in ((22, 26), (14, 46), (8, 90)):
            c = QColor(col)
            c.setAlpha(a)
            p.setPen(QPen(c, w, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            p.setBrush(Qt.NoBrush)
            p.drawPath(path)
        p.setPen(QPen(QColor(0, 0, 0, 200), 7, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.setBrush(col)
        p.drawPath(path)
        p.restore()
        p.save()
        p.setOpacity(fade)
        sub = QRectF(x - 330, y + 212, 660, 34)
        self._glass(p, sub, 17, 215, col)
        text_in(p, sub, b["sub"], 15, "#ffffff")
        p.restore()

    def _draw_confetti(self, p):
        p.setPen(Qt.NoPen)
        for x, y, _vx, _vy, rot, _vr, col, w, h in self.confetti:
            p.save()
            p.translate(x, y)
            p.rotate(math.degrees(rot))
            p.scale(1.0, 0.35 + 0.65 * abs(math.cos(rot * 1.7)))
            p.setBrush(QColor(col))
            p.drawRect(QRectF(-w / 2, -h / 2, w, h))
            p.restore()

    def _draw_end(self, p):
        v = self.v
        W, H = self.width(), self.height()
        t = self.now - self.end_t0
        p.fillRect(0, 0, self.panel_x, H, QColor(4, 8, 20, int(150 * clamp(t / 0.4))))
        win = v["end_msg"].startswith("You win")
        pop = ease_back(t / 0.45)
        cx, cy = self.rw / 2, H / 2 - 30
        card = QRectF(cx - 330, cy - 120, 660, 250)
        p.save()
        p.translate(cx, cy)
        p.scale(pop, pop)
        p.translate(-cx, -cy)
        col = QColor("#ffd54f" if win else "#9db4d8")
        self._glass(p, card, 28, 235, col)
        text_in(p, QRectF(card.left(), card.top() + 24, card.width(), 40), "VICTORY" if win else "GAME OVER", 18,
                "#ffd54f" if win else "#7f93b5", True, Qt.AlignCenter)
        p.setFont(font(40, True))
        p.setPen(QColor("#ffffff"))
        p.drawText(card.adjusted(26, 60, -26, -70), int(Qt.AlignCenter | Qt.TextWordWrap), v["end_msg"])
        if v.get("end_sub"):
            text_in(p, QRectF(card.left() + 26, cy + 38, card.width() - 52, 26), v["end_sub"], 15, "#9db4d8", False)
        p.restore()
        for k in ("again", "menu2"):
            self._draw_btn(p, self.btns[k])

    # ---------------- text ----------------
    def _prompt_text(self, my_turn, pending):
        v = self.v
        names = v["names"]
        if v["phase"] == "lobby":
            joined = sum(1 for nm in names if nm != WAITING)
            hint = self.lobby_hint or "Cards are dealt as soon as everyone has joined."
            return f"Waiting for players ({joined}/{self.n}). {hint}"
        if v["phase"] == "over":
            return v["end_msg"]
        last = v["last"]
        if self.conn_until is not None:
            return "Connection lost. Trying to reconnect…"
        if self.paused():
            return self._away_text()
        if my_turn:
            if pending and v.get("final"):
                return (f"Play limit reached! {names[last['player']]} made the last play. "
                        f"Call Bluff!, or Accept: the player with the fewest cards wins.")
            if pending:
                return (f"{names[last['player']]} played their last cards! "
                        f"Call Bluff!, or Accept and let them win.")
            if last:
                what = claim_text(last["count"], last["claim"])
                return (f"Your turn. {names[last['player']]} claims {what}. Believe it? "
                        f"Call Bluff!, or play your own cards.")
            return "Your turn - you start the round. Select cards, pick a claim, then Play."
        who = names[v["turn"]]
        if last:
            return f"{who} is thinking: call Bluff on {names[last['player']]}, or play?"
        return f"{who} is starting the round…"



# ====================================================================== controllers
class LocalController:
    """You vs CPU bots, everything in this program."""

    def __init__(self, players, decks, classic, name=""):
        self.go_menu = False
        self.ok = True
        self.token = 0
        players = max(3, players)                 # with CPU bots, at least 3 players
        names = ["You"] + [f"Bot {i}" for i in range(1, players)]
        self.engine = Engine(names, decks, classic)
        self.window = BluffWindow(self, players, 0, decks, classic, "always", "vs CPU")

    def start(self):
        self.new_game()
        self.window.show()

    def sync(self):
        self.window.set_view(self.engine.view_for(0))
        self.token += 1
        if self.engine.phase == "play" and self.engine.turn != 0:
            QTimer.singleShot(BOT_DELAY_MS, lambda t=self.token: self._bot_timer(t))

    def _bot_timer(self, token):
        if token == self.token and self.engine.phase == "play" and self.engine.turn != 0:
            self.engine.bot_step()
            self.sync()

    def play(self, cards, claim):
        if not self.engine.play(0, cards, claim):
            self.sync()

    def bluff(self):
        if not self.engine.challenge(0):
            self.sync()

    def accept(self):
        if not self.engine.accept(0):
            self.sync()

    def new_game(self):
        self.engine.deal()
        self.sync()

    def shutdown(self):
        self.token += 1


def read_lines(sock):
    """Yield every complete JSON message waiting on the socket."""
    while sock.canReadLine():
        line = bytes(sock.readLine()).decode(errors="ignore").strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except ValueError:
            continue
        if isinstance(msg, dict):
            yield msg


def send_json(sock, msg):
    if sock is not None and sock.state() == QAbstractSocket.ConnectedState:
        sock.write((json.dumps(msg) + "\n").encode())
        sock.flush()


class HostController:
    """Hosts the game. Holds the only copy of every hand and sends each friend a private view."""

    def __init__(self, players, decks, classic, name=""):
        self.go_menu = False
        self.ok = True
        self.closing = False
        self.players = players
        self.engine = Engine([name or "Host"] + [None] * (players - 1), decks, classic)
        self.socks = {}                  # seat -> socket
        self.seat_of = {}                # socket -> seat
        self.strangers = set()           # sockets that connected mid-game and may be a returning player
        self.tokens = {}                 # seat -> secret that proves a returning player is the same person
        self.joined = {0}                # seats whose player has introduced themselves
        self.away_timer = QTimer()
        self.away_timer.setInterval(500)
        self.away_timer.timeout.connect(self._check_away)
        self.window = BluffWindow(self, players, 0, decks, classic, "over_only", "Host")
        self.server = QTcpServer()
        if not self.server.listen(QHostAddress.Any, PORT):
            QMessageBox.critical(None, "Bluff", f"Cannot start the game on port {PORT}:\n"
                                                f"{self.server.errorString()}")
            self.ok = False
            return
        self.server.newConnection.connect(self._on_new_connection)
        ips = " / ".join(local_ips())
        self.window.lobby_hint = f"Friends: choose Join Game and enter IP  {ips}"
        print("Tell your friends this IP:", ips, f"(port {PORT})")

    def start(self):
        self.sync()
        self.window.show()

    # ---------- network ----------
    def _on_new_connection(self):
        while self.server.hasPendingConnections():
            sock = self.server.nextPendingConnection()
            sock.setSocketOption(QAbstractSocket.KeepAliveOption, 1)     # notice dead links sooner
            sock.readyRead.connect(lambda s=sock: self._read(s))
            sock.disconnected.connect(lambda s=sock: self._dropped(s))
            free = [s for s in range(1, self.players) if s not in self.socks]
            if self.engine.phase == "lobby" and free:
                seat = free[0]
                self.socks[seat] = sock
                self.seat_of[sock] = seat
            elif self.engine.phase == "play":
                self.strangers.add(sock)             # maybe a player coming back: wait for 'rejoin'
            else:
                send_json(sock, {"type": "error", "msg": "This game is full or already started."})
                sock.disconnectFromHost()

    def _read(self, sock):
        for msg in read_lines(sock):
            self._handle(sock, msg)

    def _try_rejoin(self, sock, msg):
        token = str(msg.get("token", ""))
        seat = next((s for s, t in self.tokens.items() if t == token and s in self.joined), None)
        if seat is None or self.engine.phase != "play" or not self.engine.active[seat]:
            return False
        old = self.socks.get(seat)
        if old is not None and old is not sock:      # the host had not noticed the old link was dead
            self.seat_of.pop(old, None)
            old.abort()
        self.socks[seat] = sock
        self.seat_of[sock] = seat
        self.engine.away.pop(seat, None)
        if not self.engine.away:
            self.away_timer.stop()
        send_json(sock, {"type": "welcome", "index": seat, "n": self.players, "token": token,
                         "decks": self.engine.decks, "classic": self.engine.classic})
        self.sync()
        return True

    def _handle(self, sock, msg):
        t = msg.get("type")
        seat = self.seat_of.get(sock)
        if seat is None:
            if sock in self.strangers:
                self.strangers.discard(sock)
                if not (t == "rejoin" and self._try_rejoin(sock, msg)):
                    send_json(sock, {"type": "error", "msg": "You are no longer part of this game."})
                    sock.disconnectFromHost()
            return
        if t == "leave":
            self._dropped(sock, immediate=True)
            return
        if t == "hello" and seat not in self.joined and self.engine.phase == "lobby":
            name = str(msg.get("name", "")).strip()[:14] or f"Player {seat + 1}"
            taken = {n.lower() for n in self.engine.names if n} | {"you", WAITING.lower()}
            while name.lower() in taken:
                name += " 2"
            self.engine.names[seat] = name
            self.joined.add(seat)
            self.tokens[seat] = secrets.token_hex(8)
            send_json(sock, {"type": "welcome", "index": seat, "n": self.players, "token": self.tokens[seat],
                             "decks": self.engine.decks, "classic": self.engine.classic})
            if len(self.joined) == self.players:
                self.engine.deal()               # everyone is here: shuffle and deal
            self.sync()
        elif seat in self.joined and self.engine.phase == "play":
            err = None
            if t == "play":
                err = self.engine.play(seat, msg.get("cards") or [], msg.get("claim"))
            elif t == "bluff":
                err = self.engine.challenge(seat)
            elif t == "accept":
                err = self.engine.accept(seat)
            else:
                return
            if err is None:
                self.sync()

    # ---------- disconnects ----------
    def _dropped(self, sock, immediate=False):
        self.strangers.discard(sock)
        if self.closing:
            return
        seat = self.seat_of.pop(sock, None)
        if seat is None:
            return
        if self.socks.get(seat) is sock:
            self.socks.pop(seat, None)
        if self.engine.phase == "play" and seat in self.joined:
            if immediate:
                self._remove_now(seat)               # they chose to leave: no waiting
            else:
                self.engine.away[seat] = time.monotonic() + RECONNECT_S   # pause and wait for them
                if not self.away_timer.isActive():
                    self.away_timer.start()
                self.sync()
            return
        self.joined.discard(seat)
        self.tokens.pop(seat, None)
        self.engine.names[seat] = None
        self.sync()

    def _remove_now(self, seat):
        self.engine.remove_player(seat)
        self.joined.discard(seat)
        self.tokens.pop(seat, None)
        self.socks.pop(seat, None)
        if not self.engine.away:
            self.away_timer.stop()
        self.sync()

    def _check_away(self):
        now = time.monotonic()
        if self.engine.phase != "play":
            self.engine.away.clear()
        for seat, deadline in list(self.engine.away.items()):
            if now >= deadline:
                self._remove_now(seat)               # time is up: they are out
        if not self.engine.away:
            self.away_timer.stop()

    def sync(self):
        self.window.set_view(self.engine.view_for(0))
        for seat, sock in list(self.socks.items()):
            if seat in self.joined:
                send_json(sock, {"type": "view", "view": self.engine.view_for(seat)})

    # ---------- your own actions ----------
    def play(self, cards, claim):
        if not self.engine.play(0, cards, claim):
            self.sync()

    def bluff(self):
        if not self.engine.challenge(0):
            self.sync()

    def accept(self):
        if not self.engine.accept(0):
            self.sync()

    def new_game(self):
        if len(self.joined) == self.players:
            self.engine.deal()
        else:                                    # someone left: wait for a replacement
            for s in range(1, self.players):
                if s not in self.joined:
                    self.engine.names[s] = None
            self.engine.reset()
        self.sync()

    def shutdown(self):
        self.closing = True
        self.away_timer.stop()
        for sock in list(self.socks.values()) + list(self.strangers):
            send_json(sock, {"type": "closed"})
            if sock.state() == QAbstractSocket.ConnectedState:
                sock.waitForBytesWritten(200)
            sock.abort()
        self.server.close()


class ClientController:
    """Joins a friend's game. Only ever receives its own private view."""

    def __init__(self, ip, name):
        self.go_menu = False
        self.ok = True
        self.closing = False
        self.ended = False               # the host told us the game is over: do not reconnect
        self.window = None
        self.ip, self.name = ip, name
        self.token = None                # given by the host; lets us take our seat back
        self.reconnecting = False
        self.give_up_at = 0.0
        self._retry_pending = False
        self._aborting = False
        self.sock = QTcpSocket()
        self.sock.connected.connect(self._on_connected)
        self.sock.readyRead.connect(self._read)
        self.sock.disconnected.connect(self._disconnected)
        err = getattr(self.sock, "errorOccurred", None) or self.sock.error
        err.connect(self._on_error)
        self.sock.connectToHost(ip, PORT)

    def start(self):
        pass                                    # the window appears once the host welcomes us

    def _on_connected(self):
        if self.reconnecting and self.token:
            send_json(self.sock, {"type": "rejoin", "token": self.token})
        else:
            send_json(self.sock, {"type": "hello", "name": self.name})

    def _fail(self, text):
        if self.closing:
            return
        self.closing = True
        self.go_menu = True
        QMessageBox.critical(None, "Bluff", text)
        if self.window is not None:
            self.window.close()
        QApplication.quit()

    # ---------- reconnecting ----------
    def _begin_reconnect(self):
        if not self.reconnecting:
            self.reconnecting = True
            self.give_up_at = time.monotonic() + RECONNECT_S
            self.window.conn_until = self.give_up_at
        self._schedule_retry()

    def _schedule_retry(self):
        if self._retry_pending or self.closing:
            return
        self._retry_pending = True
        QTimer.singleShot(1500, self._retry)

    def _retry(self):
        self._retry_pending = False
        if self.closing or self.ended or not self.reconnecting:
            return
        if time.monotonic() >= self.give_up_at:
            self._give_up("You were removed from the game.")
            return
        if self.sock.state() != QAbstractSocket.UnconnectedState:
            self._aborting = True
            self.sock.abort()
            self._aborting = False
        self.sock.connectToHost(self.ip, PORT)

    def _give_up(self, text):
        self.reconnecting = False
        self.ended = True
        if self.window is not None:
            self.window.show_notice(text)

    def _on_error(self, *_):
        if self.window is None:
            self._fail("Could not connect to the host. Check the IP, and that the host has "
                       "already pressed Host Game.")
        elif self.reconnecting:
            self._schedule_retry()

    def _disconnected(self):
        if self.closing or self._aborting or self.ended:
            return
        if self.window is None:
            self._fail("Connection lost.")
        elif self.token and self.window.v["phase"] == "play":
            self._begin_reconnect()              # the game waits for us for a minute
        else:
            self.ended = True
            self.window.show_notice("Disconnected from the host.")

    def _read(self):
        for msg in read_lines(self.sock):
            t = msg.get("type")
            if t == "welcome":
                self.token = msg.get("token", self.token)
                if self.window is None:
                    self.window = BluffWindow(self, int(msg["n"]), int(msg["index"]), int(msg["decks"]),
                                              bool(msg["classic"]), "never", "Guest")
                    self.window.lobby_hint = "The host deals as soon as everyone has joined."
                    self.window.show()
                else:                            # we are back in our seat
                    self.reconnecting = False
                    self.window.conn_until = None
            elif t == "view" and self.window is not None:
                self.reconnecting = False
                self.window.conn_until = None
                self.window.set_view(msg["view"])
            elif t == "closed":
                self.ended = True
                self.reconnecting = False
                if self.window is not None and self.window.v["phase"] != "over":
                    self.window.show_notice("The host closed the game.")
            elif t == "error":
                if self.window is None:
                    self._fail(str(msg.get("msg", "Error.")))
                    return
                self._give_up(str(msg.get("msg", "Error.")))

    # ---------- your actions are only requests; the host decides ----------
    def play(self, cards, claim):
        send_json(self.sock, {"type": "play", "cards": [list(c) for c in cards], "claim": claim})

    def bluff(self):
        send_json(self.sock, {"type": "bluff"})

    def accept(self):
        send_json(self.sock, {"type": "accept"})

    def new_game(self):
        pass                                    # only the host can start a new deal

    def shutdown(self):
        self.closing = True
        send_json(self.sock, {"type": "leave"})  # tell the host we are leaving on purpose: no waiting
        if self.sock.state() == QAbstractSocket.ConnectedState:
            self.sock.waitForBytesWritten(200)
        self.sock.abort()


# ====================================================================== main
def main():
    _preflight_display()
    app = QApplication(sys.argv)
    while True:
        dlg = StartDialog()
        if dlg.exec_() != QDialog.Accepted:
            break
        if dlg.mode == "cpu":
            ctrl = LocalController(dlg.players, dlg.decks, dlg.classic, dlg.name)
        elif dlg.mode == "host":
            ctrl = HostController(dlg.players, dlg.decks, dlg.classic, dlg.name)
        else:
            ctrl = ClientController(dlg.ip, dlg.name)
        if not ctrl.ok:
            continue
        ctrl.start()
        app.exec_()                 # returns when the game window is closed
        ctrl.shutdown()
        if not ctrl.go_menu:
            break
    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        import traceback
        _fatal("Bluff crashed:\n\n" + traceback.format_exc())
