import socket
import json


class Client:
    def __init__(self, host, port, broadcast_port, verbose = True):
        self.host = host
        self.port = port
        self.verbose = verbose
        self.broadcast_port = broadcast_port
        self.connected = False
        self.status = {}
        self.channels = {}

    def get(self, req, channel = None):
        if channel:
            conn = self.channels[channel]
        else:
            conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            conn.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            conn.connect((self.host, self.broadcast_port))
        req = req.encode()
        conn.sendall(req)
        reply = conn.recv(1024).decode()
        if not channel: conn.close()
        if reply: return json.loads(reply)
        else:
            if self.verbose: 
                print('server does not appear to be running. closing connection')
            self.conn.close()
            for i in self.channels: self.channels[i].close()
            self.connected = False
            return reply

    def kill(self):
        assert self.connected, "not connected to the server"
        self.conn.sendall(json.dumps({'command': 'KILL'}).encode())
        self.conn.close()
        for i in self.channels: self.channels[i].close()
        self.connected = False

    def exit(self):
        if self.connected:
            self.conn.sendall(json.dumps({'command': 'EXIT'}).encode())
            self.conn.close()
            for i in self.channels: self.channels[i].close()
            self.connected = False
    
    def connect(self):
        if self.connected:
            self.exit()
        self.conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.conn.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        if self.verbose: 
            print('connecting to host')
        try:
            self.conn.connect((self.host, self.port))
            if self.verbose: print('connected!')
            self.connected = True
        except ConnectionRefusedError:
            self.connected = False
            self.conn.close()
            for i in self.channels: self.channels[i].close()
            raise ConnectionRefusedError
        
    def new_channel(self, name):
        conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        conn.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        conn.connect((self.host, self.broadcast_port))
        self.channels[name] = conn

    def run_command(self, command, args = {}):
        assert self.connected, "not connected to the server"
        args['command'] = command
        command = json.dumps(args).encode()
        self.conn.sendall(command)
        reply = self.conn.recv(1024)
        if reply:
            return reply.decode('utf-8')
        else:
            if self.verbose: print('server does not appear to be running. closing connection')
            self.conn.close()
            for i in self.channels: self.channels[i].close()
            self.connected = False
            return reply   

    def __del__(self):
        self.exit()

if __name__=='__main__':
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default = socket.gethostbyname(socket.gethostname()))
    parser.add_argument("--port", default = 5562)
    parser.add_argument("--broadcast_port", default = 5563)

    args = parser.parse_args()
    client = Client(args.host, int(args.port), int(args.broadcast_port))
    client.connect()

    running = True
    while running:
        cmd = input("enter a command: ")
        client.conn.sendall(cmd.encode('utf-8'))
        if cmd =='EXIT':
            client.exit()
            running = False