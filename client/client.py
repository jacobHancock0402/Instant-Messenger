import socket
import sys
import signal
import asyncio
import threading
import json
from pathlib import Path
import os
import shutil
import logging
import time

class Client():

    closed = False
    json_messages = []
    regular_messages = []
    file_messages = b""
    file_transfer = False
    client_socket = None
    user_name = ""
    server_disconnected = False
    
    def __init__(self):
        # Set up logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('client.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)

    # Function to take input in the command line
    def take_input(self, client_socket, user_name):
        try:
            message = ""
            recipient = "everyone"
            while not self.closed:
                broadcast = ""
                action = ""
                # Check whether user wants to message or download a file
                while action not in ("message", "download") and not self.closed:
                    try:
                        action = input("Do you want to message or download? ").strip().lower()
                        if action not in ("message", "download"):
                            self.logger.warning("Invalid action entered: %s", action)
                    except (EOFError, KeyboardInterrupt):
                        self.closed = True
                        break
                        
                if self.closed:
                    break
                    
                # If user wants to message then request a message to send
                if action == "message":
                    try:
                        message = input("Enter Message to Server: ")
                        # Check if user wants to broadcast or unicast the message
                        while broadcast not in ("n","y") and not self.closed:
                            try:
                                broadcast = input("Do you want to send this message to everyone? Use Y or N ").strip().lower()
                                if broadcast not in ("n","y"):
                                    print("Please input Y or N")
                            except (EOFError, KeyboardInterrupt):
                                self.closed = True
                                break
                                
                        if self.closed:
                            break
                            
                        if broadcast == "n":
                            try:
                                recipient = input("Who do you want to send the message to? ")
                            except (EOFError, KeyboardInterrupt):
                                self.closed = True
                                break
                        else:
                            recipient = "everyone"
                            
                        if not self.closed:
                            self.send_message(message, user_name, recipient, client_socket, action=action)
                            self.logger.info("Message sent successfully")
                    except (EOFError, KeyboardInterrupt):
                        self.closed = True
                        break
                else:
                    # Request list of files from server
                    self.send_message("", "", "", client_socket, action="view")
                    files = None
                    # Wait until server sends the list
                    while not files and not self.closed:
                        self.receive_file(client_socket)
                        if len(self.json_messages) > 0:
                            f = self.json_messages[0]
                            self.json_messages.pop(0)
                            try:
                                files = json.loads(f)
                            except json.JSONDecodeError:
                                files = f       
                    
                    if self.closed:
                        break
                        
                    # Print the name of each file on a seperate line                        
                    self.logger.info("Available files for download:")
                    for file in files:
                        self.logger.info(f"  - {file}")
                    # Ask which file the user wants to downlaod
                    while(True) and not self.closed:
                        try:
                            download_file = input("Which file would you like to download? ")
                            print()
                            # Ask what the name of folder should be
                            folder_name = input("What should the folder name be? ")
                        except (EOFError, KeyboardInterrupt):
                            self.closed = True
                            break
                            
                        if self.closed:
                            break
                            
                        self.file_transfer = True
                        re_prompt = False
                        self.send_message(download_file, "", "", client_socket, action="download")
                        files = None
                        # Check if folder exists. Create it if not
                        if(not os.path.exists(folder_name)):
                            Path(folder_name).mkdir(parents=True, exist_ok=True)
                        file_path = folder_name + "/" + download_file
                        # Download the file
                        with open(file_path, 'wb') as file:
                            while True and not self.closed:
                                self.receive_file(client_socket)
                                chunk = None
                                if len(self.file_messages) > 0:
                                    if b"No file with that name" in self.file_messages:
                                        self.logger.warning("File not found: %s", download_file)
                                        re_prompt = True
                                        self.file_messages = b""
                                        break
                                    chunk = self.file_messages
                                    self.file_messages = b""
                                    file.write(chunk)
                                elif not chunk and os.path.getsize(file_path) > 0 :
                                    break
                        if(re_prompt):
                            shutil.rmtree(folder_name)
                            continue
                        self.logger.info("File downloaded successfully: %s", download_file)
                        self.file_transfer = False
                        break
        # EOFError if client disconnects. This will be handled elsewhere so we pass
        except EOFError:
            pass
        except KeyboardInterrupt:
            self.closed = True

    # Function to check server connection
    def check_server_connection(self, client_socket):
        try:
            # Don't actually send data - just check if socket is still valid
            # The socket.error will be raised if the connection is broken
            client_socket.getpeername()
            return True
        except (OSError, ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
            return False
        except Exception:
            # For other errors, assume connection is still valid
            return True

    # Function that receives message from server and stores them in the correct queue
    def receive_file(self, client_socket):
        try:
            # This branch is for file transfer as we need to read a larger amount of data. Stores them in file_messages
            if self.file_transfer:
                new_message = client_socket.recv(200000)
                if not new_message:  # Server disconnected
                    self.server_disconnected = True
                    return ""
                self.file_messages+=new_message
                return 
            new_message = client_socket.recv(1024)
            if not new_message:  # Server disconnected
                self.server_disconnected = True
                return ""
            # Each message is seperated by \n, so we split by this to get each individual message
            new_message = new_message.decode('utf-8').split("\n")
            # Parse each message and append to the correct list
            for message in new_message:
                message = message.strip("\n")
                if(len(message) > 0):
                    try:
                        json.loads(message)
                        self.json_messages.append(message)
                    # Exception if not JSON as cannot read as JSON
                    except json.JSONDecodeError:
                        self.regular_messages.append(message)
                return new_message
        except (ConnectionResetError, OSError, ConnectionAbortedError, BrokenPipeError) as e:
            # Only treat these as disconnection if they're not the Windows non-blocking error
            if "10035" not in str(e):  # Windows non-blocking error
                self.logger.warning(f"Connection error: {e}")
                self.server_disconnected = True
            return ""
        except Exception as e:
            self.logger.error(f"Unexpected error in receive_file: {e}")
            # Don't treat unexpected errors as disconnection
            return ""

    # async def get_user_input(self):
    #     return await asyncio.get_event_loop().run_in_executor(None, input, "Enter something: ")
    # Function that handles general function of client e.g. starting up and printing new messages
    async def handle_client(self, client_socket, user_name):
        try:
            #Read and print welcome message from server
            client_socket.sendall(user_name.encode('utf-8'))
            welcome_message = client_socket.recv(1024).decode('utf-8')
            print(welcome_message)
            if(welcome_message == "Username already in use. Try again"):
                self.logger.warning("Username already in use, disconnecting")
                self.send_message(f"{self.user_name} has disconnected", self.user_name, "everyone", self.client_socket, action="disconnect")
                # Close the socket
                self.client_socket.close()
                return
                sys.exit(0)
            client_socket.setblocking(0)
            input_thread = threading.Thread(target=self.take_input, args=(client_socket, user_name))
            input_thread.start()
            
            self.logger.info(f"Successfully connected to server as {user_name}")
            
            # Constantly check for new messages
            while not self.closed and not self.server_disconnected:
                self.receive_file(client_socket)
                
                # Check if server disconnected
                if self.server_disconnected:
                    self.logger.warning("Server connection lost")
                    self.logger.info("Server has disconnected. Exiting...")
                    break
                
                # Check server connection less frequently to avoid false positives
                # Only check every 10 iterations (roughly every second)
                if len(self.regular_messages) % 10 == 0:
                    if not self.check_server_connection(client_socket):
                        self.logger.warning("Server connection check failed")
                        self.server_disconnected = True
                        self.logger.info("Server connection lost. Exiting...")
                        break
                
                if(len(self.regular_messages) > 0):
                    self.logger.info(f"Received message: {self.regular_messages[0]}")
                    self.regular_messages.pop(0)
                
                # Small delay to prevent excessive CPU usage
                await asyncio.sleep(0.1)
            
            # Clean up when exiting
            if self.client_socket:
                try:
                    if not self.server_disconnected:
                        self.send_message(f"{self.user_name} has disconnected", self.user_name, "everyone", self.client_socket, action="disconnect")
                    self.client_socket.close()
                except:
                    pass
                    
        except Exception as e:
            self.logger.error(f"Error in handle_client: {e}")
            if self.client_socket:
                try:
                    self.client_socket.close()
                except:
                    pass

    # Function for sending message
    def send_message(self, message, sender, recipient, client_socket, action=None):
        # The data to send. Sender and recipient are user_names. action is the type of action associated with message, e.g. download
        data = {"message": message, "sender": sender, "recipient": recipient.strip(), "action": action}
        # Store data as JSON
        json_string = json.dumps(data)
        try:
            # Send the data
            client_socket.sendall(json_string.encode('utf-8'))
        except Exception as e:
            self.logger.error(f"Error sending data to server: {e}")

    async def main(self):
        try:
            # Check correct usage
            if len(sys.argv) < 3:
                self.logger.error("Incorrect usage. Expected: python script_name.py user_name host_name port")
                sys.exit(1)
            # Extract components
            self.user_name = sys.argv[1]
            host_name = sys.argv[2]
            port = int(sys.argv[3])

            self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

            server_address = (host_name, port)
            # Connect to server
            self.client_socket.connect(server_address)
            self.logger.info(f"Attempting to connect to server at {host_name}:{port}")
            await self.handle_client(self.client_socket, self.user_name)
        except ConnectionRefusedError:
            self.logger.error(f"Could not connect to server at {host_name}:{port}. Server may be down.")
            self.logger.error("Make sure the server is running and the port is correct.")
        except Exception as e:
            self.logger.error(f"Unexpected error in main: {e}")
        finally:
            if self.server_disconnected:
                self.logger.info("Client exiting due to server disconnection")
            elif self.closed:
                self.logger.info("Client exiting due to user request")
            else:
                self.logger.info("Client exiting")

if __name__ == "__main__":
    cli = Client()
    # The parameters below aren't accessed but have to include as they come with function
    def handle_disconnect(signal, frame):
        cli.logger.info("Disconnecting...")
        cli.closed = True
        # Tell server that this client is disconnecting
        if cli.client_socket:
            try:
                cli.send_message(f"{cli.user_name} has disconnected", cli.user_name, "everyone", cli.client_socket, action="disconnect")
                # Close the socket
                cli.client_socket.close()
            except:
                pass
        sys.exit(0)
    # Calls exit_gracefully when CTRL + C
    signal.signal(signal.SIGINT, handle_disconnect)
    # Runs the Client main asynchronously
    try:
        asyncio.run(cli.main())
    except KeyboardInterrupt:
        handle_disconnect(None, None)