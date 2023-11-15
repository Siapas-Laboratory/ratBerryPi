import socket
import json
import logging
import typing

logger = logging.getLogger(__name__)

class Client:
    """
    a client which manages multiple channels for 
    communicating with the server
    
    Attributes:

    host: str
    port: int
    channels: Dict[str, Channel]


    Methods:

    get(req, channel)
    kill()
    close_channel(channel)
    close_all_channels()
    new_channel(name)
    run_command(command, args, channel)

    """

    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self._channels = {}
    
    @property
    def channels(self):
        """
        a dictionary mapping names to all channels 
        for communicating with the server
        """
        return self._channels

    def get(self, req: str, channel: str = None) -> typing.Any:
        """
        get an attribute of the interface running on the server

        Args:
            req: str
                a string indicating the attribute to get from the server
                this string should be everything that would come after the
                period when directly accessing an instance of the interface
                class. for example, if we want the position of a pump named 
                pump1 when using the reward interface, the request would be
                'pumps["pump1"].position'
            channel: str, optional
                the communication channel to use when getting the attribute.
                the default behavior is to temporarily create a new channel to
                get the information
        Returns:
            reply: typing.Any
                the requested attriibute
        """
        reply = self.run_command("GET", args = {'req': req}, channel = channel)
        return json.loads(reply)

    def kill(self) -> None:
        """
        kill the server
        """
        self.run_command('KILL')

    def close_channel(self, channel: str) -> None:
        """
        close a specified channel for communicating with the server
        """
        self.channels[channel].close()
        del self._channels[channel]
    
    def close_all_channels(self) -> None:
        """
        close all channels for communicating with the server
        """
        for i in list(self.channels.keys()):
            self.close_channel(i)

    def new_channel(self, name: str) -> None:
        """
        create a new channel for communicating with the server

        Args:
            name: str
                name for referencing the newly created channel
        """
        if name not in self.channels:
            self._channels[name] = Channel(self.host, self.port, name)
        else:
            raise ValueError("channel already exists")

    def run_command(self, command: str, args: dict = {}, channel: str = None) -> str:
        """
        wrapper for run_command method of Channel class. 
        either creates a temporary channel to run a command or
        uses a specified channel.

        Args:
            command: str
                a method of the interface class to call
            args: dict, optional
                a dictionary mapping the names of any arguments
                that the method takes to the desired values. 
                (default is an empty dictionary. if the requested method
                has positional arguments this will raise an error)
            channel:str, optional
                the communication channel to use when running the command.
                the default behavior is to temporarily create a new channel
        Returns:
            reply: str
                the response from the server. this is usually either 'SUCCESS'
                or 'ERROR' followed by an end character, unless the command is
                'GET', in which case it will be a json serialized string representing
                the requested data
        """
        try:
            if channel:
                return self.channels[channel].run_command(command, args)
            else:
                c = Channel(self.host, self.port)
                reply = c.run_command(command, args)
                c.close()
                return reply
        except ConnectionAbortedError:
            if channel: del self._channels[channel]
            raise ConnectionAbortedError

    def __del__(self):
        """
        make sure we close all channels before deleting
        """
        self.close_all_channels()

class Channel:
    """
    a channel for communicating with the server
    
    Attributes:

    host: str
    port: int
    connected: bool


    Methods:

    close(channel)
    run_command(command, args)

    """

    def __init__(self, host: str, port: int, name: str = None):
        self._conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._conn.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._conn.connect((host, port))
        self.name = name
        self.connected = True
    
    def run_command(self, command: str, args: dict = {}) -> str:
        """
        run a command on the interface running on the server

        Args:
            command: str
                a method of the interface class to call
            args: dict, optional
                a dictionary mapping the names of any arguments
                that the method takes to the desired values. 
                (default is an empty dictionary. if the requested method
                has positional arguments this will raise an error)
        Returns:
            reply: str
                the response from the server. this is usually either 'SUCCESS'
                or 'ERROR' followed by an end character, unless the command is
                'GET', in which case it will be a json serialized string representing
                the requested data
        """

        if not self.connected:
            raise ConnectionError
        args['command'] = command
        command = json.dumps(args).encode()
        self._conn.sendall(command)
        reply = self._conn.recv(1024)

        if reply:
            return reply.decode('utf-8')
        else:
            logger.debug(f"connection closed on the server side")
            self.close()
            raise ConnectionAbortedError
        
    def close(self) -> None:
        """
        close the connection if it is not already closed
        """
        if self.connected:
            logger.debug(f"closing channel '{self.name}'")
            self._conn.close()
            self.connected = False

    def __del__(self):
        """
        make sure we close the connection before deleting the channel
        """
        self.close()

if __name__=='__main__':
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("host")
    parser.add_argument("--port", default = 5562)

    args = parser.parse_args()
    client = Client(args.host, int(args.port))
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