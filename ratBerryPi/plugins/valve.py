from RPi import GPIO
import time
from ratBerryPi.plugins.base import BasePlugin
from ratBerryPi.utils import config_output

class Valve(BasePlugin):
    def __init__(self, name, parent, valvePin, NC = True):
        super(Valve, self).__init__(name, parent)
        self.valvePin = valvePin
        self.NC = NC
        self.valvePin = config_output(valvePin)
        self.valvePin.value = False
        self.is_open = not self.NC

    @property
    def is_open(self):
        if self.NC:
            return self.valvePin.value
        else:
            return not self.valvePin.value

    def open(self):
        if not self.is_open:
            if self.NC:
                self.valvePin.value = True
            else:
                self.valvePin.value = False
            time.sleep(.05) # max response time for the valves is 20 ms

    def close(self):
        if self.is_open:
            if self.NC:
                self.valvePin.value = False
            else:
                self.valvePin.value = True
            time.sleep(.05) # max response time for the valves is 20 ms