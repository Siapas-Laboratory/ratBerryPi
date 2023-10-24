import threading

class BaseResource:
    def __init__(self, name, parent):
        self.name = name
        self.parent = parent
        self.lock = threading.RLock()

class ResourceLocked(BaseException):
    def __init__(self, msg):
        self.message = msg
    def __str__(self):
        return self.message