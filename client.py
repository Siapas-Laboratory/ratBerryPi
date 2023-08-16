import socket
import pickle
import yaml

with open('config.yaml', 'r') as f:
    config = yaml.safe_load(f)
HOST = socket.gethostname()
PORT = config['PORT']
BROADCAST_PORT = config['BROADCAST_PORT']


class Client:
    def __init__(self, host = HOST, port = PORT, broadcast_port = BROADCAST_PORT, verbose = True):
        self.host = host
        self.port = port
        self.verbose = verbose
        self.broadcast_port = broadcast_port
        self.connected = False
        self.status = {}

    def get_prop(self, module, prop):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as conn:
            conn.connect((self.host, self.broadcast_port))
            req = f"{module} {prop}"
            conn.sendall(req.encode('utf-8'))
            reply = conn.recv(1024)
            if reply:
                return reply.decode('utf-8')
            else:
                if self.verbose: print('server does not appear to be running. closing connection')
                self.connected = False
                return reply

    def kill(self):
        assert self.connected, "not connected to the server"
        self.conn.sendall(pickle.dumps({'command': 'KILL'}))
        self.conn.close()
        self.connected = False

    def exit(self):
        if self.connected:
            self.conn.sendall(pickle.dumps({'command': 'EXIT'}))
            self.conn.close()
            self.connected = False
    
    def connect(self):
        if self.connected:
            self.exit()
        self.conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        if self.verbose: print('connecting to host')
        self.conn.connect((self.host, self.port))
        if self.verbose: print('connected!')
        self.connected = True
        
    def run_command(self, command, args):
        assert self.connected, "not connected to the server"
        args['command'] = command
        command = pickle.dumps(args)
        self.conn.sendall(command)
        reply = self.conn.recv(1024)
        if reply:
            return reply.decode('utf-8')
        else:
            if self.verbose: print('server does not appear to be running. closing connection')
            self.conn.close()
            self.connected = False
            return reply   

    def __del__(self):
        self.exit()

def remote_connect(host, port, broadcast_port):

    client = Client(host, port, broadcast_port)
    try:
        client.connect()
        return client, None
    except ConnectionRefusedError:
        server_thread = remote_boot(host)
        client.connect()
        return client, server_thread
    
def remote_boot(host, path = '~/Downloads/rpi-reward-module'):

    import paramiko
    import threading

    class server_thread(threading.Thread):
        def __init__(self):
            super(server_thread, self).__init__()
            
        def run(self):
            ssh = paramiko.SSHClient()
            ssh.load_system_host_keys()
            ssh.connect(host, username='pi')
            transport = ssh.get_transport()
            transport.set_keepalive(1) 
            ssh.exec_command(f"cd {path}; python3 server.py")
            self.running = True   
            while self.running:
                pass

        def join(self):
            self.running = False
            super(server_thread, self).join()

    t = server_thread()
    t.start()
    return t

if __name__=='__main__':
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default = HOST)
    parser.add_argument("--port", default = PORT)
    parser.add_argument("--broadcast_port", default = BROADCAST_PORT)

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