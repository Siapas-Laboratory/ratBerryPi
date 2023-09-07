import RPi.GPIO as GPIO
from .base import BasePlugin
import sys
sys.path.append("../")
from utils import config_output

class LED(BasePlugin):
    #TODO: need s function to flash the led for a specified amount of time
    def __init__(self, name, parent, LEDPin):
        super(LED, self).__init__(name, parent)
        self.name = name
        self.LEDPin = config_output(LEDPin)
        self.LEDPin.value = False
        self.on = False
    
    def turn_on(self):
        self.LEDPin.value = True
        self.on = True
    
    def turn_off(self):
        self.LEDPin.value = False
        self.on = False