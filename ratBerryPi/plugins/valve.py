from RPi import GPIO
import time
from ratBerryPi.plugins.base import BasePlugin
from ratBerryPi.utils import config_output, ResourceLocked

class Valve(BasePlugin):
    def __init__(self, name, parent, valvePin, NC = True):
        super(Valve, self).__init__(name, parent)
        self.valvePin = valvePin
        self.NC = NC
        self.valvePin = config_output(valvePin)
        self.valvePin.value = False

    @property
    def is_open(self):
        if self.NC:
            return self.valvePin.value
        else:
            return not self.valvePin.value

    def open(self):
        acquired = self.lock.acquire(False)
        if acquired:
            if not self.is_open:
                if self.NC:
                    self.valvePin.value = True
                else:
                    self.valvePin.value = False
                time.sleep(.05) # max response time for the valves is 20 ms
            self.lock.release()
        else:
            raise ResourceLocked(f"Valve {self.name} in use")

    def close(self):
        acquired = self.lock.acquire(False)
        if acquired:
            if self.is_open:
                if self.NC:
                    self.valvePin.value = False
                else:
                    self.valvePin.value = True
                time.sleep(.05) # max response time for the valves is 20 ms
            self.lock.release()
        else:
            raise ResourceLocked(f"Valve {self.name} in use")