import socket
import threading
import select
import errno
from reward import RewardInterface, PumpInUse, NoLickometer, NoFillValve, NoLED, NoSpeaker
from pump import EndTrackError
from plugins import lickometer, audio, LED
import yaml
import pickle


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

            except  KeyboardInterrupt:
                print('shutting down')
                self.shutdown()
            except Exception as e:
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

        args = pickle.loads(data)
        command = args.pop('command')
        if command == "EXIT":
            print("client disconnected")
            self.waiting = False
            return
        elif command == "KILL":
            print("server is shutting down")
            self.on = False
            self.waiting = False
            return
        elif command == 'CheckServer':
            reply = '1'
        else:
            try:
                f = getattr(self.reward_interface, command)
                f(**args)
                reply = '1'
            except (ValueError, TypeError, AttributeError, KeyError):
                reply = '2'
            except NoLickometer:
                reply = '3'
            except NoLED:
                reply = '4'
            except NoSpeaker:
                reply = '5'
            except PumpInUse:
                reply = '6'
            except EndTrackError:
                reply = '7'

        self.conn.sendall(str.encode(reply))
        print('reply sent')

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
