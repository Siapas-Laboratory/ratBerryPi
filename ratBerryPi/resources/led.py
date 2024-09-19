from .base import BaseResource
from ratBerryPi.utils import config_output
from typing import Union
from digitalio import DigitalInOut

class LED(BaseResource):
    """
    interface for controlling an LED

    ...
    Attributes:
        LEDPin (DigitalInOut)
            DigitalInOut object for controlling the GPIO
            pin associated to the LED
    """
    def __init__(self, name: str, parent, LEDPin: Union[str, int]):
        """
        Args:
            name:
                name of the LED
            parent:
                parent object associated with the lickometer
            LEDPin:
                name of GPIO pin to use to toggle the LED
        """
        super(LED, self).__init__(name, parent)
        self.LEDPin = config_output(LEDPin)
        self.LEDPin.value = False

    @property
    def on(self) -> bool:
        """
        flag indicating if the LED is on
        """
        return self.LEDPin.value

    def turn_on(self) -> None:
        """
        turn on the LED
        """
        self.LEDPin.value = True
        self.logger.info(f"{self.name}, on")
    
    def turn_off(self) -> None:
        """
        turn off the LED
        """
        self.LEDPin.value = False
        self.logger.info(f"{self.name}, off")