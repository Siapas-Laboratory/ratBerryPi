HOST = '192.168.0.246'
PORT = 5562
ASYNC_PORT = 5563

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
    import os
    server_file = os.path.join(path, 'server.py')
    config_file = os.path.join(path, 'config.yaml')
    ssh = paramiko.SSHClient()
    ssh.load_system_host_keys()
    ssh.connect(host, username='pi')
    _, stdout, _ = ssh.exec_command(f"cd {path}; python3 server.py")
    running = True
    while running:
        try:
            out = stdout.readline()
            print(out)
        except KeyboardInterrupt:
            ssh.close()
            running = False
