from pump import Syringe, Pump, PumpThread, EndTrackError
from plugins import lickometer, audio, LED
import RPi.GPIO as GPIO
import yaml
from datetime import datetime
import pandas as pd
import os

class NoSpeaker(Exception):
    pass

class NoLED(Exception):
    pass

class NoLickometer(Exception):
    pass

class PumpInUse(Exception):
    pass

class NoFillValve(Exception):
    pass

class RewardInterface:
    def __init__(self, burst_thresh = .5, reward_thresh = 1):

        GPIO.setmode(GPIO.BCM)
        with open('config.yaml', 'r') as f:
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

        self.plugins = {}
        if 'plugins' in config:
            for k, v in config['plugins'].items():
                if v['type'] == 'LED':
                    self.plugins[k] = LED.LED(v['LEDPin'])
                elif v['type'] == 'speaker':
                    if not hasattr(self, 'audio_interface'):
                        self.audio_interface = audio.AudioInterface()
                    self.plugins[k] = audio.Speaker(self.audio_interface, v['SDPin'])

        self.modules = {}
        for i in config['modules']:
            config['modules'][i]['pump'] = self.pumps[config['modules'][i]['pump']]
            if 'plugins' in config['modules'][i]:
                config['modules'][i]['plugins'] = {k: self.plugins[v] for k,v in config['modules'][i]['plugins'].items()}

            self.modules[i] = RewardModule(i, **config['modules'][i], reward_thresh=reward_thresh)
        self.recording = False
        self.log = []

    def record(self, reset = True):
        self.recording = True
        if reset:
            self.reset_all_licks()
        for i in self.modules:
            self.modules[i].log = []
            self.modules[i].recording = True
        self.log = [{'time': datetime.now(), 'event': 'start', 'module': None}]
        print('recording')

    def save(self):
        for i in self.modules:
            self.modules[i].recording = False
            self.log.extend(self.modules[i].log)
        df = pd.DataFrame(self.log)
        df = df.sort_values('time')
        fname = datetime.strftime(datetime.now(), "%Y_%m_%d_%H_%M_%S.csv")
        df.to_csv(os.path.join('data',fname)) 
        print('saved!')

    def trigger_reward(self, module, amount, force = False, lick_triggered = False):
        self.modules[module].trigger_reward(amount, force = force, lick_triggered = lick_triggered)

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
    
    def reset_licks(self, module):
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
    
    def toggle_LED(self, on, module = None, led = None):
        if module is not None:
            if hasattr(self.modules[module], 'LED'):
                if isinstance(self.modules[module].LED, LED.LED):
                    if on: self.modules[module].LED.turn_on()
                    else: self.modules[module].LED.turn_off()
                else:
                    raise NoLED
            else:
                raise NoLED
        elif led is not None:
            if isinstance(self.plugins[led], LED.LED):
                if on: self.plugins[led].turn_on()
                else: self.plugins[led].turn_off()
            else:
                raise NoLED

    def play_tone(self, freq, dur, volume = 1, module = None, speaker = None):
        if module is not None:
            if hasattr(self.modules[module], 'speaker'):
                if isinstance(self.modules[module].speaker, audio.Speaker):
                    self.modules[module].speaker.play_tone(freq, dur, volume)
                else:
                    raise NoSpeaker
            else:
                raise NoSpeaker
        elif speaker is not None:
            if isinstance(self.plugins[speaker], audio.Speaker):
                self.plugins[speaker].play_tone(freq, dur, volume)
            else:
                raise NoSpeaker
    
    def __del__(self):
        GPIO.cleanup()


class RewardModule:

    def __init__(self, name, pump, valvePin = None, lickPin = None, 
                plugins = {}, burst_thresh = .5, reward_thresh = 3):

        self.pump = pump
        self.name = name
        self.valvePin = valvePin
        self.in_use = False
        self.reward_thresh = reward_thresh
        self.pump_thread = None

        if lickPin:
            self.lickometer = lickometer.Lickometer(lickPin, burst_thresh = burst_thresh, parent = self)
        else:
            self.lickometer = None

        for i,v in plugins.items():
            setattr(self, i, v)

        if self.valvePin is not None:
            GPIO.setup(self.valvePin,GPIO.OUT)
            GPIO.output(self.valvePin,GPIO.LOW)

        self.log = []
        self.recording = False
    
    @property
    def pump_trigger(self):
        if self.lickometer:
            return self.lickometer.in_burst and (self.lickometer.burst_lick>self.reward_thresh)
        else:
            return None
    
    def record(self):
        self.log = []
        self.recording = True

    def trigger_reward(self, amount, force = False, lick_triggered = False):
        
        if self.pump.in_use and not force: raise PumpInUse
        if self.pump.track_end(True) and not force: raise EndTrackError
        if force and self.pump_thread: self.pump_thread.stop()
        self.pump_thread = PumpThread(self.pump, amount, lick_triggered, 
                                      valvePin = self.valvePin, forward = True, 
                                      parent = self)
        self.pump_thread.start()

    def __del__(self):
        GPIO.cleanup()

    