from abc import ABC, abstractmethod
import threading
import RPi.GPIO as GPIO

class BaseInterface(ABC):
    
    def __init__(self, on:threading.Event):
        super(BaseInterface, self).__init__()
        GPIO.setmode(GPIO.BCM)
        self.on = on

    
    @abstractmethod
    def start(self):
        pass

    @abstractmethod
    def stop(self):
        pass

    