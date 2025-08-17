import socket
import threading
import sys
import json
import os
import logging
import signal

# Global flag to control server shutdown
server_running = True

# Function to handle client disconnection
def handle_disconnect(client_address, user_name, connection):
    logging.info("%s (%s) has disconnected", user_name, client_address)
    # Broadcast that user_name has disconnected
    client_connections.pop(user_name)
    client_addresses.pop(user_name)
    send_to_all_clients(user_name + " has left\n")
    # Remove all traces of this client and close the connection
    connection.close()

# Function to handle client activities
def handle_client(connection, client_address, user_name):
    logging.info("New connection from %s (%s)", user_name, client_address)
    welcome_message = "Welcome to the server! You can leave by pressing CTRL + C\n"
    # Adds connection and address to the dictionaries
    client_addresses[user_name] = client_address
    client_connections[user_name] = connection
    # Send a welcome message to the client
    connection.sendall(welcome_message.encode('utf-8'))
    logging.info("Welcome message sent to %s (%s)", user_name, client_address)
    # Makes sockets functions non-blocking
    connection.setblocking(0)
    logging.info("User %s (%s) has joined the server", user_name, client_address)
    # Broadcast that this client has joined the server (to other clients only)
    send_to_all_clients(user_name + " has joined\n", sender=user_name)
    while True:
        try:
            # Receive data from client
            data = connection.recv(1024).decode('utf-8')
            
            # Check if we received any data
            if not data:
                continue
                
            # Try to parse JSON data
            try:
                data = json.loads(data)
            except json.JSONDecodeError:
                logging.warning("Received invalid JSON data from %s: %s", client_address, data)
                continue
                
            # Validate that data is a dictionary and has required fields
            if not isinstance(data, dict) or "action" not in data:
                logging.warning("Received malformed data from %s: %s", client_address, data)
                continue
                
            # Branch for getting list of files
            if(data["action"] == "view"):
                logging.info("User %s (%s) requested file list", user_name, client_address)
                connection.sendall((json.dumps(os.listdir("./download")) + "\n").encode('utf-8'))
                logging.info("File list sent to %s (%s)", user_name, client_address)
            # Branch for downloading a file
            elif(data["action"] == "download"):
                if "message" not in data:
                    logging.warning("Download request missing filename from %s (%s)", user_name, client_address)
                    continue
                logging.info("User %s (%s) requested download: %s", user_name, client_address, data['message'])
                # Read and send the selected file
                file_path = "./download/" + data["message"]
                # Check if file exists
                if not os.path.exists(file_path):
                    logging.warning("File not found: %s requested by %s (%s)", data['message'], user_name, client_address)
                    message = "No file with that name\n"
                    connection.sendall(message.encode('utf-8'))
                else:
                    with open(file_path, 'rb') as file:
                        while True:
                            chunk = file.read() 
                            if not chunk:
                                break
                            connection.sendall(chunk)
                    logging.info("File '%s' sent to %s (%s)", data['message'], user_name, client_address)
            # Branch for disconnection. This should be for manual disconnection, i.e. CTRL + C
            elif(data["action"] == "disconnect"):
                logging.info("User %s (%s) requested graceful disconnect", user_name, client_address)
                handle_disconnect(client_address, user_name, connection)
                return
            # Branch for regular message
            else:
                # Validate required fields for messages
                if "sender" not in data or "message" not in data or "recipient" not in data:
                    logging.warning("Message request missing required fields from %s (%s): %s", user_name, client_address, data)
                    continue
                    
                # Concatenate sender name and message so to display who sends the message
                message = data["sender"] + ": " + data["message"]
                # Branch upon whether we are broadcasting or unicasting
                if(data["recipient"] == "everyone"):
                    logging.info("User %s (%s) broadcasts: '%s'", user_name, client_address, data['message'])
                    send_to_all_clients(f"{message}\n", sender=user_name)
                else:
                    if(data["recipient"] in client_connections):
                        logging.info("User %s (%s) sends to %s: '%s'", user_name, client_address, data['recipient'], data['message'])
                        client_connections[data["recipient"]].sendall(f"{message}\n".encode())
                    else:
                        logging.warning("Failed to send message from %s (%s) to '%s': user not found", user_name, client_address, data['recipient'])

        # This is bad practice but I just want to ignore the errors about not instantly completing the non-blocking operation, as not neccessary
        except BlockingIOError:
            pass
        
        # Handle abrupt disconnect
        except ConnectionResetError:
            handle_disconnect(client_address, user_name, connection)
            return
        except Exception as e:
            logging.error("Unexpected error handling client %s: %s", client_address, e)
            continue


# Function to send data to all clients
def send_to_all_clients(data, sender=""):
    for name, client in client_connections.items():
        # Send message to everyone but the sender
        if(name != sender):
            client.sendall(data.encode('utf-8'))

                
# Function to handle graceful shutdown
def handle_shutdown(signal, frame):
    global server_running
    logging.info("Shutting down server...")
    server_running = False
    # Close all client connections
    for name, client in list(client_connections.items()):
        try:
            client.close()
        except:
            pass
    # Close server socket
    try:
        server_socket.close()
    except:
        pass
    logging.info("Server shutdown complete.")
    sys.exit(0)

# Set up the variables
client_connections = {}
client_addresses = {}
port = sys.argv[1]
server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server_address = ('127.0.0.1', int(port))
server_socket.bind(server_address)
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('server.log'),
        logging.StreamHandler()  # This will output to console/terminal
    ]
)
logging.info("The server has started at %s", server_address)

# Set up signal handler for graceful shutdown
signal.signal(signal.SIGINT, handle_shutdown)

# Listen for incoming connections
server_socket.listen(5)
logging.info("Server listening on %s", server_address)
logging.info("Press Ctrl+C to stop the server")

# Loop that waits for connection from new clients
while server_running:
    try:
        # Set a timeout so we can check server_running flag
        server_socket.settimeout(1.0)
        connection, client_address = server_socket.accept()
        logging.info("New connection attempt from %s", client_address)

        # Create a new thread for each client connection
        user_name = connection.recv(1024).decode('utf-8')
        
        # Check if user_name already in use
        if(user_name in client_connections.keys()):
            logging.warning("Connection rejected: username '%s' already in use from %s", user_name, client_address)
            msg = "Username already in use. Try again"
            connection.sendall(msg.encode('utf-8'))
            connection.close()
            continue
            
        logging.info("Username '%s' accepted from %s", user_name, client_address)
        client_thread = threading.Thread(target=handle_client, args=(connection, client_address, user_name))
        client_thread.daemon = True  # Make thread daemon so it doesn't prevent shutdown
        client_thread.start()
        logging.info("Client thread started for %s (%s)", user_name, client_address)
        
    except socket.timeout:
        # Timeout occurred, check if we should continue
        continue
    except Exception as e:
        if server_running:
            logging.error("Error accepting connection: %s", e)
        break

# Clean shutdown
handle_shutdown(None, None)