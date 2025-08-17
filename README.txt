Start the server in command line by navigating to the server folder and using "python server.py <port>" e.g "python server.py 8000" will run on port 8000

Run the client in command line by navigating to the client folder and using "python client.py <user_name> <host_name> <port> e.g "python client.py Jacob 127.0.0.1 8000" will connect Jacob to the server 127.0.0.1 via port 8000

To message, type in "message" after the first prompt. You can then choose to unicast or broadcast by typing "Y" or "N"

If you type "N", you will be able to type in the user_name of the client you want to unicast to

To download, type in "download" after the first prompt. You will then see a list of files in the download folder. Type in the full name of the file you want to download, and then the name of the folder you want to save it to

When a client joins or leaves the server, purposefully or not, the server will broadcast this to each client, and it will be printed in the command line

server.log is initially empty but will fill with logs once you run the server

I have provided an example file within server/download for testing purposes