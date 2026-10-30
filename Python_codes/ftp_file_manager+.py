#!/usr/bin/env python3
"""
Phone FTP Explorer
-------------------
A desktop file manager for browsing your Android phone's storage (shared over
FTP by apps like "File Manager+") and importing/exporting files between your
phone and your Linux PC.

Features: breadcrumb + history navigation, bookmarks sidebar, List & Grid
(with image thumbnails) views, search, sorting, new folder / rename / delete,
properties dialog, right-click context menus, and import/export transfers.

Setup (run once):
    sudo apt install python3-tk        # if tkinter isn't already installed
    pip install --user customtkinter pillow

Run:
    python3 ftp_explorer.py
"""

import os
import json
import posixpath
import re
import tempfile
import threading
import queue
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
from ftplib import FTP, error_perm

try:
    import customtkinter as ctk
except ImportError:
    print("Missing dependency 'customtkinter'. Install it with:\n"
          "    pip install --user customtkinter pillow")
    raise SystemExit(1)

try:
    from PIL import Image
except ImportError:
    Image = None  # thumbnails will simply be skipped

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

BOOKMARKS_FILE = os.path.join(os.path.expanduser("~"), ".ftp_explorer_bookmarks.json")
THUMB_MAX_BYTES = 3 * 1024 * 1024
THUMB_SIZE = (64, 64)
DEFAULT_TILE_COLOR = ("gray86", "gray20")
SELECTED_TILE_COLOR = "#1f6aa5"

ICON_EXT_MAP = {
    "image": (".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".heic"),
    "video": (".mp4", ".mkv", ".mov", ".avi", ".3gp", ".webm"),
    "audio": (".mp3", ".wav", ".flac", ".m4a", ".ogg", ".aac"),
    "archive": (".zip", ".rar", ".7z", ".tar", ".gz"),
    "pdf": (".pdf",),
    "doc": (".doc", ".docx", ".txt", ".odt"),
    "apk": (".apk",),
}
ICON_EMOJI = {
    "dir": "📁", "image": "🖼️", "video": "🎞️", "audio": "🎵",
    "archive": "🗜️", "pdf": "📕", "doc": "📄", "apk": "📦", "file": "📄",
}


# --------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------
def human_size(n):
    n = float(n)
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def classify(entry):
    if entry["type"] == "dir":
        return "dir"
    ext = os.path.splitext(entry["name"])[1].lower()
    for cat, exts in ICON_EXT_MAP.items():
        if ext in exts:
            return cat
    return "file"


def get_icon(entry):
    return ICON_EMOJI[classify(entry)]


def is_image(entry):
    return classify(entry) == "image"


def load_bookmarks():
    try:
        with open(BOOKMARKS_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return []


def save_bookmarks(bookmarks):
    try:
        with open(BOOKMARKS_FILE, "w") as f:
            json.dump(bookmarks, f, indent=2)
    except Exception:
        pass


# --------------------------------------------------------------------------
# FTP helper layer
# --------------------------------------------------------------------------
class FTPClientWrapper:
    LIST_RE = re.compile(
        r"^([\-dl])\S+\s+\d+\s+\S+\s+\S+\s+(\d+)\s+(\w+\s+\d+\s+[\d:]+)\s+(.+)$"
    )

    def __init__(self):
        self.ftp = None

    def connect(self, host, port, user, password, timeout=10):
        self.ftp = FTP(timeout=timeout)
        self.ftp.connect(host, int(port), timeout=timeout)
        self.ftp.login(user, password)
        self.ftp.set_pasv(True)

    def disconnect(self):
        if self.ftp:
            try:
                self.ftp.quit()
            except Exception:
                pass
        self.ftp = None

    def pwd(self):
        return self.ftp.pwd()

    def list_dir(self, path):
        entries = []
        try:
            for name, facts in self.ftp.mlsd(path):
                if name in (".", ".."):
                    continue
                entries.append({
                    "name": name,
                    "type": "dir" if facts.get("type") == "dir" else "file",
                    "size": int(facts.get("size", 0) or 0),
                    "modified": facts.get("modify", ""),
                })
            return entries
        except Exception:
            pass

        entries = []
        lines = []
        self.ftp.cwd(path)
        self.ftp.retrlines("LIST", lines.append)
        for line in lines:
            m = self.LIST_RE.match(line)
            if not m:
                continue
            type_flag, size, mtime, name = m.groups()
            if name in (".", ".."):
                continue
            entries.append({
                "name": name,
                "type": "dir" if type_flag == "d" else "file",
                "size": int(size),
                "modified": mtime,
            })
        return entries

    def download_file(self, remote_path, local_path, progress_cb=None):
        try:
            total = self.ftp.size(remote_path)
        except Exception:
            total = 0
        done = [0]
        with open(local_path, "wb") as f:
            def _cb(data):
                f.write(data)
                done[0] += len(data)
                if progress_cb:
                    progress_cb(done[0], total)
            self.ftp.retrbinary(f"RETR {remote_path}", _cb, blocksize=32768)

    def download_dir(self, remote_dir, local_dir, progress_cb=None):
        os.makedirs(local_dir, exist_ok=True)
        for entry in self.list_dir(remote_dir):
            r_path = posixpath.join(remote_dir, entry["name"])
            l_path = os.path.join(local_dir, entry["name"])
            if entry["type"] == "dir":
                self.download_dir(r_path, l_path, progress_cb)
            else:
                self.download_file(r_path, l_path, progress_cb)

    def upload_file(self, local_path, remote_path, progress_cb=None):
        total = os.path.getsize(local_path)
        done = [0]
        with open(local_path, "rb") as f:
            def _cb(block):
                done[0] += len(block)
                if progress_cb:
                    progress_cb(done[0], total)
            self.ftp.storbinary(f"STOR {remote_path}", f, blocksize=32768, callback=_cb)

    def upload_dir(self, local_dir, remote_dir, progress_cb=None):
        try:
            self.ftp.mkd(remote_dir)
        except error_perm:
            pass
        for name in sorted(os.listdir(local_dir)):
            l_path = os.path.join(local_dir, name)
            r_path = posixpath.join(remote_dir, name)
            if os.path.isdir(l_path):
                self.upload_dir(l_path, r_path, progress_cb)
            else:
                self.upload_file(l_path, r_path, progress_cb)

    def make_dir(self, path):
        self.ftp.mkd(path)

    def delete_file(self, path):
        self.ftp.delete(path)

    def delete_dir(self, path):
        for entry in self.list_dir(path):
            sub = posixpath.join(path, entry["name"])
            if entry["type"] == "dir":
                self.delete_dir(sub)
            else:
                self.ftp.delete(sub)
        self.ftp.rmd(path)

    def rename(self, old_path, new_path):
        self.ftp.rename(old_path, new_path)


# --------------------------------------------------------------------------
# Background thumbnail loader (uses its own dedicated FTP connection so it
# never collides with commands issued from the main thread/connection)
# --------------------------------------------------------------------------
class ThumbnailWorker(threading.Thread):
    def __init__(self, app):
        super().__init__(daemon=True)
        self.app = app
        self.queue = queue.Queue()
        self.client = None
        self.creds = None
        self.tmp_dir = tempfile.mkdtemp(prefix="ftpexp_thumbs_")

    def set_credentials(self, host, port, user, pwd):
        self.creds = (host, port, user, pwd)
        self.client = None  # force reconnect with new creds

    def request(self, remote_path, name, generation, callback):
        self.queue.put((remote_path, name, generation, callback))

    def run(self):
        while True:
            remote_path, name, generation, callback = self.queue.get()
            if Image is None:
                continue
            if self.client is None and self.creds:
                try:
                    self.client = FTPClientWrapper()
                    self.client.connect(*self.creds)
                except Exception:
                    self.client = None
            if self.client is None:
                continue
            try:
                safe_name = re.sub(r"[^a-zA-Z0-9_.-]", "_", name)
                local_tmp = os.path.join(self.tmp_dir, f"{generation}_{safe_name}")
                self.client.download_file(remote_path, local_tmp)
                img = Image.open(local_tmp)
                img.thumbnail(THUMB_SIZE)
                img = img.convert("RGB")
                photo = ctk.CTkImage(light_image=img, dark_image=img, size=img.size)
                self.app.after(0, callback, name, generation, photo)
            except Exception:
                pass


# --------------------------------------------------------------------------
# Main application
# --------------------------------------------------------------------------
class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Phone FTP Explorer")
        self.geometry("980x640")
        self.minsize(780, 480)

        self.client = FTPClientWrapper()
        self.thumb_worker = ThumbnailWorker(self)
        self.thumb_worker.start()

        self.current_path = "/"
        self.root_path = "/"
        self.back_stack = []
        self.forward_stack = []
        self.current_entries = []
        self.entries_map = {}
        self.view_mode = "list"
        self.sort_key = "name"
        self.sort_reverse = False
        self.search_text = ""
        self.grid_selected = set()
        self.grid_tiles = {}
        self.render_generation = 0
        self.bookmarks = load_bookmarks()
        self.busy = False

        self.login_frame = self._build_login_frame()
        self.explorer_frame = self._build_explorer_frame()
        self.login_frame.pack(fill="both", expand=True)

    # ====================== LOGIN SCREEN ======================
    def _build_login_frame(self):
        frame = ctk.CTkFrame(self, fg_color="transparent")
        card = ctk.CTkFrame(frame, corner_radius=16)
        card.place(relx=0.5, rely=0.5, anchor="center")

        ctk.CTkLabel(card, text="📱  Connect to Phone", font=ctk.CTkFont(size=22, weight="bold")) \
            .grid(row=0, column=0, columnspan=2, pady=(24, 18), padx=30)

        self.host_var = tk.StringVar(value="10.209.14.237")
        self.port_var = tk.StringVar(value="7627")
        self.user_var = tk.StringVar(value="")
        self.pass_var = tk.StringVar(value="")

        def add_row(r, label, var, show=None):
            ctk.CTkLabel(card, text=label).grid(row=r, column=0, sticky="w", padx=(30, 10), pady=8)
            entry = ctk.CTkEntry(card, textvariable=var, width=220, show=show)
            entry.grid(row=r, column=1, padx=(0, 30), pady=8)
            return entry

        add_row(1, "Host / IP", self.host_var)
        add_row(2, "Port", self.port_var)
        add_row(3, "Username", self.user_var)
        pass_entry = add_row(4, "Password", self.pass_var, show="•")

        self.login_status = ctk.CTkLabel(card, text="", text_color="#ff6868")
        self.login_status.grid(row=5, column=0, columnspan=2, pady=(4, 0))

        self.connect_btn = ctk.CTkButton(card, text="Connect", command=self._on_connect_clicked, height=38)
        self.connect_btn.grid(row=6, column=0, columnspan=2, pady=(16, 26), padx=30, sticky="ew")
        pass_entry.bind("<Return>", lambda e: self._on_connect_clicked())
        return frame

    def _on_connect_clicked(self):
        host, port = self.host_var.get().strip(), self.port_var.get().strip()
        user, pwd = self.user_var.get().strip(), self.pass_var.get()
        if not host or not port:
            self.login_status.configure(text="Host and port are required.")
            return
        self.connect_btn.configure(state="disabled", text="Connecting...")
        self.login_status.configure(text="")

        def task():
            try:
                self.client.connect(host, port, user, pwd)
                root = self.client.pwd()
                self.after(0, lambda: self._on_connected(root, host, port, user, pwd))
            except Exception as e:
                self.after(0, lambda: self._on_connect_failed(str(e)))

        threading.Thread(target=task, daemon=True).start()

    def _on_connect_failed(self, msg):
        self.connect_btn.configure(state="normal", text="Connect")
        self.login_status.configure(text=f"Couldn't connect: {msg}")

    def _on_connected(self, root_path, host, port, user, pwd):
        self.connect_btn.configure(state="normal", text="Connect")
        self.root_path = root_path or "/"
        self.thumb_worker.set_credentials(host, int(port), user, pwd)
        self.login_frame.pack_forget()
        self.explorer_frame.pack(fill="both", expand=True)
        self._render_sidebar()
        self.navigate_to(self.root_path, record_history=False)

    def disconnect(self):
        self.client.disconnect()
        self.thumb_worker.client = None
        self.thumb_worker.creds = None
        self.back_stack.clear()
        self.forward_stack.clear()
        self.explorer_frame.pack_forget()
        self.login_frame.pack(fill="both", expand=True)

    # ====================== EXPLORER SCREEN ======================
    def _build_explorer_frame(self):
        frame = ctk.CTkFrame(self, fg_color="transparent")

        # ---- Toolbar ----
        toolbar = ctk.CTkFrame(frame, fg_color="transparent")
        toolbar.pack(fill="x", padx=12, pady=(10, 4))

        self.back_btn = ctk.CTkButton(toolbar, text="←", width=34, command=self.go_back, state="disabled")
        self.back_btn.pack(side="left")
        self.forward_btn = ctk.CTkButton(toolbar, text="→", width=34, command=self.go_forward, state="disabled")
        self.forward_btn.pack(side="left", padx=(4, 0))
        ctk.CTkButton(toolbar, text="⬆ Up", width=56, command=self.go_up).pack(side="left", padx=(8, 0))
        ctk.CTkButton(toolbar, text="🏠", width=34, command=lambda: self.navigate_to(self.root_path)).pack(side="left", padx=(4, 0))
        ctk.CTkButton(toolbar, text="⟲", width=34, command=self.refresh_listing).pack(side="left", padx=(4, 0))
        ctk.CTkButton(toolbar, text="＋ Folder", width=90, command=self.new_folder).pack(side="left", padx=(10, 0))
        ctk.CTkButton(toolbar, text="✎ Rename", width=90, command=self.rename_selected).pack(side="left", padx=(4, 0))
        ctk.CTkButton(toolbar, text="🗑 Delete", width=80, fg_color="#8a2c2c", hover_color="#6e2222",
                      command=self.delete_selected).pack(side="left", padx=(4, 0))

        ctk.CTkButton(toolbar, text="Disconnect", width=100, fg_color="#5a5a5a", hover_color="#444444",
                      command=self.disconnect).pack(side="right")
        self.view_seg = ctk.CTkSegmentedButton(toolbar, values=["List", "Grid"], command=self._on_view_change)
        self.view_seg.set("List")
        self.view_seg.pack(side="right", padx=(0, 10))
        self.sort_dir_btn = ctk.CTkButton(toolbar, text="⬆", width=30, command=self._toggle_sort_dir)
        self.sort_dir_btn.pack(side="right", padx=(0, 4))
        self.sort_var = tk.StringVar(value="Name")
        ctk.CTkOptionMenu(toolbar, values=["Name", "Size", "Modified"], variable=self.sort_var, width=100,
                          command=self._on_sort_change).pack(side="right", padx=(0, 4))
        self.search_var = tk.StringVar()
        self.search_entry = ctk.CTkEntry(toolbar, textvariable=self.search_var,
                                          placeholder_text="Search this folder...", width=170)
        self.search_entry.pack(side="right", padx=(0, 10))
        self.search_var.trace_add("write", lambda *a: self._on_search_change())

        # ---- Breadcrumb ----
        self.breadcrumb_frame = ctk.CTkFrame(frame, fg_color="transparent")
        self.breadcrumb_frame.pack(fill="x", padx=12, pady=(2, 6))

        # ---- Body: sidebar + content ----
        body = ctk.CTkFrame(frame, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=12, pady=(0, 4))

        sidebar = ctk.CTkFrame(body, width=170, corner_radius=10)
        sidebar.pack(side="left", fill="y", padx=(0, 8))
        ctk.CTkLabel(sidebar, text="Quick Access", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=12, pady=(12, 6))
        self.sidebar_list_frame = ctk.CTkScrollableFrame(sidebar, width=150, fg_color="transparent")
        self.sidebar_list_frame.pack(fill="both", expand=True, padx=4, pady=(0, 10))

        content = ctk.CTkFrame(body, fg_color="transparent")
        content.pack(side="left", fill="both", expand=True)

        # List view
        self.list_container = ctk.CTkFrame(content)
        style = ttk.Style()
        style.theme_use("default")
        style.configure("Treeview", background="#2b2b2b", fieldbackground="#2b2b2b",
                         foreground="white", rowheight=26, borderwidth=0, font=("Sans", 11))
        style.configure("Treeview.Heading", background="#1f1f1f", foreground="white", font=("Sans", 11, "bold"))
        style.map("Treeview", background=[("selected", "#1f6aa5")])

        self.tree = ttk.Treeview(self.list_container, columns=("size", "modified"), show="tree headings",
                                  selectmode="extended")
        self.tree.heading("#0", text="Name", command=lambda: self._set_sort("name"))
        self.tree.heading("size", text="Size", command=lambda: self._set_sort("size"))
        self.tree.heading("modified", text="Modified", command=lambda: self._set_sort("modified"))
        self.tree.column("#0", width=400)
        self.tree.column("size", width=100, anchor="e")
        self.tree.column("modified", width=160)
        self.tree.pack(side="left", fill="both", expand=True, padx=4, pady=4)
        scroll = ttk.Scrollbar(self.list_container, orient="vertical", command=self.tree.yview)
        scroll.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.bind("<Double-1>", self._on_tree_double_click)
        self.tree.bind("<<TreeviewSelect>>", lambda e: self._update_status_bar(total_items=len(self.entries_map)))
        self.tree.bind("<Button-3>", self._on_tree_right_click)
        self.tree.bind("<Delete>", lambda e: self.delete_selected())
        self.tree.bind("<F2>", lambda e: self.rename_selected())
        self.list_container.pack(fill="both", expand=True)

        # Grid view (built but not packed until selected)
        self.grid_container = ctk.CTkScrollableFrame(content, fg_color="transparent")
        self.grid_container.bind("<Button-3>", lambda e: self._show_context_menu(e, []))

        # ---- Bottom bar ----
        bottom = ctk.CTkFrame(frame, fg_color="transparent")
        bottom.pack(fill="x", padx=12, pady=(0, 10))
        ctk.CTkButton(bottom, text="⬇ Import", command=self.download_selected).pack(side="left")
        ctk.CTkButton(bottom, text="⬆ Export Files...", command=self.upload_files).pack(side="left", padx=8)
        ctk.CTkButton(bottom, text="⬆ Export Folder...", command=self.upload_folder).pack(side="left")
        self.status_var = tk.StringVar(value="Ready")
        ctk.CTkLabel(bottom, textvariable=self.status_var).pack(side="right", padx=(10, 0))
        self.progress_bar = ctk.CTkProgressBar(bottom, width=180)
        self.progress_bar.set(0)
        self.progress_bar.pack(side="right")

        self.bind_all("<F5>", lambda e: self.refresh_listing())
        self.bind_all("<Control-f>", lambda e: self.search_entry.focus_set())
        return frame

    # ---------------- Navigation ----------------
    def navigate_to(self, path, record_history=True):
        path = path or "/"
        if record_history and path != self.current_path:
            self.back_stack.append(self.current_path)
            self.forward_stack.clear()
        self.current_path = path
        self.grid_selected.clear()
        self._build_breadcrumb()
        self._update_nav_buttons()
        self.refresh_listing()

    def go_up(self):
        parent = posixpath.dirname(self.current_path.rstrip("/")) or "/"
        self.navigate_to(parent)

    def go_back(self):
        if not self.back_stack:
            return
        self.forward_stack.append(self.current_path)
        prev = self.back_stack.pop()
        self.navigate_to(prev, record_history=False)
        self._update_nav_buttons()

    def go_forward(self):
        if not self.forward_stack:
            return
        self.back_stack.append(self.current_path)
        nxt = self.forward_stack.pop()
        self.navigate_to(nxt, record_history=False)
        self._update_nav_buttons()

    def _update_nav_buttons(self):
        self.back_btn.configure(state="normal" if self.back_stack else "disabled")
        self.forward_btn.configure(state="normal" if self.forward_stack else "disabled")

    def _build_breadcrumb(self):
        for child in self.breadcrumb_frame.winfo_children():
            child.destroy()
        segments = [s for s in self.current_path.strip("/").split("/") if s]
        ctk.CTkButton(self.breadcrumb_frame, text="🏠", width=30,
                      command=lambda: self.navigate_to(self.root_path)).pack(side="left")
        start_idx = 0
        display_segments = segments
        if len(segments) > 4:
            ctk.CTkLabel(self.breadcrumb_frame, text=" … ").pack(side="left")
            display_segments = segments[-3:]
            start_idx = len(segments) - 3
        cumulative = "/" + "/".join(segments[:start_idx]) if start_idx else "/"
        for seg in display_segments:
            cumulative = posixpath.join(cumulative, seg)
            ctk.CTkLabel(self.breadcrumb_frame, text="›").pack(side="left", padx=2)
            ctk.CTkButton(self.breadcrumb_frame, text=seg, fg_color="transparent",
                          command=lambda p=cumulative: self.navigate_to(p)).pack(side="left")
        ctk.CTkButton(self.breadcrumb_frame, text="✎", width=26,
                      command=self._toggle_path_edit).pack(side="left", padx=(8, 0))

    def _toggle_path_edit(self):
        existing = getattr(self, "path_edit_entry", None)
        if existing is not None and existing.winfo_ismapped():
            existing.pack_forget()
            return
        self.path_edit_var = tk.StringVar(value=self.current_path)
        self.path_edit_entry = ctk.CTkEntry(self.breadcrumb_frame, textvariable=self.path_edit_var, width=300)
        self.path_edit_entry.pack(side="left", padx=(8, 0))
        self.path_edit_entry.focus_set()
        self.path_edit_entry.bind("<Return>", lambda e: self.navigate_to(self.path_edit_var.get()))
        self.path_edit_entry.bind("<Escape>", lambda e: self.path_edit_entry.pack_forget())

    # ---------------- Sidebar / bookmarks ----------------
    def _render_sidebar(self):
        for child in self.sidebar_list_frame.winfo_children():
            child.destroy()
        ctk.CTkButton(self.sidebar_list_frame, text="🏠 Home", anchor="w", fg_color="transparent",
                      command=lambda: self.navigate_to(self.root_path)).pack(fill="x", pady=2)
        for bm in self.bookmarks:
            btn = ctk.CTkButton(self.sidebar_list_frame, text=f"⭐ {bm['name']}", anchor="w", fg_color="transparent",
                                 command=lambda p=bm["path"]: self.navigate_to(p))
            btn.pack(fill="x", pady=2)
            btn.bind("<Button-3>", lambda e, b=bm: self._sidebar_context_menu(e, b))

    def _sidebar_context_menu(self, event, bookmark):
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="Remove Bookmark", command=lambda: self.remove_bookmark(bookmark))
        menu.tk_popup(event.x_root, event.y_root)

    def add_bookmark(self, entry):
        path = posixpath.join(self.current_path, entry["name"])
        if any(b["path"] == path for b in self.bookmarks):
            return
        self.bookmarks.append({"name": entry["name"], "path": path})
        save_bookmarks(self.bookmarks)
        self._render_sidebar()

    def remove_bookmark(self, bookmark):
        self.bookmarks = [b for b in self.bookmarks if b["path"] != bookmark["path"]]
        save_bookmarks(self.bookmarks)
        self._render_sidebar()

    # ---------------- Listing / rendering ----------------
    def refresh_listing(self):
        self._run_async(lambda: self.client.list_dir(self.current_path), on_done=self._on_listed)

    def _on_listed(self, entries, error):
        if error:
            messagebox.showerror("Error", f"Couldn't list folder:\n{error}")
            return
        self.current_entries = entries
        self.render()

    def render(self):
        self.render_generation += 1
        text = self.search_text.lower()
        filtered = [e for e in self.current_entries if text in e["name"].lower()] if text else list(self.current_entries)
        key_fn = {
            "name": lambda e: e["name"].lower(),
            "size": lambda e: e["size"],
            "modified": lambda e: e["modified"],
        }[self.sort_key]
        dirs = sorted([e for e in filtered if e["type"] == "dir"], key=key_fn, reverse=self.sort_reverse)
        files = sorted([e for e in filtered if e["type"] == "file"], key=key_fn, reverse=self.sort_reverse)
        ordered = dirs + files
        self.entries_map = {e["name"]: e for e in ordered}
        if self.view_mode == "list":
            self._render_list(ordered)
        else:
            self._render_grid(ordered)
        self._update_status_bar(total_items=len(ordered))

    def _render_list(self, entries):
        self.tree.delete(*self.tree.get_children())
        for e in entries:
            icon = get_icon(e) + " "
            size_txt = "—" if e["type"] == "dir" else human_size(e["size"])
            self.tree.insert("", "end", iid=e["name"], text=icon + e["name"], values=(size_txt, e["modified"]))

    def _render_grid(self, entries):
        for child in self.grid_container.winfo_children():
            child.destroy()
        self.grid_tiles = {}
        cols = 6
        for idx, entry in enumerate(entries):
            r, c = divmod(idx, cols)
            tile = ctk.CTkFrame(self.grid_container, width=100, height=110, corner_radius=10,
                                 fg_color=DEFAULT_TILE_COLOR)
            tile.grid(row=r, column=c, padx=6, pady=6)
            tile.grid_propagate(False)
            icon_lbl = ctk.CTkLabel(tile, text=get_icon(entry), font=ctk.CTkFont(size=30))
            icon_lbl.pack(pady=(8, 2))
            name_lbl = ctk.CTkLabel(tile, text=entry["name"], font=ctk.CTkFont(size=10), wraplength=90)
            name_lbl.pack()
            for widget in (tile, icon_lbl, name_lbl):
                widget.bind("<Button-1>", lambda e, n=entry["name"]: self._on_grid_click(n, e))
                widget.bind("<Double-Button-1>", lambda e, en=entry: self._on_grid_double_click(en))
                widget.bind("<Button-3>", lambda e, en=entry: self._on_grid_right_click(e, en))
            self.grid_tiles[entry["name"]] = {"frame": tile, "icon_label": icon_lbl}
            if is_image(entry) and entry["size"] <= THUMB_MAX_BYTES:
                remote_path = posixpath.join(self.current_path, entry["name"])
                self.thumb_worker.request(remote_path, entry["name"], self.render_generation, self._apply_thumbnail)

    def _apply_thumbnail(self, name, generation, photo):
        if generation != self.render_generation:
            return
        tile = self.grid_tiles.get(name)
        if tile:
            tile["icon_label"].configure(image=photo, text="")
            tile["icon_label"].image = photo

    # ---------------- Selection helpers ----------------
    def get_selected_entries(self):
        if self.view_mode == "list":
            names = self.tree.selection()
        else:
            names = list(self.grid_selected)
        return [self.entries_map[n] for n in names if n in self.entries_map]

    def _on_grid_click(self, name, event):
        ctrl = bool(event.state & 0x0004)
        if ctrl:
            if name in self.grid_selected:
                self.grid_selected.discard(name)
            else:
                self.grid_selected.add(name)
        else:
            self.grid_selected = {name}
        for n in self.grid_tiles:
            selected = n in self.grid_selected
            self.grid_tiles[n]["frame"].configure(fg_color=SELECTED_TILE_COLOR if selected else DEFAULT_TILE_COLOR)
        self._update_status_bar(total_items=len(self.entries_map))

    def _on_grid_double_click(self, entry):
        if entry["type"] == "dir":
            self.navigate_to(posixpath.join(self.current_path, entry["name"]))

    def _on_tree_double_click(self, _event):
        sel = self.tree.selection()
        if not sel:
            return
        entry = self.entries_map.get(sel[0])
        if entry and entry["type"] == "dir":
            self.navigate_to(posixpath.join(self.current_path, entry["name"]))

    # ---------------- View / sort / search ----------------
    def _on_view_change(self, value):
        self.view_mode = "list" if value == "List" else "grid"
        if self.view_mode == "list":
            self.grid_container.pack_forget()
            self.list_container.pack(fill="both", expand=True)
        else:
            self.list_container.pack_forget()
            self.grid_container.pack(fill="both", expand=True)
        self.render()

    def _on_sort_change(self, value):
        self.sort_key = value.lower()
        self.sort_reverse = False
        self.sort_dir_btn.configure(text="⬆")
        self.render()

    def _set_sort(self, key):
        if self.sort_key == key:
            self.sort_reverse = not self.sort_reverse
        else:
            self.sort_key = key
            self.sort_reverse = False
        self.sort_var.set(key.capitalize())
        self.sort_dir_btn.configure(text="⬇" if self.sort_reverse else "⬆")
        self.render()

    def _toggle_sort_dir(self):
        self.sort_reverse = not self.sort_reverse
        self.sort_dir_btn.configure(text="⬇" if self.sort_reverse else "⬆")
        self.render()

    def _on_search_change(self):
        self.search_text = self.search_var.get()
        self.render()

    # ---------------- Context menus ----------------
    def _on_tree_right_click(self, event):
        iid = self.tree.identify_row(event.y)
        if iid:
            if iid not in self.tree.selection():
                self.tree.selection_set(iid)
            entries = self.get_selected_entries()
        else:
            entries = []
        self._show_context_menu(event, entries)

    def _on_grid_right_click(self, event, entry):
        if entry["name"] not in self.grid_selected:
            self.grid_selected = {entry["name"]}
            for n in self.grid_tiles:
                selected = n in self.grid_selected
                self.grid_tiles[n]["frame"].configure(fg_color=SELECTED_TILE_COLOR if selected else DEFAULT_TILE_COLOR)
        self._show_context_menu(event, self.get_selected_entries())

    def _show_context_menu(self, event, entries):
        menu = tk.Menu(self, tearoff=0, bg="#2b2b2b", fg="white", activebackground="#1f6aa5", activeforeground="white")
        if not entries:
            menu.add_command(label="New Folder", command=self.new_folder)
            menu.add_command(label="Refresh", command=self.refresh_listing)
        elif len(entries) == 1:
            entry = entries[0]
            if entry["type"] == "dir":
                menu.add_command(label="Open", command=lambda: self.navigate_to(posixpath.join(self.current_path, entry["name"])))
                menu.add_command(label="Add Bookmark", command=lambda: self.add_bookmark(entry))
            else:
                menu.add_command(label="Download", command=lambda: self._download_entries([entry]))
            menu.add_separator()
            menu.add_command(label="Rename", command=lambda: self.rename_entry(entry))
            menu.add_command(label="Delete", command=lambda: self.delete_entries([entry]))
            menu.add_command(label="Properties", command=lambda: self.show_properties(entry))
        else:
            menu.add_command(label="Download", command=lambda: self._download_entries(entries))
            menu.add_command(label="Delete", command=lambda: self.delete_entries(entries))
        menu.tk_popup(event.x_root, event.y_root)

    # ---------------- File operations ----------------
    def new_folder(self):
        name = simpledialog.askstring("New Folder", "Folder name:", parent=self)
        if not name:
            return
        remote_path = posixpath.join(self.current_path, name)
        self._run_async(lambda: self.client.make_dir(remote_path),
                         on_done=lambda r, err: self._after_mutation("Create folder", err))

    def rename_entry(self, entry):
        new_name = simpledialog.askstring("Rename", "New name:", initialvalue=entry["name"], parent=self)
        if not new_name or new_name == entry["name"]:
            return
        old_path = posixpath.join(self.current_path, entry["name"])
        new_path = posixpath.join(self.current_path, new_name)
        self._run_async(lambda: self.client.rename(old_path, new_path),
                         on_done=lambda r, err: self._after_mutation("Rename", err))

    def rename_selected(self):
        entries = self.get_selected_entries()
        if len(entries) != 1:
            messagebox.showinfo("Rename", "Select exactly one item to rename.")
            return
        self.rename_entry(entries[0])

    def delete_entries(self, entries):
        names = ", ".join(e["name"] for e in entries)
        if not messagebox.askyesno("Delete", f"Permanently delete:\n{names}\n\nThis cannot be undone."):
            return

        def task():
            for e in entries:
                path = posixpath.join(self.current_path, e["name"])
                if e["type"] == "dir":
                    self.client.delete_dir(path)
                else:
                    self.client.delete_file(path)

        self._run_async(task, on_done=lambda r, err: self._after_mutation("Delete", err))

    def delete_selected(self):
        entries = self.get_selected_entries()
        if not entries:
            messagebox.showinfo("Delete", "Select one or more items first.")
            return
        self.delete_entries(entries)

    def _after_mutation(self, label, error):
        if error:
            messagebox.showerror(label, f"{label} failed:\n{error}")
        self.refresh_listing()

    def show_properties(self, entry):
        win = ctk.CTkToplevel(self)
        win.title("Properties")
        win.geometry("380x230")
        win.attributes("-topmost", True)
        full_path = posixpath.join(self.current_path, entry["name"])
        rows = [
            ("Name", entry["name"]),
            ("Type", "Folder" if entry["type"] == "dir" else "File"),
            ("Size", "—" if entry["type"] == "dir" else f"{human_size(entry['size'])} ({entry['size']:,} bytes)"),
            ("Modified", entry["modified"] or "Unknown"),
            ("Path", full_path),
        ]
        for i, (k, v) in enumerate(rows):
            ctk.CTkLabel(win, text=k + ":", font=ctk.CTkFont(weight="bold"), anchor="w") \
                .grid(row=i, column=0, sticky="nw", padx=14, pady=6)
            ctk.CTkLabel(win, text=str(v), anchor="w", wraplength=220, justify="left") \
                .grid(row=i, column=1, sticky="w", padx=4, pady=6)

    # ---------------- Transfers ----------------
    def _download_entries(self, entries):
        dest_dir = filedialog.askdirectory(title="Choose a folder on this PC to save into")
        if not dest_dir:
            return

        def task():
            for entry in entries:
                r_path = posixpath.join(self.current_path, entry["name"])
                l_path = os.path.join(dest_dir, entry["name"])
                if entry["type"] == "dir":
                    self.client.download_dir(r_path, l_path, self._progress_cb)
                else:
                    self.client.download_file(r_path, l_path, self._progress_cb)

        self._run_async(task, on_done=lambda r, err: self._finish_transfer("Import", err))

    def download_selected(self):
        entries = self.get_selected_entries()
        if not entries:
            messagebox.showinfo("Import", "Select one or more files/folders first.")
            return
        self._download_entries(entries)

    def upload_files(self):
        paths = filedialog.askopenfilenames(title="Choose file(s) to send to the phone")
        if not paths:
            return

        def task():
            for p in paths:
                remote = posixpath.join(self.current_path, os.path.basename(p))
                self.client.upload_file(p, remote, self._progress_cb)

        self._run_async(task, on_done=lambda r, err: self._finish_transfer("Export", err, refresh=True))

    def upload_folder(self):
        path = filedialog.askdirectory(title="Choose a folder to send to the phone")
        if not path:
            return
        remote = posixpath.join(self.current_path, os.path.basename(path.rstrip("/")))

        def task():
            self.client.upload_dir(path, remote, self._progress_cb)

        self._run_async(task, on_done=lambda r, err: self._finish_transfer("Export", err, refresh=True))

    def _progress_cb(self, current, total):
        self.after(0, self._update_progress_ui, current, total)

    def _update_progress_ui(self, current, total):
        if total:
            self.progress_bar.set(min(current / total, 1.0))
            self.status_var.set(f"Transferring... {human_size(current)}/{human_size(total)}")
        else:
            self.status_var.set(f"Transferring... {human_size(current)}")

    def _finish_transfer(self, label, error, refresh=False):
        self.progress_bar.set(0)
        if error:
            messagebox.showerror(label, f"{label} failed:\n{error}")
            self.status_var.set("Error")
        else:
            self.status_var.set(f"{label} complete")
        if refresh:
            self.refresh_listing()

    # ---------------- Status bar ----------------
    def _update_status_bar(self, total_items=None):
        sel = self.get_selected_entries()
        parts = []
        if total_items is not None:
            parts.append(f"{total_items} item(s)")
        if sel:
            total_size = sum(e["size"] for e in sel if e["type"] == "file")
            parts.append(f"{len(sel)} selected ({human_size(total_size)})")
        self.status_var.set(" • ".join(parts) if parts else "Ready")

    # ---------------- Async helper ----------------
    def _run_async(self, func, on_done=None):
        if self.busy:
            return
        self.busy = True

        def task():
            try:
                result = func()
                error = None
            except Exception as e:
                result, error = None, e

            def finish():
                self.busy = False
                if on_done:
                    on_done(result, error)
            self.after(0, finish)

        threading.Thread(target=task, daemon=True).start()


if __name__ == "__main__":
    app = App()
    app.mainloop()
