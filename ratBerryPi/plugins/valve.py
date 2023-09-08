from RPi import GPIO
import time
from .base import BasePlugin
from ..utils import config_output

class Valve(BasePlugin):
    def __init__(self, name, parent, valvePin, NC = True):
        super(Valve, self).__init__(name, parent)
        self.valvePin = valvePin
        self.NC = NC
        self.valvePin = config_output(valvePin)
        self.valvePin.value = False
        self.opened = not self.NC

    def open(self):
        if not self.opened:
            print(f'opening {self.valvePin}')
            if self.NC:
                self.valvePin.value = True
            else:
                self.valvePin.value = False
            time.sleep(.05) # max response time for the valves is 20 ms
            self.opened = True

    def close(self):
        if self.opened:
            print(f'closing {self.valvePin}')
            if self.NC:
                self.valvePin.value = False
            else:
                self.valvePin.value = True
            time.sleep(.05) # max response time for the valves is 20 ms
            self.opened = False
