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
    def __init__(self, port:int, interface_cls:BaseInterface):

        self.port = port
        self.on = threading.Event()

        # create an instance of the reward interface
        assert issubclass(interface_cls, BaseInterface), "interface must be a subclass of BaseInterface"
        self.interface = interface_cls(self.on)


    def start(self):
        """
        start the server  
        """

        self.on.set()
        self.interface.start()
        self.client_threads = []

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.settimeout(0.1)
        sock.bind(('', self.port))
        sock.listen()

        while self.on.is_set():
            try:
                conn, (_, _) =  sock.accept() # (this is blocking)
                t = threading.Thread(target = self.handle_client, args = (conn,))
                logging.debug('broad connection made')
                t.start()
                self.client_threads.append(t)
            except socket.timeout:
                pass
            except KeyboardInterrupt:
                self.shutdown()
            except Exception as e:
                logging.exception(e)
                self.shutdown()

    def handle_client(self, conn):
        """
        handle clients

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
                self.handle_request(conn, data)
        conn.close()

    
    def handle_request(self, conn, data):
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
            conn.close()
            return
        elif command == "KILL":
            logging.info("client requested for the server to shut down")
            self.on.clear()
            return
        elif command == 'CheckServer':
            reply = json.dumps(True)
        elif command == 'GET':
            reply = json.dumps(eval(f"self.interface.{args['req']}"))
        else:
            try:
                f = getattr(self.interface, command)
                res = f(**args)
                reply = 'SUCCESS' if not res else json.dumps(res)
            except Exception as e:
                logging.exception(e)
                reply = 'ERROR'

        conn.sendall(str.encode(reply + '\n'))
        logging.info('reply sent')
                
    def shutdown(self):
        """
        shutdown the server
        """
        logging.info('shutting down...')
        self.on.clear()
        self.interface.stop()
        self.interface = None

    def __del__(self):
        if self.on.is_set():
            self.shutdown()

if __name__ == '__main__':

    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("-p","--port", default = 5562)
    parser.add_argument("-i","--interface_type", default = "RewardInterface")

    args = parser.parse_args()

    log_dir = os.path.join(os.path.expanduser('~'), ".ratBerryPi", "logs")
    os.makedirs(log_dir, exist_ok = True)
    logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.DEBUG, 
                        filename=os.path.join(log_dir, f"{datetime.now().strftime('%m-%d-%Y-%H-%M-%S.log')}"))
    logging.getLogger().addHandler(logging.StreamHandler())

    interface_cls = globals()[args.interface_type]
    server = Server(args.port, interface_cls)
    server.start()
