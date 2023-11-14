import socket
import json
import logging

logger = logging.getLogger(__name__)

class Client:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self._channels = {}
    
    @property
    def channels(self):
        return self._channels

    def get(self, req, channel = None):
        reply = self.run_command("GET", args = {'req': req}, channel = channel)
        return json.loads(reply)

    def kill(self):
        self.run_command('KILL')

    def close_channel(self, channel):
        self.channels[channel].close()
        del self._channels[channel]
    
    def close_all_channels(self):
        for i in list(self.channels.keys()):
            self.close_channel(i)

    def new_channel(self, name):
        if name not in self.channels:
            self._channels[name] = Channel(self.host, self.port, name)
        else:
            raise ValueError("channel already exists")

    def run_command(self, command, args = {}, channel = None):
        try:
            if channel:
                return self.channels[channel].run_command(command, args)
            else:
                c = Channel(self.host, self.port)
                reply = c.run_command(command, args)
                c.close()
                return reply
        except ConnectionAbortedError:
            if channel: del self._channels[channel]
            raise ConnectionAbortedError

    def __del__(self):
        self.close_all_channels()

class Channel:
    def __init__(self, host, port, name = None):
        self.conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.conn.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.conn.connect((host, port))
        self.name = name
        self.connected = True
    
    def run_command(self, command, args = {}):
        if not self.connected:
            raise ConnectionError
        args['command'] = command
        command = json.dumps(args).encode()
        self.conn.sendall(command)
        reply = self.conn.recv(1024)

        if reply:
            return reply.decode('utf-8')
        else:
            logger.debug(f"connection closed on the server side")
            self.close()
            raise ConnectionAbortedError
        
    def close(self):
        if self.connected:
            logger.debug(f"closing channel '{self.name}'")
            self.conn.close()
            self.connected = False

if __name__=='__main__':
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default = socket.gethostbyname(socket.gethostname()))
    parser.add_argument("--port", default = 5562)

    args = parser.parse_args()
    client = Client(args.host, int(args.port))
    client.connect()

    running = True
    while running:
        cmd = input("enter a command: ")
        client.conn.sendall(cmd.encode('utf-8'))
        if cmd =='EXIT':
            client.exit()
            running = False