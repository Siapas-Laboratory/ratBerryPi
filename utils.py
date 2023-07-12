HOST = '192.168.0.246'
PORT = 5560
ASYNC_PORT = 5561

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
    import subprocess
    import os
    proc = subprocess.run(f"ssh pi@{host} 'python3 {os.path.join(path, 'server.py')} --reward_config {os.path.join(path, 'config.yaml')}'", 
                          shell=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    while True:
        line = proc.stdout.readline()
        if not line:
            break
        print("test:", line.rstrip())