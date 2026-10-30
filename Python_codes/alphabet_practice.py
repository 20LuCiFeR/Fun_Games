import tkinter as tk
import random
import time

class TypingPracticeApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Typing Practice")
        self.root.geometry("420x300")
        self.root.configure(bg="#020617")

        self.start_time = None
        self.correct_count = 0

        self.prev_letter = ""
        self.current_letter = self.random_letter()
        self.next_letter = self.random_letter()

        self.create_ui()
        self.update_letters()

        self.root.bind("<Key>", self.on_key_press)

    def random_letter(self):
        return chr(random.randint(65, 90))  # A-Z

    def create_ui(self):
        tk.Label(
            self.root,
            text="Typing Practice",
            font=("Arial", 16, "bold"),
            fg="#e5e7eb",
            bg="#020617"
        ).pack(pady=10)

        frame = tk.Frame(self.root, bg="#020617")
        frame.pack(pady=10)

        self.prev_label = tk.Label(
            frame, text="-",
            font=("Arial", 40),
            fg="#64748b",
            bg="#020617"
        )
        self.prev_label.pack(side="left", padx=15)

        self.current_label = tk.Label(
            frame, text="A",
            font=("Arial", 64, "bold"),
            fg="#38bdf8",
            bg="#020617"
        )
        self.current_label.pack(side="left", padx=15)

        self.next_label = tk.Label(
            frame, text="-",
            font=("Arial", 40),
            fg="#64748b",
            bg="#020617"
        )
        self.next_label.pack(side="left", padx=15)

        self.stats_label = tk.Label(
            self.root,
            text="Correct: 0 | Speed: 0.00 APS",
            font=("Arial", 12),
            fg="#e5e7eb",
            bg="#020617"
        )
        self.stats_label.pack(pady=10)

        self.hint_label = tk.Label(
            self.root,
            #text="Red = wrong key",
            font=("Arial", 10),
            fg="#94a3b8",
            bg="#020617"
        )
        self.hint_label.pack()

    def update_letters(self):
        self.prev_label.config(text=self.prev_letter or "-")
        self.current_label.config(
            text=self.current_letter,
            fg="#38bdf8"   # reset to default blue
        )
        self.next_label.config(text=self.next_letter)

    def on_key_press(self, event):
        key = event.char.upper()

        if not key.isalpha() or len(key) != 1:
            return

        if self.start_time is None:
            self.start_time = time.perf_counter()

        if key == self.current_letter:
            # ✅ correct → shift immediately
            self.correct_count += 1
            self.shift_letters()
        else:
            # ❌ wrong → show red
            self.current_label.config(fg="#ef4444")

        self.update_stats()

    def shift_letters(self):
        self.prev_letter = self.current_letter
        self.current_letter = self.next_letter
        self.next_letter = self.random_letter()
        self.update_letters()

    def update_stats(self):
        elapsed = time.perf_counter() - self.start_time
        aps = self.correct_count / elapsed if elapsed > 0 else 0.0

        self.stats_label.config(
            text=f"Correct: {self.correct_count} | Speed: {aps:.2f} APS"
        )


if __name__ == "__main__":
    root = tk.Tk()
    TypingPracticeApp(root)
    root.mainloop()

