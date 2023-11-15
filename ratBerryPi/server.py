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
        sock.bind(('', self.port))
        sock.listen()

        while self.on.is_set():
            try:
                ready = select.select([sock], [],[], 0.1)
                if ready[0]:
                    conn, (ip, port) =  sock.accept() # (this is blocking)
                    t = threading.Thread(target = self.handle_client, args = (conn,))
                    logging.debug(f'connection made with {ip} on port {port}')
                    t.start()
                    self.client_threads.append(t)
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
        host, port = conn.getpeername() 
        while self.on.is_set():
            try:
                ready = select.select([conn], [],[], 0.1)
                if ready[0]:
                    data = conn.recv(1024)
                    if not data: # if the client left close the connection
                        logging.debug(f'connection closed by {host} on port {port}')
                        conn.close()
                        return
                    else: # otherwise handle the request
                        self.handle_request(conn, data)
            except socket.error as e:
                if e.errno == errno.ECONNRESET:
                    logging.warning(f'connection abruptly reset by {host} on port {port}')
                else:
                    logging.exception(e)
                return
        logging.debug(f'closing connection with {host} on port {port}')
        conn.shutdown(socket.SHUT_RDWR)
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
        if command == "KILL":
            logging.info("client requested for the server to shut down")
            self.on.clear()
            return
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
                
    def shutdown(self):
        """
        shutdown the server
        """
        logging.info('shutting down server...')
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
