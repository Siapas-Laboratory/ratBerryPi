import socket
import threading
from utils import *
from reward import RewardInterface, RewardModule
import subprocess
import os
import select


class Server:
    def __init__(self, host=HOST, port=PORT, broadcast_port = BROADCAST_PORT, reward_interface = None):
        self.host = host
        self.port = port
        self.broadcast_port = broadcast_port
        self.conn = None
        self.waiting = False
        self.on = False
        self.broadcast_thread = None
        self.reward_interface = RewardInterface() if not reward_interface else reward_interface
        
    def broadcast(self):
        client_threads = []
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((self.host, self.broadcast_port))
        sock.listen()
        while self.on:
            conn, (ip, _) =  sock.accept()
            t = threading.Thread(target = self.respond, args = (conn,))
            t.start()
            client_threads.append(t)
    
    def respond(self, conn):
        conn.setblocking(0)
        ready = select.select([conn], [], [], .5)
        if ready[0]:
            data = conn.recv(1024)
        else:
            conn.close()
            return
        if not data:
            return
        else:
            data = data.decode('utf-8').split(' ')
            if len(data)==2:
                mod, prop = data
                if prop == 'status':
                    if self.reward_interface.modules[mod].pump_thread:
                        reply = f'{self.reward_interface.modules[mod].pump_thread.status}'
                    else:
                        reply = 'None'
                elif prop == 'position':
                    reply = f'{self.reward_interface.modules[mod].pump.position}'
                else:
                    try:
                        reply = f'{getattr(self.reward_interface.modules[mod], prop)}'
                    except AttributeError:
                        reply = 'invalid request'
                conn.sendall(reply.encode('utf-8'))
            else:
                conn.sendall(b'invalid request')

    def start(self):
        self.on = True
        self.broadcast_thread = threading.Thread(target = self.broadcast)
        self.broadcast_thread.start()

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

            except (Exception, KeyboardInterrupt) as e:
                print(e)
                print('shutting down')
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

        data = data.decode('utf-8')
        data = data.split(' ')

        args = data[1:] if len(data)>1 else []
        command = data[0]

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
                    reply = f"{command} {mod} {amount} mL unsuccessful; reached the end of the track"
                except ValueError:
                    reply = f"invalid amount {amount} specified"
            self.conn.sendall(str.encode(reply))
            print("reply sent")
        elif command == 'FillSyringe':
            if len(args)<2:
                reply = "invalid command"
            else:
                try:
                    pump = args[0]
                    amount = float(args[1])
                    self.reward_interface.fill_syringe(pump, amount)
                    reply = f"{command} {pump} {amount} mL successful"
                except PumpInUse:
                    reply = f"{command} {pump} {amount} mL unsuccessful; pump is currently in use"
                except EndTrackError:
                    reply = f"{command} {pump} {amount} mL unsuccessful; reached the end of the track"
                except ValueError:
                    reply = f"invalid amount {amount} specified"
                except NoFillValve:
                    reply = f"No fill valve specified for pump {pump}"
            self.conn.sendall(str.encode(reply))
            print("reply sent")
        elif command == "SetAllSyringeTypes":
            if len(args)<1:
                reply = "invalid command"
            else:
                try:
                    syringeType = args[0]
                    self.reward_interface.change_syringe(syringeType = syringeType)
                    reply = f"{command} to {syringeType} successful"
                except:
                    reply = f"{command} to {syringeType} unsuccessful. invalid syringeType"
            self.conn.sendall(str.encode(reply))
            print("reply sent")
        elif command == "SetSyringeType":
            if len(args)<2:
                reply = "invalid command"
            else:
                try:
                    pump = args[0]
                    syringeType = args[1]
                    self.reward_interface.change_syringe(syringeType = syringeType, pump = pump)
                    reply = f"{command} {pump} to {syringeType} successful"
                except:
                    reply = f"{command} {pump} to {syringeType} unsuccessful. invalid syringeType"
            self.conn.sendall(str.encode(reply))
            print("reply sent")
        elif command == "SetAllSyringeIDs":
            if len(args)<1:
                reply = "invalid command"
            else:
                try:
                    ID = float(args[0])
                    self.reward_interface.change_syringe(ID = ID)
                    reply = f"{command} to {ID} successful"
                except ValueError:
                    reply = f"invalid ID {ID} specified"
            self.conn.sendall(str.encode(reply))
            print("reply sent")
        elif command == "SetSyringeID":
            if len(args)<2:
                reply = "invalid command"
            else:
                try:
                    pump = args[0]
                    ID = float(args[1])
                    self.reward_interface.change_syringe(ID = ID, pump = pump)
                    reply = f"{command} {pump} to {ID} successful"
                except ValueError:
                    reply = f"invalid ID {ID} specified"
            self.conn.sendall(str.encode(reply))
            print("reply sent")     
        else:
            self.conn.sendall(b"invalid command")
            print("reply sent")

    def shutdown(self):
        self.on = False
        if self.conn:
            self.conn.close()
            self.conn = None
        if self.broadcast_thread:
            self.broadcast_thread.join()
            self.broadcast_thread = None
        self.reward_interface = None

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
    server.start()
