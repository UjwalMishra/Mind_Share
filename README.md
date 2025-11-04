# 🔗 Mind Share — Seamless LAN Communication (HackerWrath 2.0)

> A **cross-platform mesh-based local network communication suite** that lets devices on the same LAN share files, sync clipboards, send messages, and more — **without Internet**.

---

## 📘 Table of Contents

- [🚀 Overview](#-overview)
- [🕸 Architecture at a Glance](#-architecture-at-a-glance)
- [⚙️ Core Architecture](#️-core-architecture)
- [💡 Key Features](#-key-features)
- [🧠 How It Works](#-how-it-works)
- [🧰 Tech Stack](#-tech-stack)
- [🧪 Use Cases](#-use-cases)
- [⚡ Future Enhancements](#-future-enhancements)
- [🏁 Getting Started](#-getting-started)
- [🧩 Project Structure](#-project-structure)
- [⚙️ Setup & Installation](#️-setup--installation)
- [🧠 Network Overview Diagram](#-network-overview-diagram)
- [🛠 Developer Notes](#-developer-notes)
- [🤝 Team](#-team)
- [🪪 License](#-license)
- [📞 Contact](#-contact)

---

## 🚀 Overview

**Mind Share** (developed under *HackerWrath 2.0*) is a **real-time, mesh-based LAN communication system** enabling **local connectivity** between devices on the same network — all without external servers or internet access.

Each device acts as both **client and server**, allowing decentralized, high-speed peer-to-peer communication.  
The system demonstrates cross-platform interaction between **Python**, **React Native**, and **Tkinter** components.

---

## 🕸 Architecture at a Glance

### **Hybrid Mesh Design**
- Every device forms part of a self-healing mesh, enabling peer discovery and direct communication.
- Uses **UDP for discovery** and **TCP for reliable transfer**.
- No central coordination required — fully distributed.

### **Cross-Platform Compatibility**
- 💻 **Desktop:** Windows / Linux (Tkinter GUI)
- 📱 **Mobile:** Android (React Native)
- ⚙️ **Backend:** Python-based socket server managing message routing and data transfer

---

## ⚙️ Core Architecture

| Component | Description |
|------------|--------------|
| **Mesh Network** | Fully decentralized node structure; each device can send/receive data directly or relay messages. |
| **Protocols** | Combines UDP (broadcast discovery) and TCP (reliable transmission). |
| **Cross-Platform Bridge** | React Native mobile client communicates with Python-based node. |
| **GUI Layer** | Tkinter-powered desktop application for user-friendly control and monitoring. |
| **Notification Layer** | OS-level + in-app notifications for updates, messages, and file events. |

---

## 💡 Key Features

### 🔊 Smart Broadcast  
Broadcast messages or files to **multiple LAN-connected devices** simultaneously.

### 🗂️ File Sharing  
Instantly share any file type — `jpg`, `mp4`, `ppt`, `txt`, and more.  
Supports **drag-and-drop** on desktop for effortless sharing.

### 📋 Clipboard Sync  
Copy on one device, paste on another — clipboard sync in real time.

### 💬 Real-Time Messaging  
Chat directly between any two connected devices with minimal latency.

### 🖥️ Notifications  
Receive native alerts for:
- New messages  
- File transfers  
- Clipboard changes  
- Connection updates  

### 📡 One-to-Many Communication  
Support for **unicast**, **broadcast**, and **multicast**.

---

## 🧠 How It Works

1. **Device Discovery (UDP)**  
   - Devices periodically announce their presence via UDP broadcast.  
   - Other devices listen on a predefined port to detect peers.

2. **Handshake & Connection (TCP)**  
   - Once discovered, devices establish direct TCP connections for reliable data transmission.

3. **Mesh Routing**  
   - Each node maintains a routing table of connected peers.  
   - Messages and files can be relayed through intermediate nodes if required.

4. **Real-Time Sync**  
   - Clipboard data, messages, and files are serialized and exchanged instantly over the TCP layer.

---

## 🧰 Tech Stack

| Layer | Technology |
|:------|:------------|
| **Frontend (Desktop)** | Python + Tkinter |
| **Frontend (Mobile)** | React Native |
| **Networking Layer** | TCP, UDP, Custom Mesh Protocol |
| **Backend (Device Node)** | Python (Sockets + Threading) |
| **Notifications** | OS-level + Custom Popup Handler |

---

## 🧪 Use Cases

- Share files instantly during meetings without the internet  
- Use your phone’s clipboard or camera directly on your PC  
- Collaborate on LAN in colleges, offices, or hackathons  
- Transfer media between Android and Windows/Linux seamlessly  

---

## ⚡ Future Enhancements

- 🔐 End-to-end encryption for all communications  
- 📸 Use phone camera as a virtual webcam  
- 💡 Smart clipboard actions (auto-open copied URLs, text-to-action)  
- 🌈 UI overhaul using Electron or Flutter  

---

