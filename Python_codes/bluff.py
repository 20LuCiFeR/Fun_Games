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

Install:  automatic (if PyQt5 is missing, the script installs it with pip)
Run:      python bluff.py
"""

import json
import random
import sys
from collections import Counter


def _ensure_pyqt5():
    """Install PyQt5 automatically if it is missing."""
    try:
        import PyQt5  # noqa: F401
        return
    except ImportError:
        pass
    import importlib
    import site
    import subprocess

    print("PyQt5 not found, installing it (one-time only)...")
    attempts = (
        ["install", "PyQt5"],
        ["install", "--user", "PyQt5"],
        ["install", "--break-system-packages", "PyQt5"],   # needed on newer Linux systems
    )
    for args in attempts:
        try:
            subprocess.check_call([sys.executable, "-m", "pip"] + args)
            break
        except (subprocess.CalledProcessError, OSError):
            continue
    else:
        sys.exit("Could not install PyQt5. Check your internet or run: pip install PyQt5")

    importlib.invalidate_caches()
    user_site = site.getusersitepackages()
    if user_site not in sys.path:
        sys.path.append(user_site)
    try:
        import PyQt5  # noqa: F401
    except ImportError:
        sys.exit("PyQt5 was installed but could not be loaded. Please run the script again.")


_ensure_pyqt5()

from PyQt5.QtCore import QRectF, Qt, QTimer
from PyQt5.QtGui import QColor, QFont, QPainter, QPen
from PyQt5.QtNetwork import (
    QAbstractSocket, QHostAddress, QNetworkInterface, QTcpServer, QTcpSocket,
)
from PyQt5.QtWidgets import (
    QApplication, QButtonGroup, QCheckBox, QDialog, QFrame, QGridLayout, QHBoxLayout,
    QLabel, QLayout, QLineEdit, QMessageBox, QPushButton, QSizePolicy, QSpinBox,
    QScrollArea, QVBoxLayout, QWidget,
)

PORT = 5566
BOT_DELAY_MS = 2000          # pause before every bot move
HISTORY_VISIBLE = 4          # plays visible without scrolling
HISTORY_MAX = 60             # how many past plays can be scrolled through
WAITING = "Waiting…"

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

    # ---------- actions (each returns None on success, or an error text) ----------
    def play(self, p, cards, claim):
        if self.phase != "play":
            return "The game is not running."
        if p != self.turn:
            return "It is not your turn."
        if self.pending_win():
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
        self.turn = (p + 1) % self.n
        if self.classic:
            self.req = self.req % 13 + 1
        return None

    def challenge(self, p):
        """Only the player whose turn is next may call Bluff."""
        if self.phase != "play" or p != self.turn or self.last is None:
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
        else:
            self.turn = loser                       # whoever picked up the pile starts the next round
        return None

    def accept(self, p):
        if self.phase != "play" or p != self.turn or not self.pending_win():
            return "Nothing to accept."
        self.winner = self.last["player"]
        self.phase = "over"
        return None

    def abort(self, msg):
        self.phase = "over"
        self.winner = None
        self.abort_msg = msg

    # ---------- what one player is allowed to see ----------
    def view_for(self, p):
        names = [("You" if i == p else (nm or WAITING)) for i, nm in enumerate(self.names)]
        if self.phase != "over":
            end_msg = ""
        elif self.abort_msg:
            end_msg = self.abort_msg
        elif self.winner == p:
            end_msg = "You win! 🎉"
        else:
            end_msg = f"{names[self.winner]} wins 😅"
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
            "end_msg": end_msg, "pending_win": self.pending_win(),
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


# ====================================================================== custom widgets
class PileWidget(QWidget):
    """Small face-down pile icon with the number of cards in it."""

    def __init__(self):
        super().__init__()
        self.count = 0
        self.setFixedSize(92, 60)

    def set_count(self, n):
        self.count = n
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        cw, ch = 24, 34
        cx, cy = self.width() / 2, 22
        if self.count == 0:
            p.setPen(QPen(QColor(255, 255, 255, 120), 1.5, Qt.DashLine))
            p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(QRectF(cx - cw / 2, cy - ch / 2, cw, ch), 4, 4)
        else:
            layers = min(5, 1 + self.count // 4)
            for i in range(layers):
                p.save()
                p.translate(cx, cy - i * 1.2)
                p.rotate(((i * 37) % 17) - 8)
                rect = QRectF(-cw / 2, -ch / 2, cw, ch)
                p.setPen(QPen(QColor("white"), 1.5))
                p.setBrush(QColor("#1565c0"))
                p.drawRoundedRect(rect, 4, 4)
                if i == layers - 1:
                    p.setPen(QPen(QColor(255, 255, 255, 110), 1))
                    p.setBrush(Qt.NoBrush)
                    p.drawRoundedRect(rect.adjusted(3, 3, -3, -3), 2, 2)
                p.restore()
        p.setPen(QColor("white"))
        p.setFont(QFont(self.font().family(), 9, QFont.Bold))
        p.drawText(QRectF(0, 44, self.width(), 14), Qt.AlignCenter, f"Pile: {self.count}")


class ClaimCards(QWidget):
    """Little face-up cards showing the CLAIMED rank: '3 Fives' is drawn as three small '5' cards."""

    def __init__(self):
        super().__init__()
        self.rank = 0
        self.count = 0
        self.tint = "#90a4ae"
        self.setFixedSize(92, 28)

    def set_claim(self, rank, count, tint="#90a4ae"):
        self.rank, self.count, self.tint = rank, count, tint
        self.update()

    def paintEvent(self, _):
        if self.count <= 0:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        shown = min(self.count, 4)
        label = rank_short(self.rank)
        p.setFont(QFont(self.font().family(), 8 if len(label) > 1 else 9, QFont.Bold))
        for i in range(shown):
            rect = QRectF(2 + i * 12, 2, 20, 24)
            p.setPen(QPen(QColor(self.tint), 1.5))
            p.setBrush(QColor("white"))
            p.drawRoundedRect(rect, 3, 3)
            p.setPen(QColor("#212121"))
            p.drawText(rect.adjusted(3, 0, 0, 0), Qt.AlignVCenter | Qt.AlignLeft, label)
        p.setPen(QColor("white"))
        p.setFont(QFont(self.font().family(), 9, QFont.Bold))
        p.drawText(QRectF(2 + (shown - 1) * 12 + 25, 0, 34, 28), Qt.AlignVCenter | Qt.AlignLeft,
                   f"×{self.count}")


class PlayerBadge(QFrame):
    def __init__(self, idx):
        super().__init__()
        self.idx = idx
        lay = QHBoxLayout(self)
        lay.setContentsMargins(5, 3, 6, 3)
        lay.setSpacing(5)
        self.avatar = QLabel()
        self.avatar.setAlignment(Qt.AlignCenter)
        self.avatar.setFixedSize(24, 24)
        lay.addWidget(self.avatar)
        col = QVBoxLayout()
        col.setSpacing(0)
        self.name = QLabel()
        self.name.setStyleSheet("font-weight: bold; font-size: 11px;")
        self.count = QLabel()
        self.count.setStyleSheet("font-size: 10px; color: #cfd8dc;")
        col.addWidget(self.name)
        col.addWidget(self.count)
        lay.addLayout(col)
        lay.addStretch(1)

    def set_state(self, name, count_text, active, present=True):
        self.name.setText(name)
        self.count.setText(count_text)
        self.avatar.setText(initials(name, self.idx))
        style = avatar_style(self.idx, 24)
        if not present:
            style = style.replace(AVATAR_COLORS[self.idx % len(AVATAR_COLORS)], "#546e7a")
        self.avatar.setStyleSheet(style)
        if active:
            self.setStyleSheet("PlayerBadge { background-color: rgba(255, 213, 79, 70);"
                               "border: 2px solid #ffd54f; border-radius: 8px; }")
        else:
            self.setStyleSheet("PlayerBadge { background-color: rgba(0, 0, 0, 70);"
                               "border: 2px solid rgba(255, 255, 255, 40); border-radius: 8px; }")


class HistoryRow(QFrame):
    def __init__(self):
        super().__init__()
        self.setFixedHeight(34)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(5, 2, 5, 2)
        lay.setSpacing(5)
        self.avatar = QLabel()
        self.avatar.setFixedSize(22, 22)
        self.avatar.setAlignment(Qt.AlignCenter)
        lay.addWidget(self.avatar)
        self.text = QLabel()
        self.text.setTextFormat(Qt.RichText)
        self.text.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        lay.addWidget(self.text)
        self.cards = ClaimCards()
        lay.addWidget(self.cards)

    def clear(self):
        self.avatar.setText("")
        self.avatar.setStyleSheet("background: transparent;")
        self.text.setText('<span style="color:#7aa68a;">&nbsp;</span>')
        self.cards.set_claim(0, 0)
        self.setStyleSheet("HistoryRow { background-color: rgba(0, 0, 0, 25);"
                           "border: 1px dashed rgba(255, 255, 255, 40); border-radius: 6px; }")

    def set_data(self, idx, letter, line1, line2, rank, count, tint, bg, border):
        self.avatar.setText(letter)
        self.avatar.setStyleSheet(avatar_style(idx, 22))
        self.text.setText(f"<div style='font-size:11px;'>{line1}</div>"
                          f"<div style='font-size:9px;'>{line2}</div>")
        self.cards.set_claim(rank, count, tint)
        self.setStyleSheet(f"HistoryRow {{ background-color: {bg}; border: 2px solid {border};"
                           f"border-radius: 6px; }}")


# ====================================================================== start dialog
class StartDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Bluff")
        self.mode = None
        self.players = 4
        self.decks = 1
        self.classic = False
        self.name = ""
        self.ip = ""
        lay = QVBoxLayout(self)
        lay.setSpacing(8)

        grid = QGridLayout()
        grid.addWidget(QLabel("Your name:"), 0, 0)
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("(optional)")
        self.name_edit.setMaxLength(14)
        grid.addWidget(self.name_edit, 0, 1)
        grid.addWidget(QLabel("Total players:"), 1, 0)
        self.spin_players = QSpinBox()
        self.spin_players.setRange(2, 6)
        self.spin_players.setValue(4)
        grid.addWidget(self.spin_players, 1, 1)
        grid.addWidget(QLabel("Number of decks:"), 2, 0)
        self.spin_decks = QSpinBox()
        self.spin_decks.setRange(1, 4)
        self.spin_decks.setValue(1)
        grid.addWidget(self.spin_decks, 2, 1)
        lay.addLayout(grid)

        self.info = QLabel()
        self.info.setStyleSheet("color: #455a64;")
        lay.addWidget(self.info)
        self.spin_players.valueChanged.connect(self._update_info)
        self.spin_decks.valueChanged.connect(self._update_info)

        self.chk = QCheckBox("Classic rank order (A, 2, 3 ... K) instead of free choice")
        lay.addWidget(self.chk)

        def button(text, mode):
            b = QPushButton(text)
            b.setMinimumHeight(34)
            b.clicked.connect(lambda: self._choose(mode))
            lay.addWidget(b)

        button("Play vs CPU  (you + bots)", "cpu")
        button("Host Game  (friends join you)", "host")
        sep = QLabel("To join a friend's game, type their IP:")
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


# ====================================================================== game window (pure display)
def blank_view(n, me, decks, classic):
    names = [WAITING] * n
    names[me] = "You"
    return {"phase": "lobby", "names": names, "me": me, "hand": {}, "counts": [0] * n, "pile": 0,
            "last": None, "history": [], "req": 1, "turn": 0, "decks": decks, "classic": classic,
            "end_msg": "", "pending_win": False}


class BluffWindow(QWidget):
    """Draws whatever 'view' it is given and sends the player's clicks to its controller."""
    CARD_W, CARD_H = 34, 42

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
        self._over_shown = False
        self._hist_len = -1
        self.setObjectName("root")
        self.setWindowTitle("Bluff" + (f" ({role})" if role else ""))
        self._build_ui()
        self.refresh()

    # ================= UI =================
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(5)
        root.setContentsMargins(8, 6, 8, 8)
        root.setSizeConstraint(QLayout.SetFixedSize)
        self.setStyleSheet(
            "QWidget#root { background-color: #1f5f3f; }"
            "QLabel { color: white; font-size: 10px; }"
            "QPushButton { font-size: 10px; }")

        # ---- header ----
        head = QHBoxLayout()
        title = QLabel("♠ ♥  BLUFF  ♦ ♣")
        title.setStyleSheet("font-size: 14px; font-weight: bold; letter-spacing: 2px;")
        head.addWidget(title)
        head.addStretch(1)
        self.info_label = QLabel()
        self.info_label.setStyleSheet("color: #c8e6c9; font-size: 10px;")
        head.addWidget(self.info_label)
        small = ("QPushButton { background-color: rgba(0,0,0,90); color: white;"
                 "border: 1px solid rgba(255,255,255,80); border-radius: 5px; }"
                 "QPushButton:hover { background-color: rgba(0,0,0,140); }"
                 "QPushButton:disabled { color: #78909c; }")
        self.b_new = QPushButton("New")
        self.b_menu = QPushButton("Menu")
        for b in (self.b_new, self.b_menu):
            b.setFixedSize(48, 20)
            b.setFocusPolicy(Qt.NoFocus)
            b.setStyleSheet(small)
            head.addWidget(b)
        self.b_new.clicked.connect(lambda: self.ctrl.new_game())
        self.b_menu.clicked.connect(self.menu_clicked)
        root.addLayout(head)

        # ---- players ----
        prow = QHBoxLayout()
        prow.setSpacing(4)
        self.badges = []
        for i in range(self.n):
            badge = PlayerBadge(i)
            prow.addWidget(badge, 1)
            self.badges.append(badge)
        root.addLayout(prow)

        # ---- small table box (claim + pile) and the scrolling recent-plays box ----
        mid = QHBoxLayout()
        mid.setSpacing(6)

        table = QFrame()
        table.setObjectName("table")
        table.setStyleSheet("QFrame#table { background-color: rgba(0,0,0,55); border-radius: 8px; }")
        table.setFixedWidth(104)
        tl = QVBoxLayout(table)
        tl.setContentsMargins(4, 6, 4, 4)
        tl.setSpacing(2)
        self.claim_label = QLabel()
        self.claim_label.setAlignment(Qt.AlignCenter)
        self.claim_label.setTextFormat(Qt.RichText)
        self.claim_label.setFixedHeight(40)
        tl.addWidget(self.claim_label)
        self.pile_widget = PileWidget()
        tl.addWidget(self.pile_widget, 0, Qt.AlignHCenter)
        tl.addStretch(1)
        mid.addWidget(table)

        hist = QFrame()
        hist.setObjectName("hist")
        hist.setStyleSheet("QFrame#hist { background-color: rgba(0,0,0,55); border-radius: 8px; }")
        hl = QVBoxLayout(hist)
        hl.setContentsMargins(6, 4, 6, 6)
        hl.setSpacing(2)
        cap = QLabel("RECENT PLAYS  (newest first, scroll for older)")
        cap.setStyleSheet("font-size: 9px; font-weight: bold; color: #c8e6c9; letter-spacing: 1px;")
        hl.addWidget(cap)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setFixedHeight(HISTORY_VISIBLE * 34 + (HISTORY_VISIBLE - 1) * 2 + 4)
        self.scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
            "QWidget#rowsbox { background: transparent; }"
            "QScrollBar:vertical { background: rgba(0,0,0,70); width: 9px; margin: 0; border-radius: 4px; }"
            "QScrollBar::handle:vertical { background: rgba(255,255,255,150); min-height: 24px;"
            "border-radius: 4px; }"
            "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }"
            "QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }")
        self.scroll.viewport().setAutoFillBackground(False)
        self.rows_box = QWidget()
        self.rows_box.setObjectName("rowsbox")
        self.rows_layout = QVBoxLayout(self.rows_box)
        self.rows_layout.setContentsMargins(0, 0, 2, 0)
        self.rows_layout.setSpacing(2)
        self.rows_layout.addStretch(1)
        self.rows = []
        for _ in range(HISTORY_VISIBLE):
            self._add_row()
        self.scroll.setWidget(self.rows_box)
        hl.addWidget(self.scroll)
        mid.addWidget(hist, 1)
        root.addLayout(mid)

        # ---- prompt ----
        self.prompt = QLabel()
        self.prompt.setAlignment(Qt.AlignCenter)
        self.prompt.setWordWrap(True)
        self.prompt.setFixedHeight(34)
        self.prompt.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.prompt.setStyleSheet("font-size: 11px; font-weight: bold; background-color: rgba(0,0,0,70);"
                                  "border-radius: 6px; padding: 2px 8px;")
        root.addWidget(self.prompt)

        # ---- claim chips + hand grid (all share the same 13 columns) ----
        cap1 = QLabel("I CLAIM THESE CARDS ARE:")
        cap1.setStyleSheet("font-size: 9px; font-weight: bold; color: #c8e6c9; letter-spacing: 1px;")
        root.addWidget(cap1)

        hand_box = QWidget()
        grid = QGridLayout(hand_box)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(2)
        self.chip_group = QButtonGroup(self)
        self.chip_group.setExclusive(True)
        self.chips = []
        chip_style = ("QPushButton { background-color: rgba(0,0,0,90); color: white; font-weight: bold;"
                      "font-size: 10px; border: 1px solid rgba(255,255,255,70); border-radius: 5px; }"
                      "QPushButton:checked { background-color: #ffca28; color: #212121; border: 2px solid white; }"
                      "QPushButton:disabled { color: #b0bec5; }"
                      "QPushButton:checked:disabled { background-color: #c9a227; color: #212121; }")
        for r in range(1, 14):
            c = QPushButton(rank_short(r))
            c.setCheckable(True)
            c.setFixedSize(self.CARD_W, 20)
            c.setFocusPolicy(Qt.NoFocus)
            c.setStyleSheet(chip_style)
            c.clicked.connect(lambda _=False: self.refresh())
            self.chip_group.addButton(c, r)
            grid.addWidget(c, 0, r - 1)
            self.chips.append(c)
        self.chips[0].setChecked(True)

        cap2 = QLabel("YOUR HAND  (click a card to select, again for more copies; header = all of a rank)")
        cap2.setStyleSheet("font-size: 9px; font-weight: bold; color: #c8e6c9;")
        grid.addWidget(cap2, 1, 0, 1, 13)

        self.headers = {}
        for r in range(1, 14):
            h = QPushButton()
            h.setFixedSize(self.CARD_W, 15)
            h.setFocusPolicy(Qt.NoFocus)
            h.clicked.connect(lambda _=False, rank=r: self.select_rank(rank))
            grid.addWidget(h, 2, r - 1)
            self.headers[r] = h

        self.slots = {}
        for r in range(1, 14):
            for s in range(4):
                b = QPushButton()
                b.setFixedSize(self.CARD_W, self.CARD_H)
                b.setFocusPolicy(Qt.NoFocus)
                sp = b.sizePolicy()
                sp.setRetainSizeWhenHidden(True)
                b.setSizePolicy(sp)
                b.clicked.connect(lambda _=False, c=(r, s): self.cycle_slot(c))
                grid.addWidget(b, 3 + s, r - 1)
                self.slots[(r, s)] = b
        root.addWidget(hand_box, 0, Qt.AlignHCenter)

        # ---- action buttons ----
        arow = QHBoxLayout()
        arow.setSpacing(5)

        def action_button(text, color, hover):
            b = QPushButton(text)
            b.setFixedHeight(28)
            b.setFocusPolicy(Qt.NoFocus)
            b.setStyleSheet(f"QPushButton {{ background-color: {color}; color: white; font-weight: bold;"
                            f"border: none; border-radius: 6px; padding: 0 10px; font-size: 11px; }}"
                            f"QPushButton:hover {{ background-color: {hover}; }}"
                            f"QPushButton:disabled {{ background-color: #546e7a; color: #b0bec5; }}")
            arow.addWidget(b, 1)
            return b

        self.b_clear = QPushButton("Clear")
        self.b_clear.setFixedSize(46, 28)
        self.b_clear.setFocusPolicy(Qt.NoFocus)
        self.b_clear.setStyleSheet("QPushButton { background-color: rgba(0,0,0,90); color: white;"
                                   "border: 1px solid rgba(255,255,255,80); border-radius: 6px; font-size: 10px; }"
                                   "QPushButton:disabled { color: #78909c; }")
        self.b_clear.clicked.connect(self.clear_selection)
        arow.addWidget(self.b_clear)
        self.b_play = action_button("Play", "#2e7d32", "#388e3c")
        self.b_bluff = action_button("Bluff!", "#c62828", "#d32f2f")
        self.b_accept = action_button("Accept", "#ef6c00", "#f57c00")
        self.b_play.clicked.connect(self.play_clicked)
        self.b_bluff.clicked.connect(lambda: self.ctrl.bluff())
        self.b_accept.clicked.connect(lambda: self.ctrl.accept())
        sp = self.b_accept.sizePolicy()
        sp.setRetainSizeWhenHidden(True)
        self.b_accept.setSizePolicy(sp)
        root.addLayout(arow)

    def _add_row(self):
        r = HistoryRow()
        self.rows_layout.insertWidget(len(self.rows), r)
        self.rows.append(r)

    # ================= receiving a new view =================
    def set_view(self, v):
        self.v = v
        self.hand = Counter({tuple(int(x) for x in k.split(",")): n for k, n in v["hand"].items()})
        self.refresh()
        if v["phase"] == "over" and not self._over_shown:
            self._over_shown = True
            msg = v["end_msg"]
            QTimer.singleShot(150, lambda: QMessageBox.information(self, "Game Over", msg))
        elif v["phase"] != "over":
            self._over_shown = False

    def show_notice(self, text):
        """Connection problems: freeze the game and show a message."""
        v = dict(self.v)
        v.update(phase="over", end_msg=text, pending_win=False)
        self.set_view(v)

    # ================= helpers =================
    def me(self):
        return self.v["me"]

    def my_turn(self):
        return self.v["phase"] == "play" and self.v["turn"] == self.me()

    def selected_total(self):
        return sum(min(n, self.hand.get(c, 0)) for c, n in self.sel.items())

    def claim_rank(self):
        return self.v["req"] if self.classic else max(1, self.chip_group.checkedId())

    def rank_totals(self):
        c = Counter()
        for (r, _s), n in self.hand.items():
            c[r] += n
        return c

    # ================= selecting your cards =================
    def cycle_slot(self, card):
        have = self.hand.get(card, 0)
        if have <= 0 or self.v["phase"] != "play":
            return
        self.sel[card] = (self.sel.get(card, 0) + 1) % (have + 1)
        self.refresh()

    def select_rank(self, rank):
        if self.v["phase"] != "play":
            return
        cards = [(rank, s) for s in range(4) if self.hand.get((rank, s), 0) > 0]
        if not cards:
            return
        all_sel = all(self.sel.get(c, 0) >= self.hand[c] for c in cards)
        for c in cards:
            self.sel[c] = 0 if all_sel else self.hand[c]
        self.refresh()

    def clear_selection(self):
        self.sel = Counter()
        self.refresh()

    def play_clicked(self):
        if not self.my_turn() or self.v["pending_win"]:
            return
        cards = []
        for c, k in self.sel.items():
            cards.extend([c] * min(k, self.hand.get(c, 0)))
        if not cards:
            return
        claim = self.claim_rank()
        self.sel = Counter()
        self.ctrl.play(cards, claim)

    def menu_clicked(self):
        self.ctrl.go_menu = True
        self.close()

    # ================= display =================
    def refresh(self):
        v = self.v
        phase = v["phase"]
        my_turn = self.my_turn()
        pending = v["pending_win"]
        claim = self.claim_rank()

        # hand grid
        for card, b in self.slots.items():
            have = self.hand.get(card, 0)
            if have <= 0:
                self.sel[card] = 0
                b.setVisible(False)
                continue
            self.sel[card] = min(self.sel.get(card, 0), have)
            k = self.sel[card]
            fg = "#c62828" if card[1] in RED_SUITS else "#212121"
            bg, border = ("#fff59d", "2px solid #1565c0") if k > 0 else ("white", "1px solid #90a4ae")
            sub = (f"{k}/{have}" if have > 1 else "✓") if k > 0 else (f"×{have}" if have > 1 else "")
            b.setText(f"{rank_short(card[0])}{SUITS[card[1]]}\n{sub}")
            b.setStyleSheet(f"QPushButton {{ background-color: {bg}; color: {fg}; border: {border};"
                            f"border-radius: 4px; font-size: 10px; font-weight: bold; padding: 0; }}")
            b.setVisible(True)

        totals = self.rank_totals()
        for r, h in self.headers.items():
            total = totals.get(r, 0)
            chosen = sum(self.sel.get((r, s), 0) for s in range(4))
            h.setText(f"{rank_short(r)} · {total}" if total else rank_short(r))
            h.setEnabled(total > 0)
            if total and chosen >= total:
                h.setStyleSheet("QPushButton { background-color: #1565c0; color: white; font-size: 9px;"
                                "font-weight: bold; border: none; border-radius: 4px; padding: 0; }")
            else:
                h.setStyleSheet("QPushButton { background-color: rgba(0,0,0,70); color: #e0f2f1;"
                                "font-size: 9px; border: none; border-radius: 4px; padding: 0; }"
                                "QPushButton:disabled { color: rgba(255,255,255,60); }")

        # claim chips
        if self.classic:
            self.chips[v["req"] - 1].setChecked(True)
        for c in self.chips:
            c.setEnabled(not self.classic and my_turn)

        # players
        for i, badge in enumerate(self.badges):
            name = v["names"][i]
            if phase == "lobby":
                badge.set_state(name, "joined" if name != WAITING else "…", False, name != WAITING)
            else:
                cnt = v["counts"][i]
                badge.set_state(name, f"{cnt} card{'s' if cnt != 1 else ''}",
                                phase == "play" and v["turn"] == i)

        # table box: current claim + pile
        if v["last"]:
            lp = v["last"]
            line = (f"<div style='font-size:14px; font-weight:bold;'>{claim_text(lp['count'], lp['claim'])}</div>"
                    f"<div style='font-size:9px; color:#c8e6c9;'>claimed by {v['names'][lp['player']]}</div>")
        else:
            line = ("<div style='font-size:12px; font-weight:bold;'>New round</div>"
                    "<div style='font-size:9px; color:#c8e6c9;'>no claim yet</div>")
        self.claim_label.setText(line)
        self.pile_widget.set_count(v["pile"])

        # recent plays, newest first. 4 rows are visible, the rest can be scrolled to
        shown = v["history"][::-1]
        while len(self.rows) < max(HISTORY_VISIBLE, len(shown)):
            self._add_row()
        for i, row in enumerate(self.rows):
            if i < len(shown):
                row.show()
                self._fill_history_row(row, shown[i], i == 0)
            elif i < HISTORY_VISIBLE:
                row.show()
                row.clear()
            else:
                row.hide()
        if len(shown) != self._hist_len:
            self.scroll.verticalScrollBar().setValue(0)          # jump to the newest play
            self._hist_len = len(shown)

        # buttons
        n_sel = self.selected_total()
        self.b_play.setText(f"Play {n_sel} as {RANK_NAMES[claim][1]}" if n_sel else "Play")
        self.b_play.setEnabled(my_turn and n_sel > 0 and not pending)
        self.b_bluff.setEnabled(my_turn and v["last"] is not None)
        self.b_accept.setVisible(my_turn and pending)
        self.b_accept.setEnabled(my_turn and pending)
        self.b_clear.setEnabled(n_sel > 0)
        if self.new_policy == "always":
            self.b_new.setEnabled(True)
        elif self.new_policy == "over_only":
            self.b_new.setEnabled(phase == "over")
        else:
            self.b_new.setEnabled(False)

        self.info_label.setText(f"{self.decks} deck{'s' if self.decks > 1 else ''} · "
                                f"{'classic order' if self.classic else 'free choice'}"
                                + (f" · must claim: {RANK_NAMES[v['req']][1]}" if self.classic else ""))
        self.prompt.setText(self._prompt_text(my_turn, pending))

    def _fill_history_row(self, row, e, is_newest):
        v = self.v
        names = v["names"]
        who = names[e["player"]]
        line1 = f"<b>{who}</b> played <b>{claim_text(e['count'], e['claim'])}</b>"
        verdict = e.get("verdict")
        tint = "#90a4ae"
        if verdict in ("lie", "true"):
            cards = sorted(tuple(c) for c in e["revealed"])
            shown = " ".join(card_str(c) for c in cards[:6]) + (f" +{len(cards) - 6}" if len(cards) > 6 else "")
            tk = names[e["taker"]]
            if verdict == "lie":
                line2 = f"<span style='color:#ffcdd2;'><b>✘ LIE</b> · {shown} · pile → {tk}</span>"
                bg, border, tint = "rgba(183, 28, 28, 110)", "#ef5350", "#ef5350"
            else:
                line2 = f"<span style='color:#c8e6c9;'><b>✔ TRUE</b> · {shown} · pile → {tk}</span>"
                bg, border, tint = "rgba(27, 94, 32, 130)", "#66bb6a", "#66bb6a"
        elif is_newest and v["phase"] == "play" and v["last"] is not None:
            turn = v["turn"]
            decider = "your" if turn == v["me"] else f"{names[turn]}'s"
            line2 = f"<span style='color:#fff9c4;'>waiting for {decider} decision…</span>"
            bg, border, tint = "rgba(0, 0, 0, 90)", "#ffd54f", "#ffd54f"
        elif is_newest and v["phase"] == "over":
            line2 = "<span style='color:#fff9c4;'>nobody called Bluff</span>"
            bg, border, tint = "rgba(0, 0, 0, 90)", "#ffd54f", "#ffd54f"
        else:
            line2 = "<span style='color:#9ec5ab;'>accepted — no challenge</span>"
            bg, border = "rgba(0, 0, 0, 40)", "rgba(255,255,255,30)"
        row.set_data(e["player"], initials(who, e["player"]), line1, line2, e["claim"], e["count"],
                     tint, bg, border)

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
        if my_turn:
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
        self.joined = {0}                # seats whose player has introduced themselves
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
            free = [s for s in range(1, self.players) if s not in self.socks]
            if self.engine.phase != "lobby" or not free:
                send_json(sock, {"type": "error", "msg": "This game is full or already started."})
                sock.disconnectFromHost()
                continue
            seat = free[0]
            self.socks[seat] = sock
            self.seat_of[sock] = seat
            sock.readyRead.connect(lambda s=sock: self._read(s))
            sock.disconnected.connect(lambda s=sock: self._dropped(s))

    def _read(self, sock):
        for msg in read_lines(sock):
            self._handle(sock, msg)

    def _handle(self, sock, msg):
        seat = self.seat_of.get(sock)
        if seat is None:
            return
        t = msg.get("type")
        if t == "hello" and seat not in self.joined and self.engine.phase == "lobby":
            name = str(msg.get("name", "")).strip()[:14] or f"Player {seat + 1}"
            taken = {n.lower() for n in self.engine.names if n} | {"you", WAITING.lower()}
            while name.lower() in taken:
                name += " 2"
            self.engine.names[seat] = name
            self.joined.add(seat)
            send_json(sock, {"type": "welcome", "index": seat, "n": self.players,
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

    def _dropped(self, sock):
        if self.closing:
            return
        seat = self.seat_of.pop(sock, None)
        if seat is None:
            return
        self.socks.pop(seat, None)
        name = self.engine.names[seat] or f"Player {seat + 1}"
        was_joined = seat in self.joined
        self.joined.discard(seat)
        self.engine.names[seat] = None
        if self.engine.phase == "play":
            self.engine.abort(f"{name} left the game.")
        if was_joined or self.engine.phase != "play":
            self.sync()

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
            self.engine.reset()
        self.sync()

    def shutdown(self):
        self.closing = True
        for sock in list(self.socks.values()):
            sock.abort()
        self.server.close()


class ClientController:
    """Joins a friend's game. Only ever receives its own private view."""

    def __init__(self, ip, name):
        self.go_menu = False
        self.ok = True
        self.closing = False
        self.window = None
        self.name = name
        self.sock = QTcpSocket()
        self.sock.connected.connect(lambda: send_json(self.sock, {"type": "hello", "name": self.name}))
        self.sock.readyRead.connect(self._read)
        self.sock.disconnected.connect(self._disconnected)
        err = getattr(self.sock, "errorOccurred", None) or self.sock.error
        err.connect(self._on_error)
        self.sock.connectToHost(ip, PORT)

    def start(self):
        pass                                    # the window appears once the host welcomes us

    def _fail(self, text):
        if self.closing:
            return
        self.closing = True
        self.go_menu = True
        QMessageBox.critical(None, "Bluff", text)
        if self.window is not None:
            self.window.close()
        QApplication.quit()

    def _on_error(self, *_):
        if self.window is None:
            self._fail("Could not connect to the host. Check the IP, and that the host has "
                       "already pressed Host Game.")

    def _disconnected(self):
        if self.closing:
            return
        if self.window is None:
            self._fail("Connection lost.")
        else:
            self.window.show_notice("Disconnected from the host.")

    def _read(self):
        for msg in read_lines(self.sock):
            t = msg.get("type")
            if t == "welcome" and self.window is None:
                self.window = BluffWindow(self, int(msg["n"]), int(msg["index"]), int(msg["decks"]),
                                          bool(msg["classic"]), "never", "Guest")
                self.window.lobby_hint = "The host deals as soon as everyone has joined."
                self.window.show()
            elif t == "view" and self.window is not None:
                self.window.set_view(msg["view"])
            elif t == "error":
                self._fail(str(msg.get("msg", "Error.")))
                return

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
        self.sock.abort()


# ====================================================================== main
if __name__ == "__main__":
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
