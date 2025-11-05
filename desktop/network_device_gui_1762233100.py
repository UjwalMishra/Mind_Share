import os
import time
import json
import threading
import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext, messagebox

# Optional Windows beep
try:
    import winsound
except Exception:
    winsound = None

# --- Import your POC class ---
from poc import LocalNetworkDevice

# ========== RUNTIME PATCH (NO CHANGES TO poc.py) ==========
# We monkey-patch LocalNetworkDevice to (a) ensure it has message_callback,
# and (b) handle 'data' messages by ACK-first + async-callback (so sender never blocks).

import struct, socket, types

# 1) Ensure instances have message_callback even if poc.py didn't define it
_original_init = LocalNetworkDevice.__init__
def _patched_init(self, *args, **kwargs):
    _original_init(self, *args, **kwargs)
    if not hasattr(self, "message_callback"):
        self.message_callback = None
LocalNetworkDevice.__init__ = _patched_init

# 2) Patch handle_client to ACK first and then fire GUI callback in a thread
_original_handle_client = LocalNetworkDevice.handle_client

def _handle_client_patched(self, client_socket: socket.socket, address):
    try:
        raw = client_socket.recv(1024).decode("utf-8")
        message = json.loads(raw)
        mtype = message.get("type", "")

        if mtype == "discovery":
            response = {
                "type": "discovery_response",
                "device_name": self.device_name,
                "device_id": getattr(self, "device_id", "unknown"),
                "ip": self.get_local_ip(),
                "port": self.port
            }
            client_socket.send(json.dumps(response).encode("utf-8"))

        elif mtype == "data":
            payload = message.get("payload", "")
            sender  = message.get("sender", "Unknown")
            print(f"📨 Received data from {address[0]}: {payload}")

            # ACK first (never block the sender)
            try:
                client_socket.send(json.dumps({"type":"ack","status":"received"}).encode("utf-8"))
            except Exception as e:
                print(f"❌ Ack send error: {e}")

            # Async notify GUI
            cb = getattr(self, "message_callback", None)
            if cb:
                try:
                    threading.Thread(target=cb, args=(address[0], sender, payload), daemon=True).start()
                except Exception as e:
                    print(f"❌ Callback error: {e}")

        elif mtype == "file_transfer_request":
            filename  = message.get("filename", "file.bin")
            sender    = message.get("sender", "Unknown")
            file_size = int(message.get("file_size", 0))
            print(f"📤 {sender} wants to send file: {filename} ({file_size} bytes)")

            # Optimize socket like your poc
            try:
                client_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                client_socket.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 65536)
                client_socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 65536)
            except Exception:
                pass

            # Accept and delegate to original receive_file
            try:
                client_socket.send(json.dumps({"status":"accepted"}).encode("utf-8"))
            except Exception as e:
                print(f"❌ Could not send accept: {e}")
                return

            try:
                self.receive_file(client_socket, address, filename, file_size)
            except Exception as e:
                print(f"❌ Error in receive_file: {e}")

        else:
            # Fallback to original for any unknown type
            _original_handle_client(self, client_socket, address)

    except Exception as e:
        print(f"❌ Error handling client {address}: {e}")
    finally:
        try:
            client_socket.close()
        except Exception:
            pass

LocalNetworkDevice.handle_client = _handle_client_patched
# ========== END PATCH ==========


# ---------- Retro Theme Helpers ----------
RETRO_BG      = "#111217"
RETRO_PANEL   = "#151823"
RETRO_ACCENT  = "#60F9A6"
RETRO_ACCENT2 = "#4AE0FF"
RETRO_TEXT    = "#E8F0F2"
RETRO_MID     = "#2A2F3A"
RETRO_WARN    = "#F7B500"
RETRO_ERROR   = "#FF5C7C"
RETRO_GOOD    = "#80FFA7"
DEFAULT_FONT  = ("Consolas", 10)

def style_retro(app: tk.Tk):
    style = ttk.Style(app)
    try:
        style.theme_use("clam")
    except Exception:
        pass

    style.configure(".", background=RETRO_BG, foreground=RETRO_TEXT, fieldbackground=RETRO_PANEL, font=DEFAULT_FONT)
    style.configure("Retro.TFrame", background=RETRO_BG)
    style.configure("Panel.TFrame", background=RETRO_PANEL)
    style.configure("Retro.TLabelframe", background=RETRO_PANEL, foreground=RETRO_TEXT, bordercolor=RETRO_MID, relief="solid")
    style.configure("Retro.TLabelframe.Label", background=RETRO_PANEL, foreground=RETRO_ACCENT, font=("Consolas", 10, "bold"))

    style.configure("Retro.TButton", background=RETRO_MID, foreground=RETRO_TEXT, bordercolor=RETRO_ACCENT, focusthickness=3, focuscolor=RETRO_ACCENT)
    style.map("Retro.TButton", background=[("active", RETRO_ACCENT2), ("pressed", RETRO_ACCENT)], foreground=[("active", "#0A0B0E"), ("pressed", "#0A0B0E")])

    style.configure("Accent.TButton", background=RETRO_ACCENT, foreground="#0A0B0E", font=("Consolas", 10, "bold"))
    style.map("Accent.TButton", background=[("active", RETRO_ACCENT2), ("pressed", RETRO_GOOD)])

    style.configure("Danger.TButton", background=RETRO_ERROR, foreground="#0A0B0E", font=("Consolas", 10, "bold"))
    style.map("Danger.TButton", background=[("active", "#ff91a6"), ("pressed", "#ffb1c0")])

    style.configure("Retro.TLabel", background=RETRO_BG, foreground=RETRO_TEXT)
    style.configure("Panel.TLabel", background=RETRO_PANEL, foreground=RETRO_TEXT)

    style.configure("Retro.Treeview", background=RETRO_PANEL, fieldbackground=RETRO_PANEL, foreground=RETRO_TEXT, bordercolor=RETRO_MID, rowheight=26)
    style.map("Retro.Treeview", background=[("selected", "#234040")], foreground=[("selected", RETRO_ACCENT)])
    style.configure("Retro.Treeview.Heading", background=RETRO_MID, foreground=RETRO_ACCENT, relief="flat", font=("Consolas", 10, "bold"))

    style.configure("Retro.Vertical.TScrollbar", gripcount=0, background=RETRO_MID, darkcolor=RETRO_MID, lightcolor=RETRO_MID,
                    troughcolor=RETRO_BG, bordercolor=RETRO_BG, arrowcolor=RETRO_TEXT)

    style.configure("Retro.Horizontal.TProgressbar", background=RETRO_ACCENT, troughcolor=RETRO_MID)


# ---------- Notification Popup ----------
class NotificationPopup:
    def __init__(self, parent, title, message, sender_name, duration=3500):
        self.parent = parent
        self.duration = duration

        self.popup = tk.Toplevel(parent)
        self.popup.withdraw()
        self.popup.overrideredirect(True)
        self.popup.attributes("-topmost", True)

        wrap = tk.Frame(self.popup, bg=RETRO_PANEL, bd=2, highlightthickness=2, highlightbackground=RETRO_ACCENT)
        wrap.pack(fill=tk.BOTH, expand=True)

        title_lbl = tk.Label(wrap, text=f"✉  {title}", font=("Consolas", 10, "bold"), bg=RETRO_PANEL, fg=RETRO_ACCENT)
        title_lbl.pack(anchor="w", padx=12, pady=(10, 2))

        from_lbl = tk.Label(wrap, text=f"From: {sender_name}", font=("Consolas", 9), bg=RETRO_PANEL, fg=RETRO_TEXT)
        from_lbl.pack(anchor="w", padx=12)

        preview = message if len(message) <= 80 else message[:80] + "…"
        msg_lbl = tk.Label(wrap, text=preview, font=("Consolas", 9), bg=RETRO_PANEL, fg=RETRO_TEXT, wraplength=320, justify="left")
        msg_lbl.pack(anchor="w", padx=12, pady=(6, 12))

        # Position bottom-right
        self.popup.update_idletasks()
        w, h = 360, 130
        sw = self.popup.winfo_screenwidth()
        sh = self.popup.winfo_screenheight()
        x = sw - w - 24
        y = sh - h - 48
        self.popup.geometry(f"{w}x{h}+{x}+{y}")
        self.popup.deiconify()

        # Sound
        try:
            if winsound:
                winsound.MessageBeep(winsound.MB_ICONINFORMATION)
        except Exception:
            pass

        self.popup.after(self.duration, self.close)
        wrap.bind("<Button-1>", lambda e: self.close())

        # Fade-in
        try:
            self.popup.attributes("-alpha", 0.0)
            for i in range(1, 11):
                self.popup.attributes("-alpha", i / 10.0)
                self.popup.update()
                time.sleep(0.01)
        except Exception:
            pass

    def close(self):
        try:
            for i in range(10, 0, -1):
                self.popup.attributes("-alpha", i / 10.0)
                self.popup.update()
                time.sleep(0.01)
        except Exception:
            pass
        try:
            self.popup.destroy()
        except Exception:
            pass


# ---------- Progress Overlay ----------
class ProgressOverlay:
    def __init__(self, parent, text="Working…"):
        self.top = tk.Toplevel(parent)
        self.top.overrideredirect(True)
        self.top.attributes("-topmost", True)
        self.top.configure(bg="#000000")
        self.top.attributes("-alpha", 0.85)

        self.top.geometry(f"{parent.winfo_width()}x{parent.winfo_height()}+{parent.winfo_rootx()}+{parent.winfo_rooty()}")

        frame = tk.Frame(self.top, bg=RETRO_BG, bd=2, highlightthickness=2, highlightbackground=RETRO_ACCENT)
        frame.place(relx=0.5, rely=0.5, anchor="center", relwidth=0.5)

        lbl = tk.Label(frame, text=text, font=("Consolas", 12, "bold"), bg=RETRO_BG, fg=RETRO_ACCENT)
        lbl.pack(padx=20, pady=(20, 6))

        self.pb = ttk.Progressbar(frame, mode="indeterminate", style="Retro.Horizontal.TProgressbar")
        self.pb.pack(fill="x", padx=20, pady=(0, 20))
        self.pb.start(12)

        tip = tk.Label(frame, text="Press ESC to cancel (if supported)", font=("Consolas", 9), bg=RETRO_BG, fg=RETRO_TEXT)
        tip.pack(padx=20, pady=(0, 16))

        self.cancelled = False
        self.top.bind("<Escape>", self._cancel)

    def _cancel(self, _):
        self.cancelled = True

    def close(self):
        try:
            self.pb.stop()
            self.top.destroy()
        except Exception:
            pass


# ---------- Main App ----------
class RetroNetworkGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("RetroLink ┊ Local Network Manager")
        self.root.geometry("1080x720")
        self.root.minsize(960, 640)
        self.root.configure(bg=RETRO_BG)

        style_retro(self.root)

        deco = tk.Frame(self.root, bg=RETRO_ACCENT, height=2)
        deco.pack(fill="x", side="top")

        self.device = LocalNetworkDevice()
        self.is_running = False
        self.monitoring_active = False
        self.auto_discovery_active = False

        self.received_messages = []

        self._build_header()
        self._build_body()
        self._wire_callbacks()
        self._refresh_network_info()

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ----- UI BUILD -----
    def _build_header(self):
        hdr = ttk.Frame(self.root, style="Retro.TFrame")
        hdr.pack(fill="x", padx=16, pady=(10, 6))

        title = tk.Label(hdr, text="RetroLink", fg=RETRO_ACCENT, bg=RETRO_BG, font=("Consolas", 18, "bold"))
        subtitle = tk.Label(hdr, text="Local device discovery • P2P messaging • Broadcast • File transfer",
                            fg=RETRO_TEXT, bg=RETRO_BG, font=("Consolas", 10))
        title.grid(row=0, column=0, sticky="w")
        subtitle.grid(row=1, column=0, sticky="w")

        btns = ttk.Frame(hdr, style="Retro.TFrame")
        btns.grid(row=0, column=1, rowspan=2, sticky="e")

        self.btn_start = ttk.Button(btns, text="▶ Start", style="Accent.TButton", command=self._start_services)
        self.btn_stop  = ttk.Button(btns, text="■ Stop",  style="Danger.TButton", command=self._stop_services, state="disabled")
        self.btn_start.grid(row=0, column=0, padx=6)
        self.btn_stop.grid(row=0, column=1, padx=6)

        self.lbl_status = tk.Label(hdr, text="Status: Stopped", bg=RETRO_BG, fg=RETRO_ERROR, font=("Consolas", 10, "bold"))
        self.lbl_status.grid(row=0, column=2, padx=(16, 0))

        hdr.columnconfigure(0, weight=1)

    def _build_body(self):
        body = ttk.Frame(self.root, style="Retro.TFrame")
        body.pack(fill="both", expand=True, padx=16, pady=(0, 16))

        # Left: Dashboard & Quick actions
        left = ttk.Frame(body, style="Retro.TFrame")
        left.pack(side="left", fill="y")

        dash = ttk.LabelFrame(left, text="Dashboard", style="Retro.TLabelframe")
        dash.pack(fill="x", padx=(0, 12), pady=(0, 12))

        self.var_ip        = tk.StringVar(value="-")
        self.var_broadcast = tk.StringVar(value="-")
        self.var_tcp       = tk.StringVar(value="-")
        self.var_udp       = tk.StringVar(value="-")
        self.var_devname   = tk.StringVar(value="-")
        self.var_devid     = tk.StringVar(value="-")
        self.var_counts    = tk.StringVar(value="Devices: 0 • App: 0")

        grid = ttk.Frame(dash, style="Panel.TFrame")
        grid.pack(fill="x", padx=10, pady=10)

        def row(r, label, var):
            tk.Label(grid, text=label, bg=RETRO_PANEL, fg=RETRO_ACCENT).grid(row=r, column=0, sticky="w")
            tk.Label(grid, textvariable=var, bg=RETRO_PANEL, fg=RETRO_TEXT).grid(row=r, column=1, sticky="w", padx=(10,0))

        row(0, "Local IP:", self.var_ip)
        row(1, "Broadcast:", self.var_broadcast)
        row(2, "TCP Port:", self.var_tcp)
        row(3, "UDP Port:", self.var_udp)
        row(4, "Device:", self.var_devname)
        row(5, "Device ID:", self.var_devid)

        sep = tk.Frame(dash, bg=RETRO_MID, height=1)
        sep.pack(fill="x", padx=10, pady=6)
        tk.Label(dash, textvariable=self.var_counts, bg=RETRO_PANEL, fg=RETRO_TEXT).pack(anchor="w", padx=10, pady=(0,10))

        qa = ttk.LabelFrame(left, text="Quick Actions", style="Retro.TLabelframe")
        qa.pack(fill="x", padx=(0, 12))
        self.btn_discover = ttk.Button(qa, text="🔎 Discover", style="Retro.TButton", command=self._discover_devices)
        self.btn_refresh  = ttk.Button(qa, text="↻ Refresh",  style="Retro.TButton", command=self._refresh_devices_table)
        self.btn_discover.grid(row=0, column=0, padx=8, pady=8, sticky="ew")
        self.btn_refresh.grid(row=0, column=1, padx=8, pady=8, sticky="ew")
        qa.columnconfigure(0, weight=1)
        qa.columnconfigure(1, weight=1)

        # Right: Notebook
        right = ttk.Frame(body, style="Retro.TFrame")
        right.pack(side="left", fill="both", expand=True)

        self.nb = ttk.Notebook(right)
        self.nb.pack(fill="both", expand=True)

        self._build_tab_devices()
        self._build_tab_messaging()
        self._build_tab_files()
        self._build_tab_logs()
        self._build_tab_network()

    def _build_tab_devices(self):
        tab = ttk.Frame(self.nb, style="Retro.TFrame")
        self.nb.add(tab, text="🖧 Devices")

        cols = ("name", "ip", "status", "last_seen")
        self.tv = ttk.Treeview(tab, columns=cols, show="headings", style="Retro.Treeview")
        for c, w, a, t in [
            ("name", 240, "w", "Device Name"),
            ("ip", 160, "center", "IP Address"),
            ("status", 120, "center", "Status"),
            ("last_seen", 120, "center", "Last Seen")
        ]:
            self.tv.heading(c, text=t)
            self.tv.column(c, width=w, anchor=a)

        vs = ttk.Scrollbar(tab, orient="vertical", command=self.tv.yview, style="Retro.Vertical.TScrollbar")
        self.tv.configure(yscrollcommand=vs.set)
        self.tv.pack(side="left", fill="both", expand=True, padx=(0, 6), pady=10)
        vs.pack(side="left", fill="y", pady=10)

        bar = ttk.LabelFrame(tab, text="Target (Peer-to-Peer)", style="Retro.TLabelframe")
        bar.pack(fill="x", padx=6, pady=(0, 10))
        ttk.Label(bar, text="Select:", style="Panel.TLabel").pack(side="left", padx=8, pady=8)
        self.cb_targets = ttk.Combobox(bar, state="readonly", width=48)
        self.cb_targets.pack(side="left", padx=6, pady=8, fill="x", expand=True)

    def _build_tab_messaging(self):
        tab = ttk.Frame(self.nb, style="Retro.TFrame")
        self.nb.add(tab, text="✉ Messaging")

        modes = ttk.LabelFrame(tab, text="Mode", style="Retro.TLabelframe")
        modes.pack(fill="x", padx=10, pady=(10, 6))
        self.msg_mode = tk.StringVar(value="p2p")
        ttk.Radiobutton(modes, text="Peer-to-Peer", value="p2p", variable=self.msg_mode).pack(side="left", padx=10, pady=8)
        ttk.Radiobutton(modes, text="Broadcast",   value="broadcast", variable=self.msg_mode).pack(side="left", padx=10, pady=8)

        msg_box = ttk.LabelFrame(tab, text="Message", style="Retro.TLabelframe")
        msg_box.pack(fill="both", expand=True, padx=10, pady=(0,10))
        self.txt_msg = scrolledtext.ScrolledText(msg_box, height=8, font=("Consolas", 10), bg=RETRO_PANEL, fg=RETRO_TEXT,
                                                 insertbackground=RETRO_ACCENT, bd=0, relief="flat")
        self.txt_msg.pack(fill="both", expand=True, padx=10, pady=10)
        self.btn_send = ttk.Button(msg_box, text="➤ Send", style="Accent.TButton", command=self._send_message)
        self.btn_send.pack(padx=10, pady=(0,10), anchor="e")

        recv = ttk.LabelFrame(tab, text="Received", style="Retro.TLabelframe")
        recv.pack(fill="both", expand=True, padx=10, pady=(0,10))
        cols = ("time", "from", "content")
        self.tv_recv = ttk.Treeview(recv, columns=cols, show="headings", style="Retro.Treeview")
        self.tv_recv.heading("time", text="Time")
        self.tv_recv.heading("from", text="From")
        self.tv_recv.heading("content", text="Message")
        self.tv_recv.column("time", width=120, anchor="center")
        self.tv_recv.column("from", width=220, anchor="w")
        self.tv_recv.column("content", width=560, anchor="w")
        vs2 = ttk.Scrollbar(recv, orient="vertical", command=self.tv_recv.yview, style="Retro.Vertical.TScrollbar")
        self.tv_recv.configure(yscrollcommand=vs2.set)
        self.tv_recv.pack(side="left", fill="both", expand=True, padx=(0, 6), pady=10)
        vs2.pack(side="left", fill="y", pady=10)
        self.btn_clear_recv = ttk.Button(recv, text="🗑 Clear", style="Retro.TButton", command=self._clear_received)
        self.btn_clear_recv.pack(anchor="ne", padx=10, pady=(10, 0))

    def _build_tab_files(self):
        tab = ttk.Frame(self.nb, style="Retro.TFrame")
        self.nb.add(tab, text="⬆ Files")

        row = ttk.LabelFrame(tab, text="Send File (Peer-to-Peer)", style="Retro.TLabelframe")
        row.pack(fill="x", padx=10, pady=10)

        ttk.Label(row, text="Target:", style="Panel.TLabel").grid(row=0, column=0, padx=10, pady=10, sticky="w")
        self.cb_file_target = ttk.Combobox(row, state="readonly", width=44)
        self.cb_file_target.grid(row=0, column=1, padx=6, pady=10, sticky="we")

        ttk.Label(row, text="File:", style="Panel.TLabel").grid(row=1, column=0, padx=10, pady=10, sticky="w")
        self.var_file = tk.StringVar(value="")
        ent = ttk.Entry(row, textvariable=self.var_file)
        ent.grid(row=1, column=1, padx=6, pady=10, sticky="we")

        btn_pick = ttk.Button(row, text="Browse…", style="Retro.TButton", command=self._pick_file)
        btn_pick.grid(row=1, column=2, padx=6, pady=10)

        self.btn_send_file = ttk.Button(row, text="Send File", style="Accent.TButton", command=self._send_file)
        self.btn_send_file.grid(row=2, column=1, padx=6, pady=(4, 12), sticky="e")

        row.columnconfigure(1, weight=1)

        helpbox = ttk.LabelFrame(tab, text="Notes", style="Retro.TLabelframe")
        helpbox.pack(fill="x", padx=10, pady=(0,10))
        tk.Label(helpbox,
                 text="• Recipient must be running this app (port open)\n"
                      "• Working overlay shows while transfer happens\n"
                      "• Receiver saves files under /downloads",
                 bg=RETRO_PANEL, fg=RETRO_TEXT, justify="left").pack(anchor="w", padx=10, pady=10)

    def _build_tab_logs(self):
        tab = ttk.Frame(self.nb, style="Retro.TFrame")
        self.nb.add(tab, text="📋 Logs")
        self.txt_log = scrolledtext.ScrolledText(tab, height=20, font=("Consolas", 10), bg=RETRO_PANEL, fg=RETRO_TEXT,
                                                 insertbackground=RETRO_ACCENT, bd=0, relief="flat")
        self.txt_log.pack(fill="both", expand=True, padx=10, pady=10)
        ttk.Button(tab, text="Clear Logs", style="Retro.TButton",
                   command=lambda: self.txt_log.delete("1.0", tk.END)).pack(anchor="e", padx=10, pady=(0,10))

    def _build_tab_network(self):
        tab = ttk.Frame(self.nb, style="Retro.TFrame")
        self.nb.add(tab, text="⚙ Network")

        info = ttk.LabelFrame(tab, text="Network Info", style="Retro.TLabelframe")
        info.pack(fill="x", padx=10, pady=10)
        self.txt_info = scrolledtext.ScrolledText(info, height=10, font=("Consolas", 10), bg=RETRO_PANEL, fg=RETRO_TEXT,
                                                  insertbackground=RETRO_ACCENT, bd=0, relief="flat")
        self.txt_info.pack(fill="both", expand=True, padx=10, pady=10)

        ctl = ttk.LabelFrame(tab, text="Controls", style="Retro.TLabelframe")
        ctl.pack(fill="x", padx=10, pady=(0,10))
        ttk.Button(ctl, text="Discover Now",  style="Retro.TButton", command=self._discover_devices).pack(side="left", padx=8, pady=8)
        ttk.Button(ctl, text="Refresh Devices", style="Retro.TButton", command=self._refresh_devices_table).pack(side="left", padx=8, pady=8)

    # ----- CALLBACKS / WIRING -----
    def _wire_callbacks(self):
        # If set_message_callback exists use it, else attribute set (thanks to patch)
        if hasattr(self.device, "set_message_callback"):
            try:
                self.device.set_message_callback(self._on_message)
            except Exception:
                self.device.message_callback = self._on_message
        else:
            self.device.message_callback = self._on_message

    # ----- SERVICE CONTROL -----
    def _start_services(self):
        if self.is_running:
            return
        self._log("Starting services...")
        self.is_running = True
        self.btn_start.config(state="disabled")
        self.btn_stop.config(state="normal")
        self.lbl_status.config(text="Status: Running", fg=RETRO_GOOD)

        threading.Thread(target=self._thread_start_services, daemon=True).start()
        self.monitoring_active = True
        threading.Thread(target=self._monitor_loop, daemon=True).start()
        self.auto_discovery_active = True
        threading.Thread(target=self._auto_discover_loop, daemon=True).start()

    def _thread_start_services(self):
        try:
            self.device.start_all_services()
            self._log("✔ Services started")
            self._refresh_network_info()
        except Exception as e:
            self._log(f"✖ Error starting services: {e}")
            messagebox.showerror("Error", f"Failed to start: {e}")

    def _stop_services(self):
        if not self.is_running:
            return
        self._log("Stopping services...")
        self.monitoring_active = False
        self.auto_discovery_active = False
        try:
            self.device.stop()
        except Exception as e:
            self._log(f"Stop error: {e}")
        self.is_running = False
        self.btn_start.config(state="normal")
        self.btn_stop.config(state="disabled")
        self.lbl_status.config(text="Status: Stopped", fg=RETRO_ERROR)
        self._log("■ Services stopped")

    # ----- DISCOVERY / REFRESH -----
    def _discover_devices(self):
        if not self.is_running:
            messagebox.showwarning("Not running", "Start services first.")
            return
        overlay = ProgressOverlay(self.root, "Scanning local network…")
        def task():
            try:
                devices = self.device.discover_devices()
                self._log(f"Discovery complete: {len(devices)} device(s) updated")
            except Exception as e:
                self._log(f"Discovery error: {e}")
            finally:
                self.root.after(0, overlay.close)
                self.root.after(0, self._refresh_devices_table)
        threading.Thread(target=task, daemon=True).start()

    def _refresh_devices_table(self):
        for i in self.tv.get_children():
            self.tv.delete(i)

        total = 0
        app = 0
        targets = []

        for ip, info in sorted(self.device.devices.items(), key=lambda kv: kv[0]):
            total += 1
            status = "Device"
            if info.get("port"):
                status = "App Running" if info.get("status") != "offline" else "App Offline"
                app += 1

            last_seen = int(time.time() - info.get("last_seen", time.time()))
            last_text = f"{last_seen}s ago"
            self.tv.insert("", "end", values=(info.get("name", "?"), ip, status, last_text))

            if info.get("port") and info.get("status") != "offline":
                targets.append(f"{info.get('name','?')} ({ip})")

        self.cb_targets["values"] = targets
        if targets and not self.cb_targets.get():
            self.cb_targets.set(targets[0])

        self.cb_file_target["values"] = targets
        if targets and not self.cb_file_target.get():
            self.cb_file_target.set(targets[0])

        self.var_counts.set(f"Devices: {total} • App: {app}")

    # ----- MESSAGING -----
    def _send_message(self):
        if not self.is_running:
            messagebox.showwarning("Not running", "Start services first.")
            return

        message = self.txt_msg.get("1.0", tk.END).strip()
        if not message:
            messagebox.showwarning("Empty", "Enter a message.")
            return

        mode = self.msg_mode.get()
        if mode == "broadcast":
            self._log(f"Broadcasting: {message}")
            def task():
                try:
                    self.device.broadcast_data(message)
                    self._log("Broadcast done")
                except Exception as e:
                    self._log(f"Broadcast error: {e}")
                    messagebox.showerror("Broadcast failed", str(e))
            threading.Thread(target=task, daemon=True).start()
        else:
            target = self.cb_targets.get()
            if not target:
                messagebox.showwarning("Select target", "Pick a target on the Devices tab.")
                return
            ip = target.split("(")[-1].split(")")[0]
            self._log(f"Sending to {target}: {message}")
            def task():
                ok = self.device.send_data(ip, message)
                if ok:
                    self._log(f"Sent ✓ to {target}")
                else:
                    self._log(f"Send failed ✖ to {target}")
                    messagebox.showerror("Send failed", f"Could not send to {target}")
            threading.Thread(target=task, daemon=True).start()

        self.txt_msg.delete("1.0", tk.END)

    def _on_message(self, sender_ip, sender_name, msg):
        ts = time.strftime("%H:%M:%S")
        self.received_messages.append({"time": ts, "from": f"{sender_name} ({sender_ip})", "content": msg})
        self.root.after(0, lambda: self.tv_recv.insert("", 0, values=(ts, f"{sender_name} ({sender_ip})", msg)))
        self.root.after(0, lambda: NotificationPopup(self.root, "New Message", msg, sender_name))
        self._log(f"Received from {sender_name} ({sender_ip}): {msg}")

    def _clear_received(self):
        self.received_messages.clear()
        for i in self.tv_recv.get_children():
            self.tv_recv.delete(i)
        self._log("Cleared received messages")

    # ----- FILES -----
    def _pick_file(self):
        path = filedialog.askopenfilename(title="Select a file to send")
        if path:
            self.var_file.set(path)

    def _send_file(self):
        if not self.is_running:
            messagebox.showwarning("Not running", "Start services first.")
            return
        target = self.cb_file_target.get()
        if not target:
            messagebox.showwarning("Select target", "Pick a target device.")
            return
        path = self.var_file.get().strip()
        if not path or not os.path.isfile(path):
            messagebox.showwarning("Pick a file", "Select a valid file.")
            return
        ip = target.split("(")[-1].split(")")[0]

        overlay = ProgressOverlay(self.root, f"Sending “{os.path.basename(path)}” to {target}…")
        def task():
            try:
                ok = self.device.send_file(ip, path)
                if ok:
                    self._log(f"File sent ✓ {os.path.basename(path)} → {target}")
                else:
                    self._log(f"File send failed ✖ to {target}")
                    messagebox.showerror("Send failed", f"Could not send file to {target}")
            finally:
                self.root.after(0, overlay.close)
        threading.Thread(target=task, daemon=True).start()

    # ----- MONITOR & AUTO DISCOVER -----
    def _monitor_loop(self):
        while self.monitoring_active and self.is_running:
            try:
                changed = False
                now = time.time()
                stale = []
                for ip, info in list(self.device.devices.items()):
                    if now - info.get("last_seen", now) > 20:
                        stale.append(ip)
                        changed = True
                        continue
                    if info.get("port"):
                        try:
                            s = socket.socket()
                            s.settimeout(1.5)
                            res = s.connect_ex((ip, info["port"]))
                            s.close()
                            alive = (res == 0)
                        except Exception:
                            alive = False
                        prior = info.get("status")
                        info["status"] = "online" if alive else "offline"
                        if prior != info["status"]:
                            changed = True
                            self._log(("Device online ✓ " if alive else "Device offline ⚠ ") + f"{info.get('name','?')} ({ip})")
                for ip in stale:
                    nm = self.device.devices[ip]["name"]
                    del self.device.devices[ip]
                    self._log(f"Removed stale device 🗑 {nm} ({ip})")
                    changed = True
                if changed:
                    self.root.after(0, self._refresh_devices_table)
            except Exception as e:
                if self.monitoring_active:
                    self._log(f"Monitor error: {e}")
            time.sleep(3)

    def _auto_discover_loop(self):
        counter = 0
        while self.auto_discovery_active and self.is_running:
            time.sleep(30)
            if not (self.auto_discovery_active and self.is_running):
                break
            counter += 1
            self._log(f"Auto-discovery #{counter}…")
            try:
                self.device.discover_devices()
                self.root.after(0, self._refresh_devices_table)
            except Exception as e:
                self._log(f"Auto-discovery error: {e}")

    # ----- INFO / LOGS -----
    def _refresh_network_info(self):
        try:
            info = [
                f"Local IP Address : {self.device.get_local_ip()}",
                f"Broadcast Address: {self.device.get_broadcast_address()}",
                f"TCP Port        : {self.device.port}",
                f"UDP Broadcast   : {self.device.broadcast_port}",
                f"Device Name     : {self.device.device_name}",
                f"Device ID       : {self.device.device_id}",
                "",
                "Modes:",
                "• Peer-to-Peer → direct to a selected device",
                "• Broadcast    → send to all discovered app devices",
                "",
                "Discovery:",
                "• Ping sweep to find active actors",
                "• TCP probe to detect app peers",
                "• BLE-like UDP adverts + scanner",
            ]
            self.txt_info.delete("1.0", tk.END)
            self.txt_info.insert("1.0", "\n".join(info))

            self.var_ip.set(self.device.get_local_ip())
            self.var_broadcast.set(self.device.get_broadcast_address())
            self.var_tcp.set(str(self.device.port))
            self.var_udp.set(str(self.device.broadcast_port))
            self.var_devname.set(self.device.device_name)
            self.var_devid.set(self.device.device_id)
        except Exception as e:
            self._log(f"Info update error: {e}")

    def _log(self, msg: str):
        ts = time.strftime("%H:%M:%S")
        self.txt_log.insert(tk.END, f"[{ts}] {msg}\n")
        self.txt_log.see(tk.END)

    # ----- CLOSE -----
    def _on_close(self):
        try:
            self.monitoring_active = False
            self.auto_discovery_active = False
            if self.is_running:
                self.device.stop()
        finally:
            self.root.destroy()


def main():
    root = tk.Tk()
    app = RetroNetworkGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
