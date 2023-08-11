import socket
import threading
import select
import errno
from reward import RewardInterface, PumpInUse, NoLickometer, NoFillValve, NoLED, NoSpeaker
from pump import EndTrackError
from plugins import lickometer, audio, LED
import yaml


class Server:
    def __init__(self, reward_interface = None):
        self.host = socket.gethostname()
        with open('config.yaml', 'r') as f:
            config = yaml.safe_load(f)
        self.port = config['PORT']
        self.broadcast_port = config['BROADCAST_PORT']
        self.conn = None
        self.waiting = False
        self.on = False
        self.broadcast_thread = None
        self.reward_interface = reward_interface if reward_interface else RewardInterface()
        
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
            try:
                data = conn.recv(1024)
            except socket.error as e:
                if e.errno != errno.ECONNRESET:
                    raise e
                return
        else:
            conn.close()
            return
        if not data:
            conn.close()
            return
        else:
            data_str = data.decode('utf-8')
            data = data_str.split(' ')
            if len(data)==2:
                mod, prop = data
                if prop == 'status':
                    if self.reward_interface.modules[mod].pump_thread:
                        reply = f'{self.reward_interface.modules[mod].pump_thread.status}'
                    else:
                        reply = 'None'
                elif prop == 'position':
                    reply = f'{self.reward_interface.modules[mod].pump.position}'
                elif prop == 'licks':
                    try:
                        reply = f'{self.reward_interface.modules[mod].lickometer.licks}'
                    except AttributeError as e:
                        reply = f'invalid lick request for "{mod}"'
                else:
                    try:
                        reply = f'{getattr(self.reward_interface.modules[mod], prop)}'
                    except AttributeError as e:
                        reply = f'invalid prop request for "{mod}"'
                        print(e)
                conn.sendall(reply.encode('utf-8'))
            else:
                reply = f'invalid request "{data_str}"'
                conn.sendall(reply.encode('utf-8'))

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
                if e.errno != errno.ECONNRESET:
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
        # resetting the lick count
        # getting the module names


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
                except ValueError:
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
                except ValueError:
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

        elif command == "PlayTone":
            if len(args)<3:
                reply = "invalid command"
            else:
                freq = args[1]
                dur = args[2]
                volume = args[3] if len(args)>3 else 1

                if args[0] in self.reward_interface.plugins:
                    speaker = self.reward_interface.plugins[args[0]]
                    if not isinstance(speaker, audio.Speaker):
                        reply = f"{args[0]} not a speaker"
                    else:
                        speaker.play_tone(freq, dur, volume)
                        reply = f"{command} {speaker} {freq} {dur} {volume} successful"
                
                elif args[0] in self.reward_interface.modules:
                    mod = args[0]
                    try:
                        self.reward_interface.modules[mod].play_tone(freq, dur, volume)
                        reply = f"{command} {mod} {freq} {dur} {volume} successful"
                    except NoSpeaker:
                        reply = f"no speaker on module {mod}"

                else:
                    reply = f"unrecognized speaker or module {args[0]}"

        elif command == "ToggleLED":
            if len(args)<2:
                reply = "invalid command"
            else:
                on = args[1].lower() == 'on'
                if args[0] in self.reward_interface.plugins:
                    led = self.reward_interface.plugins[args[0]]
                    if not isinstance(led, LED.LED):
                        reply = f"{args[0]} not an LED"
                    else:  
                        if on: led.on()
                        else: led.off()
                        reply = f"{command} {args[0]} {args[1]} successful"
                elif args[0] in self.reward_interface.modules:
                    mod = args[0]
                    try:
                        self.reward_interface.modules[mod].toggle_LED(on)
                        reply = f"{command} {args[0]} {args[1]} successful"
                    except NoLED:
                        reply = f"no LED on module {mod}"

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
    from reward import RewardInterface

    parser = argparse.ArgumentParser()
    parser.add_argument('--burst_thresh', default = 0.5,
                         help = 'time threshold in seconds on the inter lick interval for starting a new burst, consequently also the time after a lick before stopping the pump')
    parser.add_argument('--reward_thresh', default = 3, help = 'number of licks within a burst required to start the pump')
    
    args = parser.parse_args()

    reward_interface = RewardInterface(args.burst_thresh, args.reward_thresh)

    server = Server(reward_interface=reward_interface)
    server.start()
