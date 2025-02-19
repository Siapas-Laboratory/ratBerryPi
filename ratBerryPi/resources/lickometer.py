from datetime import datetime
from gpiozero import DigitalInputDevice

import threading
import time
from .base import BaseResource
from PyQt5.QtCore import pyqtSignal, QObject
from typing import Union
import logging

logger = logging.getLogger(__name__)

class LickNotifier(QObject):
    new_lick = pyqtSignal(bool)

class Lickometer(BaseResource):
    """
    lickometer interface

    ...

    Attributes:
        licks(int): 
            current lick count
        lickPin (DigitalInputDevice): 
            reference to gpiozero interface to the pin associated to the lickometer
        lick_notifier (LickNotifier):
            QObject which emits a signal whenever a new lick is detected

    """
    def __init__(self, name: str, parent, lickPin: Union[int, DigitalInputDevice]):
        """
        Args:
            name:
                name of lickometer
            parent:
                parent object associated with the lickometer
            lickPin:
                either the name of a GPIO pin to detect licks on
                or a reference to a gpiozero DigitalInputDevice 
                to use for lick detection
        """

        super(Lickometer, self).__init__(name, parent)
        self.lickPin = lickPin
        self.licks = 0
        self.lick_notifier = LickNotifier()

        if isinstance(self.lickPin, int):
            self.lickPin = DigitalInputDevice(self.lickPin, pull_up = None, active_state = True)
            self.lickPin.when_activated = self.increment_licks
    
    def increment_licks(self, x):
        logger.info(f"{self.name}, lick") 
        self.licks += 1
        self.lick_notifier.new_lick.emit(self.licks) 

    def reset_licks(self):
        self.licks = 0