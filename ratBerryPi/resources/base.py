import threading
import logging

class BaseResource:
    def __init__(self, name, parent):
        self.name = name
        self.parent = parent
        self.lock = threading.RLock()
        # use the interface level logger
        self.logger = logging.getLogger('ratBerryPi.interfaces.base')

class ResourceLocked(BaseException):
    def __init__(self, msg):
        self.message = msg
    def __str__(self):
        return self.message