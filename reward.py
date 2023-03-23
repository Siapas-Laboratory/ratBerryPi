from utils.syringe import Syringe
import RPi.GPIO as GPIO
from datetime import datetime
import threading
import time
import yaml


class RewardInterface:
    def __init__(self, config_file, burst_thresh = 0.5, reward_thresh = 3):

        with open(config_file, 'r') as f:
            config = yaml.safe_load(f)

        for i in config:
            if 'GPIOPins' in config[i]:
                config[i]['GPIOPins'] = (config[i]['GPIOPins']['M0'], 
                                         config[i]['GPIOPins']['M1'], 
                                         config[i]['GPIOPins']['M2'])
        
        self.modules = {k: RewardModule(**c, burst_thresh=burst_thresh, 
                                        reward_thresh=reward_thresh) 
                        for k,c in config.items()}

    def get_module_names(self):
        return list(self.modules.keys())
    
    def set_syringe_type(self, module_name, syringeType):
        self.modules[module_name].set_syringe_type(syringeType)
    
    def set_syringe_ID(self, module_name, ID):
        self.modules[module_name].set_syringe_ID(ID)
    
    def lick_triggered_reward(self, module_name, amount):
        self.modules[module_name].lick_triggered_reward(amount)
    
    def trigger_reward(self, module_name, amount):
        self.modules[module_name].trigger_reward(amount)


class RewardModule:

    def __init__(self, stepPin, lickPin, defaultSyringeType = None, stepType = None, defaultID = None,
                 syringe_kwargs = {}, burst_thresh = 0.5, reward_thresh = 3):

        self.syringe = Syringe(stepPin, syringeType = defaultSyringeType, stepType = stepType, 
                               ID = defaultID, **syringe_kwargs)
        self.lickPin = lickPin
        self.licks = 0
        self.burst_lick = 0
        self.last_lick = datetime.now()
        self.rewarding = False
        self.burst_thresh = burst_thresh
        self.reward_thresh = reward_thresh
    
    def set_syringe_type(self, syringeType):
        try:
            self.syringe.syringeType = syringeType
        except ValueError as e:
            print(e)

    def set_syringe_ID(self, ID):
        self.syringe.ID = ID

    def lick_triggered_reward(self, amount):
        
        self.syringe.green_light = False
        self.rewarding = True
        
        def increment_licks(x):    
            self.licks += 1
            lick_time = datetime.now()
            self.burst_lick +=1
            if self.burst_lick > self.reward_thresh:
                self.syringe.green_light = True
            self.last_lick = lick_time
            print(self.licks, self.burst_lick, self.last_lick)
            
        def reset_burst():
            while self.rewarding:
                t = datetime.now()
                if (t - self.last_lick).total_seconds()>self.burst_thresh:
                    self.burst_lick = 0
                    self.syringe.green_light = False
                time.sleep(.1)

        GPIO.setup(self.lickPin, GPIO.IN)
        GPIO.add_event_detect(self.lickPin, GPIO.RISING, callback=increment_licks)
        thread = threading.Thread(target=reset_burst)
        thread.start()
        self.syringe.pulseForward(amount)
        self.rewarding = False
        thread.join()
        GPIO.cleanup()

    def trigger_reward(self, amount):
        self.syringe.green_light = True
        self.rewarding = True
        self.syringe.pulseForward(amount)
        self.syringe.green_light = False
        self.rewarding = False