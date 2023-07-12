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