import socket
import sys
import signal
import asyncio
import threading
import json
from pathlib import Path
import os
import shutil
class Client():

    closed = False
    json_messages = []
    regular_messages = []
    file_messages = b""
    file_transfer = False
    client_socket = None
    user_name = ""
    # Function to take input in the command line
    def take_input(self, client_socket, user_name):
        try:
            message = ""
            recipient = "everyone"
            while True:
                broadcast = ""
                action = ""
                # Check whether user wants to message or download a file
                while action not in ("message", "download"):
                    action = input("Do you want to message or download? ").strip().lower()
                    if action not in ("message", "download"):
                        print("Either enter 'message' or 'download")
                # If user wants to message then request a message to send
                if action == "message":
                    message = input("Enter Message to Server: ")
                    # Check if user wants to broadcast or unicast the message
                    while broadcast not in ("n","y"):
                        broadcast = input("Do you want to send this message to everyone? Use Y or N ").strip().lower()
                        if broadcast not in ("n","y"):
                            print("Please input Y or N")

                    if broadcast == "n":
                        recipient = input("Who do you want to send the message to? ")
                    else:
                        recipient = "everyone"
                    self.send_message(message, user_name, recipient, client_socket, action=action)
                    print("Message Sent")
                else:
                    # Request list of files from server
                    self.send_message("", "", "", client_socket, action="view")
                    files = None
                    # Wait until server sends the list
                    while not files:
                        self.receive_file(client_socket)
                        if len(self.json_messages) > 0:
                            f = self.json_messages[0]
                            self.json_messages.pop(0)
                            try:
                                files = json.loads(f)
                            except json.JSONDecodeError:
                                files = f       
                    # Print the name of each file on a seperate line                        
                    print("Here are the files in the download folder: ")
                    print()
                    for file in files:
                        print(file)
                    print()
                    # Ask which file the user wants to downlaod
                    while(True):
                        download_file = input("Which file would you like to download? ")
                        print()
                        # Ask what the name of folder should be
                        folder_name = input("What should the folder name be? ")
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
                            while True:
                                self.receive_file(client_socket)
                                chunk = None
                                if len(self.file_messages) > 0:
                                    if b"No file with that name" in self.file_messages:
                                        print("No file with that name. Try again")
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
                        print()
                        print("File Downloaded")
                        print()
                        self.file_transfer = False
                        break
        # EOFError if client disconnects. This will be handled elsewhere so we pass
        except EOFError:
            pass
    # Function that receives message from server and stores them in the correct queue
    def receive_file(self, client_socket):
        try:
            # This branch is for file transfer as we need to read a larger amount of data. Stores them in file_messages
            if self.file_transfer:
                new_message = client_socket.recv(200000)
                self.file_messages+=new_message
                return 
            new_message = client_socket.recv(1024)
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
        except (ConnectionResetError, OSError):
            return ""

    

    # async def get_user_input(self):
    #     return await asyncio.get_event_loop().run_in_executor(None, input, "Enter something: ")
    # Function that handles general function of client e.g. starting up and printing new messages
    async def handle_client(self, client_socket, user_name):
        #Read and print welcome message from server
        client_socket.sendall(user_name.encode('utf-8'))
        welcome_message = client_socket.recv(1024).decode('utf-8')
        print(welcome_message)
        if(welcome_message == "Username already in use. Try again"):
            self.send_message(f"{self.user_name} has disconnected", self.user_name, "everyone", self.client_socket, action="disconnect")
# Close the socket
            self.client_socket.close()
            return
            sys.exit(0)
        client_socket.setblocking(0)
        input_thread = threading.Thread(target=self.take_input, args=(client_socket, user_name))
        input_thread.start()
        # Constantly check for new messages
        while True:
            self.receive_file(client_socket)
            if(len(self.regular_messages) > 0):
                print()
                print(self.regular_messages[0])
                self.regular_messages.pop(0)

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
            print(f"Error sending data to server: {e}")

    async def main(self):
        # Check correct usage
        if len(sys.argv) < 3:
            print("Usage: python script_name.py user_name host_name port ")
            sys.exit(1)
        # Extract components
        self.user_name = sys.argv[1]
        host_name = sys.argv[2]
        port = int(sys.argv[3])

        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        server_address = (host_name, port)
        # Connect to server
        self.client_socket.connect(server_address)
        await self.handle_client(self.client_socket, self.user_name)

if __name__ == "__main__":
    cli = Client()
    # The parameters below aren't accessed but have to include as they come with function
    def handle_disconnect(signal, frame):
        # Tell server that this client is disconnecting
        cli.send_message(f"{cli.user_name} has disconnected", cli.user_name, "everyone", cli.client_socket, action="disconnect")
        # Close the socket
        cli.client_socket.close()
        sys.exit(0)
    # Calls exit_gracefully when CTRL + C
    signal.signal(signal.SIGINT, handle_disconnect)
    # Runs the Client main asynchronously
    asyncio.run(cli.main())