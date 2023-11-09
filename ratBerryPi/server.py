from ratBerryPi.interfaces import *

import socket
import threading
import select
import errno
import json
import logging
from datetime import datetime
import os


class Server:
    def __init__(self, port:int, broadcast_port:int, interface_cls:BaseInterface):

        self.port = port
        self.broadcast_port = broadcast_port

        # set some default values
        self.conn = None
        self.waiting = False
        self.on = threading.Event()
        self.broadcast_thread = None

        # create an instance of the reward interface
        assert issubclass(interface_cls, BaseInterface), "interface must be a subclass of BaseInterface"
        self.interface = interface_cls(self.on)


    def start(self):
        """
        start the server  
        """

        self.on.set()
        self.interface.start()
        # spawn a thread to broadcast information about the interface
        self.broadcast_thread = threading.Thread(target = self.broadcast)
        self.broadcast_thread.start()

        while self.on.is_set():
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                sock.settimeout(0.1)
                sock.bind(('', self.port))
                sock.listen()
                self.conn, (_, _) =  sock.accept() # (this is blocking)
                sock.close()
                logging.info('waiting for data')
                self.waiting = True
                self.interface.record()
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
                self.interface.stop_recording()

            except socket.timeout:
                pass
            except KeyboardInterrupt:
                self.shutdown()
            except socket.error as e:
                if e.errno == errno.ECONNRESET:
                    logging.warning("Connection abruptly reset by peer")
                else:
                    logging.exception(e)
                    self.shutdown()
            except Exception as e:
                logging.exception(e)
                self.shutdown()
        
    def handle_request(self, data):
        """
        function to handle requests sent to the server

        Args:
        -----
        data: bytes
            utf-8 encoded request sent to the server 
        """

        args = json.loads(data)
        command = args.pop('command')
        if command == "EXIT":
            logging.info("client disconnected")
            self.waiting = False
            return
        elif command == "KILL":
            logging.info("client requested for the server to shut down")
            self.on.clear()
            self.waiting = False
            return
        elif command == 'CheckServer':
            reply = '1'
        else:
            try:
                f = getattr(self.interface, command)
                f(**args)
                reply = '1'
            except Exception as e:
                logging.exception(e)
                reply = '2'

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
        sock.settimeout(0.1)
        sock.bind(('', self.broadcast_port))
        sock.listen()
        while self.on.is_set():
            try:
                conn, _ =  sock.accept()
                t = threading.Thread(target = self.respond, args = (conn,))
                logging.debug('broad connection made')
                t.start()
                client_threads.append(t)
            except socket.timeout:
                pass
            except Exception as e:
                logging.exception(e)
                break
        for t in client_threads: t.join()
            
    def respond(self, conn):
        """
        respond to requests for information about the reward interface

        Args:
        -----
        conn: socket.socket
            socket for sending and receiving data
        """
        while self.on.is_set():
            try:
                # receive the request from the client
                data = conn.recv(1024)
            except socket.error as e:
                if e.errno == errno.ECONNRESET:
                    logging.warning("Connection abruptly reset by peer")
                else:
                    logging.exception(e)
                return
            if not data: # if the client left close the connection
                logging.debug('no data')
                conn.close()
                return
            else: # otherwise handle the request
                try:
                    data = data.decode()
                    reply = json.dumps(eval(f"self.interface.{data}")).encode()
                except AttributeError as e:
                    logging.debug(e)
                    reply = f'invalid request'.encode()
                finally:
                    conn.sendall(reply)       

    def shutdown(self):
        """
        shutdown the server
        """
        logging.info('shutting down...')
        self.on.clear()
        self.waiting = False
        if self.conn:
            self.conn.close()
            self.conn = None
        if self.broadcast_thread:
            self.broadcast_thread.join()
            self.broadcast_thread = None
        self.interface.stop()
        self.interface = None

    def __del__(self):
        if self.on.is_set(): self.shutdown()

if __name__ == '__main__':

    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("-p","--port", default = 5562)
    parser.add_argument("-b","--broadcast_port", default = 5563)
    parser.add_argument("-i","--interface_type", default = "RewardInterface")

    args = parser.parse_args()

    log_dir = os.path.join(os.path.expanduser('~'), ".ratBerryPi", "logs")
    os.makedirs(log_dir, exist_ok = True)
    logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.DEBUG, 
                        filename=os.path.join(log_dir, f"{datetime.now().strftime('%m-%d-%Y-%H-%M-%S.log')}"))
    logging.getLogger().addHandler(logging.StreamHandler())

    interface_cls = globals()[args.interface_type]
    server = Server(args.port, args.broadcast_port, interface_cls)
    server.start()
