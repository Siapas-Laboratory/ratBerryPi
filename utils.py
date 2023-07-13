HOST = '192.168.0.246'
PORT = 5562
BROADCAST_PORT = 5563


class EndTrackError(Exception):
    """reached end of track"""
    pass
class PumpNotEnabled(Exception):
    pass

class NoLickometer(Exception):
    pass

class PumpInUse(Exception):
    pass

class NoFillValve(Exception):
    pass


def remote_boot(host=HOST, path = '~/Downloads/rpi-reward-module'):
    import paramiko
    import threading

    class server_thread(threading.Thread):
        def __init__(self):
            super(server_thread, self).__init__()
            
        def run(self):
            ssh = paramiko.SSHClient()
            ssh.load_system_host_keys()
            ssh.connect(host, username='pi')
            transport = ssh.get_transport()
            transport.set_keepalive(1) 
            ssh.exec_command(f"cd {path}; python3 server.py")
            self.running = True   
            while self.running:
                pass

        def join(self):
            self.running = False
            super(server_thread, self).join()

    t = server_thread()
    t.start()
    return t