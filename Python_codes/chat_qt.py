"""
IP Chat - Multi Contact (PyQt6, WhatsApp-style)
-------------------------------------------------
Run this script on every PC that wants to chat. There is NO host/join screen -
the app opens straight into the chat UI and quietly listens in the background
so friends can reach you.

Two ways a chat starts:
1. Someone adds YOUR ip as a friend on their side -> you'll see them appear
   automatically in your sidebar, no action needed from you.
2. You click "+ Add Friend" and type their IP -> they appear in your sidebar
   (and on their side, you appear automatically too).

You can add as many friends as you want; every conversation is kept separate
in the sidebar, each with its own online/offline status and chat history.
Contacts are identified by IP address (shown as their name).

You can also send files (any type - images, docs, zips, etc.) using the
"Send File" button next to the message box. Received files are saved under
~/IPChat_Received/<sender-ip>/ and can be opened straight from the chat
bubble with the "Open" button.

Requirements:
    None to install manually - this script checks for PyQt6 on startup and
    auto-installs it with pip if it's missing.

Port 5557 (TCP) must be allowed through any firewall on every PC running this.
"""

import sys
import subprocess
import importlib.util


def _ensure_dependencies():
    """Auto-install any missing required packages before we try to import them."""
    required = {"PyQt6": "PyQt6"}
    missing = [pip_name for mod_name, pip_name in required.items()
               if importlib.util.find_spec(mod_name) is None]
    if not missing:
        return
    print(f"[setup] Missing package(s): {', '.join(missing)} - installing now, please wait...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", *missing])
    except subprocess.CalledProcessError:
        # Fall back to --user install if the system install is blocked (e.g. permissions)
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--user", *missing])
    print("[setup] Done installing. Continuing startup...")


_ensure_dependencies()

import os
import socket
import base64
import threading
from datetime import datetime

from PyQt6.QtCore import Qt, pyqtSignal, QObject, QTimer
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QMessageBox, QScrollArea, QFrame,
    QListWidget, QListWidgetItem, QInputDialog, QFileDialog,
)

PORT = 5557
MAX_FILE_SIZE = 25 * 1024 * 1024  # 25 MB soft cap (files are sent as one base64 line)
RECEIVED_DIR = os.path.join(os.path.expanduser("~"), "IPChat_Received")

# NOTE ON STYLING: buttons/inputs that live inside a QFrame which has its own
# setStyleSheet(...) do NOT reliably inherit QPushButton/QLineEdit rules from
# an ancestor's stylesheet in Qt. So instead of relying on the global
# stylesheet for these controls, we apply the style directly to each widget.
BUTTON_STYLE = """
    QPushButton {
        background-color: #128C7E; color: #ffffff; border: none;
        border-radius: 8px; padding: 8px 14px; font-size: 13px;
    }
    QPushButton:hover { background-color: #0f7a6e; }
    QPushButton:pressed { background-color: #0c675d; }
"""

SECONDARY_BUTTON_STYLE = """
    QPushButton {
        background-color: #ffffff; color: #128C7E; border: 1px solid #128C7E;
        border-radius: 8px; padding: 6px 12px; font-size: 12px;
    }
    QPushButton:hover { background-color: #EAF7F5; }
    QPushButton:pressed { background-color: #DCEFEC; }
"""

LINEEDIT_STYLE = """
    QLineEdit {
        background-color: #ffffff; color: #222222; border: 1px solid #cfcfcf;
        border-radius: 18px; padding: 8px 14px; font-size: 14px;
    }
"""


def get_local_ip():
    """Best-effort guess at this machine's LAN IP (no packets are actually sent)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip


def human_size(num_bytes):
    for unit in ["B", "KB", "MB", "GB"]:
        if num_bytes < 1024:
            return f"{num_bytes:.0f} {unit}" if unit == "B" else f"{num_bytes:.1f} {unit}"
        num_bytes /= 1024
    return f"{num_bytes:.1f} TB"


def unique_path(directory, filename):
    """Return a path in `directory` for `filename`, adding (1), (2)... on collision."""
    os.makedirs(directory, exist_ok=True)
    base, ext = os.path.splitext(filename)
    candidate = os.path.join(directory, filename)
    counter = 1
    while os.path.exists(candidate):
        candidate = os.path.join(directory, f"{base} ({counter}){ext}")
        counter += 1
    return candidate


def open_in_file_explorer(path):
    try:
        if sys.platform.startswith("win"):
            os.startfile(path)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
    except Exception as e:
        QMessageBox.warning(None, "Could not open file", f"Couldn't open the file automatically:\n{e}\n\nIt is saved at:\n{path}")


class NetworkSignals(QObject):
    contact_connected = pyqtSignal(str, object)          # ip, socket connection
    message_received = pyqtSignal(str, str)               # ip, text
    file_received = pyqtSignal(str, str, str, int)         # ip, filename, saved_path, size
    contact_disconnected = pyqtSignal(str)                 # ip
    error = pyqtSignal(str)


class ContactRowWidget(QWidget):
    """One row in the sidebar: status dot + IP address + online/offline text."""

    def __init__(self, ip, online):
        super().__init__()
        layout = QHBoxLayout()
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(8)

        self.dot = QLabel()
        self.dot.setFixedSize(10, 10)
        layout.addWidget(self.dot)

        self.ip_label = QLabel(ip)
        layout.addWidget(self.ip_label)
        layout.addStretch()

        self.status_label = QLabel()
        self.status_label.setStyleSheet("color: #888888; font-size: 11px;")
        layout.addWidget(self.status_label)

        self.setLayout(layout)
        self.set_online(online)
        self.set_unread(0)

    def set_online(self, online):
        color = "#2ECC71" if online else "#B0B0B0"
        self.dot.setStyleSheet(f"background-color:{color}; border-radius:5px;")
        self.status_label.setText("Online" if online else "Offline")

    def set_unread(self, count):
        if count > 0:
            self.ip_label.setStyleSheet("color:#075E54; font-size:13px; font-weight:bold;")
        else:
            self.ip_label.setStyleSheet("color:#222222; font-size:13px; font-weight:normal;")


class ChatApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("IP Chat")
        self.resize(760, 600)

        self.signals = NetworkSignals()
        self.signals.contact_connected.connect(self.on_contact_connected)
        self.signals.message_received.connect(self.on_message_received)
        self.signals.file_received.connect(self.on_file_received)
        self.signals.contact_disconnected.connect(self.on_contact_disconnected)
        self.signals.error.connect(self.on_error)

        # messages entries are dicts:
        #   text -> {"kind":"text","text":str,"is_own":bool,"ts":str}
        #   file -> {"kind":"file","filename":str,"path":str,"size":int,"is_own":bool,"ts":str}
        self.contacts = {}        # ip -> {"conn": socket|None, "online": bool, "messages": [...]}
        self.sidebar_rows = {}    # ip -> ContactRowWidget
        self.sidebar_items = {}   # ip -> QListWidgetItem
        self.unread_counts = {}   # ip -> int
        self.current_ip = None
        self.pending_manual_connect = None
        self.server_socket = None

        self.apply_global_styles()
        self.build_ui()

        threading.Thread(target=self._server_loop, daemon=True).start()

    # ---------- styling ----------

    def apply_global_styles(self):
        self.setStyleSheet("""
            QMainWindow { background-color: #ffffff; }
            QLabel { color: #222222; font-size: 13px; }
        """)

    # ---------- UI construction ----------

    def build_ui(self):
        central = QWidget()
        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ----- Sidebar -----
        sidebar = QFrame()
        sidebar.setFixedWidth(240)
        sidebar.setStyleSheet("background-color:#F7F7F7; border-right:1px solid #dddddd;")
        side_layout = QVBoxLayout()
        side_layout.setContentsMargins(14, 14, 14, 14)
        side_layout.setSpacing(10)

        title = QLabel("Chats")
        title.setStyleSheet("font-size:20px; font-weight:bold; color:#075E54;")
        side_layout.addWidget(title)

        self.my_ip_label = QLabel(f"Your IP: {get_local_ip()}")
        self.my_ip_label.setWordWrap(True)
        self.my_ip_label.setStyleSheet("color:#555555; font-size:11px;")
        side_layout.addWidget(self.my_ip_label)

        add_btn = QPushButton("+ Add Friend")
        add_btn.setStyleSheet(BUTTON_STYLE)
        add_btn.setMinimumHeight(34)
        add_btn.clicked.connect(self.add_friend_dialog)
        side_layout.addWidget(add_btn)

        self.contact_list = QListWidget()
        self.contact_list.setStyleSheet("""
            QListWidget { border:none; background-color:#F7F7F7; }
            QListWidget::item:selected { background-color:#DCEEFB; }
            QListWidget::item:hover { background-color:#EDEDED; }
        """)
        self.contact_list.itemClicked.connect(self.on_contact_clicked)
        side_layout.addWidget(self.contact_list, stretch=1)

        sidebar.setLayout(side_layout)
        main_layout.addWidget(sidebar)

        # ----- Chat panel -----
        chat_holder = QWidget()
        chat_panel = QVBoxLayout()
        chat_panel.setContentsMargins(0, 0, 0, 0)
        chat_panel.setSpacing(0)

        header = QFrame()
        header.setFixedHeight(56)
        header.setStyleSheet("background-color:#075E54;")
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(16, 0, 16, 0)
        self.chat_header_label = QLabel("No conversation selected")
        self.chat_header_label.setStyleSheet(
            "color:white; font-size:15px; font-weight:bold; background:transparent;"
        )
        header_layout.addWidget(self.chat_header_label)
        header_layout.addStretch()
        header.setLayout(header_layout)
        chat_panel.addWidget(header)

        self.messages_container = QWidget()
        self.messages_container.setStyleSheet("background-color:#ECE5DD;")
        self.messages_layout = QVBoxLayout()
        self.messages_layout.setContentsMargins(10, 10, 10, 10)
        self.messages_layout.setSpacing(6)
        self.messages_layout.addStretch(1)
        self.messages_container.setLayout(self.messages_layout)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setWidget(self.messages_container)
        self.scroll_area.setStyleSheet("QScrollArea { border:none; }")
        chat_panel.addWidget(self.scroll_area, stretch=1)

        input_row = QFrame()
        input_row.setStyleSheet("background-color:#F0F0F0;")
        input_layout = QHBoxLayout()
        input_layout.setContentsMargins(10, 10, 10, 10)
        input_layout.setSpacing(8)

        self.file_btn = QPushButton("\U0001F4CE")  # paperclip
        self.file_btn.setToolTip("Send a file")
        self.file_btn.setStyleSheet(SECONDARY_BUTTON_STYLE)
        self.file_btn.setFixedWidth(40)
        self.file_btn.clicked.connect(self.send_file_dialog)
        input_layout.addWidget(self.file_btn)

        self.msg_input = QLineEdit()
        self.msg_input.setStyleSheet(LINEEDIT_STYLE)
        self.msg_input.returnPressed.connect(self.send_chat_message)
        input_layout.addWidget(self.msg_input, stretch=1)

        self.send_btn = QPushButton("Send")
        self.send_btn.setStyleSheet(BUTTON_STYLE)
        self.send_btn.clicked.connect(self.send_chat_message)
        input_layout.addWidget(self.send_btn)

        input_row.setLayout(input_layout)
        chat_panel.addWidget(input_row)

        chat_holder.setLayout(chat_panel)
        main_layout.addWidget(chat_holder, stretch=1)

        central.setLayout(main_layout)
        self.setCentralWidget(central)

        self.show_welcome_state()

    def show_welcome_state(self):
        self.clear_message_view()
        welcome = QLabel(
            "Add a friend using their IP (top-left), or select someone from the "
            "list to start chatting."
        )
        welcome.setWordWrap(True)
        welcome.setAlignment(Qt.AlignmentFlag.AlignCenter)
        welcome.setStyleSheet("color:#888888; font-size:13px; padding:40px; background: transparent;")
        self.messages_layout.insertWidget(0, welcome)
        self.chat_header_label.setText("No conversation selected")
        self.msg_input.setEnabled(False)
        self.send_btn.setEnabled(False)
        self.file_btn.setEnabled(False)
        self.msg_input.setPlaceholderText("Select a friend to start chatting")

    # ---------- sidebar management ----------

    def add_contact_to_sidebar(self, ip):
        item = QListWidgetItem()
        item.setData(Qt.ItemDataRole.UserRole, ip)
        row_widget = ContactRowWidget(ip, online=True)
        item.setSizeHint(row_widget.sizeHint())
        self.contact_list.addItem(item)
        self.contact_list.setItemWidget(item, row_widget)
        self.sidebar_rows[ip] = row_widget
        self.sidebar_items[ip] = item

    def update_contact_status(self, ip):
        if ip in self.sidebar_rows:
            self.sidebar_rows[ip].set_online(self.contacts[ip]["online"])
        if self.current_ip == ip:
            status_text = "Online" if self.contacts[ip]["online"] else "Offline"
            self.chat_header_label.setText(f"{ip}  \u2022  {status_text}")

    def on_contact_clicked(self, item):
        ip = item.data(Qt.ItemDataRole.UserRole)
        self.select_contact(ip)

    def select_contact(self, ip):
        self.current_ip = ip
        self.unread_counts[ip] = 0
        if ip in self.sidebar_rows:
            self.sidebar_rows[ip].set_unread(0)

        status_text = "Online" if self.contacts[ip]["online"] else "Offline"
        self.chat_header_label.setText(f"{ip}  \u2022  {status_text}")

        self.clear_message_view()
        for msg in self.contacts[ip]["messages"]:
            self.append_bubble(msg)

        self.msg_input.setEnabled(True)
        self.send_btn.setEnabled(True)
        self.file_btn.setEnabled(True)
        self.msg_input.setPlaceholderText("Type a message")
        self.msg_input.setFocus()

    # ---------- chat bubble rendering ----------

    def clear_message_view(self):
        while self.messages_layout.count() > 1:
            item = self.messages_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

    def create_bubble(self, msg):
        is_own = msg["is_own"]
        bubble = QFrame()
        bg = "#DCF8C6" if is_own else "#FFFFFF"
        bubble.setStyleSheet(f"QFrame {{ background-color: {bg}; border-radius: 10px; }}")
        bubble.setMaximumWidth(300)

        v = QVBoxLayout()
        v.setContentsMargins(10, 6, 10, 4)
        v.setSpacing(4)

        if msg["kind"] == "file":
            file_row = QHBoxLayout()
            file_row.setSpacing(6)
            icon_label = QLabel("\U0001F4CE")
            icon_label.setStyleSheet("background: transparent; font-size:16px;")
            file_row.addWidget(icon_label)

            info_label = QLabel(f"{msg['filename']}\n{human_size(msg['size'])}")
            info_label.setWordWrap(True)
            info_label.setStyleSheet("color:#222222; font-size:13px; background: transparent;")
            file_row.addWidget(info_label, stretch=1)
            v.addLayout(file_row)

            open_btn = QPushButton("Open")
            open_btn.setStyleSheet(SECONDARY_BUTTON_STYLE)
            path = msg["path"]
            open_btn.clicked.connect(lambda checked=False, p=path: open_in_file_explorer(p))
            v.addWidget(open_btn)
        else:
            text_label = QLabel(msg["text"])
            text_label.setWordWrap(True)
            text_label.setStyleSheet("color: #222222; font-size: 14px; background: transparent;")
            v.addWidget(text_label)

        time_label = QLabel(msg["ts"])
        time_label.setStyleSheet("color: #777777; font-size: 10px; background: transparent;")
        time_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        v.addWidget(time_label)

        bubble.setLayout(v)

        row = QWidget()
        row_layout = QHBoxLayout()
        row_layout.setContentsMargins(0, 0, 0, 0)
        if is_own:
            row_layout.addStretch(1)
            row_layout.addWidget(bubble)
        else:
            row_layout.addWidget(bubble)
            row_layout.addStretch(1)
        row.setLayout(row_layout)
        return row

    def append_bubble(self, msg):
        bubble_row = self.create_bubble(msg)
        self.messages_layout.insertWidget(self.messages_layout.count() - 1, bubble_row)
        QTimer.singleShot(0, self.scroll_to_bottom)

    def scroll_to_bottom(self):
        bar = self.scroll_area.verticalScrollBar()
        bar.setValue(bar.maximum())

    # ---------- add friend / outgoing connect ----------

    def add_friend_dialog(self):
        ip, ok = QInputDialog.getText(self, "Add Friend", "Enter friend's IP address:")
        ip = ip.strip() if ip else ""
        if not (ok and ip):
            return
        if ip in self.contacts and self.contacts[ip]["online"]:
            self.select_contact(ip)
            return
        self.pending_manual_connect = ip
        threading.Thread(target=self._connect_thread, args=(ip,), daemon=True).start()

    def _connect_thread(self, ip):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(8)
            sock.connect((ip, PORT))
            sock.settimeout(None)
            self.signals.contact_connected.emit(ip, sock)
            self._listen_on_connection(sock, ip)
        except Exception as e:
            self.signals.error.emit(f"Could not connect to {ip}: {e}")

    # ---------- server (always listening for incoming friends) ----------

    def _server_loop(self):
        try:
            server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server.bind(("0.0.0.0", PORT))
            server.listen(10)
            self.server_socket = server
            while True:
                conn, addr = server.accept()
                threading.Thread(
                    target=self._handle_incoming, args=(conn, addr[0]), daemon=True
                ).start()
        except Exception as e:
            self.signals.error.emit(f"Could not start listening on port {PORT}: {e}")

    def _handle_incoming(self, conn, ip):
        self.signals.contact_connected.emit(ip, conn)
        self._listen_on_connection(conn, ip)

    def _listen_on_connection(self, conn, ip):
        """Shared read-loop for both incoming and outgoing connections."""
        buffer = ""
        stop = False
        while not stop:
            try:
                data = conn.recv(65536).decode(errors="ignore")
                if not data:
                    break
                buffer += data
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    if line.startswith("MSG:"):
                        self.signals.message_received.emit(ip, line[4:])
                    elif line.startswith("FILE:"):
                        self._handle_incoming_file(ip, line[5:])
                    elif line == "EXIT":
                        stop = True
                        break
            except Exception:
                break
        self.signals.contact_disconnected.emit(ip)

    def _handle_incoming_file(self, ip, payload):
        try:
            b64_name, size_str, b64_data = payload.split(":", 2)
            filename = base64.b64decode(b64_name).decode("utf-8", errors="ignore")
            filename = os.path.basename(filename) or "received_file"
            size = int(size_str)
            file_bytes = base64.b64decode(b64_data)
            save_dir = os.path.join(RECEIVED_DIR, ip)
            save_path = unique_path(save_dir, filename)
            with open(save_path, "wb") as f:
                f.write(file_bytes)
            self.signals.file_received.emit(ip, filename, save_path, size)
        except Exception as e:
            self.signals.error.emit(f"Failed to receive file from {ip}: {e}")

    # ---------- signal handlers (run on the GUI thread) ----------

    def on_contact_connected(self, ip, conn):
        is_new = ip not in self.contacts
        if is_new:
            self.contacts[ip] = {"conn": conn, "online": True, "messages": []}
            self.unread_counts[ip] = 0
            self.add_contact_to_sidebar(ip)
        else:
            self.contacts[ip]["conn"] = conn
            self.contacts[ip]["online"] = True
            self.update_contact_status(ip)

        if self.pending_manual_connect == ip:
            self.pending_manual_connect = None
            self.select_contact(ip)

    def on_message_received(self, ip, text):
        if ip not in self.contacts:
            self.contacts[ip] = {"conn": None, "online": True, "messages": []}
            self.unread_counts[ip] = 0
            self.add_contact_to_sidebar(ip)

        timestamp = datetime.now().strftime("%H:%M")
        msg = {"kind": "text", "text": text, "is_own": False, "ts": timestamp}
        self.contacts[ip]["messages"].append(msg)
        self._deliver_or_badge(ip, msg)

    def on_file_received(self, ip, filename, path, size):
        if ip not in self.contacts:
            self.contacts[ip] = {"conn": None, "online": True, "messages": []}
            self.unread_counts[ip] = 0
            self.add_contact_to_sidebar(ip)

        timestamp = datetime.now().strftime("%H:%M")
        msg = {"kind": "file", "filename": filename, "path": path, "size": size,
               "is_own": False, "ts": timestamp}
        self.contacts[ip]["messages"].append(msg)
        self._deliver_or_badge(ip, msg)

    def _deliver_or_badge(self, ip, msg):
        if self.current_ip == ip:
            self.append_bubble(msg)
        else:
            self.unread_counts[ip] = self.unread_counts.get(ip, 0) + 1
            if ip in self.sidebar_rows:
                self.sidebar_rows[ip].set_unread(self.unread_counts[ip])

    def on_contact_disconnected(self, ip):
        if ip in self.contacts:
            self.contacts[ip]["online"] = False
            self.contacts[ip]["conn"] = None
            self.update_contact_status(ip)

    def on_error(self, msg):
        QMessageBox.critical(self, "Error", msg)
        self.pending_manual_connect = None

    # ---------- sending: text ----------

    def send_raw(self, conn, msg):
        try:
            conn.sendall((msg + "\n").encode())
        except Exception as e:
            self.signals.error.emit(str(e))

    def send_chat_message(self):
        if not self.current_ip:
            return
        text = self.msg_input.text().strip()
        if not text:
            return
        ip = self.current_ip
        self.msg_input.clear()

        timestamp = datetime.now().strftime("%H:%M")
        own_msg = {"kind": "text", "text": text, "is_own": True, "ts": timestamp}
        self.contacts[ip]["messages"].append(own_msg)
        self.append_bubble(own_msg)

        contact = self.contacts.get(ip)
        if contact and contact["online"] and contact["conn"]:
            self.send_raw(contact["conn"], f"MSG:{text}")
        else:
            threading.Thread(target=self._reconnect_and_send, args=(ip, f"MSG:{text}"), daemon=True).start()

    def _reconnect_and_send(self, ip, line):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            sock.connect((ip, PORT))
            sock.settimeout(None)
            self.signals.contact_connected.emit(ip, sock)
            sock.sendall((line + "\n").encode())
            threading.Thread(target=self._listen_on_connection, args=(sock, ip), daemon=True).start()
        except Exception as e:
            self.signals.error.emit(f"{ip} appears offline - not delivered ({e})")

    # ---------- sending: file ----------

    def send_file_dialog(self):
        if not self.current_ip:
            return
        path, _ = QFileDialog.getOpenFileName(self, "Select a file to send")
        if not path:
            return
        try:
            size = os.path.getsize(path)
        except OSError as e:
            QMessageBox.warning(self, "Can't read file", str(e))
            return
        if size > MAX_FILE_SIZE:
            QMessageBox.warning(
                self, "File too large",
                f"That file is {human_size(size)}. Please pick a file under "
                f"{human_size(MAX_FILE_SIZE)} for now."
            )
            return

        ip = self.current_ip
        filename = os.path.basename(path)
        timestamp = datetime.now().strftime("%H:%M")
        own_msg = {"kind": "file", "filename": filename, "path": path, "size": size,
                    "is_own": True, "ts": timestamp}
        self.contacts[ip]["messages"].append(own_msg)
        self.append_bubble(own_msg)

        threading.Thread(target=self._send_file_thread, args=(ip, path, filename), daemon=True).start()

    def _send_file_thread(self, ip, path, filename):
        try:
            with open(path, "rb") as f:
                raw = f.read()
            b64_name = base64.b64encode(filename.encode("utf-8")).decode("ascii")
            b64_data = base64.b64encode(raw).decode("ascii")
            line = f"FILE:{b64_name}:{len(raw)}:{b64_data}"

            contact = self.contacts.get(ip)
            if contact and contact["online"] and contact["conn"]:
                self.send_raw(contact["conn"], line)
            else:
                self._reconnect_and_send(ip, line)
        except Exception as e:
            self.signals.error.emit(f"Failed to send file to {ip}: {e}")

    # ---------- shutdown ----------

    def closeEvent(self, event):
        for ip, c in list(self.contacts.items()):
            if c["online"] and c["conn"]:
                try:
                    c["conn"].sendall(b"EXIT\n")
                    c["conn"].close()
                except Exception:
                    pass
        if self.server_socket:
            try:
                self.server_socket.close()
            except Exception:
                pass
        event.accept()


def main():
    app = QApplication(sys.argv)
    window = ChatApp()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()