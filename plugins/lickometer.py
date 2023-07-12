from datetime import datetime
import RPi.GPIO as GPIO


class Lickometer:
    def __init__(self, lickPin, burst_thresh = 0.5):
        self.lickPin = lickPin
        self.licks = 0
        self.in_burst = False
        self.burst_lick = 0
        self.last_lick = datetime.now()
        self.burst_thresh = burst_thresh

        GPIO.setup(self.lickPin, GPIO.IN)
        GPIO.add_event_detect(self.lickPin, GPIO.RISING, callback=self.increment_licks)
    
    def increment_licks(self, x):    
        self.licks += 1
        lick_time = datetime.now()
        if (lick_time - self.last_lick).total_seconds()>self.burst_thresh:
            self.burst_lick = 0
            self.in_burst = False
        else:
            self.burst_lick +=1
            self.in_burst = True
        self.last_lick = lick_time
        print(self.licks, self.burst_lick, self.last_lick)

    def reset_licks(self):
        self.licks = 0
