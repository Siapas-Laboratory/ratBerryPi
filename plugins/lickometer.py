from datetime import datetime
import RPi.GPIO as GPIO
import threading
import time
import os


class Lickometer:
    def __init__(self, lickPin, burst_thresh = 0.5, update_interval = .01, parent = None):
        self.lickPin = lickPin
        self.licks = 0
        self.in_burst = False
        self.burst_lick = 0
        self.last_lick = datetime.now()
        self.burst_thresh = burst_thresh
        self.on = True
        self.update_interval = update_interval
        self.parent = parent

        GPIO.setup(self.lickPin, GPIO.IN)
        GPIO.add_event_detect(self.lickPin, GPIO.RISING, callback=self.increment_licks)

        self.burst_thread = threading.Thread(target = self.monitor_bursts)
        self.burst_thread.start()
    
    def increment_licks(self, x):    
        self.licks += 1
        self.burst_lick +=1
        self.last_lick = datetime.now()
        if self.parent:
            if self.parent.recording:
                self.parent.log.append({'time': self.last_lick, 
                                        'event': 'lick',
                                        'module': self.parent.name})
        print(self.licks, self.burst_lick, self.last_lick)

    def reset_licks(self):
        self.licks = 0

    def monitor_bursts(self):
        while self.on:
            if (datetime.now() - self.last_lick).total_seconds()>self.burst_thresh:
                self.burst_lick = 0
                self.in_burst = False
            else:
                self.in_burst = True
            time.sleep(self.update_interval)
            
    def __del__(self):
        self.on = False
        self.burst_thread.join()