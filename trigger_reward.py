from utils.syringe import Syringe
import RPi.GPIO as GPIO
from datetime import datetime
import threading
import time

GPIO.setmode(GPIO.BCM)



def lick_triggered_reward(lickPin, stepPin, amount, syringeType = None,
                          stepType = "Half", syringeID = None,
                          burst_thresh = 0.5, reward_thresh = 3,
                          syringe_kwargs = {}):
        
    syringe = Syringe(stepPin, syringeType=syringeType,
                      stepType=stepType, ID=syringeID,
                      **syringe_kwargs)
    syringe.green_light = False
    licks = 0
    burst_lick = 0
    last_lick = datetime.now()
    rewarding = True
    
    def increment_licks(x):
        
        nonlocal licks
        nonlocal burst_lick
        nonlocal last_lick
        nonlocal syringe
        
        licks += 1
        lick_time = datetime.now()
        burst_lick +=1
        if burst_lick > reward_thresh:
            syringe.green_light = True
        last_lick = lick_time
        print(licks, burst_lick, last_lick)
        
    def reset_burst():
        nonlocal last_lick
        nonlocal rewarding
        nonlocal burst_lick
        while rewarding:
            t = datetime.now()
            if (t - last_lick).total_seconds()>burst_thresh:
                burst_lick = 0
                syringe.green_light = False
            time.sleep(.1)
    GPIO.setup(lickPin, GPIO.IN)
    GPIO.add_event_detect(lickPin, GPIO.RISING, callback=increment_licks)
    thread = threading.Thread(target=reset_burst)
    thread.start()
    syringe.pulseForward(amount)
    rewarding = False
    thread.join()
    GPIO.cleanup()

        
if __name__ == '__main__':
    import argparse
    