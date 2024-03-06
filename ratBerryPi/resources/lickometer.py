from datetime import datetime
import RPi.GPIO as GPIO
import threading
import time
from .base import BaseResource
from PyQt5.QtCore import pyqtSignal, QObject


class LickNotifier(QObject):
    new_lick = pyqtSignal(bool)

class Lickometer(BaseResource):
    def __init__(self, name, parent, lickPin, burst_thresh = 0.5, update_interval = .01):

        super(Lickometer, self).__init__(name, parent)
        self.lickPin = lickPin
        self.licks = 0
        self.in_burst = False
        self.burst_lick = 0
        self.last_lick = datetime.now()
        self.burst_thresh = burst_thresh
        self.lick_notifier = LickNotifier()


        if parent:
            self.on = self.parent.on
        else:
            self.on = threading.Event()
            self.on.set()
        self.update_interval = update_interval

        GPIO.setup(self.lickPin, GPIO.IN, GPIO.PUD_OFF)
        GPIO.add_event_detect(self.lickPin, GPIO.RISING, callback=self.increment_licks)

        self.burst_thread = threading.Thread(target = self.monitor_bursts)
        self.burst_thread.start()
    
    def increment_licks(self, x):
        self.logger.info(f"{self.name}, lick") 
        self.licks += 1
        self.burst_lick +=1
        self.last_lick = datetime.now()
        self.lick_notifier.new_lick.emit(self.licks) 

    def reset_licks(self):
        self.licks = 0

    def monitor_bursts(self):
        while not self.on.is_set():
            # wait for the on signal
            time.sleep(.1)
        while self.on.is_set():
            if (datetime.now() - self.last_lick).total_seconds()>self.burst_thresh:
                self.burst_lick = 0
                self.in_burst = False
            else:
                self.in_burst = True
            time.sleep(self.update_interval)
            
    def __del__(self):
        if self.on.is_set(): self.on.clear()
        self.burst_thread.join()