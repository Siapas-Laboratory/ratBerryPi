from plugins.pump import Syringe, Pump, PumpThread
from plugins.lickometer import Lickometer
from plugins.LED import LED
import RPi.GPIO as GPIO
from datetime import datetime
import threading
import time
import yaml
import numpy as np
from utils import *


class RewardInterface:
    def __init__(self, config_file='config.yaml', burst_thresh = 0.5, reward_thresh = 3):

        GPIO.setmode(GPIO.BCM)
        with open(config_file, 'r') as f:
            config = yaml.safe_load(f)

        self.pumps = {}
        self.fill_valves = {}

        for i in config['pumps']: 
            syringeType = config['pumps'][i].pop('defaultSyringeType') if 'defaultSyringeType' in config['pumps'][i] else None
            ID = config['pumps'][i].pop('ID') if 'defaultID' in config['pumps'][i] else None
            syringe = Syringe(syringeType = syringeType, ID = ID)
            config['pumps'][i]['syringe'] = syringe
            
            if 'GPIOPins' not in config['pumps'][i]:
                raise ValueError(f"Missing argument 'GPIOPins' for pump '{i}'")
            elif len(config['pumps'][i]['GPIOPins'])!=3:
                raise ValueError(f"Expected 3 pins to be specified for argument 'GPIOPins' for pump '{i}', {len(config['pumps'][i]['GPIOPins'])} provided")
            
            config['pumps'][i]['GPIOPins'] = tuple(config['pumps'][i]['GPIOPins'])
            if 'fillValve' in config['pumps'][i]:
                if isinstance(config['pumps'][i]['fillValve'], int):
                    self.fill_valves[i] = config['pumps'][i].pop('fillValve')
                    GPIO.setup(self.fill_valves[i], GPIO.OUT)
                    GPIO.output(self.fill_valves[i], GPIO.LOW)
                elif 'check' in config['pumps'][i]['fillValve'].lower():
                    self.fill_valves[i] = config['pumps'][i].pop('fillValve')
                else:
                    raise ValueError(f"Invalid value for 'fillValve' provided for pump '{i}'")
            self.pumps[i] = Pump(**config['pumps'][i])

        self.modules = {}
        for i in config['modules']:
            config['modules'][i]['pump'] = self.pumps[config['modules'][i]['pump']]
            self.modules[i] = RewardModule(**config['modules'][i], burst_thresh=burst_thresh, reward_thresh=reward_thresh)

    def fill_syringe(self, amount, pump):
        if pump in self.fill_valves:
            p = self.pumps[pump]
            if not p.in_use:
                pump_thread = PumpThread(p, amount, valvePin = self.fill_valves[pump], forward = False)
                pump_thread.start()
                pump_thread.join()

        else:
            raise NoFillValve

    def get_module_names(self):
        return list(self.modules.keys())
    
    def set_all_syringe_types(self, syringeType):
        for i in self.modules:
            self.modules[i].pump.change_syringe(syringeType=syringeType)
    
    def set_syringe_type(self, module_name, syringeType):
        self.modules[module_name].pump.change_syringe(syringeType=syringeType)
    
    def set_all_syringe_IDs(self, ID):
        for i in self.modules:
            self.modules[i].pump.change_syringe(ID=ID)
    
    def set_syringe_ID(self, module_name, ID):
        self.modules[module_name].pump.change_syringe(ID=ID)
    
    def lick_triggered_reward(self, module_name, amount):
        self.modules[module_name].lick_triggered_reward(amount)
    
    def trigger_reward(self, module_name, amount):
        self.modules[module_name].trigger_reward(amount)
    
    def reset_licks(self, module_name):
        if self.modules[module_name].lickometer:
            self.modules[module_name].lickometer.reset_licks()
        else:
            raise NoLickometer
        
    def reset_all_licks(self):
        for i in self.modules:
            if self.modules[i].lickometer:
                self.modules[i].lickometer.reset_licks()
            else:
                print(f"WARNING: module '{i}' does not have a lickometer")

    def __del__(self):
        GPIO.cleanup()


class RewardModule:

    def __init__(self, pump = None, valvePin = None, lickPin = None, LEDPin = None, burst_thresh = 0.5, reward_thresh = 3):

        self.pump = pump
        self.valvePin = valvePin
        self.in_use = False
        self.reward_thresh = reward_thresh
        self.pump_thread = None
        self.lickometer = Lickometer(lickPin, burst_thresh) if lickPin else None
        self.LED = LED(LEDPin) if LEDPin else None

        if self.valvePin is not None:
            GPIO.setup(self.valvePin,GPIO.OUT)
            GPIO.output(self.valvePin,GPIO.LOW)

    def lick_triggered_reward(self, amount, force = False):

        if self.lickometer: raise NoLickometer
        if self.pump.in_use and not force: raise PumpInUse
        if self.pump.track_end(True) and not force: raise EndTrackError
        if force and self.pump_thread: self.pump_thread.join()

        pump_trigger = lambda: self.lickometer.in_burst and self.lickometer.burst_lick>self.parent.reward_thresh
        self.pump_thread = PumpThread(self.pump, amount, valvePin = self.valvePin,  pump_trigger = pump_trigger, forward = True)
        self.pump_thread.start()

    def trigger_reward(self, amount, force = False):
        
        if self.pump.in_use and not force: raise PumpInUse
        if self.pump.track_end(True) and not force: raise EndTrackError
        if force and self.pump_thread: self.pump_thread.join()

        self.pump_thread = PumpThread(self.pump, amount, valvePin = self.valvePin, forward = True)
        self.pump_thread.start()

    def __del__(self):
        GPIO.cleanup()

    