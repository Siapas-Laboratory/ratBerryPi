import json
from ratBerryPi.remote.client import Client
from ratBerryPi.remote.server import Server
import os
import logging
from datetime import datetime


def create_client(host, port=5562):

    client = Client(host, port)
    client.new_channel("cli")

    running = True

    while running:
        req = input("enter a request: ").split()
        command = req.pop(0)
        if command.lower() == 'exit':
            client.close_all_channels()
            running = False
        elif command.lower() == 'get':
            print(client.get(req[-1], channel = 'cli'))
        elif len(req)%2 == 0:
            args = {}
            for i in range(0, len(req), 2):
                try:
                    args[req[i]] = json.loads(req[i+1])
                except json.decoder.JSONDecodeError:
                    args[req[i]] = req[i+1]
            print(client.run_command(command, args, channel = 'cli'))
        else:
            print('invalid command')

def start_server(port=5562):

    log_dir = os.path.join(os.path.expanduser('~'), ".ratBerryPi", "logs")
    os.makedirs(log_dir, exist_ok = True)
    logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.DEBUG, 
                        filename=os.path.join(log_dir, f"{datetime.now().strftime('%m-%d-%Y-%H-%M-%S.log')}"))
    logging.getLogger().addHandler(logging.StreamHandler())

    server = Server(port)
    server.start()

def main():
    import argparse

    parser = argparse.ArgumentParser(prog="ratBerryPi")
    parser.add_argument("--port", type=int, default = 5562)

    subparsers = parser.add_subparsers(title = "command", required = True)
    server_parser = subparsers.add_parser("server")
    server_parser.set_defaults(func=start_server)

    client_parser = subparsers.add_parser("client")
    client_parser.add_argument("--host", default="localhost")
    client_parser.set_defaults(func=create_client)

    args = vars(parser.parse_args())
    func = args.pop("func")
    func(**args)

if __name__=='__main__': main()