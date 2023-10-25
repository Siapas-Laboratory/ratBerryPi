from abc import ABC, abstractmethod
import threading
import RPi.GPIO as GPIO

class BaseInterface:
    
    def __init__(self, on:threading.Event):
        super(BaseInterface, self).__init__()
        GPIO.setmode(GPIO.BCM)
        self.on = on
        self.recording = False

    def start(self):
        if not self.on.is_set(): self.on.set()

    def record(self):
        self.recording = True

    def save(self):
        pass

    def stop(self):
        GPIO.cleanup()

    