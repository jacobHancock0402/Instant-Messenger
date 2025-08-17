# Instant Messenger

A Python-based client-server chat application with file sharing capabilities.

## Prerequisites

- Python 3.x
- Network connectivity

## Getting Started

### Starting the Server

1. Navigate to the server directory:
   ```bash
   cd server
   ```

2. Start the server with a specified port:
   ```bash
   python server.py <port>
   ```

**Example:**
```bash
python server.py 8000
```
This will start the server on port 8000.

### Running the Client

1. Navigate to the client directory:
   ```bash
   cd client
   ```

2. Connect to the server:
   ```bash
   python client.py <user_name> <host_name> <port>
   ```

**Example:**
```bash
python client.py Jacob 127.0.0.1 8000
```
This will connect user "Jacob" to the server at 127.0.0.1 via port 8000.

## Usage

### Sending Messages

1. Type `message` after the first prompt
2. Choose message type:
   - Type `Y` for broadcast (send to all clients)
   - Type `N` for unicast (send to specific client)
3. If unicasting, enter the target user's name when prompted

### File Downloads

1. Type `download` after the first prompt
2. View the list of available files in the server's download folder
3. Enter the full filename you want to download
4. Specify the destination folder for the downloaded file

## Features

- **Real-time Chat**: Send messages to all clients or specific users
- **File Sharing**: Download files from the server
- **Client Monitoring**: Server automatically notifies all clients when users join or leave
- **Logging**: Server activity is logged to `server.log`

## File Structure

```
├── client/
│   └── client.py
├── server/
│   ├── server.py
│   ├── download/
│   │   └── blank.pdf (example file)
│   └── server.log
└── README.txt
```

## Notes

- The `server.log` file starts empty and populates as the server runs
- An example file (`blank.pdf`) is provided in the server's download folder for testing
- Client connections and disconnections are automatically broadcast to all connected clients
