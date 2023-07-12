import socket
from utils import *
import threading

#TODO: need something to check that the server is on
# need to 

class Client:
    def __init__(self, host=HOST, port=PORT, async_port = ASYNC_PORT):
        self.host = host
        self.port = port
        self.async_port = async_port
        self.connect()

    def monitor(self):
        while self.connected:
            if self.async_conn:
                try:
                    data = self.async_conn.recv(1024)
                    if data:
                        data = data.decode('utf-8').split()
                        if len(data)==2:
                            mod, status = data
                            try:
                                self.status[mod] = int(status)
                            except ValueError:
                                pass
                except OSError as e:
                    print(e)
                    pass

    def kill(self):
        assert self.connected, "not connected to the server"
        self.conn.sendall(b'KILL')
        self.conn.close()
        self.async_conn.close()
        self.connected = False
        self.monitor_thread.join()

    def exit(self):
        if self.connected:
            self.conn.sendall(b'EXIT')
            self.conn.close()
            self.async_conn.close()
            self.connected = False
            self.monitor_thread.join()
    
    def connect(self):
        if hasattr(self, 'connected'):
            if self.connected:
                self.exit()  
        self.conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.conn.connect((self.host, self.port))
        self.async_conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.connected = False
        while not self.connected:
            try:
                self.async_conn.connect((self.host, self.async_port))
                self.connected = True
            except ConnectionRefusedError:
                pass
        self.status = {}
        self.monitor_thread = threading.Thread(target = self.monitor)
        self.monitor_thread.start()

    def lick_triggered_reward(self, module, amount, force = False):
        assert self.connected, "not connected to the server"
        command = f'LickTriggeredReward {module} {amount} {force}'.encode('utf-8')
        self.conn.sendall(command)
        reply = self.conn.recv(1024)
        if reply:
            return reply.decode('utf-8')
        else:
            self.conn.close()
            self.async_conn.close()
            self.connected = False
            return reply

    def trigger_reward(self, module, amount, force = False):
        assert self.connected, "not connected to the server"
        command = f'Reward {module} {amount} {force}'.encode('utf-8')
        self.conn.sendall(command)  
        reply = self.conn.recv(1024)
        if reply:
            return reply.decode('utf-8')
        else:
            self.conn.close()
            self.async_conn.close()
            self.connected = False
            return reply


if __name__=='__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default = HOST)
    parser.add_argument("--port", default = PORT)
    args = parser.parse_args()
    client = Client(args.host, int(args.port))

    running = True
    while running:
        cmd = input("enter a command: ")
        client.conn.sendall(cmd.encode('utf-8'))
        if cmd =='EXIT':
            client.exit()
            client.monitor_thread.join()
            running = False

