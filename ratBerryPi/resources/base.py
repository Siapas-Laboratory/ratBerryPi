import threading
import logging
import typing

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
    
def acquire_many_locks(locks: typing.Union[list, dict]):
    """
    try to acquire all locks from a list
    if not return the lock that failed
    and release all acquired locks

    Args:
        locks: typing.Union[list, dict]
            list of dictionary of locks to acquire
    Returns:
        ret: 
            None if successful, key or index of unacquired lock
            otherwise
    """
    if isinstance(locks, dict):
        idx = list(locks.keys())
    else:
        idx = list(range(len(locks)))
    acqd = []
    for i in idx:
        acq = locks[i].acquire(False)
        if not acq:
            for j in acqd:
                locks[j].release()
            return i
        acqd.append(i)
    return None