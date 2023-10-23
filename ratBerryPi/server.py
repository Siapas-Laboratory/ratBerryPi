#TODO: consolidate some of these errors
from ratBerryPi.reward import RewardInterface,NoLickometer, NoLED, NoSpeaker
from ratBerryPi.pump import EndTrackError, PumpNotEnabled
from ratBerryPi.utils import ResourceLocked

import socket
import threading
import select
import errno
import pickle
import logging
from datetime import datetime
import os


class Server:
    def __init__(self, port, broadcast_port):

        self.port = port
        self.broadcast_port = broadcast_port

        # set some default values
        self.conn = None
        self.waiting = False
        self.on = False
        self.broadcast_thread = None

        # create an instance of the reward interface
        self.reward_interface =  RewardInterface()


    def start(self):
        """
        start the server  
        """

        self.on = True
        # spawn a thread to broadcast information about the interface
        self.broadcast_thread = threading.Thread(target = self.broadcast)
        self.broadcast_thread.start()

        while self.on:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                logging.info(f'binding port {self.port}')
                sock.bind(('', self.port))
                sock.listen()
                logging.info('waiting for connections')
                self.conn, (_, _) =  sock.accept() # (this is blocking)
                sock.close()
                logging.info('waiting for data')
                self.waiting = True
                self.reward_interface.record()
                while self.waiting:
                    ready = select.select([self.conn], [], [], 0.5)
                    if ready[0]:
                        data = self.conn.recv(1024)
                        if not data:
                            self.waiting = False
                        else:
                            self.handle_request(data)
                self.conn.close()
                self.conn = None
                self.reward_interface.save()

            except KeyboardInterrupt:
                logging.info('shutting down')
                self.shutdown()
            except socket.error as e:
                if e.errno != errno.ECONNRESET:
                    logging.debug(e)
                    logging.info('shutting down')
                    self.shutdown()
            except Exception as e:
                if e.errno != errno.ECONNRESET:
                    logging.debug(e)
                    logging.info('shutting down')
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
            logging.info("client disconnected")
            self.waiting = False
            return
        elif command == "KILL":
            logging.info("client requested for the server to shut down")
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
            except (ValueError, TypeError, AttributeError, KeyError) as e:
                logging.exception(e)
                reply = '2'
            except NoLickometer as e:
                logging.exception(e)
                reply = '3'
            except NoLED as e:
                logging.exception(e)
                reply = '4'
            except NoSpeaker as e:
                logging.exception(e)
                reply = '5'
            except ResourceLocked as e:
                logging.exception(e)
                reply = '6'
            except EndTrackError as e:
                logging.exception(e)
                reply = '7'

        self.conn.sendall(str.encode(reply))
        logging.info('reply sent')

    def broadcast(self):
        """
        bind a socket to listen for requests for information
        about the reward interface
        """

        client_threads = [] # TODO: need to dynamically remove items from this list
        # alternatively use a threadpool??
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(('', self.broadcast_port))
        sock.listen()
        while self.on:
            try:
                conn, _ =  sock.accept()
                t = threading.Thread(target = self.respond, args = (conn,))
                logging.debug('broad connection made')
                t.start()
                client_threads.append(t)
            except KeyboardInterrupt:
                break
            except Exception as e:
                if e.errno != errno.ECONNRESET:
                    break
            
    def respond(self, conn):
        """
        respond to requests for information about the reward interface

        Args:
        -----
        conn: socket.socket
            socket for sending and receiving data
        """
        while self.on:
            try:
                # receive the request from the client
                data = conn.recv(1024)
            except socket.error as e:
                logging.debug(e)
                if e.errno != errno.ECONNRESET:
                    raise e
                return
            if not data: # if the client left close the connection
                logging.debug('no data')
                conn.close()
                return
            else: # otherwise handle the request
                try:
                    data = data.decode()
                    reply = pickle.dumps(eval(f"self.reward_interface.{data}"))
                except AttributeError as e:
                    logging.debug(e)
                    reply = f'invalid request'.encode()
                finally:
                    conn.sendall(reply)       

    def shutdown(self):
        """
        shutdown the server
        """
        self.on = False
        self.waiting = False
        if self.conn:
            self.conn.close()
            self.conn = None
        if self.broadcast_thread:
            self.broadcast_thread.join()
            self.broadcast_thread = None
        self.reward_interface.stop()
        self.reward_interface = None

    def __del__(self):
        self.shutdown()

if __name__ == '__main__':

    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", default = 5562)
    parser.add_argument("--broadcast_port", default = 5563)

    args = parser.parse_args()

    log_dir = os.path.join(os.path.expanduser('~'), ".ratBerryPi", "logs")
    os.makedirs(log_dir, exist_ok = True)
    logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.DEBUG, 
                        filename=os.path.join(log_dir, f"{datetime.now().strftime('%m-%d-%Y-%H-%M-%S.log')}"))
    logging.getLogger().addHandler(logging.StreamHandler())

    server = Server(args.port, args.broadcast_port)
    server.start()
