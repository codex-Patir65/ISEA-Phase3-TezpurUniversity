import socket
import threading
import tkinter as tk
from tkinter import messagebox
from tkinter.scrolledtext import ScrolledText

# ---------------------------------
# Global Variables
# ---------------------------------
client = None
username = ""
connected = False

# ---------------------------------
# Login Window
# ---------------------------------
login_window = tk.Tk()
login_window.title("TCP Chat Application")
login_window.geometry("400x320")
login_window.resizable(False, False)

title = tk.Label(
    login_window,
    text="TCP Chat Application",
    font=("Arial", 16, "bold")
)
title.pack(pady=15)

# Username
username_label = tk.Label(
    login_window,
    text="Username"
)
username_label.pack()

username_entry = tk.Entry(
    login_window,
    width=30
)
username_entry.pack(pady=5)

# Password (Optional)
password_label = tk.Label(
    login_window,
    text="Password (Optional)"
)
password_label.pack()

password_entry = tk.Entry(
    login_window,
    width=30,
    show="*"
)
password_entry.pack(pady=5)

# Server IP
ip_label = tk.Label(
    login_window,
    text="Server IP Address"
)
ip_label.pack()

ip_entry = tk.Entry(
    login_window,
    width=30
)

ip_entry.insert(0, "10.0.0.1")
ip_entry.pack(pady=5)

status_label = tk.Label(
    login_window,
    text="Status : Not Connected",
    fg="red"
)

status_label.pack(pady=10)

# ---------------------------------
# Open Chat Window
# ---------------------------------
def open_chat_window():

    global chat_window
    global chat_area
    global message_entry
    global users_listbox

    login_window.withdraw()

    chat_window = tk.Toplevel()
    chat_window.title(f"TCP Chat - {username}")
    chat_window.geometry("900x600")

    # Close event
    chat_window.protocol(
        "WM_DELETE_WINDOW",
        on_closing
    )

    # -----------------------------
    # Left Frame (Online Users)
    # -----------------------------
    left_frame = tk.Frame(chat_window, width=180)
    left_frame.pack(
        side=tk.LEFT,
        fill=tk.Y
    )

    tk.Label(
        left_frame,
        text="Online Users",
        font=("Arial", 12, "bold")
    ).pack(pady=5)

    users_listbox = tk.Listbox(
        left_frame,
        width=22,
        height=25
    )

    users_listbox.pack(
        padx=5,
        pady=5,
        fill=tk.BOTH,
        expand=True
    )

    # -----------------------------
    # Right Frame
    # -----------------------------
    right_frame = tk.Frame(chat_window)

    right_frame.pack(
        side=tk.RIGHT,
        fill=tk.BOTH,
        expand=True
    )

    # Chat Area
    chat_area = ScrolledText(
        right_frame,
        wrap=tk.WORD,
        state="disabled",
        font=("Arial", 11)
    )

    chat_area.pack(
        padx=10,
        pady=10,
        fill=tk.BOTH,
        expand=True
    )

    # -----------------------------
    # Bottom Frame
    # -----------------------------
    bottom_frame = tk.Frame(right_frame)

    bottom_frame.pack(
        fill=tk.X,
        padx=10,
        pady=10
    )

    # Message Box
    message_entry = tk.Entry(
        bottom_frame,
        font=("Arial", 11)
    )

    message_entry.pack(
        side=tk.LEFT,
        fill=tk.X,
        expand=True,
        padx=(0, 10)
    )

    # Send Button
    send_button = tk.Button(
        bottom_frame,
        text="Send",
        bg="green",
        fg="white",
        width=10,
        command=send_message
    )

    send_button.pack(
        side=tk.LEFT
    )

    # Disconnect Button
    disconnect_button = tk.Button(
        bottom_frame,
        text="Disconnect",
        bg="red",
        fg="white",
        width=12,
        command=disconnect
    )

    disconnect_button.pack(
        side=tk.LEFT,
        padx=10
    )

    # Press Enter to Send
    message_entry.bind(
        "<Return>",
        lambda event: send_message()
    )

    # Start Receiving Messages
    receive_thread = threading.Thread(
        target=receive_messages,
        daemon=True
    )

    receive_thread.start()

# ---------------------------------
# Connect to Server
# ---------------------------------
def connect():

    global client
    global username
    global connected

    username = username_entry.get().strip()
    server_ip = ip_entry.get().strip()

    if username == "":
        messagebox.showerror(
            "Error",
            "Username cannot be empty."
        )
        return

    try:

        client = socket.socket(
            socket.AF_INET,
            socket.SOCK_STREAM
        )

        client.connect((server_ip,5000))

        server_message = client.recv(1024).decode()

        if server_message == "NAME":
            client.send(username.encode())

        connected = True

        status_label.config(
            text="Status : Connected",
            fg="green"
        )

        open_chat_window()

    except Exception as e:

        messagebox.showerror(
            "Connection Error",
            str(e)
        )
# ---------------------------------
# Connect to Server
# ---------------------------------
def connect():

    global client
    global username
    global connected

    username = username_entry.get().strip()
    server_ip = ip_entry.get().strip()

    if username == "":
        messagebox.showerror(
            "Error",
            "Username cannot be empty."
        )
        return

    try:

        client = socket.socket(
            socket.AF_INET,
            socket.SOCK_STREAM
        )

        client.connect((server_ip,5000))

        server_message = client.recv(1024).decode()

        if server_message == "NAME":
            client.send(username.encode())

        connected = True

        status_label.config(
            text="Status : Connected",
            fg="green"
        )

        open_chat_window()

    except Exception as e:

        messagebox.showerror(
            "Connection Error",
            str(e)
        )
connect_button = tk.Button(
    login_window,
    text="Connect",
    width=20,
    bg="green",
    fg="white",
    command=connect
)

connect_button.pack(pady=10)


# ---------------------------------
# Send Message
# ---------------------------------
def send_message():

    if not connected:
        return

    message = message_entry.get().strip()

    if message == "":
        return

    try:

        client.send(message.encode())

        message_entry.delete(0, tk.END)

    except:

        messagebox.showerror(
            "Error",
            "Failed to send message."
        )


# ---------------------------------
# Disconnect
# ---------------------------------
def disconnect():

    global connected

    connected = False

    try:
        client.close()
    except:
        pass

    chat_window.destroy()

    login_window.deiconify()

    status_label.config(
        text="Status : Not Connected",
        fg="red"
    )


# ---------------------------------
# Receive Messages
# ---------------------------------
def receive_messages():

    while connected:

        try:

            message = client.recv(1024).decode()

            if not message:
                break

            # -----------------------
            # Online User List
            # -----------------------
            if message.startswith("USERLIST:"):

                users = message.replace(
                    "USERLIST:",
                    ""
                ).split(",")

                users_listbox.delete(0, tk.END)

                for user in users:

                    if user.strip() != "":

                        users_listbox.insert(
                            tk.END,
                            user
                        )

                continue

            # -----------------------
            # Display Chat Message
            # -----------------------
            chat_area.config(state="normal")

            chat_area.insert(
                tk.END,
                message + "\n"
            )

            chat_area.config(state="disabled")

            chat_area.see(tk.END)

        except:

            break
# ---------------------------------
# Handle Window Close
# ---------------------------------
def on_closing():

    global connected

    connected = False

    try:
        if client:
            client.close()
    except:
        pass

    try:
        chat_window.destroy()
    except:
        pass

    login_window.destroy()


# ---------------------------------
# Attach Close Event
# ---------------------------------
def setup_chat_window():

    chat_window.protocol(
        "WM_DELETE_WINDOW",
        on_closing
    )


# ---------------------------------
# Modify open_chat_window()
# ---------------------------------
# Add this line as the LAST line
# inside open_chat_window():
#
#     setup_chat_window()
#
# It should look like:
#
# receive_thread.start()
# setup_chat_window()
#
# ---------------------------------


# ---------------------------------
# Start GUI
# ---------------------------------
login_window.mainloop()
