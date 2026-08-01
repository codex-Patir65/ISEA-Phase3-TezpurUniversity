import socket
import threading
import csv
import os
import json
import time
import signal
import sys
import logging
from datetime import datetime
import hashlib
from concurrent.futures import ThreadPoolExecutor

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

# -------------------------------
# Task 4: Configuration Management
# -------------------------------
CONFIG_PATH = "config.json"

DEFAULT_CONFIG = {
    "server": {
        "host": "0.0.0.0",
        "port": 5000,
        "listen_backlog": 50,
        "recv_buffer_size": 1024,
        "thread_pool_size": 50,
        "heartbeat_timeout_seconds": 15,
        "max_missed_heartbeats": 3,
        "max_failed_login_attempts": 5,
        "login_block_seconds": 60
    },
    "client": {
        "default_server_ip": "10.0.0.1",
        "server_port": 5000,
        "connect_timeout_seconds": 5,
        "reconnect_attempts": 5,
        "reconnect_delay_seconds": 3,
        "reconnect_backoff_multiplier": 1.5
    },
    "files": {
        "chat_history": "chat_history.csv",
        "performance_results": "performance_results.csv",
        "security_log": "security_log.txt",
        "server_log": "server.log",
        "users_file": "users.csv"
    }
}


def load_config(path=CONFIG_PATH):
    if not os.path.exists(path):
        with open(path, "w") as f:
            json.dump(DEFAULT_CONFIG, f, indent=4)
        return DEFAULT_CONFIG
    try:
        with open(path, "r") as f:
            user_cfg = json.load(f)
        merged = {}
        for section, values in DEFAULT_CONFIG.items():
            merged[section] = {**values, **user_cfg.get(section, {})}
        return merged
    except (json.JSONDecodeError, OSError):
        # Fall back to defaults if config.json is corrupt/unreadable
        return DEFAULT_CONFIG


config = load_config()

HOST = config["server"]["host"]
PORT = config["server"]["port"]
BACKLOG = config["server"]["listen_backlog"]
BUFFER_SIZE = config["server"]["recv_buffer_size"]
THREAD_POOL_SIZE = config["server"]["thread_pool_size"]
HEARTBEAT_TIMEOUT = config["server"]["heartbeat_timeout_seconds"]
MAX_MISSED_HEARTBEATS = config["server"]["max_missed_heartbeats"]
MAX_FAILED_ATTEMPTS = config["server"]["max_failed_login_attempts"]
BLOCK_TIME = config["server"]["login_block_seconds"]

CHAT_HISTORY_FILE = config["files"]["chat_history"]
PERFORMANCE_FILE = config["files"]["performance_results"]
SECURITY_LOG_FILE = config["files"]["security_log"]
SERVER_LOG_FILE = config["files"]["server_log"]
USERS_FILE = config["files"]["users_file"]

# -------------------------------
# Task 2: Reliability - structured logging instead of bare print()
# -------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(SERVER_LOG_FILE),
        logging.StreamHandler(sys.stdout)
    ]
)
log = logging.getLogger("chat_server")

# -------------------------------
# Global Variables
# -------------------------------
clients = {}          # {socket: username}
client_info = {}      # {socket: {ip, port, login, status}}
lock = threading.Lock()

broadcast_count = 0
private_count = 0
start_time = time.time()
shutting_down = False

logged_in_users = set()
failed_attempts = {}

# -------------------------------
# Task 3: Scalability - bounded thread pool instead of unbounded threads
# -------------------------------
executor = ThreadPoolExecutor(max_workers=THREAD_POOL_SIZE, thread_name_prefix="client")

# -------------------------------
# Setup CSV files
# -------------------------------
def ensure_csv(path, header):
    if not os.path.exists(path):
        with open(path, "w", newline="") as file:
            csv.writer(file).writerow(header)


ensure_csv(CHAT_HISTORY_FILE, ["Timestamp", "Sender", "Receiver", "Message Type", "Message"])
ensure_csv(
    PERFORMANCE_FILE,
    ["timestamp", "clients", "broadcast_messages", "private_messages",
     "avg_delay_ms", "throughput_msgs_per_sec", "cpu_percent", "memory_mb"]
)

process = psutil.Process(os.getpid()) if PSUTIL_AVAILABLE else None
if PSUTIL_AVAILABLE:
    process.cpu_percent(interval=None)  # prime the CPU counter


def save_chat(sender, receiver, msg_type, message):
    try:
        with open(CHAT_HISTORY_FILE, "a", newline="") as file:
            csv.writer(file).writerow([
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                sender, receiver, msg_type, message
            ])
    except OSError as e:
        log.error(f"Could not write chat history: {e}")


def save_performance(delay_ms):
    elapsed = time.time() - start_time
    total_messages = broadcast_count + private_count
    throughput = total_messages / elapsed if elapsed > 0 else 0
    connected_clients = len(clients)

    cpu_percent = process.cpu_percent(interval=None) if PSUTIL_AVAILABLE else 0
    memory_mb = process.memory_info().rss / (1024 * 1024) if PSUTIL_AVAILABLE else 0

    try:
        with open(PERFORMANCE_FILE, "a", newline="") as file:
            csv.writer(file).writerow([
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                connected_clients, broadcast_count, private_count,
                round(delay_ms, 3), round(throughput, 2),
                round(cpu_percent, 2), round(memory_mb, 2)
            ])
    except OSError as e:
        log.error(f"Could not write performance results: {e}")

    log.info(
        f"clients={connected_clients} broadcast={broadcast_count} "
        f"private={private_count} delay={delay_ms:.3f}ms "
        f"throughput={throughput:.2f}msg/s cpu={cpu_percent:.1f}% mem={memory_mb:.1f}MB"
    )


def load_users():
    users = {}
    if not os.path.exists(USERS_FILE):
        return users
    try:
        with open(USERS_FILE, "r") as file:
            for row in csv.DictReader(file):
                users[row["username"]] = row["password"]
    except OSError as e:
        log.error(f"Could not read users file: {e}")
    return users


def verify_user(username, password):
    users = load_users()
    if username not in users:
        return False
    hashed = hashlib.sha256(password.encode()).hexdigest()
    return users[username] == hashed


def security_log(message):
    try:
        with open(SECURITY_LOG_FILE, "a") as file:
            file.write(f"{datetime.now()} : {message}\n")
    except OSError as e:
        log.error(f"Could not write security log: {e}")


# -------------------------------
# Safe send: never let one dead socket blow up the caller
# -------------------------------
def safe_send(client_socket, data: bytes) -> bool:
    try:
        client_socket.send(data)
        return True
    except (OSError, socket.error):
        return False


def broadcast(message, sender_socket=None):
    start = time.time()
    dead_clients = []

    with lock:
        targets = list(clients.keys())

    for client_socket in targets:
        if client_socket != sender_socket:
            if not safe_send(client_socket, message.encode()):
                dead_clients.append(client_socket)

    end = time.time()
    save_performance((end - start) * 1000)

    # Task 1: release resources for anything that failed mid-broadcast
    for dead in dead_clients:
        cleanup_client(dead, reason="send failure during broadcast")


def send_user_list(client_socket):
    with lock:
        users = ",".join(clients.values())
    safe_send(client_socket, f"USERLIST:{users}".encode())


def update_all_user_lists():
    with lock:
        users = ",".join(clients.values())
        targets = list(clients.keys())
    for client_socket in targets:
        safe_send(client_socket, f"USERLIST:{users}".encode())


def private_message(sender, receiver, text):
    global private_count

    with lock:
        target_socket = None
        for client_socket, uname in clients.items():
            if uname == receiver:
                target_socket = client_socket
                break

    if target_socket is None:
        return False

    if safe_send(target_socket, f"[PRIVATE] {sender}: {text}".encode()):
        private_count += 1
        save_chat(sender, receiver, "Private", text)
        return True
    return False


# -------------------------------
# Task 1 & 2: Connection Management + Reliability
# -------------------------------
def cleanup_client(client_socket, reason="disconnected"):
    """Release all resources tied to a client exactly once."""
    with lock:
        username = clients.pop(client_socket, None)
        client_info.pop(client_socket, None)
        if username and username in logged_in_users:
            logged_in_users.discard(username)

    if username:
        log.info(f"Client cleanup: {username} ({reason})")
        security_log(f"Logout: {username} ({reason})")
        broadcast(f"*** {username} left the chat ***")
        update_all_user_lists()

    try:
        client_socket.close()
    except OSError:
        pass


def handle(client_socket):
    global broadcast_count

    client_socket.settimeout(HEARTBEAT_TIMEOUT)
    missed_heartbeats = 0
    disconnect_reason = "connection closed"

    while not shutting_down:
        try:
            data = client_socket.recv(BUFFER_SIZE)
            if not data:
                disconnect_reason = "client closed connection"
                break

            message = data.decode(errors="ignore")
            missed_heartbeats = 0

            # Heartbeat reply - never displayed, never logged as chat
            if message.strip() == "PONG":
                continue

            with lock:
                sender = clients.get(client_socket)
            if sender is None:
                break

            if message.strip() == "/list":
                send_user_list(client_socket)
                continue

            if message.startswith("/msg "):
                parts = message.split(" ", 2)
                if len(parts) < 3:
                    safe_send(client_socket, "Usage: /msg <username> <message>".encode())
                    continue
                receiver, text = parts[1], parts[2]
                if not private_message(sender, receiver, text):
                    safe_send(client_socket, "User not found.".encode())
                continue

            broadcast_count += 1
            log.info(f"{sender}: {message}")
            save_chat(sender, "All", "Broadcast", message)
            broadcast(f"{sender}: {message}", client_socket)

        except socket.timeout:
            missed_heartbeats += 1
            if missed_heartbeats >= MAX_MISSED_HEARTBEATS:
                disconnect_reason = "heartbeat timeout (client unresponsive)"
                break
            if not safe_send(client_socket, b"PING"):
                disconnect_reason = "failed to send heartbeat"
                break

        except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError) as e:
            disconnect_reason = f"connection error: {e}"
            break

        except OSError as e:
            disconnect_reason = f"socket error: {e}"
            break

        except Exception as e:
            log.error(f"Unexpected error in client handler: {e}")
            disconnect_reason = f"unexpected error: {e}"
            break

    cleanup_client(client_socket, reason=disconnect_reason)


# -------------------------------
# Task 2: Graceful Shutdown
# -------------------------------
def graceful_shutdown(signum=None, frame=None):
    global shutting_down
    if shutting_down:
        return
    shutting_down = True

    log.info("Graceful shutdown initiated...")
    with lock:
        targets = list(clients.keys())

    for client_socket in targets:
        safe_send(client_socket, b"*** Server is shutting down. You will be disconnected. ***")
        try:
            client_socket.close()
        except OSError:
            pass

    executor.shutdown(wait=False, cancel_futures=True)

    try:
        server.close()
    except OSError:
        pass

    log.info("Server shut down cleanly.")
    sys.exit(0)


signal.signal(signal.SIGINT, graceful_shutdown)
signal.signal(signal.SIGTERM, graceful_shutdown)

# -------------------------------
# Main Server Setup
# -------------------------------
server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server.bind((HOST, PORT))
server.listen(BACKLOG)

log.info("====================================")
log.info(" Advanced Multi-Client Chat Server ")
log.info("====================================")
log.info(f"Listening on {HOST}:{PORT} (thread pool size={THREAD_POOL_SIZE})")

# -------------------------------
# Main Accept Loop
# -------------------------------
while True:
    try:
        client_socket, address = server.accept()
    except OSError:
        # Socket closed during graceful_shutdown
        break

    try:
        client_socket.settimeout(config["server"].get("connect_timeout_seconds", 10) or 10)
        client_socket.send("LOGIN".encode())
        credentials = client_socket.recv(BUFFER_SIZE).decode().strip()
        parts = credentials.split(":", 1)

        if len(parts) != 2:
            client_socket.send("INVALID".encode())
            client_socket.close()
            continue

        username, password = parts[0].strip(), parts[1].strip()

        if username == "" or password == "":
            client_socket.send("INVALID".encode())
            security_log(f"Empty username/password from {address[0]}")
            client_socket.close()
            continue

        if username in logged_in_users:
            client_socket.send("ALREADY_LOGGED_IN".encode())
            security_log(f"Duplicate login attempt: {username}")
            client_socket.close()
            continue

        if username in failed_attempts:
            count, block_until = failed_attempts[username]
            if time.time() < block_until:
                client_socket.send("BLOCKED".encode())
                client_socket.close()
                continue

        if not verify_user(username, password):
            if username not in failed_attempts:
                failed_attempts[username] = [1, 0]
            else:
                failed_attempts[username][0] += 1

            if failed_attempts[username][0] >= MAX_FAILED_ATTEMPTS:
                failed_attempts[username] = [0, time.time() + BLOCK_TIME]

            client_socket.send("LOGIN_FAILED".encode())
            security_log(f"Failed login: {username} ({address[0]})")
            client_socket.close()
            continue

        logged_in_users.add(username)
        failed_attempts.pop(username, None)
        client_socket.send("LOGIN_SUCCESS".encode())
        security_log(f"Successful login: {username}")

        login_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with lock:
            clients[client_socket] = username
            client_info[client_socket] = {
                "ip": address[0], "port": address[1],
                "login": login_time, "status": "Online"
            }

        log.info(f"New client: {username} from {address[0]}:{address[1]} at {login_time}")

        broadcast(f"*** {username} joined the chat ***")
        update_all_user_lists()

        executor.submit(handle, client_socket)

    except socket.timeout:
        log.warning(f"Login handshake timed out for {address}")
        client_socket.close()
    except Exception as e:
        log.error(f"Connection error during handshake: {e}")
        try:
            client_socket.close()
        except OSError:
            pass

log.info("Server main loop exited.")
