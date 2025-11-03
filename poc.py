import socket
import threading
import json
import time
import subprocess
import re
import struct
from typing import Dict, List, Tuple

class LocalNetworkDevice:
    def __init__(self, port: int = 8888, broadcast_port: int = 8889):
        self.port = port
        self.broadcast_port = broadcast_port
        self.devices = {}  # {ip: {name, port, last_seen}}
        self.server_socket = None
        self.broadcast_socket = None
        self.running = False
        self.device_name = socket.gethostname()
        self.device_id = f"{self.device_name}_{int(time.time())}"
        self.message_callback = None  # Callback for received messages
    
    def set_message_callback(self, callback):
        """Set callback function for received messages"""
        self.message_callback = callback
        
    def get_local_ip(self) -> str:
        """Get the local IP address"""
        try:
            # Connect to a remote address to get local IP
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                return s.getsockname()[0]
        except:
            return "127.0.0.1"
    
    def get_broadcast_address(self) -> str:
        """Get the broadcast address for the network"""
        local_ip = self.get_local_ip()
        # Assume /24 subnet
        network = '.'.join(local_ip.split('.')[:-1]) + '.255'
        return network
    
    def ping_sweep(self) -> List[str]:
        """Perform ping sweep to find active devices on network"""
        local_ip = self.get_local_ip()
        base_ip = '.'.join(local_ip.split('.')[:-1])
        active_ips = []
        
        print("Performing ping sweep...")
        
        def ping_host(ip):
            try:
                # Use ping command
                result = subprocess.run(
                    ['ping', '-c', '1', '-W', '1', ip], 
                    capture_output=True, 
                    text=True, 
                    timeout=2
                )
                if result.returncode == 0:
                    active_ips.append(ip)
            except:
                pass
        
        # Create threads for parallel pinging
        threads = []
        for i in range(1, 255):
            ip = f"{base_ip}.{i}"
            if ip != local_ip:  # Skip self
                thread = threading.Thread(target=ping_host, args=(ip,))
                threads.append(thread)
                thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        return active_ips
    
    def start_broadcast_advertiser(self):
        """Start UDP broadcast advertiser (like BLE advertising)"""
        try:
            self.broadcast_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.broadcast_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            
            while self.running:
                advertisement = {
                    'type': 'device_advertisement',
                    'device_name': self.device_name,
                    'device_id': self.device_id,
                    'ip': self.get_local_ip(),
                    'port': self.port,
                    'timestamp': time.time()
                }
                
                message = json.dumps(advertisement).encode('utf-8')
                broadcast_addr = self.get_broadcast_address()
                
                try:
                    self.broadcast_socket.sendto(message, (broadcast_addr, self.broadcast_port))
                    print(f"Broadcasting advertisement to {broadcast_addr}:{self.broadcast_port}")
                except Exception as e:
                    print(f"Broadcast error: {e}")
                
                time.sleep(5)  # Advertise every 5 seconds
                
        except Exception as e:
            print(f"Advertiser error: {e}")
        finally:
            if self.broadcast_socket:
                self.broadcast_socket.close()
    
    def start_broadcast_scanner(self):
        """Start UDP broadcast scanner (like BLE scanning)"""
        try:
            scanner_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            scanner_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            scanner_socket.bind(('', self.broadcast_port))
            scanner_socket.settimeout(1)
            
            print(f"Scanner listening on port {self.broadcast_port}")
            
            while self.running:
                try:
                    data, address = scanner_socket.recvfrom(1024)
                    message = json.loads(data.decode('utf-8'))
                    
                    if (message['type'] == 'device_advertisement' and 
                        message['device_id'] != self.device_id):  # Ignore self
                        
                        ip = message['ip']
                        self.devices[ip] = {
                            'name': message['device_name'],
                            'device_id': message['device_id'],
                            'port': message['port'],
                            'last_seen': time.time()
                        }
                        print(f"Discovered device: {message['device_name']} at {ip}")
                        
                except socket.timeout:
                    continue
                except Exception as e:
                    if self.running:
                        print(f"Scanner error: {e}")
                    
        except Exception as e:
            print(f"Scanner setup error: {e}")
        finally:
            scanner_socket.close()
    
    def scan_network(self) -> List[str]:
        """Scan local network for active devices using multiple methods"""
        print("Scanning network for active devices...")
        
        # Method 1: Ping sweep
        ping_results = self.ping_sweep()
        print(f"Ping sweep found {len(ping_results)} active devices")
        
        # Method 2: Port scanning on our application port
        app_devices = []
        for ip in ping_results:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(0.5)
                result = sock.connect_ex((ip, self.port))
                if result == 0:
                    app_devices.append(ip)
                sock.close()
            except:
                pass
        
        print(f"Found {len(app_devices)} devices running our application")
        return ping_results
    
    def start_server(self):
        """Start the server to listen for incoming connections"""
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        try:
            self.server_socket.bind(('0.0.0.0', self.port))
            self.server_socket.listen(5)
            self.running = True
            
            print(f"TCP Server started on {self.get_local_ip()}:{self.port}")
            
            while self.running:
                try:
                    client_socket, address = self.server_socket.accept()
                    threading.Thread(
                        target=self.handle_client, 
                        args=(client_socket, address)
                    ).start()
                except:
                    if self.running:
                        continue
                    else:
                        break
                        
        except Exception as e:
            print(f"Server error: {e}")
        finally:
            if self.server_socket:
                self.server_socket.close()
    
    def handle_client(self, client_socket: socket.socket, address: Tuple[str, int]):
        """Handle incoming client connections"""
        try:
            data = client_socket.recv(1024).decode('utf-8')
            message = json.loads(data)
            
            if message['type'] == 'discovery':
                # Respond to discovery request
                response = {
                    'type': 'discovery_response',
                    'device_name': self.device_name,
                    'device_id': self.device_id,
                    'ip': self.get_local_ip(),
                    'port': self.port
                }
                client_socket.send(json.dumps(response).encode('utf-8'))
                
            elif message['type'] == 'data':
                # Handle incoming data
                sender_name = message.get('sender', f'Device-{address[0]}')
                payload = message['payload']
                
                print(f"Received data from {address[0]}: {payload}")
                
                # Call the callback if it's set (for GUI integration)
                if self.message_callback:
                    self.message_callback(address[0], sender_name, payload)
                
                response = {'type': 'ack', 'status': 'received'}
                client_socket.send(json.dumps(response).encode('utf-8'))
                
        except Exception as e:
            print(f"Error handling client {address}: {e}")
        finally:
            client_socket.close()
    
    def discover_devices(self) -> Dict[str, dict]:
        """Discover devices on the network using multiple methods"""
        print("Starting comprehensive device discovery...")
        
        # Clear old devices
        current_time = time.time()
        self.devices = {ip: info for ip, info in self.devices.items() 
                       if current_time - info['last_seen'] < 30}
        
        # Method 1: Network scan for all active devices
        active_ips = self.scan_network()
        
        # Method 2: Try to connect to devices running our app
        discovered_devices = {}
        for ip in active_ips:
            if ip == self.get_local_ip():
                continue  # Skip self
                
            try:
                # Send discovery request
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(2)
                sock.connect((ip, self.port))
                
                discovery_msg = {
                    'type': 'discovery',
                    'device_name': self.device_name,
                    'device_id': self.device_id
                }
                
                sock.send(json.dumps(discovery_msg).encode('utf-8'))
                response = sock.recv(1024).decode('utf-8')
                device_info = json.loads(response)
                
                if device_info['type'] == 'discovery_response':
                    discovered_devices[ip] = {
                        'name': device_info['device_name'],
                        'device_id': device_info.get('device_id', 'unknown'),
                        'port': device_info['port'],
                        'last_seen': time.time()
                    }
                    
                sock.close()
                
            except Exception as e:
                # Device found but not running our app
                discovered_devices[ip] = {
                    'name': f'Device-{ip.split(".")[-1]}',
                    'device_id': f'unknown_{ip}',
                    'port': None,
                    'last_seen': time.time(),
                    'status': 'not_running_app'
                }
        
        self.devices.update(discovered_devices)
        
        print(f"Discovery complete. Found {len(discovered_devices)} devices total")
        print(f"Devices running our app: {len([d for d in discovered_devices.values() if d.get('port')])}")
        
        return discovered_devices
    
    def send_data(self, target_ip: str, data: str) -> bool:
        """Send data to a specific device"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            sock.connect((target_ip, self.port))
            
            message = {
                'type': 'data',
                'payload': data,
                'sender': self.device_name
            }
            
            sock.send(json.dumps(message).encode('utf-8'))
            response = sock.recv(1024).decode('utf-8')
            result = json.loads(response)
            
            sock.close()
            return result.get('status') == 'received'
            
        except Exception as e:
            print(f"Error sending data to {target_ip}: {e}")
            return False
    
    def broadcast_data(self, data: str):
        """Broadcast data to all discovered devices"""
        app_devices = {ip: info for ip, info in self.devices.items() if info.get('port')}
        if not app_devices:
            print("No devices running our application discovered. Run discover_devices() first.")
            return
        
        for ip, device_info in app_devices.items():
            success = self.send_data(ip, data)
            status = "✓" if success else "✗"
            print(f"{status} Sent to {device_info['name']} ({ip})")

    def start_all_services(self):
        """Start all services (server, advertiser, scanner)"""
        self.running = True
        
        # Start TCP server
        server_thread = threading.Thread(target=self.start_server, daemon=True)
        server_thread.start()
        
        # Start UDP advertiser (BLE-like advertising)
        advertiser_thread = threading.Thread(target=self.start_broadcast_advertiser, daemon=True)
        advertiser_thread.start()
        
        # Start UDP scanner (BLE-like scanning)
        scanner_thread = threading.Thread(target=self.start_broadcast_scanner, daemon=True)
        scanner_thread.start()
        
        time.sleep(1)  # Give services time to start
        print("All services started!")
        
        return server_thread, advertiser_thread, scanner_thread
    
    def stop(self):
        """Stop the server"""
        self.running = False
        if self.server_socket:
            self.server_socket.close()
        if self.broadcast_socket:
            self.broadcast_socket.close()

def main():
    device = LocalNetworkDevice()
    
    # Start all services
    device.start_all_services()
    
    while True:
        print("\n=== Local Network Device Discovery ===")
        print("1. Discover devices (comprehensive scan)")
        print("2. List discovered devices")
        print("3. Send data to specific device")
        print("4. Broadcast data to all devices")
        print("5. Show network info")
        print("6. Exit")
        
        choice = input("\nEnter your choice (1-6): ").strip()
        
        if choice == '1':
            devices = device.discover_devices()
            print(f"\nFound {len(devices)} devices:")
            for ip, info in devices.items():
                status = "📱 App running" if info.get('port') else "💻 Device found"
                print(f"  - {info['name']} ({ip}) - {status}")
        
        elif choice == '2':
            if device.devices:
                print("\nAll discovered devices:")
                for ip, info in device.devices.items():
                    status = "📱 App running" if info.get('port') else "💻 Device found"
                    age = int(time.time() - info['last_seen'])
                    print(f"  - {info['name']} ({ip}) - {status} - {age}s ago")
            else:
                print("No devices discovered yet.")
        
        elif choice == '3':
            app_devices = {ip: info for ip, info in device.devices.items() if info.get('port')}
            if not app_devices:
                print("No devices running our application. Discover devices first.")
                continue
                
            print("Devices running our application:")
            ips = list(app_devices.keys())
            for i, (ip, info) in enumerate(app_devices.items()):
                print(f"  {i+1}. {info['name']} ({ip})")
            
            try:
                idx = int(input("Select device (number): ")) - 1
                if 0 <= idx < len(ips):
                    target_ip = ips[idx]
                    data = input("Enter data to send: ")
                    success = device.send_data(target_ip, data)
                    print("Data sent successfully!" if success else "Failed to send data.")
                else:
                    print("Invalid selection.")
            except ValueError:
                print("Invalid input.")
        
        elif choice == '4':
            data = input("Enter data to broadcast: ")
            device.broadcast_data(data)
        
        elif choice == '5':
            print(f"\nNetwork Information:")
            print(f"Local IP: {device.get_local_ip()}")
            print(f"Broadcast Address: {device.get_broadcast_address()}")
            print(f"TCP Port: {device.port}")
            print(f"UDP Broadcast Port: {device.broadcast_port}")
            print(f"Device Name: {device.device_name}")
            print(f"Device ID: {device.device_id}")
        
        elif choice == '6':
            print("Stopping...")
            device.stop()
            break
        
        else:
            print("Invalid choice.")

if __name__ == "__main__":
    main()
