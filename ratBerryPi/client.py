import socket
import json


class Client:
    def __init__(self, host, port, verbose = True):
        self.host = host
        self.port = port
        self.verbose = verbose
        self.channels = {}

    def get(self, req, channel = None):
        reply = self.run_command("GET", args = {'req': req}, channel = channel)
        return json.loads(reply)

    def kill(self):
        self.run_command('KILL')

    def close_channel(self, all = True, channel = None):
        if not all:
            if not channel:
                raise ValueError("missing argument 'channel'")
            self.run_command("EXIT", channel = channel)
            self.channels[channel].close()
            del self.channels[channel]
        else:
            for i in self.channels:
                self.run_command("EXIT", channel = i)
                self.channels[i].close()
                del self.channels[i]
        
    def new_channel(self, name):
        conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        conn.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        conn.connect((self.host, self.port))
        self.channels[name] = conn

    def run_command(self, command, args = {}, channel = None):
        args['command'] = command
        command = json.dumps(args).encode()

        if channel:
            conn = self.channels[channel]
        else:
            conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            conn.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            conn.connect((self.host, self.port))
        conn.sendall(command)
        reply = conn.recv(1024)
        if reply:
            return reply.decode('utf-8')
        else:
            if self.verbose: 
                print('server does not appear to be running. closing all connections')
            for i in self.channels: 
                self.channels[i].close()
            if not channel:
                conn.close
            raise ConnectionAbortedError

    def __del__(self):
        self.close_channel()

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