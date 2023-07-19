from plugins.pump import Syringe, Pump, PumpThread, EndTrackError
from plugins.lickometer import Lickometer
from plugins.LED import LED
import RPi.GPIO as GPIO
import yaml

class NoLickometer(Exception):
    pass

class PumpInUse(Exception):
    pass

class NoFillValve(Exception):
    pass

class RewardInterface:
    def __init__(self, config_file='config.yaml', burst_thresh = .5, reward_thresh = 1):

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

    def fill_syringe(self, pump, amount):
        if pump in self.fill_valves:
            p = self.pumps[pump]
            if not p.in_use:
                pump_thread = PumpThread(p, amount, False, valvePin = self.fill_valves[pump], forward = False)
                pump_thread.start()
                pump_thread.join()
        else:
            raise ValueError('Either the specified pump has no fill valve or it does not exist')

    
    def change_syringe(self, pump=None, syringeType=None, ID=None):
        if pump:
            self.pumps[pump].change_syringe(syringeType=syringeType, ID=ID)
        else:
            for i in self.pumps:
                self.pumps[i].change_syringe(syringeType=syringeType, ID=ID)
    
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
                raise NoLickometer

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
    
    @property
    def pump_trigger(self):
        if self.lickometer:
            return self.lickometer.in_burst and (self.lickometer.burst_lick>self.reward_thresh)
        else:
            return None
    
    def lick_triggered_reward(self, amount, force = False):

        if self.lickometer is None: raise NoLickometer
        if self.pump.in_use and not force: raise PumpInUse
        if self.pump.track_end(True) and not force: raise EndTrackError
        if force and self.pump_thread: self.pump_thread.stop()

        self.pump_thread = PumpThread(self.pump, amount, True, valvePin = self.valvePin, forward = True, parent = self)
        self.pump_thread.start()

    def trigger_reward(self, amount, force = False):
        
        if self.pump.in_use and not force: raise PumpInUse
        if self.pump.track_end(True) and not force: raise EndTrackError
        if force and self.pump_thread: self.pump_thread.stop()

        self.pump_thread = PumpThread(self.pump, amount, False, valvePin = self.valvePin, forward = True)
        self.pump_thread.start()


    def __del__(self):
        GPIO.cleanup()

    