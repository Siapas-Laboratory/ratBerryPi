import threading

class BasePlugin:
    def __init__(self, name, parent):
        self.name = name
        self.parent = parent
        self.lock = threading.Lock()