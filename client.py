import socket
from utils import *
import threading

#TODO: need something to check that the server is on
# need to 

class Client:
    def __init__(self, host=HOST, port=PORT, broadcast_port = BROADCAST_PORT, verbose = True):
        self.host = host
        self.port = port
        self.verbose = verbose
        self.broadcast_port = broadcast_port
        self.connected = False
        self.status = {}

    def get_prop(self, module, prop):
        conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        conn.connect((self.host, self.broadcast_port))
        req = f"{module} {prop}"
        conn.sendall(req.encode('utf-8'))
        reply = conn.recv(1024)
        if reply:
            return reply.decode('utf-8')
        else:
            if self.verbose: print('server does not appear to be running. closing connection')
            self.conn.close()
            self.connected = False
            return reply

    def kill(self):
        assert self.connected, "not connected to the server"
        self.conn.sendall(b'KILL')
        self.conn.close()
        self.connected = False
        
    def exit(self):
        if self.connected:
            self.conn.sendall(b'EXIT')
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

    def fill_syringe(self, pump, amount):
        command = f'FillSyringe {pump} {amount}'.encode('utf-8')
        reply = self.run_command(command)
        return reply

    def lick_triggered_reward(self, module, amount, force = False):
        command = f'LickTriggeredReward {module} {amount} {force}'.encode('utf-8')
        reply = self.run_command(command)
        return reply

    def trigger_reward(self, module, amount, force = False):
        command = f'Reward {module} {amount} {force}'.encode('utf-8')
        reply = self.run_command(command)
        return reply

    def set_syringe_ID(self, ID, pump = None, set_all = True):
        if set_all:
            command = f'SetAllSyringeIDs {ID}'.encode('utf-8')
        else:
            command = f'SetAllSyringeIDs {pump} {ID}'.encode('utf-8')
        reply = self.run_command(command)
        return reply

    def set_syringe_type(self, syringeType, pump = None, set_all = True):
        if set_all:
            command = f'SetAllSyringeTypes {syringeType}'.encode('utf-8')
        else:
            command = f'SetAllSyringeType {pump} {syringeType}'.encode('utf-8')
        reply = self.run_command(command)
        return reply

    def run_command(self, command):
        assert self.connected, "not connected to the server"
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


if __name__=='__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default = HOST)
    parser.add_argument("--port", default = PORT)
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

