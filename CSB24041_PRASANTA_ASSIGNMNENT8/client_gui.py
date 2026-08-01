import socket
import threading
import time
import json
import os
import logging
import tkinter as tk
from tkinter import messagebox
from tkinter.scrolledtext import ScrolledText

# ---------------------------------
# Task 4: Configuration Management
# ---------------------------------
CONFIG_PATH = "config.json"

DEFAULT_CLIENT_CONFIG = {
    "default_server_ip": "10.0.0.1",
    "server_port": 5000,
    "connect_timeout_seconds": 5,
    "reconnect_attempts": 5,
    "reconnect_delay_seconds": 3,
    "reconnect_backoff_multiplier": 1.5
}


def load_client_config():
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r") as f:
                cfg = json.load(f)
            return {**DEFAULT_CLIENT_CONFIG, **cfg.get("client", {})}
        except (json.JSONDecodeError, OSError):
            pass
    return DEFAULT_CLIENT_CONFIG


cfg = load_client_config()
SERVER_PORT = cfg["server_port"]
CONNECT_TIMEOUT = cfg["connect_timeout_seconds"]
RECONNECT_ATTEMPTS = cfg["reconnect_attempts"]
RECONNECT_DELAY = cfg["reconnect_delay_seconds"]
RECONNECT_BACKOFF = cfg["reconnect_backoff_multiplier"]

# ---------------------------------
# Task 2: Reliability - logging instead of silent excepts
# ---------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler("client.log"), logging.StreamHandler()]
)
log = logging.getLogger("chat_client")

# ---------------------------------
# Global State
# ---------------------------------
client = None
username = ""
password_cache = ""
server_ip_cache = ""
connected = False          # user is logged in and chat window is open
manual_disconnect = False  # True only when the user clicked Disconnect
reconnecting = False

# ---------------------------------
# Login Window
# ---------------------------------
login_window = tk.Tk()
login_window.title("Secure TCP Chat Application")
login_window.geometry("400x330")
login_window.resizable(False, False)

title = tk.Label(login_window, text="Secure TCP Chat Application", font=("Arial", 16, "bold"))
title.pack(pady=15)

username_label = tk.Label(login_window, text="Username", font=("Arial", 11))
username_label.pack()
username_entry = tk.Entry(login_window, width=30, font=("Arial", 11))
username_entry.pack(pady=5)

password_label = tk.Label(login_window, text="Password", font=("Arial", 11))
password_label.pack()
password_entry = tk.Entry(login_window, width=30, font=("Arial", 11), show="*")
password_entry.pack(pady=5)

ip_label = tk.Label(login_window, text="Server IP Address", font=("Arial", 11))
ip_label.pack()
ip_entry = tk.Entry(login_window, width=30, font=("Arial", 11))
ip_entry.insert(0, cfg["default_server_ip"])
ip_entry.pack(pady=5)

status_label = tk.Label(login_window, text="Status : Disconnected", fg="red", font=("Arial", 10, "bold"))
status_label.pack(pady=10)


def set_status(text, color):
    # Thread-safe UI update
    login_window.after(0, lambda: status_label.config(text=text, fg=color))


# ---------------------------------
# Chat Window
# ---------------------------------
def open_chat_window():
    global chat_window, chat_area, message_entry, users_listbox, connection_banner

    login_window.withdraw()

    chat_window = tk.Toplevel()
    chat_window.title(f"TCP Chat - {username}")
    chat_window.geometry("900x600")
    chat_window.protocol("WM_DELETE_WINDOW", on_closing)

    connection_banner = tk.Label(chat_window, text="", font=("Arial", 10, "bold"), bg="#2e7d32", fg="white")
    connection_banner.pack(fill=tk.X)
    connection_banner.pack_forget()  # hidden unless we're reconnecting

    left_frame = tk.Frame(chat_window, width=180)
    left_frame.pack(side=tk.LEFT, fill=tk.Y)

    tk.Label(left_frame, text="Online Users", font=("Arial", 12, "bold")).pack(pady=5)
    users_listbox = tk.Listbox(left_frame, width=22, height=25)
    users_listbox.pack(padx=5, pady=5, fill=tk.BOTH, expand=True)

    right_frame = tk.Frame(chat_window)
    right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

    chat_area = ScrolledText(right_frame, wrap=tk.WORD, state="disabled", font=("Arial", 11))
    chat_area.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

    bottom_frame = tk.Frame(right_frame)
    bottom_frame.pack(fill=tk.X, padx=10, pady=10)

    message_entry = tk.Entry(bottom_frame, font=("Arial", 11))
    message_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))

    send_button = tk.Button(bottom_frame, text="Send", bg="green", fg="white", width=10, command=send_message)
    send_button.pack(side=tk.LEFT)

    disconnect_button = tk.Button(bottom_frame, text="Disconnect", bg="red", fg="white", width=12, command=disconnect)
    disconnect_button.pack(side=tk.LEFT, padx=10)

    message_entry.bind("<Return>", lambda event: send_message())

    threading.Thread(target=receive_messages, daemon=True).start()


def append_system_message(text):
    def _do():
        chat_area.config(state="normal")
        chat_area.insert(tk.END, f"*** {text} ***\n")
        chat_area.config(state="disabled")
        chat_area.see(tk.END)
    try:
        chat_window.after(0, _do)
    except (NameError, tk.TclError):
        pass


def show_reconnect_banner(text):
    def _do():
        connection_banner.config(text=text, bg="#c62828")
        connection_banner.pack(fill=tk.X)
    try:
        chat_window.after(0, _do)
    except (NameError, tk.TclError):
        pass


def hide_reconnect_banner():
    def _do():
        connection_banner.pack_forget()
    try:
        chat_window.after(0, _do)
    except (NameError, tk.TclError):
        pass


# ---------------------------------
# Connect / Authenticate
# ---------------------------------
def do_login(sock, uname, pwd):
    """Perform the LOGIN handshake on an already-open socket. Returns server response string."""
    server_message = sock.recv(1024).decode()
    if server_message != "LOGIN":
        return "INVALID"
    sock.send(f"{uname}:{pwd}".encode())
    return sock.recv(1024).decode()


def connect():
    global client, username, password_cache, server_ip_cache, connected, manual_disconnect

    uname = username_entry.get().strip()
    pwd = password_entry.get().strip()
    server_ip = ip_entry.get().strip()

    if uname == "" or pwd == "":
        messagebox.showerror("Error", "Username and Password cannot be empty.")
        return

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(CONNECT_TIMEOUT)
        sock.connect((server_ip, SERVER_PORT))

        response = do_login(sock, uname, pwd)

        if response == "LOGIN_SUCCESS":
            sock.settimeout(None)  # blocking mode for normal chat operation
            client = sock
            username, password_cache, server_ip_cache = uname, pwd, server_ip
            connected = True
            manual_disconnect = False
            set_status("Status : Connected", "green")
            open_chat_window()
            return

        error_messages = {
            "LOGIN_FAILED": ("Login Failed", "Invalid Username or Password."),
            "ALREADY_LOGGED_IN": ("Login Failed", "User already logged in."),
            "BLOCKED": ("Blocked", "Too many failed login attempts.\nTry again after 60 seconds."),
            "INVALID": ("Error", "Invalid Login Request."),
        }
        title_msg, body_msg = error_messages.get(response, ("Error", f"Unexpected server response: {response}"))
        messagebox.showerror(title_msg, body_msg)
        sock.close()

    except socket.timeout:
        messagebox.showerror("Connection Error", "Connection timed out. Check the server IP/port and try again.")
    except (ConnectionRefusedError, OSError) as e:
        messagebox.showerror("Connection Error", f"Could not reach server: {e}")
    except Exception as e:
        log.error(f"Unexpected connect() error: {e}")
        messagebox.showerror("Connection Error", str(e))


# ---------------------------------
# Task 2: Automatic Reconnection
# ---------------------------------
def attempt_reconnect():
    """Runs in a background thread after an unexpected disconnect."""
    global client, connected, reconnecting

    if manual_disconnect or reconnecting:
        return
    reconnecting = True

    delay = RECONNECT_DELAY
    for attempt in range(1, RECONNECT_ATTEMPTS + 1):
        if manual_disconnect:
            break

        show_reconnect_banner(f"Connection lost. Reconnecting... (attempt {attempt}/{RECONNECT_ATTEMPTS})")
        log.warning(f"Reconnect attempt {attempt}/{RECONNECT_ATTEMPTS}")
        time.sleep(delay)

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(CONNECT_TIMEOUT)
            sock.connect((server_ip_cache, SERVER_PORT))
            response = do_login(sock, username, password_cache)

            if response == "LOGIN_SUCCESS":
                sock.settimeout(None)
                client = sock
                connected = True
                reconnecting = False
                hide_reconnect_banner()
                append_system_message("Reconnected to server")
                log.info("Reconnected successfully.")
                threading.Thread(target=receive_messages, daemon=True).start()
                return
            else:
                sock.close()
                log.warning(f"Reconnect rejected by server: {response}")

        except (socket.timeout, OSError) as e:
            log.warning(f"Reconnect attempt failed: {e}")

        delay *= RECONNECT_BACKOFF

    reconnecting = False
    if not manual_disconnect:
        show_reconnect_banner("Reconnection failed. Please reconnect manually.")
        append_system_message("Could not reconnect to server after several attempts")
        connected = False
        login_window.after(0, lambda: messagebox.showerror(
            "Disconnected", "Lost connection to the server and could not reconnect automatically."
        ))


# ---------------------------------
# Send Message
# ---------------------------------
def send_message():
    if not connected or client is None:
        messagebox.showwarning("Not Connected", "You are not currently connected to the server.")
        return

    message = message_entry.get().strip()
    if message == "":
        return

    try:
        client.send(message.encode())
        message_entry.delete(0, tk.END)
    except OSError as e:
        log.error(f"Send failed: {e}")
        messagebox.showerror("Error", "Failed to send message. Attempting to reconnect...")
        threading.Thread(target=attempt_reconnect, daemon=True).start()


# ---------------------------------
# Disconnect (manual, user-initiated)
# ---------------------------------
def disconnect():
    global connected, manual_disconnect

    manual_disconnect = True
    connected = False

    try:
        if client:
            client.close()
    except OSError:
        pass

    try:
        chat_window.destroy()
    except (NameError, tk.TclError):
        pass

    login_window.deiconify()
    set_status("Status : Disconnected", "red")


# ---------------------------------
# Receive Messages
# ---------------------------------
def receive_messages():
    global connected

    while connected:
        try:
            data = client.recv(1024)
            if not data:
                raise ConnectionResetError("Server closed the connection")

            message = data.decode(errors="ignore")

            # Heartbeat - reply silently, never display
            if message.strip() == "PING":
                try:
                    client.send(b"PONG")
                except OSError:
                    pass
                continue

            if message.startswith("USERLIST:"):
                users = message.replace("USERLIST:", "").split(",")

                def _update_list():
                    users_listbox.delete(0, tk.END)
                    for user in users:
                        if user.strip():
                            users_listbox.insert(tk.END, user)
                chat_window.after(0, _update_list)
                continue

            def _show(msg=message):
                chat_area.config(state="normal")
                chat_area.insert(tk.END, msg + "\n")
                chat_area.config(state="disabled")
                chat_area.see(tk.END)
            chat_window.after(0, _show)

        except (ConnectionResetError, ConnectionAbortedError, OSError) as e:
            log.warning(f"Connection lost: {e}")
            connected = False
            if not manual_disconnect:
                threading.Thread(target=attempt_reconnect, daemon=True).start()
            break
        except Exception as e:
            log.error(f"Unexpected error in receive loop: {e}")
            connected = False
            break


# ---------------------------------
# Graceful Window Close
# ---------------------------------
def on_closing():
    global connected, manual_disconnect
    manual_disconnect = True
    connected = False
    try:
        if client:
            client.close()
    except OSError:
        pass
    try:
        chat_window.destroy()
    except (NameError, tk.TclError):
        pass
    login_window.destroy()


connect_button = tk.Button(login_window, text="Connect", width=20, bg="green", fg="white", command=connect)
connect_button.pack(pady=10)

login_window.mainloop()
