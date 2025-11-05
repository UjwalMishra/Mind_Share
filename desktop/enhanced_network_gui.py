import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import tkinterdnd2 as tkdnd
import threading
import time
import winsound
import os
import pyperclip
import json
import subprocess
import socket
import sys

# This assumes 'poc.py' with the LocalNetworkDevice class is in the same directory.
try:
    from poc import LocalNetworkDevice
except ImportError:
    # Create a dummy class if poc.py is not available, to allow the GUI to run for review.
    print("Warning: 'poc.py' not found. Using a dummy LocalNetworkDevice class.")
    class LocalNetworkDevice:
        def __init__(self):
            self.device_name = "Dummy Device"
            self.device_id = "dummy-123"
            self.port = 12345
            self.broadcast_port = 12346
            self.devices = {}
            self.handle_client = lambda sock, addr: None
        def get_local_ip(self): return "127.0.0.1"
        def get_broadcast_address(self): return "127.0.0.255"
        def start_all_services(self): print("Dummy services started.")
        def stop(self): print("Dummy services stopped.")
        def discover_devices(self): print("Discovering dummy devices.")
        def send_file(self, ip, path): print(f"Sending {path} to {ip}."); return True
        def receive_file(self, sock, addr, name, size): return True

# ====================================================================================
# THEME DEFINITIONS
# ====================================================================================

class LightTheme:
    """Clean retro color scheme - warm and minimal"""
    NAME = 'light'
    # Warm cream/beige background
    BG_MAIN = '#f5f1e8'
    BG_SECONDARY = '#fefdfb'
    BG_ACCENT = '#e8e2d5'
    
    # Warm green accents
    ACCENT_MAIN = '#4a7c2c'
    ACCENT_DARK = '#2d5016'
    ACCENT_LIGHT = '#6b9d4a'
    
    # Complementary warm colors
    ACCENT_WARN = '#d4855f'
    TEXT_MAIN = '#2a2520'
    TEXT_SECONDARY = '#5a5550'
    TEXT_LIGHT = '#ffffff'
    
    # Status colors
    STATUS_ACTIVE = '#4a7c2c'
    STATUS_INACTIVE = '#a67c52'
    
    FONT_MAIN = ('Segoe UI', 10)
    FONT_BOLD = ('Segoe UI', 10, 'bold')
    FONT_TITLE = ('Segoe UI', 16, 'bold')
    FONT_BUTTON = ('Segoe UI', 9)

class DarkTheme:
    """Modern dark/retro theme"""
    NAME = 'dark'
    # Dark backgrounds
    BG_MAIN = '#111217'
    BG_SECONDARY = '#151823'
    BG_ACCENT = '#2A2F3A'
    
    # Bright green/cyan accents
    ACCENT_MAIN = '#60F9A6'
    ACCENT_DARK = '#4AE0FF'
    ACCENT_LIGHT = '#80FFA7'
    
    # Complementary colors
    ACCENT_WARN = '#FF5C7C'
    TEXT_MAIN = '#E8F0F2'
    TEXT_SECONDARY = '#A0A8B0'
    TEXT_LIGHT = '#0A0B0E'

    # Status colors
    STATUS_ACTIVE = '#80FFA7'
    STATUS_INACTIVE = '#FF5C7C'
    
    FONT_MAIN = ('Consolas', 10)
    FONT_BOLD = ('Consolas', 10, 'bold')
    FONT_TITLE = ('Consolas', 18, 'bold')
    FONT_BUTTON = ('Consolas', 9)

# ====================================================================================
# POPUP CLASSES (Now theme-aware)
# ====================================================================================

class NotificationPopup:
    """A theme-aware popup notification"""
    def __init__(self, parent, title, message, sender_name, theme, duration=5000):
        self.popup = tk.Toplevel(parent)
        self.popup.overrideredirect(True)
        self.popup.attributes('-topmost', True)
        self.popup.geometry("360x130")

        # Position the popup at the bottom-right corner
        screen_width = self.popup.winfo_screenwidth()
        screen_height = self.popup.winfo_screenheight()
        x = screen_width - 380
        y = screen_height - 160
        self.popup.geometry(f"360x130+{x}+{y}")

        # Apply theme
        self.popup.configure(bg=theme.ACCENT_DARK)
        inner_frame = tk.Frame(self.popup, bg=theme.BG_SECONDARY)
        inner_frame.pack(fill=tk.BOTH, expand=True, padx=3, pady=3)
        content_frame = tk.Frame(inner_frame, bg=theme.BG_SECONDARY, padx=20, pady=15)
        content_frame.pack(fill=tk.BOTH, expand=True)

        tk.Label(content_frame, text=f"📨 {title}", font=(theme.FONT_MAIN[0], 11, 'bold'), fg=theme.ACCENT_DARK, bg=theme.BG_SECONDARY).pack(anchor=tk.W)
        tk.Label(content_frame, text=f"From: {sender_name}", font=theme.FONT_MAIN, fg=theme.TEXT_SECONDARY, bg=theme.BG_SECONDARY).pack(anchor=tk.W, pady=(3, 0))
        preview = message[:55] + "..." if len(message) > 55 else message
        tk.Label(content_frame, text=preview, font=theme.FONT_MAIN, fg=theme.TEXT_MAIN, bg=theme.BG_SECONDARY, wraplength=320, justify=tk.LEFT).pack(anchor=tk.W, pady=(8, 0))
        
        close_btn = tk.Label(content_frame, text="×", font=(theme.FONT_MAIN[0], 16), fg=theme.ACCENT_WARN, bg=theme.BG_SECONDARY, cursor='hand2')
        close_btn.place(relx=1.0, rely=0.0, anchor=tk.NE, x=-5, y=-5)
        close_btn.bind("<Button-1>", lambda e: self.close_popup())

        self.popup.after(duration, self.close_popup)
        self.popup.bind("<Button-1>", lambda e: self.close_popup())
        
        try:
            winsound.MessageBeep(winsound.MB_ICONINFORMATION)
        except Exception:
            self.popup.bell()
        
        self.fade_in()

    def fade_in(self):
        self.popup.attributes('-alpha', 0.0)
        for i in range(1, 11):
            self.popup.attributes('-alpha', i / 10.0)
            self.popup.update()
            time.sleep(0.02)

    def close_popup(self):
        try:
            for i in range(10, 0, -1):
                self.popup.attributes('-alpha', i / 10.0)
                self.popup.update()
                time.sleep(0.02)
            self.popup.destroy()
        except tk.TclError:
            pass # Already destroyed

class FileTransferPopup:
    """A theme-aware file transfer popup"""
    def __init__(self, parent, filename, sender_name, file_size, theme):
        self.accepted = False
        self.popup = tk.Toplevel(parent)
        self.popup.title("File Transfer Request")
        self.popup.geometry("420x220")
        self.popup.resizable(False, False)
        self.popup.attributes('-topmost', True)
        self.popup.configure(bg=theme.BG_SECONDARY)
        
        # Center the popup
        self.popup.update_idletasks()
        width = self.popup.winfo_width()
        height = self.popup.winfo_height()
        x = (self.popup.winfo_screenwidth() // 2) - (width // 2)
        y = (self.popup.winfo_screenheight() // 2) - (height // 2)
        self.popup.geometry(f"{width}x{height}+{x}+{y}")

        content_frame = tk.Frame(self.popup, bg=theme.BG_SECONDARY, padx=30, pady=25)
        content_frame.pack(fill=tk.BOTH, expand=True)

        tk.Label(content_frame, text="📤 Incoming File Transfer", font=(theme.FONT_MAIN[0], 13, 'bold'), fg=theme.ACCENT_DARK, bg=theme.BG_SECONDARY).pack(pady=(0, 15))
        
        info_frame = tk.Frame(content_frame, bg=theme.BG_SECONDARY)
        info_frame.pack(fill=tk.X, pady=(0, 10))
        tk.Label(info_frame, text=f"From: {sender_name}", font=theme.FONT_MAIN, fg=theme.TEXT_SECONDARY, bg=theme.BG_SECONDARY).pack(anchor=tk.W, pady=2)
        tk.Label(info_frame, text=f"File: {filename}", font=theme.FONT_BOLD, fg=theme.TEXT_MAIN, bg=theme.BG_SECONDARY).pack(anchor=tk.W, pady=2)
        size_mb = file_size / (1024 * 1024)
        tk.Label(info_frame, text=f"Size: {size_mb:.2f} MB", font=theme.FONT_MAIN, fg=theme.TEXT_SECONDARY, bg=theme.BG_SECONDARY).pack(anchor=tk.W, pady=2)

        button_frame = tk.Frame(content_frame, bg=theme.BG_SECONDARY)
        button_frame.pack(side=tk.BOTTOM, pady=(15, 0))

        accept_btn = tk.Button(button_frame, text="✓ Accept", command=self.accept_transfer, font=theme.FONT_BUTTON, fg=theme.TEXT_LIGHT, bg=theme.ACCENT_MAIN, activebackground=theme.ACCENT_DARK, activeforeground=theme.TEXT_LIGHT, relief='flat', bd=0, padx=25, pady=8, cursor='hand2')
        accept_btn.pack(side=tk.LEFT, padx=5)
        decline_btn = tk.Button(button_frame, text="✗ Decline", command=self.decline_transfer, font=theme.FONT_BUTTON, fg=theme.TEXT_LIGHT, bg=theme.ACCENT_WARN, activebackground='#c46f4a', activeforeground=theme.TEXT_LIGHT, relief='flat', bd=0, padx=25, pady=8, cursor='hand2')
        decline_btn.pack(side=tk.LEFT, padx=5)

        tk.Label(content_frame, text="Do you want to accept this file?", font=theme.FONT_MAIN, fg=theme.TEXT_MAIN, bg=theme.BG_SECONDARY).pack(side=tk.BOTTOM)

        self.auto_decline_timer = self.popup.after(30000, self.decline_transfer)

    def accept_transfer(self):
        self.accepted = True
        if self.auto_decline_timer: self.popup.after_cancel(self.auto_decline_timer)
        self.popup.destroy()

    def decline_transfer(self):
        self.accepted = False
        if self.auto_decline_timer: self.popup.after_cancel(self.auto_decline_timer)
        self.popup.destroy()

# ====================================================================================
# MAIN APPLICATION
# ====================================================================================
class EnhancedNetworkDeviceGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Mind Share")
        self.root.geometry("1250x820")

        # --- THEME MANAGEMENT ---
        self.theme = LightTheme
        
        self.device = LocalNetworkDevice()
        self.is_running = False
        self.comm_mode = tk.StringVar(value="peer_to_peer")
        self.selected_files = []

        self.apply_theme()
        self.setup_device_callbacks()
        self.setup_ui()
        self.update_all_widget_styles(self.root) # Initial style application
        self.start_auto_refresh()
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def apply_theme(self):
        """Configures all ttk styles based on the current theme."""
        style = ttk.Style()
        style.theme_use('clam')
        
        # Generic App styles that will be redefined on theme switch
        style.configure('App.TFrame', background=self.theme.BG_MAIN)
        style.configure('App.TLabelframe', background=self.theme.BG_MAIN, foreground=self.theme.ACCENT_DARK, bordercolor=self.theme.BG_ACCENT, borderwidth=1, relief='solid')
        style.configure('App.TLabelframe.Label', background=self.theme.BG_MAIN, foreground=self.theme.ACCENT_DARK, font=self.theme.FONT_BOLD)
        style.configure('App.TButton', background=self.theme.ACCENT_MAIN, foreground=self.theme.TEXT_LIGHT, bordercolor=self.theme.ACCENT_DARK, focuscolor='none', font=self.theme.FONT_BUTTON, borderwidth=0, relief='flat', padding=(15, 8))
        style.map('App.TButton', background=[('active', self.theme.ACCENT_DARK), ('disabled', self.theme.BG_ACCENT)], foreground=[('disabled', self.theme.TEXT_SECONDARY)])
        style.configure('App.TLabel', background=self.theme.BG_MAIN, foreground=self.theme.TEXT_MAIN, font=self.theme.FONT_MAIN)
        style.configure('Title.TLabel', background=self.theme.BG_MAIN, foreground=self.theme.ACCENT_DARK, font=self.theme.FONT_TITLE)
        style.configure('App.TCheckbutton', background=self.theme.BG_MAIN, foreground=self.theme.TEXT_MAIN, font=self.theme.FONT_MAIN)
        style.configure('App.TRadiobutton', background=self.theme.BG_MAIN, foreground=self.theme.TEXT_MAIN, font=self.theme.FONT_MAIN)
        style.configure('App.TCombobox', fieldbackground=self.theme.BG_SECONDARY, background=self.theme.BG_SECONDARY, foreground=self.theme.TEXT_MAIN, selectbackground=self.theme.ACCENT_LIGHT, selectforeground=self.theme.TEXT_LIGHT, bordercolor=self.theme.BG_ACCENT, arrowcolor=self.theme.ACCENT_MAIN)
        style.configure('App.Treeview', background=self.theme.BG_SECONDARY, foreground=self.theme.TEXT_MAIN, fieldbackground=self.theme.BG_SECONDARY, bordercolor=self.theme.BG_ACCENT, font=self.theme.FONT_MAIN, rowheight=25)
        style.configure('App.Treeview.Heading', background=self.theme.BG_ACCENT, foreground=self.theme.ACCENT_DARK, font=self.theme.FONT_BOLD, borderwidth=0, relief='flat')
        style.map('App.Treeview', background=[('selected', self.theme.ACCENT_LIGHT)], foreground=[('selected', self.theme.TEXT_LIGHT)])
        style.map('App.Treeview.Heading', background=[('active', self.theme.ACCENT_LIGHT)])
        style.configure('App.TNotebook', background=self.theme.BG_MAIN, bordercolor=self.theme.BG_ACCENT, tabmargins=[0, 5, 0, 0])
        style.configure('App.TNotebook.Tab', background=self.theme.BG_ACCENT, foreground=self.theme.TEXT_MAIN, padding=[15, 8], font=self.theme.FONT_MAIN, borderwidth=0)
        style.map('App.TNotebook.Tab', background=[('selected', self.theme.BG_SECONDARY)], foreground=[('selected', self.theme.ACCENT_DARK)], expand=[('selected', [1, 1, 1, 0])])

    def switch_theme(self):
        """Switches the theme and updates the entire UI."""
        self.theme = DarkTheme if self.theme.NAME == 'light' else LightTheme
        self.apply_theme()
        self.update_all_widget_styles(self.root)

    def update_all_widget_styles(self, widget):
        """Recursively updates styles for all non-ttk widgets."""
        try:
            # Update the widget itself based on its type
            widget_class = widget.winfo_class()

            if widget_class in ('Tk', 'Toplevel'):
                widget.configure(bg=self.theme.BG_MAIN)

            elif widget_class in ('Frame', 'Labelframe'):
                 widget.configure(background=self.theme.BG_MAIN)
                 if hasattr(widget, 'btn_container'): widget.btn_container.configure(bg=self.theme.BG_MAIN)
                 if hasattr(widget, 'disc_container'): widget.disc_container.configure(bg=self.theme.BG_MAIN)
                 if hasattr(widget, 'mode_container'): widget.mode_container.configure(bg=self.theme.BG_MAIN)

            elif widget_class == 'Label':
                if widget not in self.info_labels.values(): # Don't override specific labels
                    widget.configure(background=self.theme.BG_MAIN, foreground=self.theme.TEXT_MAIN)
            
            elif widget_class in ('Radiobutton', 'Checkbutton'):
                widget.configure(background=self.theme.BG_MAIN, foreground=self.theme.TEXT_MAIN, activebackground=self.theme.BG_ACCENT)

            elif 'scrolledtext' in str(type(widget)).lower():
                widget.configure(bg=self.theme.BG_SECONDARY, fg=self.theme.TEXT_MAIN, insertbackground=self.theme.ACCENT_MAIN)
            
            # Update special labels
            if hasattr(self, 'title_label'): self.title_label.configure(font=self.theme.FONT_TITLE)
            if hasattr(self, 'status_label'): self.status_label.configure(foreground=self.theme.STATUS_INACTIVE if not self.is_running else self.theme.STATUS_ACTIVE)
            if hasattr(self, 'drop_area'): self.drop_area.configure(bg=self.theme.BG_SECONDARY, fg=self.theme.TEXT_SECONDARY)
            if hasattr(self, 'info_labels'):
                for label_widget in self.info_labels.values():
                    label_widget.configure(bg=self.theme.BG_MAIN, fg=self.theme.TEXT_MAIN, font=self.theme.FONT_MAIN)
                    label_widget.master.configure(bg=self.theme.BG_MAIN)
                    label_widget.master.winfo_children()[0].configure(bg=self.theme.BG_MAIN, fg=self.theme.ACCENT_DARK, font=self.theme.FONT_BOLD)

        except tk.TclError as e:
            # This can happen if a widget is destroyed during the update
            # print(f"Could not update widget {widget}: {e}")
            pass

        # Recurse for all children
        for child in widget.winfo_children():
            self.update_all_widget_styles(child)

    def setup_device_callbacks(self):
        def enhanced_handle_client(client_socket, address):
            try:
                data = client_socket.recv(1024).decode('utf-8')
                if not data: return
                message = json.loads(data)

                if message['type'] == 'discovery':
                    response = {'type': 'discovery_response', 'device_name': self.device.device_name, 'device_id': self.device.device_id, 'ip': self.device.get_local_ip(), 'port': self.device.port}
                    client_socket.send(json.dumps(response).encode('utf-8'))
                elif message['type'] == 'data':
                    self.root.after(0, self.add_received_message, address[0], message.get('sender', 'Unknown'), message['payload'])
                    client_socket.send(json.dumps({'type': 'ack', 'status': 'received'}).encode('utf-8'))
                elif message['type'] == 'clipboard_data':
                    self.root.after(0, self.handle_clipboard_data, address[0], message.get('sender', 'Unknown'), message['clipboard_content'])
                    client_socket.send(json.dumps({'type': 'ack', 'status': 'received'}).encode('utf-8'))
                elif message['type'] == 'file_transfer_request':
                    filename, sender, file_size = message['filename'], message['sender'], message['file_size']
                    decision_result, decision_event = {'accepted': False}, threading.Event()
                    self.root.after(0, self.show_file_transfer_prompt, filename, sender, file_size, decision_result, decision_event)
                    decision_event.wait()
                    if decision_result['accepted']:
                        client_socket.send(json.dumps({'status': 'accepted'}).encode('utf-8'))
                        threading.Thread(target=self.receive_file_thread, args=(client_socket, address, filename, file_size, sender), daemon=True).start()
                    else:
                        client_socket.send(json.dumps({'status': 'declined', 'reason': 'User declined'}).encode('utf-8'))
                        client_socket.close()
            except Exception as e:
                self.log_message(f"Error handling client {address}: {e}")
                try: client_socket.close()
                except Exception: pass
        self.device.handle_client = enhanced_handle_client

    def show_file_transfer_prompt(self, filename, sender, file_size, result_container, event_to_set):
        try:
            popup = FileTransferPopup(self.root, filename, sender, file_size, self.theme)
            self.root.wait_window(popup.popup)
            result_container['accepted'] = popup.accepted
        except Exception as e:
            self.log_message(f"Failed to show file transfer popup: {e}")
            result_container['accepted'] = False
        finally:
            event_to_set.set()

    def receive_file_thread(self, client_socket, address, filename, file_size, sender):
        success = self.device.receive_file(client_socket, address, filename, file_size)
        if success:
            self.root.after(0, self.add_received_file, filename, sender, file_size)
        else:
            self.log_message(f"File transfer failed from {sender} for {filename}")

    def setup_ui(self):
        main_frame = ttk.Frame(self.root, padding="20", style='App.TFrame')
        main_frame.grid(row=0, column=0, sticky="nsew")
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(4, weight=1)

        # Header with Title and Theme Toggle
        header_frame = ttk.Frame(main_frame, style='App.TFrame')
        header_frame.grid(row=0, column=0, sticky="ew", pady=(0, 20))
        self.title_label = ttk.Label(header_frame, text="Mind Share", style='Title.TLabel')
        self.title_label.pack(side=tk.LEFT)
        self.theme_toggle_btn = ttk.Button(header_frame, text="Toggle Theme", command=self.switch_theme, style='App.TButton')
        self.theme_toggle_btn.pack(side=tk.RIGHT)
        header_frame.columnconfigure(0, weight=1)

        # The rest of the UI setup... (using generic style names)
        service_frame = ttk.LabelFrame(main_frame, text="Service Control", padding="15", style='App.TLabelframe')
        service_frame.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        btn_container = tk.Frame(service_frame, bg=self.theme.BG_MAIN)
        btn_container.pack(fill=tk.X)
        self.start_btn = ttk.Button(btn_container, text="🚀 Start Services", command=self.start_services, style='App.TButton')
        self.start_btn.pack(side=tk.LEFT, padx=(0, 10))
        self.stop_btn = ttk.Button(btn_container, text="🛑 Stop Services", command=self.stop_services, state='disabled', style='App.TButton')
        self.stop_btn.pack(side=tk.LEFT, padx=(0, 20))
        self.status_label = ttk.Label(btn_container, text="Status: Stopped", style='App.TLabel', font=self.theme.FONT_BOLD)
        self.status_label.pack(side=tk.LEFT, padx=(10, 20))
        self.auto_refresh_var = tk.BooleanVar(value=True)
        auto_refresh_cb = ttk.Checkbutton(btn_container, text="Auto-refresh devices", variable=self.auto_refresh_var, style='App.TCheckbutton')
        auto_refresh_cb.pack(side=tk.LEFT)

        discovery_frame = ttk.LabelFrame(main_frame, text="Device Discovery", padding="15", style='App.TLabelframe')
        discovery_frame.grid(row=2, column=0, sticky="ew", pady=(0, 10))
        disc_container = tk.Frame(discovery_frame, bg=self.theme.BG_MAIN)
        disc_container.pack(fill=tk.X)
        self.discover_btn = ttk.Button(disc_container, text="🔍 Discover Devices", command=self.discover_devices, state='disabled', style='App.TButton')
        self.discover_btn.pack(side=tk.LEFT, padx=(0, 10))
        self.refresh_btn = ttk.Button(disc_container, text="🔄 Refresh List", command=self.refresh_device_list, state='disabled', style='App.TButton')
        self.refresh_btn.pack(side=tk.LEFT, padx=(0, 20))
        self.device_count_label = ttk.Label(disc_container, text="Devices found: 0", style='App.TLabel')
        self.device_count_label.pack(side=tk.LEFT)

        comm_frame = ttk.LabelFrame(main_frame, text="Communication Mode", padding="15", style='App.TLabelframe')
        comm_frame.grid(row=3, column=0, sticky="ew", pady=(0, 10))
        mode_container = tk.Frame(comm_frame, bg=self.theme.BG_MAIN)
        mode_container.pack(fill=tk.X)
        ttk.Radiobutton(mode_container, text="📡 Peer-to-Peer", variable=self.comm_mode, value="peer_to_peer", style='App.TRadiobutton').pack(side=tk.LEFT, padx=(0, 30))
        ttk.Radiobutton(mode_container, text="📢 Broadcast", variable=self.comm_mode, value="broadcast", style='App.TRadiobutton').pack(side=tk.LEFT)

        self.notebook = ttk.Notebook(main_frame, style='App.TNotebook')
        self.notebook.grid(row=4, column=0, sticky="nsew", pady=(0, 10))
        
        # Setup tabs
        self.setup_tabs()

    def setup_tabs(self):
        tab_specs = {
            "📱 Devices": self.setup_device_list_tab,
            "💬 Messages": self.setup_communication_tab,
            "📁 File Sharing": self.setup_file_sharing_tab,
            "📥 Received": self.setup_received_messages_tab,
            "📋 Clipboard": self.setup_clipboard_tab,
            "📜 Log": self.setup_log_tab,
            "ℹ️ Network Info": self.setup_network_info_tab
        }
        for name, setup_func in tab_specs.items():
            tab_frame = ttk.Frame(self.notebook, style='App.TFrame')
            self.notebook.add(tab_frame, text=name)
            setup_func(tab_frame)

    # --- Individual Tab Setup Methods ---
    # These methods now take a 'parent' argument (the tab frame)
    # and build their content inside it.

    def setup_device_list_tab(self, parent):
        list_frame = ttk.Frame(parent, style='App.TFrame')
        list_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)
        columns = ('Name', 'IP', 'Status', 'Last Seen')
        self.device_tree = ttk.Treeview(list_frame, columns=columns, show='headings', style='App.Treeview')
        for col, text, width in [('Name', 'Device Name', 250), ('IP', 'IP Address', 180), ('Status', 'Status', 150), ('Last Seen', 'Last Seen', 120)]:
            self.device_tree.heading(col, text=text)
            self.device_tree.column(col, width=width)
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.device_tree.yview)
        self.device_tree.configure(yscrollcommand=scrollbar.set)
        self.device_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def setup_communication_tab(self, parent):
        target_frame = ttk.LabelFrame(parent, text="Target Selection", padding="15", style='App.TLabelframe')
        target_frame.pack(fill=tk.X, padx=15, pady=15)
        ttk.Label(target_frame, text="Select Target Device:", style='App.TLabel').pack(anchor=tk.W, pady=(0, 5))
        self.target_combo = ttk.Combobox(target_frame, state="readonly", width=60, style='App.TCombobox', font=self.theme.FONT_MAIN)
        self.target_combo.pack(fill=tk.X)
        
        message_frame = ttk.LabelFrame(parent, text="Message", padding="15", style='App.TLabelframe')
        message_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=(0, 15))
        ttk.Label(message_frame, text="Enter message to send:", style='App.TLabel').pack(anchor=tk.W, pady=(0, 5))
        
        button_container = tk.Frame(message_frame, bg=self.theme.BG_MAIN)
        button_container.pack(side=tk.BOTTOM, fill=tk.X, pady=(10, 0))
        self.send_btn = ttk.Button(button_container, text="📤 Send Message", command=self.send_message, state='disabled', style='App.TButton')
        self.send_btn.pack()
        
        self.message_text = scrolledtext.ScrolledText(message_frame, height=8, width=70, relief='solid', bd=1)
        self.message_text.pack(fill=tk.BOTH, expand=True)

    def setup_file_sharing_tab(self, parent):
        target_frame = ttk.LabelFrame(parent, text="Target Device", padding="15", style='App.TLabelframe')
        target_frame.pack(fill=tk.X, padx=15, pady=15)
        ttk.Label(target_frame, text="Select Target Device:", style='App.TLabel').pack(anchor=tk.W, pady=(0, 5))
        self.file_target_combo = ttk.Combobox(target_frame, state="readonly", width=60, style='App.TCombobox', font=self.theme.FONT_MAIN)
        self.file_target_combo.pack(fill=tk.X)
        
        methods_frame = ttk.LabelFrame(parent, text="File Selection", padding="15", style='App.TLabelframe')
        methods_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=(0, 15))
        
        browse_frame = tk.Frame(methods_frame, bg=self.theme.BG_MAIN)
        browse_frame.pack(fill=tk.X, pady=(0, 15))
        ttk.Button(browse_frame, text="📂 Browse File", command=self.browse_files, style='App.TButton').pack(side=tk.LEFT, padx=(0, 15))
        self.selected_file_label = ttk.Label(browse_frame, text="No file selected", style='App.TLabel')
        self.selected_file_label.pack(side=tk.LEFT)
        
        send_button_frame = tk.Frame(methods_frame, bg=self.theme.BG_MAIN)
        send_button_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=(10, 0))
        self.send_file_btn = ttk.Button(send_button_frame, text="📤 Send File", command=self.send_file, state='disabled', style='App.TButton')
        self.send_file_btn.pack()
        
        self.drop_area = tk.Label(methods_frame, text="\n🎯\n\nDrag and drop a file here\n", font=('Segoe UI', 11), relief='solid', bd=1)
        self.drop_area.pack(fill=tk.BOTH, expand=True, pady=(0, 15))
        self.drop_area.drop_target_register(tkdnd.DND_FILES)
        self.drop_area.dnd_bind('<<Drop>>', self.on_file_drop)
        self.drop_area.dnd_bind('<<DragEnter>>', lambda e: self.drop_area.config(bg=self.theme.ACCENT_LIGHT))
        self.drop_area.dnd_bind('<<DragLeave>>', lambda e: self.drop_area.config(bg=self.theme.BG_SECONDARY))

    def setup_received_messages_tab(self, parent):
        received_frame = ttk.Frame(parent, style='App.TFrame')
        received_frame.pack(fill=tk.BOTH, expand=True)

        # Received Messages Treeview
        messages_lf = ttk.LabelFrame(received_frame, text="Incoming Messages & Files", padding="15", style='App.TLabelframe')
        messages_lf.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)
        msg_columns = ('Time', 'From', 'Type', 'Content/File')
        self.received_tree = ttk.Treeview(messages_lf, columns=msg_columns, show='headings', style='App.Treeview')
        for col, text, w in [('Time', 'Time', 160), ('From', 'From', 220), ('Type', 'Type', 100), ('Content/File', 'Details', 500)]:
             self.received_tree.heading(col, text=text)
             self.received_tree.column(col, width=w)
        msg_scrollbar = ttk.Scrollbar(messages_lf, orient=tk.VERTICAL, command=self.received_tree.yview)
        self.received_tree.configure(yscrollcommand=msg_scrollbar.set)
        self.received_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        msg_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Action buttons
        actions_frame = tk.Frame(received_frame, bg=self.theme.BG_MAIN)
        actions_frame.pack(fill=tk.X, pady=(0, 15), padx=15, anchor=tk.E)
        ttk.Button(actions_frame, text="📂 Open Downloads", command=self.open_downloads_folder, style='App.TButton').pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(actions_frame, text="🗑️ Clear List", command=self.clear_received_messages, style='App.TButton').pack(side=tk.LEFT)

    def setup_clipboard_tab(self, parent):
        target_frame = ttk.LabelFrame(parent, text="Target Device", padding="15", style='App.TLabelframe')
        target_frame.pack(fill=tk.X, padx=15, pady=15)
        ttk.Label(target_frame, text="Select Target Device:", style='App.TLabel').pack(anchor=tk.W, pady=(0, 5))
        self.clipboard_target_combo = ttk.Combobox(target_frame, state="readonly", width=60, style='App.TCombobox', font=self.theme.FONT_MAIN)
        self.clipboard_target_combo.pack(fill=tk.X)
        
        current_frame = ttk.LabelFrame(parent, text="Clipboard Content", padding="15", style='App.TLabelframe')
        current_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=(0, 15))
        
        actions_frame = tk.Frame(current_frame, bg=self.theme.BG_MAIN)
        actions_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=(10, 0))
        ttk.Button(actions_frame, text="🔄 Refresh from my Clipboard", command=self.refresh_clipboard_display, style='App.TButton').pack(side=tk.LEFT, padx=(0, 10))
        self.send_clipboard_btn = ttk.Button(actions_frame, text="📤 Send my Clipboard", command=self.send_clipboard, state='disabled', style='App.TButton')
        self.send_clipboard_btn.pack(side=tk.LEFT)
        
        self.clipboard_text = scrolledtext.ScrolledText(current_frame, height=9, state='disabled', relief='solid', bd=1)
        self.clipboard_text.pack(fill=tk.BOTH, expand=True)

    def setup_log_tab(self, parent):
        log_text_frame = ttk.LabelFrame(parent, text="Application Log", padding="15", style='App.TLabelframe')
        log_text_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)
        self.log_text = scrolledtext.ScrolledText(log_text_frame, state='disabled', height=18, relief='solid', bd=1)
        self.log_text.pack(fill=tk.BOTH, expand=True)

    def setup_network_info_tab(self, parent):
        info_container = ttk.LabelFrame(parent, text="My Device Information", padding="25", style='App.TLabelframe')
        info_container.pack(padx=20, pady=20, fill=tk.X)
        self.info_labels = {}
        info_data = {"Device Name:": self.device.device_name, "Device ID:": self.device.device_id, "Local IP:": self.device.get_local_ip(), "Broadcast Address:": self.device.get_broadcast_address(), "TCP Port:": str(self.device.port), "UDP Broadcast Port:": str(self.device.broadcast_port)}
        for i, (label_text, value_text) in enumerate(info_data.items()):
            row_frame = tk.Frame(info_container, bg=self.theme.BG_MAIN)
            row_frame.pack(fill=tk.X, pady=8)
            tk.Label(row_frame, text=label_text, width=22, anchor=tk.W).pack(side=tk.LEFT, padx=(0, 10))
            self.info_labels[label_text] = tk.Label(row_frame, text=value_text, anchor=tk.W)
            self.info_labels[label_text].pack(side=tk.LEFT, fill=tk.X, expand=True)
            
    # --- Other methods (mostly unchanged) ---
    def on_closing(self):
        if messagebox.askokcancel("Quit", "Do you want to quit?"):
            self.stop_services()
            self.root.destroy()

    def start_services(self):
        if not self.is_running:
            self.log_message("Starting services...")
            self.device.start_all_services()
            self.is_running = True
            self.status_label.config(text="Status: Running", foreground=self.theme.STATUS_ACTIVE)
            for btn in [self.stop_btn, self.discover_btn, self.refresh_btn, self.send_btn, self.send_clipboard_btn, self.send_file_btn]:
                btn.config(state='normal')
            self.start_btn.config(state='disabled')
            self.discover_devices()

    def stop_services(self):
        if self.is_running:
            self.log_message("Stopping services...")
            self.device.stop()
            self.is_running = False
            self.status_label.config(text="Status: Stopped", foreground=self.theme.STATUS_INACTIVE)
            for btn in [self.stop_btn, self.discover_btn, self.refresh_btn, self.send_btn, self.send_clipboard_btn, self.send_file_btn]:
                btn.config(state='disabled')
            self.start_btn.config(state='normal')
            self.device.devices.clear()
            self.refresh_device_list()

    def discover_devices(self):
        if not self.is_running: return
        self.log_message("Discovering devices...")
        threading.Thread(target=lambda: (self.device.discover_devices(), self.root.after(0, self.refresh_device_list)), daemon=True).start()

    def refresh_device_list(self):
        self.log_message("Refreshing device list...")
        self.device_tree.delete(*self.device_tree.get_children())
        sorted_devices = sorted(self.device.devices.items(), key=lambda item: item[1]['name'])
        app_devices = []
        my_ip = self.device.get_local_ip()
        for ip, info in sorted_devices:
            is_self = (ip == my_ip)
            status = "Active (App)" if info.get('port') else "Reachable"
            age_seconds = int(time.time() - info['last_seen'])
            last_seen = f"{age_seconds}s ago"
            self.device_tree.insert('', 'end', values=(f"{info['name']} (You)" if is_self else info['name'], ip, status, last_seen))
            if info.get('port') and not is_self:
                app_devices.append(f"{info['name']} ({ip})")
        self.device_count_label.config(text=f"Devices found: {len(sorted_devices)}")
        for combo in [self.target_combo, self.file_target_combo, self.clipboard_target_combo]:
            current_value = combo.get()
            combo['values'] = app_devices
            if current_value in app_devices: combo.set(current_value)
            elif app_devices: combo.set(app_devices[0])
            else: combo.set('')

    def start_auto_refresh(self):
        if self.is_running and self.auto_refresh_var.get():
            self.refresh_device_list()
        self.root.after(15000, self.start_auto_refresh)

    def send_message(self):
        message = self.message_text.get("1.0", tk.END).strip()
        if not message: return
        target_str = self.target_combo.get()
        if self.comm_mode.get() == 'peer_to_peer' and not target_str: return
        
        if self.comm_mode.get() == 'broadcast':
            self.log_message(f"Broadcasting message: {message[:50]}...")
            threading.Thread(target=self.device.broadcast_data, args=(message,), daemon=True).start()
        else:
            target_ip = target_str.split('(')[-1].replace(')', '')
            self.log_message(f"Sending message to {target_ip}: {message[:50]}...")
            threading.Thread(target=self.device.send_data, args=(target_ip, message), daemon=True).start()
        self.message_text.delete("1.0", tk.END)
        
    def browse_files(self):
        filepath = filedialog.askopenfilename()
        if filepath:
            self.selected_files = [filepath]
            self.selected_file_label.config(text=os.path.basename(filepath))
            self.send_file_btn.config(state='normal')

    def on_file_drop(self, event):
        filepath = event.data.strip('{}')
        if os.path.isfile(filepath):
            self.selected_files = [filepath]
            self.selected_file_label.config(text=os.path.basename(filepath))
            self.send_file_btn.config(state='normal')
        self.drop_area.config(bg=self.theme.BG_SECONDARY)
        
    def send_file(self):
        if not self.selected_files: return
        target_str = self.file_target_combo.get()
        if not target_str: return
        target_ip = target_str.split('(')[-1].replace(')', '')
        filepath = self.selected_files[0]
        threading.Thread(target=self._send_file_worker, args=(target_ip, filepath), daemon=True).start()

    def _send_file_worker(self, target_ip, filepath):
        success = self.device.send_file(target_ip, filepath)
        if success:
            self.log_message(f"File sent successfully to {target_ip}.")
            self.root.after(0, lambda: messagebox.showinfo("Success", f"File '{os.path.basename(filepath)}' sent successfully!"))
        else:
            self.log_message(f"Failed to send file to {target_ip}.")
            self.root.after(0, lambda: messagebox.showerror("Failure", "Failed to send the file."))
            
    def add_received_message(self, ip, sender_name, message_content):
        timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
        msg_type = "Clipboard" if "Clipboard content received" in message_content else "Message"
        self.received_tree.insert('', 'end', values=(timestamp, f"{sender_name} ({ip})", msg_type, message_content))
        if msg_type == "Message": 
            NotificationPopup(self.root, "New Message", message_content, sender_name, self.theme)

    def clear_received_messages(self):
        if messagebox.askyesno("Confirm", "Are you sure you want to clear this list?"):
            self.received_tree.delete(*self.received_tree.get_children())
            
    def add_received_file(self, filename, sender, file_size):
        timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
        size_mb = f"{file_size / (1024*1024):.2f} MB"
        self.received_tree.insert('', 'end', values=(timestamp, sender, "File", f"{filename} ({size_mb})"))
        NotificationPopup(self.root, "File Received", filename, sender, self.theme)

    def open_downloads_folder(self):
        path = os.path.join(os.getcwd(), 'downloads')
        os.makedirs(path, exist_ok=True)
        try:
            if sys.platform == "win32": os.startfile(path)
            elif sys.platform == "darwin": subprocess.Popen(["open", path])
            else: subprocess.Popen(["xdg-open", path])
        except Exception as e:
            messagebox.showerror("Error", f"Could not open the downloads folder.\nPath: {path}")

    def refresh_clipboard_display(self):
        try:
            content = self.root.clipboard_get()
        except tk.TclError:
            content = "[Clipboard is empty or non-text]"
        self.clipboard_text.config(state='normal')
        self.clipboard_text.delete('1.0', tk.END)
        self.clipboard_text.insert('1.0', content)
        self.clipboard_text.config(state='disabled')
        
    def send_clipboard(self):
        target_str = self.clipboard_target_combo.get()
        if not target_str: return
        try:
            content = self.root.clipboard_get()
            if not content: return
            target_ip = target_str.split('(')[-1].replace(')', '')
            message = {'type': 'clipboard_data', 'clipboard_content': content, 'sender': self.device.device_name}
            threading.Thread(target=self._send_clipboard_worker, args=(target_ip, message), daemon=True).start()
        except tk.TclError:
            messagebox.showinfo("Empty Clipboard", "Nothing to send.")

    def _send_clipboard_worker(self, target_ip, message):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(5)
                sock.connect((target_ip, self.device.port))
                sock.send(json.dumps(message).encode('utf-8'))
                sock.recv(1024) # Wait for ACK
        except Exception as e:
            self.log_message(f"Clipboard send failed: {e}")

    def handle_clipboard_data(self, ip, sender_name, content):
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(content)
            log_msg = f"Clipboard content received from {sender_name} and copied locally."
            self.add_received_message(ip, sender_name, log_msg)
            NotificationPopup(self.root, "Clipboard Updated", "Content copied to your clipboard!", sender_name, self.theme)
        except Exception as e:
            self.log_message(f"Failed to update local clipboard: {e}")

    def log_message(self, message):
        if self.root.winfo_exists():
            self.root.after(0, lambda: self._log_to_widget(message))

    def _log_to_widget(self, message):
        timestamp = time.strftime('%H:%M:%S')
        self.log_text.config(state='normal')
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.config(state='disabled')
        self.log_text.see(tk.END)

if __name__ == "__main__":
    root = tkdnd.Tk()
    app = EnhancedNetworkDeviceGUI(root)
    root.mainloop()