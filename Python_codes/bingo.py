"""
Bingo (compact UI) - Solo / vs CPU / Multiplayer (same network) - PyQt5

Three modes:
 * Solo        : just your own board; click a number to cut it when the opponent calls it.
 * vs CPU      : take turns calling numbers against the computer.
 * Host / Join : two people play from their own computers on the same WiFi / network.
                 One player clicks "Host Game" (their IP is shown in the window),
                 the other enters that IP and clicks "Join Game".

Board: "Auto" fills 1-25 randomly, "Manual" lets you click empty boxes to place 1, 2, 3 ... 25.
The first player to complete 5 lines (row / column / diagonal) wins (B-I-N-G-O).
A red line is drawn through every completed line.

Install:  automatic (if PyQt5 is missing, the script installs it with pip)
Run:      python bingo_all.py
"""

import json
import random
import sys
from math import hypot


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

from PyQt5.QtCore import QLineF, QPointF, Qt, QTimer
from PyQt5.QtGui import QColor, QPainter, QPen
from PyQt5.QtNetwork import (
    QAbstractSocket, QHostAddress, QNetworkInterface, QTcpServer, QTcpSocket,
)
from PyQt5.QtWidgets import (
    QApplication, QDialog, QGridLayout, QHBoxLayout, QLabel, QLayout,
    QLineEdit, QMessageBox, QPushButton, QVBoxLayout, QWidget,
)

PORT = 5555
SIZE = 5
TOTAL = SIZE * SIZE

LINES = []
for r in range(SIZE):
    LINES.append([r * SIZE + c for c in range(SIZE)])
for c in range(SIZE):
    LINES.append([r * SIZE + c for r in range(SIZE)])
LINES.append([i * SIZE + i for i in range(SIZE)])
LINES.append([i * SIZE + (SIZE - 1 - i) for i in range(SIZE)])

CELL = """
QPushButton {{
    background-color: {bg}; color: {fg};
    border: 1px solid #607d8b; border-radius: 3px;
    font-size: 8px; font-weight: bold; padding: 0px;
}}
"""


def local_ips():
    ips = []
    for a in QNetworkInterface.allAddresses():
        s = a.toString()
        if a.protocol() == QAbstractSocket.IPv4Protocol and not s.startswith("127."):
            ips.append(s)
    return ips or ["127.0.0.1"]


class Board:
    def __init__(self):
        self.nums = [0] * TOTAL      # 0 = empty box
        self.cut = [False] * TOTAL

    def randomize(self):
        self.nums = random.sample(range(1, TOTAL + 1), TOTAL)
        self.cut = [False] * TOTAL

    def index_of(self, n):
        return self.nums.index(n)

    def cut_number(self, n):
        if n in self.nums:
            self.cut[self.index_of(n)] = True

    def done_lines(self):
        return [ln for ln in LINES if all(self.cut[i] for i in ln)]

    def lines_count(self):
        return len(self.done_lines())

    def best_move(self):
        """For the CPU: pick the number that gets its lines complete fastest."""
        best_score, best = -1, []
        for idx, n in enumerate(self.nums):
            if self.cut[idx]:
                continue
            score = sum(sum(self.cut[i] for i in ln) ** 2 for ln in LINES if idx in ln)
            if score > best_score:
                best_score, best = score, [n]
            elif score == best_score:
                best.append(n)
        return random.choice(best)


class LineOverlay(QWidget):
    """Transparent layer over the grid: draws a red line through every completed line."""

    def __init__(self, parent, cells):
        super().__init__(parent)
        self.cells = cells
        self.lines = []
        self.setAttribute(Qt.WA_TransparentForMouseEvents)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(QPen(QColor(198, 40, 40, 215), 2, Qt.SolidLine, Qt.RoundCap))
        for a, b in self.lines:
            pa = QPointF(self.cells[a].geometry().center())
            pb = QPointF(self.cells[b].geometry().center())
            d = pb - pa
            length = hypot(d.x(), d.y())
            if length:
                u = d / length
                pa, pb = pa - u * 5, pb + u * 5
            p.drawLine(QLineF(pa, pb))


class GridBox(QWidget):
    def resizeEvent(self, e):
        super().resizeEvent(e)
        if hasattr(self, "overlay"):
            self.overlay.setGeometry(self.rect())


class ModeDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Bingo")
        self.mode = None
        self.ip = ""
        lay = QVBoxLayout(self)

        def btn(text, mode):
            b = QPushButton(text)
            b.setMinimumHeight(28)
            b.clicked.connect(lambda: self._choose(mode))
            lay.addWidget(b)

        btn("Solo  (your board only)", "solo")
        btn("vs CPU", "cpu")
        btn("Host Game", "host")
        self.ip_edit = QLineEdit()
        self.ip_edit.setPlaceholderText("Host IP, e.g. 192.168.1.5  (same PC: 127.0.0.1)")
        lay.addWidget(self.ip_edit)
        btn("Join Game", "join")

    def _choose(self, mode):
        ip = self.ip_edit.text().strip()
        if mode == "join" and not ip:
            self.ip_edit.setFocus()
            return
        self.mode, self.ip = mode, ip
        self.accept()


class Bingo(QWidget):
    def __init__(self, mode, ip=""):
        super().__init__()
        self.mode = mode                         # solo | cpu | host | join
        self.multi = mode in ("host", "join")
        self.is_host = mode == "host"
        self.ok = True
        self.go_menu = False
        self.closing = False
        self.setWindowTitle({"solo": "Bingo", "cpu": "Bingo vs CPU",
                             "host": "Bingo (Host)", "join": "Bingo (Guest)"}[mode])

        self.board = Board()
        self.cpu = Board()
        self.cpu_token = 0
        self.next_num = 1
        self.manual = False
        self.phase = "waiting" if self.multi else "setup"   # waiting -> setup -> play -> over
        self.me_ready = False
        self.opp_ready = False
        self.my_turn = False
        self.awaiting = None          # multi: "ack" (I called a number) / "result" (opponent called one)
        self.won_shown = False
        self.end_msg = ""
        self.last_msg = ""
        self.sock = None
        self.server = None

        self._build_ui()
        if self.multi:
            self._setup_network(ip)
        self.refresh()

    # ================= UI =================
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(2)
        root.setContentsMargins(3, 3, 3, 3)
        root.setSizeConstraint(QLayout.SetFixedSize)
        self.setStyleSheet("QLabel { font-size: 7px; } QPushButton { font-size: 7px; padding: 0px; }")

        self.status = QLabel()
        self.status.setAlignment(Qt.AlignCenter)
        self.status.setWordWrap(True)
        self.status.setFixedSize(109, 22)
        self.status.setTextInteractionFlags(Qt.TextSelectableByMouse)
        root.addWidget(self.status, 0, Qt.AlignHCenter)

        self.gridbox = GridBox()
        grid = QGridLayout(self.gridbox)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(1)
        self.cells = []
        for i in range(TOTAL):
            b = QPushButton()
            b.setFixedSize(21, 21)
            b.clicked.connect(lambda _, k=i: self.cell_clicked(k))
            grid.addWidget(b, i // SIZE, i % SIZE)
            self.cells.append(b)
        self.overlay = LineOverlay(self.gridbox, self.cells)
        self.gridbox.overlay = self.overlay
        root.addWidget(self.gridbox, 0, Qt.AlignHCenter)

        self.letters = QLabel()
        self.letters.setAlignment(Qt.AlignCenter)
        self.letters.setTextFormat(Qt.RichText)
        root.addWidget(self.letters)

        row = QHBoxLayout()
        row.setSpacing(1)
        self.b_auto = QPushButton("Auto")
        self.b_manual = QPushButton("Manual")
        self.b_undo = QPushButton("Undo")
        self.b_go = QPushButton("Go")
        self.b_new = QPushButton("New")
        self.b_menu = QPushButton("Menu")
        self.b_auto.clicked.connect(self.auto_fill)
        self.b_manual.clicked.connect(self.manual_mode)
        self.b_undo.clicked.connect(self.undo)
        self.b_go.clicked.connect(self.go_clicked)
        self.b_new.clicked.connect(self.new_clicked)
        self.b_menu.clicked.connect(self.menu_clicked)
        for b in (self.b_auto, self.b_manual, self.b_undo, self.b_go, self.b_new, self.b_menu):
            b.setFixedSize(26 if b is self.b_manual else 21, 14)
            row.addWidget(b)
        if not self.multi:
            self.b_go.hide()
        root.addLayout(row)

    def refresh(self):
        for i, b in enumerate(self.cells):
            n = self.board.nums[i]
            b.setText(str(n) if n else "")
            if self.board.cut[i]:
                bg, fg = "#66bb6a", "white"
            else:
                bg, fg = ("#eceff1" if n else "#cfd8dc"), "#263238"
            b.setStyleSheet(CELL.format(bg=bg, fg=fg))

        self.overlay.lines = [(ln[0], ln[-1]) for ln in self.board.done_lines()]
        self.overlay.update()

        n = self.board.lines_count()
        self.letters.setText("".join(
            f'<span style="color:{"#2e7d32" if k < n else "#b0bec5"};'
            f'font-size:9px;font-weight:bold;">{ch} </span>'
            for k, ch in enumerate("BINGO")) + f" &nbsp;({min(n, 5)}/5)")

        full = self.next_num > TOTAL
        editing_ok = self.can_edit()
        self.b_auto.setEnabled(editing_ok)
        self.b_manual.setEnabled(editing_ok)
        self.b_undo.setEnabled(self.manual and self.phase == "setup" and not self.me_ready
                               and self.next_num > 1)
        self.b_go.setEnabled(self.multi and self.phase == "setup" and not self.me_ready and full)
        if self.multi:
            self.b_new.setEnabled(self.phase == "over" and self._connected())
        else:
            self.b_new.setEnabled(True)
        self.status.setText(self._status_text())

    def _status_text(self):
        p = self.phase
        if p == "waiting":
            if self.is_host:
                return "IP: " + " / ".join(local_ips())
            return "Connecting..."
        if p == "setup":
            if self.multi and self.me_ready:
                return "Waiting for opponent..."
            if self.manual and self.next_num <= TOTAL:
                return f"Click a box: {self.next_num}"
            if self.multi and self.next_num > TOTAL:
                return "Board ready, press Go"
            return "Choose Auto or Manual"
        if p == "play":
            if self.mode == "solo":
                return "Click a number to cut it"
            if self.awaiting == "ack":
                turn = "Waiting for reply..."
            elif self.my_turn:
                turn = "Your turn"
            else:
                turn = "CPU is thinking..." if self.mode == "cpu" else "Opponent's turn"
            return turn + ("\n" + self.last_msg if self.last_msg else "")
        return self.end_msg

    # ================= setting up the board =================
    def can_edit(self):
        if self.multi:
            return self.phase == "setup" and not self.me_ready
        return True

    def _restart_board(self):
        self.board = Board()
        self.cpu = Board()
        self.cpu_token += 1
        self.next_num = 1
        self.manual = False
        self.won_shown = False
        self.awaiting = None
        self.my_turn = False
        self.end_msg = ""
        self.last_msg = ""
        if not self.multi:
            self.phase = "setup"

    def auto_fill(self):
        if not self.can_edit():
            return
        self._restart_board()
        self.board.randomize()
        self.next_num = TOTAL + 1
        self._board_full()
        self.refresh()

    def manual_mode(self):
        if not self.can_edit():
            return
        self._restart_board()
        self.manual = True
        self.refresh()

    def undo(self):
        if self.manual and self.phase == "setup" and not self.me_ready and self.next_num > 1:
            self.next_num -= 1
            self.board.nums[self.board.index_of(self.next_num)] = 0
            self.refresh()

    def _board_full(self):
        """All 25 numbers are placed."""
        if self.mode == "solo":
            self.phase = "play"
        elif self.mode == "cpu":
            self.cpu.randomize()
            self.phase = "play"
            self.my_turn = random.choice([True, False])
            if not self.my_turn:
                self._schedule_cpu()
        # multiplayer: wait for the "Go" button

    def new_clicked(self):
        if self.multi:
            if self.phase == "over" and self._connected():
                self._send({"type": "newgame"})
                self._multi_reset()
        else:
            self._restart_board()
            self.refresh()

    def menu_clicked(self):
        self.go_menu = True
        self.close()

    # ================= click =================
    def cell_clicked(self, i):
        if self.phase == "setup":
            if self.manual and self.can_edit() and self.board.nums[i] == 0 \
                    and self.next_num <= TOTAL:
                self.board.nums[i] = self.next_num
                self.next_num += 1
                if self.next_num > TOTAL:
                    self._board_full()
                self.refresh()
            return
        if self.phase != "play":
            return

        if self.mode == "solo":
            self.board.cut[i] = not self.board.cut[i]     # cut / uncut
            self.refresh()
            if self.board.lines_count() >= 5 and not self.won_shown:
                self.won_shown = True
                QMessageBox.information(self, "BINGO!", "BINGO! 5 lines complete 🎉")
        elif self.mode == "cpu":
            if self.my_turn and not self.board.cut[i]:
                self._cpu_call(self.board.nums[i], "You")
        else:
            if self.my_turn and self.awaiting is None and not self.board.cut[i]:
                self._call_multi(self.board.nums[i])

    # ================= vs CPU =================
    def _schedule_cpu(self):
        QTimer.singleShot(700, lambda t=self.cpu_token: self._cpu_turn(t))

    def _cpu_turn(self, token):
        if token != self.cpu_token or self.phase != "play" or self.my_turn:
            return
        self._cpu_call(self.cpu.best_move(), "CPU")

    def _cpu_call(self, n, who):
        self.board.cut_number(n)
        self.cpu.cut_number(n)
        self.last_msg = f"{who}: {n}"
        me = self.board.lines_count() >= 5
        cpu = self.cpu.lines_count() >= 5
        if me and cpu:
            self._finish("Draw 🤝")
        elif me:
            self._finish("BINGO! You win 🎉")
        elif cpu:
            self._finish("CPU wins 😅")
        else:
            self.my_turn = who == "CPU"
            self.refresh()
            if who == "You":
                self._schedule_cpu()

    def _finish(self, msg):
        self.phase = "over"
        self.my_turn = False
        self.end_msg = msg
        self.refresh()
        QMessageBox.information(self, "Game Over", msg)

    # ================= Multiplayer =================
    def go_clicked(self):
        if self.multi and self.phase == "setup" and not self.me_ready and self.next_num > TOTAL:
            self.me_ready = True
            self._send({"type": "ready"})
            self._maybe_start()
            self.refresh()

    def _maybe_start(self):
        if self.is_host and self.me_ready and self.opp_ready and self.phase == "setup":
            host_first = random.choice([True, False])
            self._send({"type": "start", "host_first": host_first})
            self._begin_play(host_first)

    def _begin_play(self, host_first):
        self.phase = "play"
        self.my_turn = host_first if self.is_host else not host_first
        self.awaiting = None
        self.last_msg = ""
        self.refresh()

    def _call_multi(self, n):
        self.my_turn = False
        self.awaiting = "ack"
        self.board.cut_number(n)
        self.last_msg = f"You: {n}"
        self._send({"type": "call", "n": n})
        self.refresh()

    def _on_call(self, n):
        if self.phase != "play" or self.my_turn or self.awaiting is not None:
            return
        if not isinstance(n, int) or not 1 <= n <= TOTAL:
            return
        self.board.cut_number(n)
        self.last_msg = f"Opp: {n}"
        self.awaiting = "result"
        self._send({"type": "ack", "lines": self.board.lines_count()})
        self.refresh()

    def _on_ack(self, opp_lines):
        if self.awaiting != "ack":
            return
        mine = self.board.lines_count()
        if mine >= 5 and opp_lines >= 5:
            outcome = "draw"
        elif mine >= 5:
            outcome = "caller"
        elif opp_lines >= 5:
            outcome = "receiver"
        else:
            outcome = "none"
        self._send({"type": "result", "outcome": outcome})
        self._apply_result(outcome, True)

    def _on_result(self, outcome):
        if self.awaiting != "result":
            return
        self._apply_result(outcome, False)

    def _apply_result(self, outcome, i_am_caller):
        self.awaiting = None
        if outcome == "none":
            self.my_turn = not i_am_caller
            self.refresh()
            return
        if outcome == "draw":
            msg = "Draw 🤝"
        else:
            i_won = (outcome == "caller") == i_am_caller
            msg = "BINGO! You win 🎉" if i_won else "Opponent wins 😅"
        self._finish(msg)

    def _multi_reset(self):
        self._restart_board()
        self.me_ready = False
        self.opp_ready = False
        self.phase = "setup"
        self.refresh()

    # ---- network ----
    def _connected(self):
        return self.sock is not None and self.sock.state() == QAbstractSocket.ConnectedState

    def _setup_network(self, ip):
        if self.is_host:
            self.server = QTcpServer(self)
            if not self.server.listen(QHostAddress.Any, PORT):
                QMessageBox.critical(self, "Error",
                                     f"Cannot use port {PORT}:\n{self.server.errorString()}")
                self.ok = False
                return
            self.server.newConnection.connect(self._on_new_connection)
            print("Tell your friend this IP:", " / ".join(local_ips()), f"(port {PORT})")
        else:
            self.sock = QTcpSocket(self)
            self._hook_socket()
            err = getattr(self.sock, "errorOccurred", None) or self.sock.error
            err.connect(self._on_sock_error)
            self.sock.connectToHost(ip, PORT)

    def _hook_socket(self):
        self.sock.connected.connect(self._on_connected)
        self.sock.readyRead.connect(self._on_ready_read)
        self.sock.disconnected.connect(self._on_disconnected)

    def _on_new_connection(self):
        self.sock = self.server.nextPendingConnection()
        self.server.close()
        self._hook_socket()
        self._on_connected()

    def _on_connected(self):
        if self.phase == "waiting":
            self.phase = "setup"
        self.refresh()

    def _on_sock_error(self, *_):
        if self.phase == "waiting" and not self.closing:
            self.phase = "over"
            self.end_msg = "Could not connect. Check the IP"
            self.refresh()

    def _on_disconnected(self):
        if self.closing:
            return
        if self.phase != "over":
            self.phase = "over"
            self.end_msg = "Opponent left"
        self.refresh()

    def _send(self, msg):
        if self._connected():
            self.sock.write((json.dumps(msg) + "\n").encode())
            self.sock.flush()

    def _on_ready_read(self):
        while self.sock.canReadLine():
            line = bytes(self.sock.readLine()).decode(errors="ignore").strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except ValueError:
                continue
            self._handle(msg)

    def _handle(self, msg):
        t = msg.get("type")
        if t == "ready":
            self.opp_ready = True
            self._maybe_start()
            self.refresh()
        elif t == "start" and not self.is_host and self.phase == "setup":
            self._begin_play(bool(msg.get("host_first")))
        elif t == "call":
            self._on_call(msg.get("n"))
        elif t == "ack":
            self._on_ack(int(msg.get("lines", 0)))
        elif t == "result":
            self._on_result(msg.get("outcome"))
        elif t == "newgame":
            self._multi_reset()

    def closeEvent(self, e):
        self.closing = True
        self.cpu_token += 1
        if self.server:
            self.server.close()
        if self.sock:
            self.sock.abort()
        super().closeEvent(e)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    while True:
        dlg = ModeDialog()
        if dlg.exec_() != QDialog.Accepted:
            break
        win = Bingo(dlg.mode, dlg.ip)
        if not win.ok:
            continue
        win.show()
        app.exec_()                 # returns here when the window is closed
        if not win.go_menu:
            break
    sys.exit(0)
