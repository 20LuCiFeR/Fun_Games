"""
2048 - PyQt5

Kaise khelein:
 * Arrow keys (ya W A S D) se saari tiles ek taraf slide hoti hain.
 * Same number wali do tiles takraye to mil kar double ho jati hain (2+2=4, 4+4=8 ...).
 * Har move ke baad ek nayi tile (2 ya 4) aati hai.
 * 2048 ki tile ban gayi to jeet! (uske baad bhi khel sakte ho)
 * Board bhar gaya aur koi move nahi bacha to game over.

Install:  pip install PyQt5
Run:      python game_2048.py
"""

import os
import random
import sys

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QApplication, QGridLayout, QHBoxLayout, QLabel, QLayout, QMessageBox,
    QPushButton, QVBoxLayout, QWidget,
)

N = 4
BEST_FILE = os.path.join(os.path.expanduser("~"), ".game_2048_best")

# tile ka number -> (background, text color)
COLORS = {
    0: ("#cdc1b4", "#776e65"),
    2: ("#eee4da", "#776e65"),
    4: ("#ede0c8", "#776e65"),
    8: ("#f2b179", "#f9f6f2"),
    16: ("#f59563", "#f9f6f2"),
    32: ("#f67c5f", "#f9f6f2"),
    64: ("#f65e3b", "#f9f6f2"),
    128: ("#edcf72", "#f9f6f2"),
    256: ("#edcc61", "#f9f6f2"),
    512: ("#edc850", "#f9f6f2"),
    1024: ("#edc53f", "#f9f6f2"),
    2048: ("#edc22e", "#f9f6f2"),
}


def slide_left(row):
    """Ek row ko left slide + merge karo. (nayi row, is move se mila score) wapas karta hai."""
    tiles = [x for x in row if x]
    out, score, i = [], 0, 0
    while i < len(tiles):
        if i + 1 < len(tiles) and tiles[i] == tiles[i + 1]:
            out.append(tiles[i] * 2)
            score += tiles[i] * 2
            i += 2                      # ek move mein ek tile sirf ek baar judti hai
        else:
            out.append(tiles[i])
            i += 1
    out += [0] * (N - len(out))
    return out, score


class Game2048(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("2048")
        self.setFocusPolicy(Qt.StrongFocus)
        self.best = self._load_best()
        self.won_shown = False

        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(5)
        root.setSizeConstraint(QLayout.SetFixedSize)
        self.setStyleSheet("QWidget { background-color: #faf8ef; }")

        top = QHBoxLayout()
        self.score_label = QLabel()
        self.best_label = QLabel()
        for lbl in (self.score_label, self.best_label):
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet("background-color: #bbada0; color: white; border-radius: 4px;"
                              "font-size: 11px; font-weight: bold; padding: 3px 8px;")
            top.addWidget(lbl)
        self.btn_new = QPushButton("New")
        self.btn_new.setFocusPolicy(Qt.NoFocus)     # taaki arrow keys window ko hi milein
        self.btn_new.setStyleSheet("QPushButton { background-color: #8f7a66; color: white;"
                                   "border-radius: 4px; font-size: 11px; font-weight: bold;"
                                   "padding: 4px 10px; }")
        self.btn_new.clicked.connect(self.new_game)
        top.addWidget(self.btn_new)
        root.addLayout(top)

        board = QWidget()
        board.setStyleSheet("background-color: #bbada0; border-radius: 6px;")
        grid = QGridLayout(board)
        grid.setContentsMargins(5, 5, 5, 5)
        grid.setSpacing(5)
        self.tiles = []
        for r in range(N):
            row = []
            for c in range(N):
                t = QLabel()
                t.setFixedSize(56, 56)
                t.setAlignment(Qt.AlignCenter)
                grid.addWidget(t, r, c)
                row.append(t)
            self.tiles.append(row)
        root.addWidget(board)

        self.status = QLabel("Arrow keys / WASD se khelo")
        self.status.setAlignment(Qt.AlignCenter)
        self.status.setStyleSheet("color: #776e65; font-size: 10px;")
        root.addWidget(self.status)

        self.new_game()

    # ---------- best score ----------
    def _load_best(self):
        try:
            with open(BEST_FILE) as f:
                return int(f.read().strip())
        except (OSError, ValueError):
            return 0

    def _save_best(self):
        try:
            with open(BEST_FILE, "w") as f:
                f.write(str(self.best))
        except OSError:
            pass

    # ---------- game logic ----------
    def new_game(self):
        self.grid = [[0] * N for _ in range(N)]
        self.score = 0
        self.over = False
        self.won_shown = False
        self.add_tile()
        self.add_tile()
        self.status.setText("Arrow keys / WASD se khelo")
        self.refresh()

    def add_tile(self):
        empty = [(r, c) for r in range(N) for c in range(N) if self.grid[r][c] == 0]
        if empty:
            r, c = random.choice(empty)
            self.grid[r][c] = 4 if random.random() < 0.1 else 2

    def move(self, direction):
        """direction: 'left' | 'right' | 'up' | 'down'. Kuch badla to True."""
        # har direction ko "left slide" mein badal ke lines nikalo
        if direction in ("left", "right"):
            lines = [row[:] for row in self.grid]
        else:
            lines = [[self.grid[r][c] for r in range(N)] for c in range(N)]
        if direction in ("right", "down"):
            lines = [ln[::-1] for ln in lines]

        gained, new_lines = 0, []
        for ln in lines:
            out, s = slide_left(ln)
            new_lines.append(out)
            gained += s

        if direction in ("right", "down"):
            new_lines = [ln[::-1] for ln in new_lines]
        if direction in ("left", "right"):
            new_grid = new_lines
        else:
            new_grid = [[new_lines[c][r] for c in range(N)] for r in range(N)]

        if new_grid == self.grid:
            return False
        self.grid = new_grid
        self.score += gained
        self.add_tile()
        return True

    def can_move(self):
        for r in range(N):
            for c in range(N):
                if self.grid[r][c] == 0:
                    return True
                if c + 1 < N and self.grid[r][c] == self.grid[r][c + 1]:
                    return True
                if r + 1 < N and self.grid[r][c] == self.grid[r + 1][c]:
                    return True
        return False

    # ---------- keys ----------
    def keyPressEvent(self, e):
        keys = {
            Qt.Key_Left: "left", Qt.Key_A: "left",
            Qt.Key_Right: "right", Qt.Key_D: "right",
            Qt.Key_Up: "up", Qt.Key_W: "up",
            Qt.Key_Down: "down", Qt.Key_S: "down",
        }
        d = keys.get(e.key())
        if d is None:
            super().keyPressEvent(e)
            return
        if self.over:
            return
        if self.move(d):
            self.refresh()
            if not self.won_shown and any(2048 in row for row in self.grid):
                self.won_shown = True
                self.status.setText("2048! Jeet gaye 🎉 (khelte raho)")
                QMessageBox.information(self, "2048", "2048 ban gaya! Aap jeet gaye 🎉\nChaho to aur khelo.")
            elif not self.can_move():
                self.over = True
                self.status.setText("Game Over! 'New' dabao")
                QMessageBox.information(self, "Game Over", f"Koi move nahi bacha.\nScore: {self.score}")

    # ---------- display ----------
    def refresh(self):
        for r in range(N):
            for c in range(N):
                v = self.grid[r][c]
                bg, fg = COLORS.get(v, ("#3c3a32", "#f9f6f2"))
                size = 20 if v < 100 else 17 if v < 1000 else 14
                t = self.tiles[r][c]
                t.setText(str(v) if v else "")
                t.setStyleSheet(f"background-color: {bg}; color: {fg}; border-radius: 4px;"
                                f"font-size: {size}px; font-weight: bold;")
        if self.score > self.best:
            self.best = self.score
            self._save_best()
        self.score_label.setText(f"Score\n{self.score}")
        self.best_label.setText(f"Best\n{self.best}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = Game2048()
    w.show()
    sys.exit(app.exec_())
