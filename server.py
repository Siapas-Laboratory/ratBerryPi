import socket
import threading
from utils import *
from reward import RewardInterface, RewardModule
import subprocess
import os


class Server:
    def __init__(self, host=HOST, port=PORT, async_port = ASYNC_PORT, reward_interface = None):
        self.host = host
        self.port = port
        self.async_port = async_port
        self.conn = None
        self.async_conn = None
        self.waiting = False
        self.on = False
        self.status = {i: 0 for i in self.reward_interface.modules}
        self.monitor_thread = None
        self.reward_interface = None
        
    def monitor(self):
        while self.on:
            for i in self.reward_interface.modules:
                if self.reward_interface.modules[i].pump_thread:
                    status = self.reward_interface.modules[i].pump_thread.status
                    if status != self.status[i]:
                        self.status[i] = status
                        if self.async_conn:
                            msg = f"{i} {status}"
                            self.async_conn.sendall(msg.encode('utf-8'))

    def start(self, reward_interface = None):
        self.on = True
        self.reward_interface = RewardInterface() if not reward_interface else reward_interface
        self.monitor_thread = threading.Thread(target = self.monitor)
        self.monitor_thread.start()

        while self.on:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                print('binding the port')
                sock.bind((self.host, self.port))
                sock.listen()
                print('waiting for connections...')
                self.conn, (ip, _) =  sock.accept()
                sock.close()
                print('connection accepted, setting up async channel')
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                sock.bind((self.host, self.async_port))
                sock.listen()
                print(f"waiting for secondary connection from '{ip}'")
                async_ip = ''
                while async_ip != ip:
                    self.async_conn, (async_ip, _) =  sock.accept()
                    if async_ip != ip:
                        print('wrong ip retrying...')
                        self.async_conn.close()
                sock.close()
                print('waiting for data...')
                self.waiting = True
                while self.waiting:
                    data = self.conn.recv(1024) # receive the data
                    if not data:
                        self.waiting = False
                    else:
                        self.handle_request(data)
                self.conn.close()
                self.conn = None
                self.async_conn.close()
                self.async_conn = None

            except Exception as e:
                print(e)
                self.shutdown()

    def handle_request(self, data):
        """
        function to handle requests sent to the server

        Args:
        -----
        data: bytes
            utf-8 encoded request sent to the server 
        """

        # TODO: functions to add:
        # setting all syringe types at once
        # setting all ids at once
        # resetting the lick count
        # getting the module names
        # pulling back the syringe? (on this note also need to figure out end detection)

        command = data.decode('utf-8')
        command = command.split(' ')

        args = command[1:] if len(command)>1 else []
        command = command[0]

        if command == 'CheckServer':
            self.conn.sendall(b'1')
        if command == "EXIT":
            print("client disconnected")
            self.waiting = False
        elif command == "KILL":
            print("server is shutting down")
            self.on = False
            self.waiting = False
        elif 'Reward' in command:
            if len(args)<2:
                reply = "invalid command"
            else:
                try:
                    mod = args[0]
                    amount = float(args[1])
                    force = args[2].lower()=='true' if len(args)>2 else False
                    if command == 'LickTriggeredReward':
                        self.reward_interface.modules[mod].lick_triggered_reward(amount, force)
                        reply = f"{command} {mod} {amount} mL successful"
                    elif command == 'Reward':
                        self.reward_interface.modules[mod].trigger_reward(amount, force)
                        reply = f"{command} {mod} {amount} mL successful"
                    else:
                        reply = "invalid command"
                except NoLickometer:
                    reply = f"{command} {mod} {amount} mL unsuccessful; module does not have a lickometer"
                except PumpInUse:
                    reply = f"{command} {mod} {amount} mL unsuccessful; pump is currently in use"
                except EndTrackError:
                    # hm right now i dont think this gets caught because this error is thrown in the thread
                    # that runs the pump...
                    reply = f"{command} {mod} {amount} mL unsuccessful; reached the end of the track"
                except ValueError:
                    reply = f"invalid amount {amount} specified"
            self.conn.sendall(str.encode(reply))
            print("reply sent")
        elif command == "SetSyringeType":
            if len(args)<2:
                reply = "invalid command"
            else:
                try:
                    mod = args[0]
                    syringeType = args[1]
                    self.reward_interface.set_syringe_type(mod, syringeType)
                    reply = f"{command} {mod} to {syringeType} successful"
                except:
                    reply = f"{command} {mod} to {syringeType} unsuccessful. invalid syringeType"
            self.conn.sendall(str.encode(reply))
            print("reply sent")
        elif command == "SetSyringeID":
            if len(args)<2:
                reply = "invalid command"
            else:
                try:
                    mod = args[0]
                    ID = float(args[1])
                    self.reward_interface.set_syringe_ID(mod, ID)
                    reply = f"{command} {mod} to {ID} successful"
                except ValueError:
                    reply = f"invalid ID {ID} specified"
            self.conn.sendall(str.encode(reply))
            print("reply sent")
        else:
            self.conn.sendall(b"invalid command")
            print("reply sent")

    def shutdown(self):
        if self.conn:
            self.conn.close()
        if self.async_conn:
            self.async_conn.close()
        if self.monitor_thread:
            self.monitor_thread.join()
        self.on = False

    def __del__(self):
        self.shutdown()

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--reward_config', default = 'config.yaml', help = 'path to the config file for the reward interface')
    parser.add_argument('--burst_thresh', default = 0.5,
                         help = 'time threshold in seconds on the inter lick interval for starting a new burst, consequently also the time after a lick before stopping the pump')
    parser.add_argument('--reward_thresh', default = 3, help = 'number of licks within a burst required to start the pump')
    
    args = parser.parse_args()
    reward_interface = RewardInterface(args.reward_config, args.burst_thresh, args.reward_thresh)

    server = Server(reward_interface=reward_interface)
    server.start(reward_interface)
