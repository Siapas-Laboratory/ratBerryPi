from ratBerryPi.resources.base import BaseResource
from ratBerryPi.utils import config_output

class LED(BaseResource):
    #TODO: need s function to flash the led for a specified amount of time
    def __init__(self, name, parent, LEDPin):
        super(LED, self).__init__(name, parent)
        self.name = name
        self.LEDPin = config_output(LEDPin)
        self.LEDPin.value = False

    @property
    def on(self):
        return self.LEDPin.value

    def turn_on(self):
        self.LEDPin.value = True
        self.logger.info(f"{self.name}, on")
    
    def turn_off(self):
        self.LEDPin.value = False
        self.logger.info(f"{self.name}, off")