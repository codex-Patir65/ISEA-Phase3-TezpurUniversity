import socket
import threading
import csv
import os
import time
from datetime import datetime

# -------------------------------
# Server Configuration
# -------------------------------
HOST = "0.0.0.0"
PORT = 5000

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.bind((HOST, PORT))
server.listen()

print("====================================")
print(" Advanced Multi-Client Chat Server ")
print("====================================")
print(f"Listening on port {PORT}...\n")

# -------------------------------
# Global Variables
# -------------------------------
clients = {}          # {socket: username}
client_info = {}      # {socket: {ip, port, login, status}}
lock = threading.Lock()

broadcast_count = 0
private_count = 0
start_time = time.time()

# -------------------------------
# Create chat_history.csv
# -------------------------------
if not os.path.exists("chat_history.csv"):
    with open("chat_history.csv", "w", newline="") as file:
        writer = csv.writer(file)
        writer.writerow([
            "Timestamp",
            "Sender",
            "Receiver",
            "Message Type",
            "Message"
        ])

# -------------------------------
# Create performance_results.csv
# -------------------------------
if not os.path.exists("performance_results.csv"):
    with open("performance_results.csv", "w", newline="") as file:
        writer = csv.writer(file)
        writer.writerow([
            "clients",
            "broadcast_messages",
            "private_messages",
            "avg_delay_ms",
            "throughput_msgs_per_sec"
        ])

# -------------------------------
# Save Chat History
# -------------------------------
def save_chat(sender, receiver, msg_type, message):

    with open("chat_history.csv", "a", newline="") as file:

        writer = csv.writer(file)

        writer.writerow([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            sender,
            receiver,
            msg_type,
            message
        ])


# -------------------------------
# Save Performance
# -------------------------------
def save_performance(delay):

    elapsed = time.time() - start_time

    total_messages = broadcast_count + private_count

    if elapsed > 0:
        throughput = total_messages / elapsed
    else:
        throughput = 0

    connected_clients = len(clients)

    with open("performance_results.csv", "a", newline="") as file:

        writer = csv.writer(file)

        writer.writerow([
            connected_clients,
            broadcast_count,
            private_count,
            round(delay, 3),
            round(throughput, 2)
        ])

    print("-------------------------------------")
    print(f"Clients     : {connected_clients}")
    print(f"Broadcast   : {broadcast_count}")
    print(f"Private     : {private_count}")
    print(f"Delay       : {delay:.3f} ms")
    print(f"Throughput  : {throughput:.2f} msg/sec")
    print("-------------------------------------")

# -------------------------------
# Broadcast Message
# -------------------------------
def broadcast(message, sender_socket=None):

    start = time.time()

    with lock:

        for client in list(clients.keys()):

            if client != sender_socket:

                try:
                    client.send(message.encode())

                except:

                    pass

    end = time.time()

    delay = (end - start) * 1000

    save_performance(delay)


# -------------------------------
# Send Online User List
# -------------------------------
def send_user_list(client):

    users = ",".join(clients.values())

    try:

        client.send(
            f"USERLIST:{users}".encode()
        )

    except:

        pass


# -------------------------------
# Update User List for All Clients
# -------------------------------
def update_all_user_lists():

    users = ",".join(clients.values())

    with lock:

        for client in list(clients.keys()):

            try:

                client.send(
                    f"USERLIST:{users}".encode()
                )

            except:

                pass


# -------------------------------
# Private Message
# -------------------------------
def private_message(sender, receiver, text):

    global private_count

    private_count += 1

    with lock:

        for client, username in clients.items():

            if username == receiver:

                try:

                    client.send(
                        f"[PRIVATE] {sender}: {text}".encode()
                    )

                    save_chat(
                        sender,
                        receiver,
                        "Private",
                        text
                    )

                    return True

                except:

                    return False

    return False
# -------------------------------
# Handle Client
# -------------------------------
def handle(client):

    global broadcast_count

    while True:

        try:

            message = client.recv(1024).decode()

            if not message:
                break

            sender = clients[client]

            # -------------------------------
            # Show Online Users
            # -------------------------------
            if message.strip() == "/list":

                send_user_list(client)
                continue

            # -------------------------------
            # Private Message
            # -------------------------------
            if message.startswith("/msg "):

                parts = message.split(" ", 2)

                if len(parts) < 3:

                    client.send(
                        "Usage: /msg <username> <message>".encode()
                    )

                    continue

                receiver = parts[1]
                text = parts[2]

                success = private_message(
                    sender,
                    receiver,
                    text
                )

                if not success:

                    client.send(
                        "User not found.".encode()
                    )

                continue

            # -------------------------------
            # Broadcast Message
            # -------------------------------
            broadcast_count += 1

            full_message = f"{sender}: {message}"

            print(full_message)

            save_chat(
                sender,
                "All",
                "Broadcast",
                message
            )

            broadcast(
                full_message,
                client
            )

        except Exception:

            break

    # -------------------------------
    # Client Disconnect
    # -------------------------------
    username = clients.get(client)

    if username:

        print(f"{username} disconnected.")

        broadcast(
            f"*** {username} left the chat ***",
            client
        )

    with lock:

        if client in clients:
            del clients[client]

        if client in client_info:
            del client_info[client]

    # Update GUI client user lists
    update_all_user_lists()

    client.close()
# -------------------------------
# Main Server Loop
# -------------------------------
while True:

    client, address = server.accept()

    try:

        # Ask client for username
        client.send("NAME".encode())

        username = client.recv(1024).decode().strip()

        if username == "":
            username = f"User{len(clients) + 1}"

        login_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        with lock:

            clients[client] = username

            client_info[client] = {
                "ip": address[0],
                "port": address[1],
                "login": login_time,
                "status": "Online"
            }

        print("\n===================================")
        print("New Client Connected")
        print("===================================")
        print(f"Username    : {username}")
        print(f"IP Address  : {address[0]}")
        print(f"Port Number : {address[1]}")
        print(f"Login Time  : {login_time}")
        print(f"Status      : Online")
        print("===================================\n")

        # Notify all clients
        broadcast(f"*** {username} joined the chat ***")

        # Update online user list for GUI clients
        update_all_user_lists()

        # Start client thread
        thread = threading.Thread(
            target=handle,
            args=(client,),
            daemon=True
        )

        thread.start()

    except Exception as e:

        print("Connection Error:", e)

        client.close()
