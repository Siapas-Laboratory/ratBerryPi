from abc import ABC, abstractmethod

class BaseInterface(ABC):
    
    def __init__(self):
        super(BaseInterface, self).__init__()
    
    @abstractmethod
    def start(self):
        pass

    @abstractmethod
    def stop(self):
        pass

    