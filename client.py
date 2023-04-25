import socket

#TODO: need something to check that the server is on
# need to 

def connect_client(host, port):
    try:
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client.connect((host, int(port)))
    except socket.error as msg:
        print(msg)
        client = None
    return client

def cli(client):
    while True:
        cmd = input("enter a command: ")
        client.sendall(cmd.encode('utf-8'))

if __name__=='__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default = 'localhost')
    parser.add_argument("--port", default = '5560')
    args = parser.parse_args()
    client = connect_client(args.host, args.port)
    if client is not None:
        cli(client)

