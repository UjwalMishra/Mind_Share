import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import threading
import time
import winsound
import os
from poc import LocalNetworkDevice


class NotificationPopup:
    """A popup notification window that appears in the bottom-right corner"""
    
    def __init__(self, parent, title, message, sender_name, duration=5000):
        self.parent = parent
        self.duration = duration
        
        # Create the popup window
        self.popup = tk.Toplevel(parent)
        self.popup.title("New Message")
        self.popup.geometry("350x120")
        self.popup.resizable(False, False)
        
        # Remove window decorations and make it stay on top
        self.popup.overrideredirect(True)
        self.popup.attributes('-topmost', True)
        
        # Position in bottom-right corner
        self.position_popup()
        
        # Configure the popup appearance
        self.popup.configure(bg='#2b2b2b')
        
        # Create the content frame
        content_frame = tk.Frame(self.popup, bg='#2b2b2b', padx=15, pady=10)
        content_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title label
        title_label = tk.Label(content_frame, text="📨 New Message Received", 
                              font=('Arial', 10, 'bold'), 
                              fg='#ffffff', bg='#2b2b2b')
        title_label.pack(anchor=tk.W)
        
        # Sender label
        sender_label = tk.Label(content_frame, text=f"From: {sender_name}", 
                               font=('Arial', 9), 
                               fg='#cccccc', bg='#2b2b2b')
        sender_label.pack(anchor=tk.W, pady=(2, 0))
        
        # Message preview (truncate if too long)
        preview = message[:50] + "..." if len(message) > 50 else message
        message_label = tk.Label(content_frame, text=preview, 
                                font=('Arial', 9), 
                                fg='#ffffff', bg='#2b2b2b',
                                wraplength=300)
        message_label.pack(anchor=tk.W, pady=(5, 0))
        
        # Close button
        close_btn = tk.Button(content_frame, text="×", 
                             command=self.close_popup,
                             font=('Arial', 12, 'bold'),
                             fg='#ffffff', bg='#ff4444',
                             bd=0, padx=8, pady=2,
                             cursor='hand2')
        close_btn.place(relx=1.0, rely=0.0, anchor=tk.NE, x=-5, y=5)
        
        # Add border effect
        border_frame = tk.Frame(self.popup, bg='#4a9eff', height=3)
        border_frame.pack(side=tk.TOP, fill=tk.X)
        
        # Auto-close after duration
        self.popup.after(self.duration, self.close_popup)
        
        # Add click handler to close on click
        self.popup.bind("<Button-1>", lambda e: self.close_popup())
        content_frame.bind("<Button-1>", lambda e: self.close_popup())
        
        # Play notification sound
        self.play_notification_sound()
        
        # Fade in animation
        self.fade_in()
    
    def position_popup(self):
        """Position the popup in the bottom-right corner of the screen"""
        # Get screen dimensions
        screen_width = self.popup.winfo_screenwidth()
        screen_height = self.popup.winfo_screenheight()
        
        # Calculate position (bottom-right with some margin)
        x = screen_width - 370  # 350 width + 20 margin
        y = screen_height - 150  # 120 height + 30 margin
        
        self.popup.geometry(f"350x120+{x}+{y}")
    
    def play_notification_sound(self):
        """Play a notification sound"""
        try:
            # Play Windows notification sound
            winsound.MessageBeep(winsound.MB_ICONINFORMATION)
        except Exception:
            # Fallback: try to play system beep
            try:
                winsound.Beep(800, 200)  # 800Hz for 200ms
            except Exception:
                pass  # Silent fallback if no sound is available
    
    def fade_in(self):
        """Simple fade-in effect"""
        self.popup.attributes('-alpha', 0.0)
        self.popup.update()
        
        for i in range(1, 11):
            self.popup.attributes('-alpha', i / 10.0)
            self.popup.update()
            time.sleep(0.02)
    
    def close_popup(self):
        """Close the popup with fade-out effect"""
        try:
            # Fade out
            for i in range(10, 0, -1):
                self.popup.attributes('-alpha', i / 10.0)
                self.popup.update()
                time.sleep(0.02)
            
            self.popup.destroy()
        except tk.TclError:
            # Window already destroyed
            pass


class NetworkDeviceGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Network Device Discovery & Communication")
        self.root.geometry("800x600")
        self.root.configure(bg='#f0f0f0')
        
        # Initialize the network device
        self.device = LocalNetworkDevice()
        self.device_thread = None
        self.is_running = False
        
        # Communication mode
        self.comm_mode = tk.StringVar(value="peer_to_peer")
        
        # Received messages storage
        self.received_messages = []
        
        self.setup_ui()
    
    def setup_ui(self):
        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(4, weight=1)
        
        # Title
        title_label = ttk.Label(main_frame, text="Network Device Manager",
                               font=('Arial', 16, 'bold'))
        title_label.grid(row=0, column=0, columnspan=3, pady=(0, 20))
        
        # Service control section
        service_frame = ttk.LabelFrame(main_frame, text="Service Control", padding="10")
        service_frame.grid(row=1, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10))
        
        self.start_btn = ttk.Button(service_frame, text="Start Services",
                                   command=self.start_services)
        self.start_btn.grid(row=0, column=0, padx=(0, 10))
        
        self.stop_btn = ttk.Button(service_frame, text="Stop Services",
                                  command=self.stop_services, state='disabled')
        self.stop_btn.grid(row=0, column=1, padx=(0, 10))
        
        self.status_label = ttk.Label(service_frame, text="Status: Stopped",
                                     foreground='red')
        self.status_label.grid(row=0, column=2, padx=(10, 0))
        
        # Device discovery section
        discovery_frame = ttk.LabelFrame(main_frame, text="Device Discovery", padding="10")
        discovery_frame.grid(row=2, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10))
        
        self.discover_btn = ttk.Button(discovery_frame, text="🔍 Discover Devices",
                                      command=self.discover_devices)
        self.discover_btn.grid(row=0, column=0, padx=(0, 10))
        
        self.refresh_btn = ttk.Button(discovery_frame, text="🔄 Refresh List",
                                     command=self.refresh_device_list)
        self.refresh_btn.grid(row=0, column=1, padx=(0, 10))
        
        self.device_count_label = ttk.Label(discovery_frame, text="Devices found: 0")
        self.device_count_label.grid(row=0, column=2, padx=(10, 0))
        
        # Communication mode selection
        comm_frame = ttk.LabelFrame(main_frame, text="Communication Mode", padding="10")
        comm_frame.grid(row=3, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10))
        
        ttk.Radiobutton(comm_frame, text="📡 Peer-to-Peer (Direct Send)",
                       variable=self.comm_mode, value="peer_to_peer").grid(row=0, column=0, padx=(0, 20))
        
        ttk.Radiobutton(comm_frame, text="📢 Multicast (Broadcast to All)",
                       variable=self.comm_mode, value="multicast").grid(row=0, column=1)
        
        # Main content area with notebook
        notebook = ttk.Notebook(main_frame)
        notebook.grid(row=4, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        
        # Device list tab
        device_frame = ttk.Frame(notebook)
        notebook.add(device_frame, text="📱 Device List")
        
        # Device list with scrollbar
        list_frame = ttk.Frame(device_frame)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Treeview for device list
        columns = ('Name', 'IP', 'Status', 'Last Seen')
        self.device_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=8)
        
        # Define headings
        self.device_tree.heading('Name', text='Device Name')
        self.device_tree.heading('IP', text='IP Address')
        self.device_tree.heading('Status', text='Status')
        self.device_tree.heading('Last Seen', text='Last Seen')
        
        # Configure column widths
        self.device_tree.column('Name', width=150)
        self.device_tree.column('IP', width=120)
        self.device_tree.column('Status', width=120)
        self.device_tree.column('Last Seen', width=100)
        
        # Scrollbar for treeview
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.device_tree.yview)
        self.device_tree.configure(yscrollcommand=scrollbar.set)
        
        self.device_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Communication tab
        comm_tab_frame = ttk.Frame(notebook)
        notebook.add(comm_tab_frame, text="💬 Send Data")
        
        # Target selection for peer-to-peer
        target_frame = ttk.LabelFrame(comm_tab_frame, text="Target Selection (Peer-to-Peer)", padding="10")
        target_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Label(target_frame, text="Select Target Device:").pack(anchor=tk.W)
        self.target_combo = ttk.Combobox(target_frame, state="readonly", width=50)
        self.target_combo.pack(fill=tk.X, pady=(5, 0))
        
        # Message input
        message_frame = ttk.LabelFrame(comm_tab_frame, text="Message", padding="10")
        message_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        ttk.Label(message_frame, text="Enter message to send:").pack(anchor=tk.W)
        self.message_text = scrolledtext.ScrolledText(message_frame, height=6, width=60)
        self.message_text.pack(fill=tk.BOTH, expand=True, pady=(5, 10))
        
        # Send button
        self.send_btn = ttk.Button(message_frame, text="📤 Send Message",
                                  command=self.send_message)
        self.send_btn.pack(pady=(0, 5))

        # Received Messages tab
        received_frame = ttk.Frame(notebook)
        notebook.add(received_frame, text="📥 Received Messages")

        # Received messages display
        received_messages_frame = ttk.LabelFrame(received_frame, text="Incoming Messages", padding="10")
        received_messages_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Treeview for received messages
        msg_columns = ('Time', 'From', 'Message')
        self.received_tree = ttk.Treeview(received_messages_frame, columns=msg_columns, show='headings', height=12)

        # Define headings for received messages
        self.received_tree.heading('Time', text='Time')
        self.received_tree.heading('From', text='From Device')
        self.received_tree.heading('Message', text='Message Content')

        # Configure column widths for received messages
        self.received_tree.column('Time', width=100)
        self.received_tree.column('From', width=150)
        self.received_tree.column('Message', width=400)

        # Scrollbar for received messages treeview
        msg_scrollbar = ttk.Scrollbar(received_messages_frame, orient=tk.VERTICAL, command=self.received_tree.yview)
        self.received_tree.configure(yscrollcommand=msg_scrollbar.set)

        self.received_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        msg_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Clear messages button
        clear_btn = ttk.Button(received_messages_frame, text="🗑️ Clear Messages",
                              command=self.clear_received_messages)
        clear_btn.pack(pady=(10, 0))

        # Log tab
        log_frame = ttk.Frame(notebook)
        notebook.add(log_frame, text="📋 Activity Log")
        
        self.log_text = scrolledtext.ScrolledText(log_frame, height=15, width=80)
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Network info tab
        info_frame = ttk.Frame(notebook)
        notebook.add(info_frame, text="ℹ️ Network Info")
        
        self.info_text = scrolledtext.ScrolledText(info_frame, height=15, width=80)
        self.info_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        self.update_network_info()
    
    def log_message(self, message):
        """Add message to log with timestamp"""
        timestamp = time.strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)
        self.root.update_idletasks()
    
    def start_services(self):
        """Start the network services"""
        if not self.is_running:
            try:
                self.log_message("Starting network services...")
                self.device_thread = threading.Thread(target=self.run_device_services, daemon=True)
                self.device_thread.start()
                
                self.is_running = True
                self.start_btn.config(state='disabled')
                self.stop_btn.config(state='normal')
                self.status_label.config(text="Status: Running", foreground='green')
                self.log_message("✅ Network services started successfully!")
                
            except Exception as e:
                self.log_message(f"❌ Error starting services: {str(e)}")
                messagebox.showerror("Error", f"Failed to start services: {str(e)}")

    def run_device_services(self):
        """Run device services in background thread"""
        try:
            # Set the callback for received messages
            self.device.set_message_callback(self.add_received_message)
            self.device.start_all_services()
        except Exception as e:
            self.log_message(f"❌ Service error: {str(e)}")

    def stop_services(self):
        """Stop the network services"""
        if self.is_running:
            try:
                self.log_message("Stopping network services...")
                self.device.stop()
                
                self.is_running = False
                self.start_btn.config(state='normal')
                self.stop_btn.config(state='disabled')
                self.status_label.config(text="Status: Stopped", foreground='red')
                self.log_message("🛑 Network services stopped")
                
            except Exception as e:
                self.log_message(f"❌ Error stopping services: {str(e)}")
                messagebox.showerror("Error", f"Failed to stop services: {str(e)}")

    def discover_devices(self):
        """Discover devices on the network"""
        if not self.is_running:
            messagebox.showwarning("Warning", "Please start services first!")
            return
            
        self.log_message("🔍 Starting device discovery...")
        self.discover_btn.config(state='disabled')
        
        # Run discovery in separate thread to avoid blocking UI
        threading.Thread(target=self._discover_devices_thread, daemon=True).start()

    def _discover_devices_thread(self):
        """Device discovery thread"""
        try:
            devices = self.device.discover_devices()
            
            # Update UI in main thread
            self.root.after(0, self._update_device_discovery_results, devices)
            
        except Exception as e:
            self.root.after(0, lambda: self.log_message(f"❌ Discovery error: {str(e)}"))
        finally:
            self.root.after(0, lambda: self.discover_btn.config(state='normal'))

    def _update_device_discovery_results(self, devices):
        """Update UI with discovery results"""
        self.log_message(f"✅ Discovery complete! Found {len(devices)} devices")
        
        for ip, info in devices.items():
            status = "📱 App Running" if info.get('port') else "💻 Device Found"
            self.log_message(f"  - {info['name']} ({ip}) - {status}")
        
        self.refresh_device_list()

    def refresh_device_list(self):
        """Refresh the device list display"""
        # Clear existing items
        for item in self.device_tree.get_children():
            self.device_tree.delete(item)
        
        # Clear target combo
        self.target_combo['values'] = []
        
        if not self.device.devices:
            self.device_count_label.config(text="Devices found: 0")
            return
        
        # Populate device tree
        app_devices = []
        for ip, info in self.device.devices.items():
            status = "📱 App Running" if info.get('port') else "💻 Device Found"
            last_seen = int(time.time() - info['last_seen'])
            last_seen_str = f"{last_seen}s ago"
            
            self.device_tree.insert('', tk.END, values=(
                info['name'], ip, status, last_seen_str
            ))
            
            # Add to combo if it's running our app
            if info.get('port'):
                app_devices.append(f"{info['name']} ({ip})")
        
        # Update combo box with app devices
        self.target_combo['values'] = app_devices
        if app_devices:
            self.target_combo.set(app_devices[0])
        
        # Update count
        total_devices = len(self.device.devices)
        app_count = len(app_devices)
        self.device_count_label.config(text=f"Devices found: {total_devices} (App: {app_count})")

    def send_message(self):
        """Send message based on selected mode"""
        if not self.is_running:
            messagebox.showwarning("Warning", "Please start services first!")
            return
        
        message = self.message_text.get(1.0, tk.END).strip()
        if not message:
            messagebox.showwarning("Warning", "Please enter a message to send!")
            return
        
        mode = self.comm_mode.get()
        
        if mode == "multicast":
            self._send_multicast(message)
        else:
            self._send_peer_to_peer(message)

    def _send_multicast(self, message):
        """Send message to all devices (broadcast)"""
        self.log_message(f"📢 Broadcasting message: '{message}'")
        
        try:
            self.device.broadcast_data(message)
            self.log_message("✅ Broadcast completed!")
            self.message_text.delete(1.0, tk.END)
            
        except Exception as e:
            self.log_message(f"❌ Broadcast error: {str(e)}")
            messagebox.showerror("Error", f"Failed to broadcast: {str(e)}")

    def _send_peer_to_peer(self, message):
        """Send message to selected device"""
        target = self.target_combo.get()
        if not target:
            messagebox.showwarning("Warning", "Please select a target device!")
            return
        
        # Extract IP from target string
        try:
            target_ip = target.split('(')[1].split(')')[0]
            self.log_message(f"📡 Sending to {target}: '{message}'")
            
            success = self.device.send_data(target_ip, message)
            
            if success:
                self.log_message(f"✅ Message sent successfully to {target}")
                self.message_text.delete(1.0, tk.END)
            else:
                self.log_message(f"❌ Failed to send message to {target}")
                messagebox.showerror("Error", f"Failed to send message to {target}")
            
        except Exception as e:
            self.log_message(f"❌ Send error: {str(e)}")
            messagebox.showerror("Error", f"Failed to send message: {str(e)}")

    def clear_received_messages(self):
        """Clear all received messages"""
        self.received_messages.clear()
        for item in self.received_tree.get_children():
            self.received_tree.delete(item)
        self.log_message("🗑️ Received messages cleared")

    def add_received_message(self, sender_ip, sender_name, message):
        """Add a received message to the display"""
        timestamp = time.strftime("%H:%M:%S")
        
        # Add to storage
        msg_data = {
            'timestamp': timestamp,
            'sender_ip': sender_ip,
            'sender_name': sender_name,
            'message': message
        }
        self.received_messages.append(msg_data)
        
        # Add to treeview (in main thread)
        self.root.after(0, self._update_received_messages_display, msg_data)
        
        # Show notification popup
        self.root.after(0, self._show_notification, "New Message", message, sender_name)
        
        # Log the received message
        self.log_message(f"📥 Received from {sender_name} ({sender_ip}): {message}")

    def _show_notification(self, title, message, sender_name):
        """Show notification popup in the main thread"""
        try:
            NotificationPopup(self.root, title, message, sender_name)
        except Exception as e:
            self.log_message(f"❌ Notification error: {str(e)}")

    def _update_received_messages_display(self, msg_data):
        """Update the received messages display in the main thread"""
        self.received_tree.insert('', 0, values=(
            msg_data['timestamp'],
            f"{msg_data['sender_name']} ({msg_data['sender_ip']})",
            msg_data['message']
        ))
        
        # Auto-scroll to show the latest message
        children = self.received_tree.get_children()
        if children:
            self.received_tree.see(children[0])

    def update_network_info(self):
        """Update network information display"""
        try:
            info = f"""Network Information:

Local IP Address: {self.device.get_local_ip()}
Broadcast Address: {self.device.get_broadcast_address()}
TCP Port: {self.device.port}
UDP Broadcast Port: {self.device.broadcast_port}
Device Name: {self.device.device_name}
Device ID: {self.device.device_id}

Service Status: {'Running' if self.is_running else 'Stopped'}

Communication Modes:
• Peer-to-Peer: Send messages directly to selected devices
• Multicast: Broadcast messages to all discovered devices

Device Discovery:
• Uses ping sweep to find active devices on network
• Attempts TCP connection to identify devices running our app
• Maintains list of discovered devices with timestamps
"""
            
            self.info_text.delete(1.0, tk.END)
            self.info_text.insert(1.0, info)
            
        except Exception as e:
            self.log_message(f"❌ Error updating network info: {str(e)}")

    def on_closing(self):
        """Handle application closing"""
        if self.is_running:
            self.stop_services()
        self.root.destroy()


def main():
    root = tk.Tk()
    app = NetworkDeviceGUI(root)
    
    # Handle window closing
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    
    # Start the GUI
    root.mainloop()


if __name__ == "__main__":
    main()
