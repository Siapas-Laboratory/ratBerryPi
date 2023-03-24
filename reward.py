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
            if 'syringe_kwargs' in config[i]:
                if 'GPIOPins' in config[i]['syringe_kwargs']:
                    config[i]['syringe_kwargs']['GPIOPins'] = (config[i]['syringe_kwargs']['GPIOPins']['M0'], 
                                                               config[i]['syringe_kwargs']['GPIOPins']['M1'], 
                                                               config[i]['syringe_kwargs']['GPIOPins']['M2'])
        self.modules = {k: RewardModule(**c, burst_thresh=burst_thresh, 
                                        reward_thresh=reward_thresh) 
                        for k,c in config.items()}

    def get_module_names(self):
        return list(self.modules.keys())
    
    def set_all_syringe_types(self, syringeType):
        for i in self.modules:
            ret = self.modules[i].set_syringe_type(syringeType)
        return ret
    
    def set_syringe_type(self, module_name, syringeType):
        ret = self.modules[module_name].set_syringe_type(syringeType)
        return ret
    
    def set_all_syringe_IDs(self, ID):
        for i in self.modules:
            self.modules[i].set_syringe_ID(ID)
    
    def set_syringe_ID(self, module_name, ID):
        self.modules[module_name].set_syringe_ID(ID)
    
    def lick_triggered_reward(self, module_name, amount):
        self.modules[module_name].lick_triggered_reward(amount)
    
    def trigger_reward(self, module_name, amount):
        self.modules[module_name].trigger_reward(amount)
    
    def reset_licks(self, module_name):
        self.modules[module_name].reset_licks()
        
    def reset_all_licks(self):
        for i in self.modules:
            self.modules[i].reset_licks()


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
        
        def increment_licks(x):    
            self.licks += 1
            lick_time = datetime.now()
            self.burst_lick +=1
            if self.burst_lick > self.reward_thresh:
                self.syringe.green_light = True
            self.last_lick = lick_time
            print(self.licks, self.burst_lick, self.last_lick)

        GPIO.setup(self.lickPin, GPIO.IN)
        GPIO.add_event_detect(self.lickPin, GPIO.RISING, callback=increment_licks)
    
    def reset_licks(self):
        self.licks = 0
    
    def set_syringe_type(self, syringeType):
        try:
            self.syringe.syringeType = syringeType
            return True
        except ValueError as e:
            print(e)
            return False

    def set_syringe_ID(self, ID):
        self.syringe.ID = ID

    def lick_triggered_reward(self, amount):
        
        self.syringe.green_light = False
        self.monitor_lick_bursts = True
        def reset_burst():
            self.burst_lick = 0
            while self.monitor_lick_bursts:
                t = datetime.now()
                if (t - self.last_lick).total_seconds()>self.burst_thresh:
                    self.burst_lick = 0
                    self.syringe.green_light = False
                time.sleep(.1)
        thread = threading.Thread(target=reset_burst)
        thread.start()
        self.syringe.pulseForward(amount)
        self.monitor_lick_bursts = False
        thread.join()


    def trigger_reward(self, amount):
        self.syringe.green_light = True
        self.rewarding = True
        self.syringe.pulseForward(amount)
        self.syringe.green_light = False
        self.rewarding = False