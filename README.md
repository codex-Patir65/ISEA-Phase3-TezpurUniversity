# GUI-Based Multi-Client Chat Application Using TCP

**Assignment 6 — ISEA Phase 3 Networking Internship, Tezpur University**

**Author:** Prasanta Patir (CSB24041)

---

## Objective

Convert the terminal-based TCP chat application from Assignment 5 into a graphical desktop application while reusing the existing multithreaded TCP server without modification to its core networking logic. This project introduces GUI programming with Tkinter, event-driven programming, multithreading for non-blocking network I/O, and a more user-friendly interface for the multi-client chat system built earlier.

## Features

- GUI login window with username, optional password, and server IP fields
- Graphical chat window with a scrollable, auto-scrolling message area
- Online users panel (Listbox) showing currently connected clients
- Broadcast messaging to all connected clients
- Private messaging via `/msg <username> <message>`
- Join/leave notifications broadcast to all clients
- Background thread for receiving messages, keeping the GUI responsive at all times
- Server-side chat history and performance logging to CSV (`chat_history.csv`, `performance_results.csv`)

## Software Requirements

| Requirement | Details |
|---|---|
| OS | Ubuntu (tested inside a Mininet VM) |
| Python | 3.x |
| Python modules | `socket`, `threading`, `csv`, `os`, `time`, `datetime`, `tkinter`, `tkinter.ttk`, `tkinter.scrolledtext`, `tkinter.messagebox` (all standard library — no `pip install` required) |
| Network emulation | Mininet with Open vSwitch |
| Packet capture | Wireshark (for protocol verification) |

## Network Topology

The application is designed to run on a Mininet single-switch topology with one server and four clients:

```bash
sudo mn --topo single,5
```

| Host | Role |
|---|---|
| h1 | Chat Server (`server.py`) |
| h2 | Client A (`client_gui.py`) |
| h3 | Client B (`client_gui.py`) |
| h4 | Client C (`client_gui.py`) |
| h5 | Client D (`client_gui.py`) |

Connectivity is verified inside the Mininet CLI before starting the application:

```
mininet> nodes
mininet> net
mininet> pingall
```

![Network topology setup]
<img width="1224" height="764" alt="network_setup" src="https://github.com/user-attachments/assets/5b5858f2-b390-4616-bd76-1aea670e7fbc" />

## Execution Steps

1. **Clone the repository** onto the machine running Mininet.
2. **Start Mininet** with the required topology:
   ```bash
   sudo mn --topo single,5
   ```
3. **Start the server** on `h1`:
   ```bash
   mininet> h1 python3 server.py
   ```
   The server listens on port `5000` and prints connection logs to the terminal.
4. **Start each GUI client** on `h2`–`h5` (each opens its own Tkinter window):
   ```bash
   mininet> h2 python3 client_gui.py
   mininet> h3 python3 client_gui.py
   mininet> h4 python3 client_gui.py
   mininet> h5 python3 client_gui.py
   ```
5. **Log in** on each client: enter a username, the server's IP address (`h1`'s IP, e.g. `10.0.0.1`), and click **Connect**.
6. **Chat**: type a plain message and press **Send** (or Enter) to broadcast, or use `/msg <username> <message>` to send a private message. The Online Users panel lists everyone currently connected.
7. **Disconnect** using the **Disconnect** button, or close the chat window.
8. **(Optional) Capture traffic** with Wireshark on the switch interface (e.g. `s1-eth1`) using the filter:
   ```
   tcp.port == 5000
   ```

## Sample Screenshots

| Login Window | Successful Connection |
|---|---|
| ![Login window]
<img width="566" height="451" alt="login_window" src="https://github.com/user-attachments/assets/840647fe-3b11-4987-8c63-92866b7f28d5" />

| ![Two clients connected]
<img width="901" height="602" alt="two_clients_connected" src="https://github.com/user-attachments/assets/5f54899c-cefb-47b5-a639-fef97aea1e28" />

| Broadcast Messaging | Private Messaging |
|---|---|
| ![Broadcast chat]
<img width="1214" height="659" alt="GUI_broadcast_chat" src="https://github.com/user-attachments/assets/cf6040bc-26a1-4673-acd4-31b0dd8f518f" />

| ![Private message]
<img width="1031" height="596" alt="GUI_private_message" src="https://github.com/user-attachments/assets/64cbda8d-aaad-4154-9364-0d19d3957296" />


| User Disconnecting |
|---|
| ![User disconnected]

<img width="804" height="620" alt="GUI_user_disconnected" src="https://github.com/user-attachments/assets/385e7e7d-c8d0-4e37-b3b4-c60b5a7c9c4f" />

Wireshark packet captures (`tcp.port == 5000`) for client connection, broadcast messaging, private messaging, and client disconnection are included under `screenshots/` and explained in `report.pdf`.

## Implementation Overview

- **`server.py`** — Reused from Assignment 5 without modification to its networking logic. Accepts TCP connections on port `5000`, performs a `"NAME"` handshake to register each client's username, and spawns one daemon thread per client (`handle()`) to process incoming messages. Shared state (`clients`, `client_info`) is protected with a `threading.Lock`. Supports broadcast (`broadcast()`), private messaging (`private_message()`, triggered by `/msg`), the `/list` command, and logs every message to `chat_history.csv` along with delay/throughput metrics in `performance_results.csv`.
- **`client_gui.py`** — Replaces the terminal client (`client.py`) with a Tkinter GUI while reusing the same socket protocol. The main thread owns the Tkinter event loop and login/chat window widgets; a background daemon thread (`receive_messages()`) handles the blocking `client.recv()` call so the GUI never freezes while waiting for incoming data. Sending a message (via the Send button or Enter key) simply calls `client.send()` on the main thread, since that call does not block.
- **`client.py`** — The original Assignment 5 terminal client, kept in the repository for reference/comparison.

For full design rationale, testing results, Wireshark analysis, and reflection answers, see `report.pdf`.

## Repository Structure

```
.
├── server.py
├── client.py
├── client_gui.py
├── report.pdf
├── screenshots/
│   ├── login_window.png
│   ├── two_clients_connected.png
│   ├── GUI_broadcast_chat.png
│   ├── GUI_private_message.png
│   ├── GUI_user_disconnected.png
│   ├── GUI_client1_connected.png
│   ├── network_setup.png
│   ├── Client1_connection.png
│   ├── broadcast_mssg.png
│   ├── private_msg.png
│   └── Client_disconnection.png
└── README.md
```
