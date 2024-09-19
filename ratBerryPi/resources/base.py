import threading
import logging

class BaseResource:
    """
    a base resource class that should be sub-classed 
    by any other resources to be used by a module of the reward interface

    ...

    Attributes:
        parent:
            the parent object that this resource is associated to
        lock (threading.Rlock):
            a re-entrant lock that allows for reservation of this resource
            by a thread that is accessing it
        logger (logging.Logger):
            logger for logging any messages produced by the resource
            in practice this is the interface logger
    """
    def __init__(self, name, parent):
        self.name = name
        self.parent = parent
        self.lock = threading.RLock()
        # use the interface level logger
        self.logger = logging.getLogger('ratBerryPi.interface')

class ResourceLocked(BaseException):
    def __init__(self, msg):
        self.message = msg
    def __str__(self):
        return self.message