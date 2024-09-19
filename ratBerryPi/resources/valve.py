import time
from .base import BaseResource, ResourceLocked
from ratBerryPi.utils import config_output
from digitalio import DigitalInOut


class Valve(BaseResource):
    """
    interface for controlling a solenoid valve

    ...

    Attributes:
        NC (bool):
            flag indicating if the valve is a normally-closed
            valve
        valvePin (DigitalInOut)
            DigitalInOut object for controlling the GPIO
            pin associated to the valve
    """
    
    def __init__(self, name: str, parent, valvePin: Union[int, str], NC: bool = True):
        """
        Args:
            name:
                name of the valve
            parent:
                parent object associated with the Valve
            valvePin:
                name of GPIO pin to use to toggle the valve
            NC:
                flag indicating if the valve is a normally-closed
                valve
        """
        super(Valve, self).__init__(name, parent)
        self.valvePin = valvePin
        self.NC = NC
        self.valvePin = config_output(valvePin)
        self.valvePin.value = False

    @property
    def is_open(self) -> None:
        """
        flag indicating if the valve is open
        """
        if self.NC:
            return self.valvePin.value
        else:
            return not self.valvePin.value

    def open(self) -> None:
        """
        open the valve
        """
        if not self.is_open:
            acquired = self.lock.acquire(False)
            if acquired:
                if self.NC:
                    self.valvePin.value = True
                else:
                    self.valvePin.value = False
                self.logger.info(f"{self.name}, open")
                time.sleep(.05) # max response time for the valves is 20 ms
                self.lock.release()
            else:
                raise ResourceLocked(f"Valve {self.name} in use")

    def close(self) -> None:
        """
        close the valve
        """
        if self.is_open:
            acquired = self.lock.acquire(False)
            if acquired:
                if self.NC:
                    self.valvePin.value = False
                else:
                    self.valvePin.value = True
                self.logger.info(f"{self.name}, close")
                time.sleep(.05) # max response time for the valves is 20 ms
                self.lock.release()
            else:
                raise ResourceLocked(f"Valve {self.name} in use")